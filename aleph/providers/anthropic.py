"""Anthropic provider.

Implements Aleph's provider interface against Anthropic's Messages API.

This module intentionally uses bare HTTP (httpx) to keep dependencies minimal.
"""

from __future__ import annotations

import json
import os
import asyncio

import httpx

from .base import LLMProvider, ModelPricing, ProviderError
from ..utils.tokens import estimate_tokens
from ..types import Message


class AnthropicProvider:
    """Anthropic Claude provider via the Messages API."""

    # Model -> pricing / limits (rough defaults; override in code if needed)
    MODEL_INFO: dict[str, ModelPricing] = {
        # NOTE: Values are approximate and may change; intended for budgeting/telemetry.
        "claude-sonnet-4-20250514": ModelPricing(200_000, 64_000, 0.003, 0.015),
        "claude-opus-4-20250514": ModelPricing(200_000, 32_000, 0.015, 0.075),
        "claude-haiku-3-5-20241022": ModelPricing(200_000, 8_192, 0.0008, 0.004),
    }

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com",
        anthropic_version: str = "2023-06-01",
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.8,
    ) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            # Don't raise immediately; allow creating instance and failing on first call.
            self._api_key = ""
        self._base_url = base_url.rstrip("/")
        self._version = anthropic_version
        self._client = http_client
        self._owned_client = http_client is None
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client

    async def aclose(self) -> None:
        if self._owned_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def count_tokens(self, text: str, model: str) -> int:
        # Keep it dependency-free by default.
        return estimate_tokens(text)

    def get_context_limit(self, model: str) -> int:
        info = self.MODEL_INFO.get(model)
        return info.context_limit if info else 200_000

    def get_output_limit(self, model: str) -> int:
        info = self.MODEL_INFO.get(model)
        return info.output_limit if info else 8_192

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        info = self.MODEL_INFO.get(model)
        if not info:
            return 0.0
        return (input_tokens / 1000.0) * info.input_cost_per_1k + (output_tokens / 1000.0) * info.output_cost_per_1k

    @staticmethod
    def _split_system(messages: list[Message]) -> tuple[str | None, list[Message]]:
        system_parts: list[str] = []
        out: list[Message] = []
        for m in messages:
            role = m.get("role", "")
            if role == "system":
                system_parts.append(m.get("content", ""))
            else:
                out.append(m)
        system = "\n\n".join([p for p in system_parts if p.strip()]) or None
        return system, out

    async def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[str, int, int, float]:
        if not self._api_key:
            raise ProviderError(
                "Anthropic API key not set. Provide api_key=... or set ANTHROPIC_API_KEY."
            )

        system, filtered = self._split_system(messages)

        # Anthropic Messages API uses roles: user/assistant only.
        anthropic_messages: list[dict[str, str]] = []
        for m in filtered:
            role = m.get("role")
            if role not in {"user", "assistant"}:
                # Best-effort fallback: treat unknown roles as user content.
                role = "user"
            anthropic_messages.append({"role": role, "content": m.get("content", "")})

        url = f"{self._base_url}/v1/messages"
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._version,
            "content-type": "application/json",
        }

        payload: dict[str, object] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system:
            payload["system"] = system
        if stop_sequences:
            payload["stop_sequences"] = stop_sequences

        client = await self._get_client()
        timeout = httpx.Timeout(timeout_seconds) if timeout_seconds else client.timeout

        def _parse_retry_after_seconds(resp: httpx.Response) -> float | None:
            ra = resp.headers.get("retry-after")
            if not ra:
                return None
            try:
                return max(0.0, float(ra.strip()))
            except ValueError:
                return None

        def _format_http_error(resp: httpx.Response) -> str:
            request_id = resp.headers.get("request-id") or resp.headers.get("x-request-id")
            retry_after = _parse_retry_after_seconds(resp)

            msg = None
            try:
                data = resp.json()
                err = data.get("error") if isinstance(data, dict) else None
                if isinstance(err, dict):
                    raw = err.get("message")
                    if isinstance(raw, str) and raw.strip():
                        msg = raw.strip()
            except Exception:
                msg = None

            if msg is None:
                body = (resp.text or "").strip()
                msg = body[:500] if body else "(no response body)"

            parts = [f"Anthropic API error {resp.status_code}: {msg}"]
            if request_id:
                parts.append(f"request_id={request_id}")
            if retry_after is not None:
                parts.append(f"retry_after_seconds={retry_after:.0f}")
            if len(parts) == 1:
                return parts[0]
            return parts[0] + " (" + ", ".join(parts[1:]) + ")"

        last_err: Exception | None = None
        for attempt in range(1, self._max_retries + 2):
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=timeout)

                if resp.status_code >= 400:
                    retryable_status = resp.status_code in {408, 409, 429, 500, 502, 503, 504}
                    if retryable_status and attempt <= self._max_retries:
                        retry_after = _parse_retry_after_seconds(resp)
                        delay = retry_after if retry_after is not None else (self._backoff_base * (2 ** (attempt - 1)))
                        await asyncio.sleep(delay)
                        continue
                    raise ProviderError(_format_http_error(resp))

                try:
                    data = resp.json()
                except json.JSONDecodeError as e:
                    raise ProviderError(f"Invalid JSON response from Anthropic: {e}")

                if not isinstance(data, dict):
                    raise ProviderError(f"Anthropic API returned invalid JSON type: {type(data)}")

                # Response content is a list of blocks; typically first is text.
                content_blocks = data.get("content") or []
                text_parts: list[str] = []
                if isinstance(content_blocks, list):
                    for block in content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            val = block.get("text", "")
                            if isinstance(val, str):
                                text_parts.append(val)
                text = "".join(text_parts).strip()

                usage = data.get("usage") or {}
                if not isinstance(usage, dict):
                    usage = {}
                input_tokens = int(usage.get("input_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or 0)

                # If usage is missing (rare), estimate.
                if input_tokens == 0:
                    input_tokens = sum(self.count_tokens(m["content"], model) for m in messages)
                if output_tokens == 0:
                    output_tokens = self.count_tokens(text, model)

                cost = self._estimate_cost(model, input_tokens, output_tokens)
                return text, input_tokens, output_tokens, cost

            except ProviderError:
                raise
            except httpx.TimeoutException as e:
                last_err = e
                if attempt <= self._max_retries:
                    await asyncio.sleep(self._backoff_base * (2 ** (attempt - 1)))
                    continue
                break
            except httpx.RequestError as e:
                last_err = e
                if attempt <= self._max_retries:
                    await asyncio.sleep(self._backoff_base * (2 ** (attempt - 1)))
                    continue
                break
            except Exception as e:
                last_err = e
                if attempt <= self._max_retries:
                    await asyncio.sleep(self._backoff_base * (2 ** (attempt - 1)))
                    continue
                break

        if isinstance(last_err, httpx.TimeoutException):
            raise ProviderError(f"Anthropic request timed out: {last_err}")
        if isinstance(last_err, httpx.RequestError):
            raise ProviderError(f"Anthropic request failed: {last_err}")
        raise ProviderError(f"Anthropic provider failed after retries: {last_err}")
