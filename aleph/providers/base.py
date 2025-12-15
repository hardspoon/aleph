"""Provider abstraction.

Aleph's core logic is provider-agnostic. Any provider can be used as long as it
implements the LLMProvider protocol.

The interface is intentionally small:
- complete(): async LLM call
- count_tokens(): token estimate
- get_context_limit()/get_output_limit(): model metadata
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..types import Message


class ProviderError(RuntimeError):
    """Raised when a provider call fails."""


class LLMProvider(Protocol):
    """Protocol all providers must implement."""

    @property
    def provider_name(self) -> str:
        ...

    async def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[str, int, int, float]:
        """Return (response_text, input_tokens, output_tokens, cost_usd)."""

    def count_tokens(self, text: str, model: str) -> int:
        ...

    def get_context_limit(self, model: str) -> int:
        ...

    def get_output_limit(self, model: str) -> int:
        ...


@dataclass(slots=True)
class ModelPricing:
    """Token and cost metadata for a model (rough)."""

    context_limit: int
    output_limit: int
    input_cost_per_1k: float
    output_cost_per_1k: float
