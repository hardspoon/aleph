"""Needle-in-a-haystack demo.

This example is designed to be runnable **even without API keys**.

- If you have ANTHROPIC_API_KEY or OPENAI_API_KEY set, it will use a real model.
- Otherwise it falls back to a tiny MockProvider that emits a couple of REPL
  actions to demonstrate the full Aleph loop.

Run:
    python examples/needle_haystack.py

Optional:
    ALEPH_PROVIDER=openai OPENAI_API_KEY=... python examples/needle_haystack.py
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Any

# Ensure the repository root is on sys.path when running as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph import Aleph, Budget
from aleph.providers.base import LLMProvider
from aleph.types import Message


class MockProvider:
    """A minimal provider that simulates an LLM with two turns.

    It emits:
    1) A Python code block that searches for the needle and stores `answer`.
    2) FINAL_VAR("answer")

    This is purely for local demonstration/testing.
    """

    def __init__(self) -> None:
        self._call_n = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    async def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[str, int, int, float]:
        self._call_n += 1

        if self._call_n == 1:
            text = """```python
# Find the line containing the needle
matches = search(r"NEEDLE", context_lines=0, max_results=5)
print(matches)
if matches:
    # Store the matching line as the answer
    answer = matches[0]["match"]
else:
    answer = "(not found)"
```"""
            return text, 0, 0, 0.0

        # second call: return final
        return 'FINAL_VAR("answer")', 0, 0, 0.0

    def count_tokens(self, text: str, model: str) -> int:
        return max(0, len(text) // 4)

    def get_context_limit(self, model: str) -> int:
        return 128_000

    def get_output_limit(self, model: str) -> int:
        return 16_384


def build_haystack(num_lines: int = 20_000) -> str:
    rng = random.Random(42)
    lines = []
    needle_line = "NEEDLE: the secret code is 12345"
    needle_pos = rng.randint(0, num_lines - 1)

    for i in range(num_lines):
        if i == needle_pos:
            lines.append(needle_line)
        else:
            # semi-random filler
            lines.append(f"line {i}: {rng.randint(0, 10**9)}")

    return "\n".join(lines)


async def main() -> None:
    provider_name = os.getenv("ALEPH_PROVIDER", "anthropic").lower()

    use_real = False
    if provider_name == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        use_real = True
    if provider_name == "openai" and os.getenv("OPENAI_API_KEY"):
        use_real = True

    if use_real:
        aleph = Aleph(
            provider=provider_name,
            root_model=(
                "claude-sonnet-4-20250514" if provider_name == "anthropic" else "gpt-4o"
            ),
            sub_model=(
                "claude-haiku-3-5-20241022" if provider_name == "anthropic" else "gpt-4o-mini"
            ),
            budget=Budget(max_cost_usd=1.0, max_iterations=15),
        )
    else:
        aleph = Aleph(
            provider=MockProvider(),
            root_model="mock",
            sub_model="mock",
            budget=Budget(max_cost_usd=0.0, max_iterations=5),
        )

    haystack = build_haystack()
    query = "Find the needle line and tell me the secret code."

    resp = await aleph.complete(query=query, context=haystack)

    print("\n=== Aleph Response ===")
    print("success:", resp.success)
    print("answer:", resp.answer)
    print("tokens:", resp.total_tokens)
    print("cost:", resp.total_cost_usd)
    print("iterations:", resp.total_iterations)


if __name__ == "__main__":
    asyncio.run(main())
