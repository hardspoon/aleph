"""Formatting helpers for MCP tool responses."""

from __future__ import annotations

import json
from typing import Any, Literal

from ..types import ContextMetadata


def _format_payload(
    payload: dict[str, Any],
    output: Literal["json", "markdown", "object"],
) -> str | dict[str, Any]:
    if output == "object":
        return payload
    if output == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"


def _format_error(
    message: str,
    output: Literal["json", "markdown", "object"],
) -> str | dict[str, Any]:
    if output == "markdown":
        return f"Error: {message}"
    return _format_payload({"error": message}, output=output)


def _format_context_loaded(
    context_id: str,
    meta: ContextMetadata,
    line_number_base: int,
    note: str | None = None,
) -> str:
    line_desc = "1-based" if line_number_base == 1 else "0-based"
    msg = (
        f"Context loaded '{context_id}': {meta.size_chars:,} chars, "
        f"{meta.size_lines:,} lines, ~{meta.size_tokens_estimate:,} tokens "
        f"(line numbers {line_desc})."
    )
    if note:
        msg += f"\nNote: {note}"
    return msg


def _to_jsonable(obj: Any) -> Any:
    """Best-effort conversion of MCP/Pydantic objects into JSON-serializable data."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return _to_jsonable(vars(obj))
        except Exception:
            pass
    return str(obj)
