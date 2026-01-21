"""Shared base class for HTTP-backed providers."""

from __future__ import annotations

import os

import httpx

from .base import ModelPricing


class BaseHTTPProvider:
    MODEL_INFO: dict[str, ModelPricing] = {}
    DEFAULT_CONTEXT_LIMIT: int = 0
    DEFAULT_OUTPUT_LIMIT: int = 0

    def __init__(
        self,
        *,
        api_key: str | None,
        api_key_env: str,
        base_url: str,
        http_client: httpx.AsyncClient | None,
        max_retries: int,
        backoff_base_seconds: float,
    ) -> None:
        self._api_key = api_key or os.getenv(api_key_env) or ""
        self._base_url = base_url.rstrip("/")
        self._client = http_client
        self._owned_client = http_client is None
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client

    async def _get_timeout(self, timeout_seconds: float | None) -> tuple[httpx.AsyncClient, httpx.Timeout | None]:
        client = await self._get_client()
        timeout = httpx.Timeout(timeout_seconds) if timeout_seconds else client.timeout
        return client, timeout

    async def aclose(self) -> None:
        if self._owned_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def get_context_limit(self, model: str) -> int:
        info = self.MODEL_INFO.get(model)
        return info.context_limit if info else self.DEFAULT_CONTEXT_LIMIT

    def get_output_limit(self, model: str) -> int:
        info = self.MODEL_INFO.get(model)
        return info.output_limit if info else self.DEFAULT_OUTPUT_LIMIT

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        info = self.MODEL_INFO.get(model)
        if not info:
            return 0.0
        return (
            (input_tokens / 1000.0) * info.input_cost_per_1k
            + (output_tokens / 1000.0) * info.output_cost_per_1k
        )
