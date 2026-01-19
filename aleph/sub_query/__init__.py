"""Sub-query module for RLM-style recursive reasoning.

This module enables Aleph to spawn sub-agents that can reason over context slices,
following the Recursive Language Model (RLM) paradigm.

Backend priority (configurable via ALEPH_SUB_QUERY_BACKEND):
1. API (if credentials available) - OpenAI-compatible APIs only
2. CLI backends (claude, codex) - uses existing subscriptions

Configuration via environment:
- ALEPH_SUB_QUERY_API_KEY (or OPENAI_API_KEY fallback)
- ALEPH_SUB_QUERY_URL (or OPENAI_BASE_URL fallback, default: https://api.openai.com/v1)
- ALEPH_SUB_QUERY_MODEL (required)
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "SubQueryConfig",
    "detect_backend",
    "DEFAULT_CONFIG",
    "has_api_credentials",
]


BackendType = Literal["claude", "codex", "gemini", "api", "auto"]

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_API_KEY_ENV = "ALEPH_SUB_QUERY_API_KEY"
DEFAULT_API_BASE_URL_ENV = "ALEPH_SUB_QUERY_URL"
DEFAULT_API_MODEL_ENV = "ALEPH_SUB_QUERY_MODEL"


@dataclass
class SubQueryConfig:
    """Configuration for sub-query backend.

    The backend priority can be configured via environment variables:

    - ALEPH_SUB_QUERY_BACKEND: Force a specific backend ("api", "claude", "codex", "gemini")
    - ALEPH_SUB_QUERY_API_KEY: API key for OpenAI-compatible providers (fallback: OPENAI_API_KEY)
    - ALEPH_SUB_QUERY_URL: Base URL for OpenAI-compatible APIs (fallback: OPENAI_BASE_URL)
    - ALEPH_SUB_QUERY_MODEL: Model name (required)

    When backend="auto" (default), the priority is:
    1. API - if API credentials are available
    2. claude CLI - if installed
    3. codex CLI - if installed
    4. gemini CLI - if installed

    Attributes:
        backend: Which backend to use. "auto" prioritizes API, then CLI.
        cli_timeout_seconds: Timeout for CLI subprocess calls.
        cli_max_output_chars: Maximum output characters from CLI.
        api_timeout_seconds: Timeout for API calls.
        api_key_env: Environment variable name for API key.
        api_base_url_env: Environment variable name for API base URL.
        api_model_env: Environment variable name for API model.
        api_model: Explicit model override (if provided programmatically).
        max_context_chars: Truncate context slices longer than this.
        include_system_prompt: Whether to include a system prompt for sub-queries.
    """

    backend: BackendType = "auto"

    # CLI options
    cli_timeout_seconds: float = 120.0
    cli_max_output_chars: int = 50_000

    # API options
    api_timeout_seconds: float = 60.0
    api_key_env: str = DEFAULT_API_KEY_ENV
    api_base_url_env: str = DEFAULT_API_BASE_URL_ENV
    api_model_env: str = DEFAULT_API_MODEL_ENV
    api_model: str | None = None

    # Behavior
    max_context_chars: int = 100_000
    include_system_prompt: bool = True

    # System prompt for sub-queries
    system_prompt: str = field(
        default="""You are a focused sub-agent processing a single task. This is a one-shot operation.

INSTRUCTIONS:
1. Answer the question based ONLY on the provided context
2. Be concise - provide direct answers without preamble
3. If context is insufficient, say "INSUFFICIENT_CONTEXT: [what's missing]"
4. Structure your response for easy parsing:
   - For summaries: bullet points or numbered lists
   - For extractions: key: value format
   - For analysis: clear sections with headers
5. Do not make up information not present in the context

OUTPUT FORMAT:
- Start directly with your answer (no "Based on the context..." preamble)
- End with a confidence indicator if uncertain: [CONFIDENCE: high/medium/low]"""
    )


def _get_api_key(api_key_env: str) -> str | None:
    """Return API key from explicit env var or OPENAI_API_KEY fallback."""
    return os.environ.get(api_key_env) or os.environ.get("OPENAI_API_KEY")


def has_api_credentials(config: SubQueryConfig | None = None) -> bool:
    """Check if API credentials are available for the sub-query backend."""
    cfg = config or DEFAULT_CONFIG
    return _get_api_key(cfg.api_key_env) is not None


def detect_backend(config: SubQueryConfig | None = None) -> BackendType:
    """Auto-detect the best available backend.

    Priority (API-first for reliability and configurability):
    1. Check ALEPH_SUB_QUERY_BACKEND env var for explicit override
    2. api - if API credentials are available
    3. claude CLI - if installed
    4. codex CLI - if installed
    5. api (fallback) - will error if no credentials, but gives helpful message

    Returns:
        The detected backend type.
    """
    cfg = config or DEFAULT_CONFIG

    # Check for explicit backend override
    explicit_backend = os.environ.get("ALEPH_SUB_QUERY_BACKEND", "").lower().strip()
    if explicit_backend in ("api", "claude", "codex", "gemini"):
        return explicit_backend  # type: ignore

    # Prefer API if explicit model is set and credentials exist
    if (cfg.api_model or os.environ.get(cfg.api_model_env)) and has_api_credentials(cfg):
        return "api"

    # Priority 1: API if credentials are available
    if has_api_credentials(cfg):
        return "api"

    # Priority 2-4: CLI backends
    if shutil.which("claude"):
        return "claude"
    if shutil.which("codex"):
        return "codex"
    if shutil.which("gemini"):
        return "gemini"

    # Fallback to API (will error with helpful message if no credentials)
    return "api"


DEFAULT_CONFIG = SubQueryConfig()
