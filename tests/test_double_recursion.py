"""Tests for nested Aleph recursion (sub_aleph -> sub_aleph)."""

from __future__ import annotations

import pytest

from aleph.core import Aleph
from aleph.types import Budget, Message


class _FakeProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}

    async def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[str, int, int, float]:
        query = ""
        for msg in messages:
            if msg.get("role") == "user":
                query = msg.get("content", "")
                break
        count = self.calls.get(query, 0)
        self.calls[query] = count + 1

        if query == "level0":
            if count == 0:
                code = (
                    "```python\n"
                    "resp = sub_aleph('level1', context='')\n"
                    "print('ROOT:' + resp.answer)\n"
                    "```"
                )
                return code, 10, 10, 0.0
            return "FINAL(root done)", 5, 5, 0.0
        if query == "level1":
            if count == 0:
                code = (
                    "```python\n"
                    "resp = sub_aleph('level2', context='')\n"
                    "print('LEVEL1:' + resp.answer)\n"
                    "```"
                )
                return code, 10, 10, 0.0
            return "FINAL(level1 done)", 5, 5, 0.0
        if query == "level2":
            return "FINAL(level2 done)", 5, 5, 0.0
        return "FINAL(unknown)", 5, 5, 0.0

    def count_tokens(self, text: str, model: str) -> int:
        return max(1, len(text) // 4)

    def get_context_limit(self, model: str) -> int:
        return 8192

    def get_output_limit(self, model: str) -> int:
        return 2048


@pytest.mark.asyncio
async def test_double_recursion_reaches_depth_two() -> None:
    provider = _FakeProvider()
    budget = Budget(max_depth=2, max_iterations=10, max_sub_queries=10)
    aleph = Aleph(
        provider=provider,
        root_model="fake-root",
        sub_model="fake-sub",
        budget=budget,
        system_prompt="Test prompt.",
    )

    response = await aleph.complete("level0", context="")
    assert response.success is True
    assert response.max_depth_reached == 2
