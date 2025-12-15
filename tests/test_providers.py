from __future__ import annotations

import asyncio

import httpx
import pytest

from aleph.providers.anthropic import AnthropicProvider
from aleph.providers.base import ProviderError
from aleph.providers.openai import OpenAIProvider


def test_openai_http_error_includes_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "bad key"}},
            headers={"x-request-id": "req_123", "retry-after": "5"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIProvider(api_key="x", http_client=client, max_retries=0)

    try:
        with pytest.raises(ProviderError) as e:
            asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}], model="gpt-4o"))
        msg = str(e.value)
        assert "OpenAI API error 401" in msg
        assert "bad key" in msg
        assert "request_id=req_123" in msg
        assert "retry_after_seconds=5" in msg
    finally:
        asyncio.run(client.aclose())


def test_openai_retries_on_429_honors_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(
                429,
                json={"error": {"message": "rate limited"}},
                headers={"retry-after": "1"},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            request=request,
        )

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIProvider(api_key="x", http_client=client, max_retries=1, backoff_base_seconds=999)

    try:
        text, *_ = asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}], model="gpt-4o"))
        assert text == "ok"
        assert sleep_calls == [1.0]
    finally:
        asyncio.run(client.aclose())


def test_openai_timeout_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIProvider(api_key="x", http_client=client, max_retries=0)

    try:
        with pytest.raises(ProviderError, match=r"OpenAI request timed out"):
            asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}], model="gpt-4o"))
    finally:
        asyncio.run(client.aclose())


def test_anthropic_http_error_includes_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "rate limited"}},
            headers={"request-id": "req_abc", "retry-after": "2"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AnthropicProvider(api_key="x", http_client=client, max_retries=0)

    try:
        with pytest.raises(ProviderError) as e:
            asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}], model="claude-sonnet-4-20250514"))
        msg = str(e.value)
        assert "Anthropic API error 429" in msg
        assert "rate limited" in msg
        assert "request_id=req_abc" in msg
        assert "retry_after_seconds=2" in msg
    finally:
        asyncio.run(client.aclose())


def test_anthropic_timeout_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AnthropicProvider(api_key="x", http_client=client, max_retries=0)

    try:
        with pytest.raises(ProviderError, match=r"Anthropic request timed out"):
            asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}], model="claude-sonnet-4-20250514"))
    finally:
        asyncio.run(client.aclose())
