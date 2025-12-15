"""Token counting utilities.

Aleph aims to work with minimal dependencies, so by default it uses a rough
character-based estimate: ~4 chars per token.

If optional libraries are installed, providers may use more accurate counters.
"""

from __future__ import annotations

from typing import Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate (works reasonably well for English text)."""

    if not text:
        return 0
    # heuristic: 1 token ~ 4 characters
    return max(1, len(text) // 4)


def try_count_tokens_tiktoken(text: str, model: str) -> Optional[int]:
    """Best-effort token counting using tiktoken (if installed)."""

    try:
        import tiktoken
    except Exception:
        return None

    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        # Fallback to a common encoding used by OpenAI chat models.
        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    try:
        return len(enc.encode(text))
    except Exception:
        return None
