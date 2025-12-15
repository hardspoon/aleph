"""Built-in helper functions exposed inside the Aleph REPL.

These helpers intentionally avoid heavy dependencies. They operate on text-like
representations of the context.

The REPL injects wrappers so that the LLM can call:
- peek(start, end)
- lines(start, end)
- search(pattern, context_lines=2)
- chunk(chunk_size, overlap=0)
- cite(snippet, line_range=None) - manually tag evidence for provenance tracking
"""

from __future__ import annotations

from typing import TypedDict

class SearchResult(TypedDict):
    match: str
    line_num: int
    context: str


def _to_text(ctx: object) -> str:
    """Best-effort conversion of context into a string."""

    if ctx is None:
        return ""
    if isinstance(ctx, str):
        return ctx
    if isinstance(ctx, bytes):
        try:
            return ctx.decode("utf-8", errors="replace")
        except Exception:
            return repr(ctx)

    # Pretty-print JSON-like structures.
    if isinstance(ctx, (dict, list, tuple)):
        try:
            import json

            return json.dumps(ctx, indent=2, ensure_ascii=False)
        except Exception:
            return str(ctx)

    return str(ctx)


def peek(ctx: object, start: int = 0, end: int | None = None) -> str:
    text = _to_text(ctx)
    return text[start:end]


def lines(ctx: object, start: int = 0, end: int | None = None) -> str:
    text = _to_text(ctx)
    parts = text.splitlines()
    return "\n".join(parts[start:end])


def search(
    ctx: object,
    pattern: str,
    context_lines: int = 2,
    flags: int = 0,
    max_results: int = 20,
) -> list[SearchResult]:
    """Regex search returning surrounding context.

    Returns list of dicts: {"match": str, "line_num": int, "context": str}
    """

    import re

    text = _to_text(ctx)
    lines_list = text.splitlines()

    results: list[SearchResult] = []
    rx = re.compile(pattern, flags=flags)

    for i, line in enumerate(lines_list):
        if rx.search(line):
            start = max(0, i - context_lines)
            end = min(len(lines_list), i + context_lines + 1)
            results.append({
                "match": line,
                "line_num": i,
                "context": "\n".join(lines_list[start:end]),
            })
            if len(results) >= max_results:
                break

    return results


def chunk(ctx: object, chunk_size: int, overlap: int = 0) -> list[str]:
    """Split context into chunks by character count."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")

    text = _to_text(ctx)
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + chunk_size)
        out.append(text[i:j])
        if j == n:
            break
        i = j - overlap
    return out


class Citation(TypedDict):
    """Manual citation for evidence tracking."""
    snippet: str
    line_range: tuple[int, int] | None
    note: str | None


def cite(
    snippet: str,
    line_range: tuple[int, int] | None = None,
    note: str | None = None,
) -> Citation:
    """Manually cite evidence for provenance tracking.

    Use this to explicitly mark a piece of context as evidence
    supporting your reasoning. Citations are collected and included
    in the final answer.

    Args:
        snippet: The relevant text being cited
        line_range: Optional (start_line, end_line) tuple
        note: Optional note about why this is relevant

    Returns:
        Citation dict that gets tracked by the session
    """
    return Citation(
        snippet=snippet[:500],  # Limit snippet size
        line_range=line_range,
        note=note,
    )
