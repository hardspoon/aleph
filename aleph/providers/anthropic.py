"""Anthropic provider.

Implements Aleph's provider interface against Anthropic's Messages API.

This module intentionally uses bare HTTP (httpx) to keep dependencies minimal.
"""

from __future__ import annotations

import json
import httpx

from .base import ModelPricing, ProviderError
from .http_base import BaseHTTPProvider
from .http_utils import post_json_with_retries
from ..utils.tokens import estimate_tokens
from ..types import Message


class AnthropicProvider(BaseHTTPProvider):
    """Anthropic Claude provider via the Messages API."""

    # Model -> pricing / limits (rough defaults; override in code if needed)
    MODEL_INFO: dict[str, ModelPricing] = {
        # NOTE: Values are approximate and may change; intended for budgeting/telemetry.
        "claude-sonnet-4-20250514": ModelPricing(200_000, 64_000, 0.003, 0.015),
        "claude-opus-4-20250514": ModelPricing(200_000, 32_000, 0.015, 0.075),
        "claude-haiku-3-5-20241022": ModelPricing(200_000, 8_192, 0.0008, 0.004),
    }
    DEFAULT_CONTEXT_LIMIT = 200_000
    DEFAULT_OUTPUT_LIMIT = 8_192

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com",
        anthropic_version: str = "2023-06-01",
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.8,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_key_env="ANTHROPIC_API_KEY",
            base_url=base_url,
            http_client=http_client,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
        )
        self._version = anthropic_version

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def count_tokens(self, text: str, model: str) -> int:
        # Keep it dependency-free by default.
        return estimate_tokens(text)

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

        client, timeout = await self._get_timeout(timeout_seconds)

        resp = await post_json_with_retries(
            client=client,
            url=url,
            headers=headers,
            payload=payload,
            timeout=timeout,
            max_retries=self._max_retries,
            backoff_base_seconds=self._backoff_base,
            provider_label="Anthropic",
            request_id_headers=("request-id", "x-request-id"),
        )

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
