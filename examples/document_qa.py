"""Multi-document QA demo using ContextCollection.

This example also works without API keys by using a small MockProvider.

Run:
    python examples/document_qa.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure the repository root is on sys.path when running as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph import Aleph, Budget
from aleph.types import ContextCollection, Message


class MockProvider:
    """A tiny provider that emits code to search multiple documents."""

    def __init__(self) -> None:
        self._n = 0

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
        self._n += 1
        if self._n == 1:
            return (
                """```python
# ctx is a ContextCollection: ctx.items is [(name, content), ...]
needle = "banana"
found = []
for name, content in ctx.items:
    if needle in str(content).lower():
        found.append(name)
print(found)
answer = f"Documents mentioning '{needle}': {found}" if found else "No docs mention banana"
```""",
                0,
                0,
                0.0,
            )
        return 'FINAL_VAR("answer")', 0, 0, 0.0

    def count_tokens(self, text: str, model: str) -> int:
        return max(0, len(text) // 4)

    def get_context_limit(self, model: str) -> int:
        return 128_000

    def get_output_limit(self, model: str) -> int:
        return 16_384


async def main() -> None:
    docs = ContextCollection(
        items=[
            ("doc_1", "Apples are great. Oranges are also great."),
            ("doc_2", "Banana bread recipe: bananas, flour, sugar."),
            ("doc_3", "Nothing to see here."),
        ]
    )

    provider_name = os.getenv("ALEPH_PROVIDER", "anthropic").lower()
    use_real = (provider_name == "anthropic" and os.getenv("ANTHROPIC_API_KEY")) or (
        provider_name == "openai" and os.getenv("OPENAI_API_KEY")
    )

    if use_real:
        aleph = Aleph(
            provider=provider_name,
            root_model=("claude-sonnet-4-20250514" if provider_name == "anthropic" else "gpt-4o"),
            sub_model=(
                "claude-haiku-3-5-20241022" if provider_name == "anthropic" else "gpt-4o-mini"
            ),
            budget=Budget(max_cost_usd=1.0, max_iterations=10),
        )
    else:
        aleph = Aleph(provider=MockProvider(), root_model="mock", sub_model="mock")

    resp = await aleph.complete("Which documents mention banana?", docs)

    print(resp.answer)


if __name__ == "__main__":
    asyncio.run(main())
