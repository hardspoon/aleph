"""Tests for CLI provider."""

from __future__ import annotations

import pytest

import aleph.providers.cli as cli_provider
from aleph.providers.cli import CLIProvider
from aleph.providers.base import ProviderError


def test_cli_provider_resolves_auto_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = CLIProvider(backend="auto")

    def fake_detect_backend() -> str:
        return "codex"

    monkeypatch.setattr(cli_provider, "detect_backend", fake_detect_backend)
    assert provider._resolve_backend() == "codex"


def test_cli_provider_rejects_unknown_backend() -> None:
    provider = CLIProvider(backend="nope")
    with pytest.raises(ProviderError, match="Unsupported CLI backend"):
        provider._resolve_backend()


@pytest.mark.asyncio
async def test_cli_provider_formats_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = CLIProvider(backend="codex")

    async def fake_run_cli_sub_query(
        prompt: str,
        context_slice: str | None,
        backend: str,
        timeout: float,
        max_output_chars: int,
    ) -> tuple[bool, str]:
        assert "SYSTEM:\nSYS" in prompt
        assert "USER:\nHi" in prompt
        assert prompt.strip().endswith("ASSISTANT:")
        assert context_slice is None
        assert backend == "codex"
        assert timeout > 0
        assert max_output_chars > 0
        return True, "OK"

    monkeypatch.setattr(cli_provider, "run_cli_sub_query", fake_run_cli_sub_query)

    output, *_ = await provider.complete(
        messages=[
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "Hi"},
        ],
        model="codex",
    )
    assert output == "OK"


@pytest.mark.asyncio
async def test_cli_provider_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = CLIProvider(backend="codex")

    async def fake_run_cli_sub_query(*args, **kwargs) -> tuple[bool, str]:
        return False, "bad"

    monkeypatch.setattr(cli_provider, "run_cli_sub_query", fake_run_cli_sub_query)

    with pytest.raises(ProviderError, match="bad"):
        await provider.complete(
            messages=[{"role": "user", "content": "Hi"}],
            model="codex",
        )
