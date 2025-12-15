"""OpenAI provider.

Implements Aleph's provider interface against OpenAI's Chat Completions API.

This module uses bare HTTP via httpx for minimal dependencies.
"""

from __future__ import annotations

import asyncio
import json
import os

import httpx

from .base import ModelPricing, ProviderError
from ..utils.tokens import estimate_tokens, try_count_tokens_tiktoken
from ..types import Message


class OpenAIProvider:
    """OpenAI provider via /v1/chat/completions."""

    MODEL_INFO: dict[str, ModelPricing] = {
        # NOTE: Prices/limits change; these defaults are for budgeting/telemetry.
        "gpt-4o": ModelPricing(128_000, 16_384, 0.0025, 0.01),
        "gpt-4o-mini": ModelPricing(128_000, 16_384, 0.00015, 0.0006),
        "gpt-4-turbo": ModelPricing(128_000, 4_096, 0.01, 0.03),
    }

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com",
        organization: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.8,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            self._api_key = ""
        self._base_url = base_url.rstrip("/")
        self._org = organization or os.getenv("OPENAI_ORG_ID")
        self._client = http_client
        self._owned_client = http_client is None
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds

    @property
    def provider_name(self) -> str:
        return "openai"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client

    async def aclose(self) -> None:
        if self._owned_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def count_tokens(self, text: str, model: str) -> int:
        # Best-effort: use tiktoken if installed.
        n = try_count_tokens_tiktoken(text, model)
        if n is not None:
            return n
        return estimate_tokens(text)

    def get_context_limit(self, model: str) -> int:
        info = self.MODEL_INFO.get(model)
        return info.context_limit if info else 128_000

    def get_output_limit(self, model: str) -> int:
        info = self.MODEL_INFO.get(model)
        return info.output_limit if info else 4_096

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        info = self.MODEL_INFO.get(model)
        if not info:
            return 0.0
        return (input_tokens / 1000.0) * info.input_cost_per_1k + (output_tokens / 1000.0) * info.output_cost_per_1k

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
            raise ProviderError("OpenAI API key not set. Provide api_key=... or set OPENAI_API_KEY.")

        url = f"{self._base_url}/v1/chat/completions"
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        if self._org:
            headers["openai-organization"] = self._org

        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop_sequences:
            payload["stop"] = stop_sequences

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
            request_id = resp.headers.get("x-request-id")
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

            parts = [f"OpenAI API error {resp.status_code}: {msg}"]
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
                    raise ProviderError(f"Invalid JSON response from OpenAI: {e}")

                if not isinstance(data, dict):
                    raise ProviderError(f"OpenAI API returned invalid JSON type: {type(data)}")

                choices = data.get("choices") or []
                if not choices:
                    raise ProviderError(f"OpenAI API returned no choices")

                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                if not isinstance(message, dict):
                    message = {}
                text = (message.get("content") or "").strip()

                usage = data.get("usage") or {}
                if not isinstance(usage, dict):
                    usage = {}
                input_tokens = int(usage.get("prompt_tokens") or 0)
                output_tokens = int(usage.get("completion_tokens") or 0)

                if input_tokens == 0:
                    input_tokens = sum(self.count_tokens(m.get("content", ""), model) for m in messages)
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
            raise ProviderError(f"OpenAI request timed out: {last_err}")
        if isinstance(last_err, httpx.RequestError):
            raise ProviderError(f"OpenAI request failed: {last_err}")
        raise ProviderError(f"OpenAI provider failed after retries: {last_err}")
