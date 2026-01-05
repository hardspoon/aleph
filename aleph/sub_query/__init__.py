"""Sub-query module for RLM-style recursive reasoning.

This module enables Aleph to spawn sub-agents that can reason over context slices,
following the Recursive Language Model (RLM) paradigm.

Backend priority (configurable via ALEPH_SUB_QUERY_BACKEND):
1. API (if credentials available) - Mimo Flash V2 or any OpenAI-compatible API
2. CLI backends (claude, codex, aider) - uses existing subscriptions
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Literal

__all__ = ["SubQueryConfig", "detect_backend", "DEFAULT_CONFIG", "has_api_credentials"]


BackendType = Literal["claude", "codex", "aider", "api", "auto"]


@dataclass
class SubQueryConfig:
    """Configuration for sub-query backend.

    The backend priority can be configured via environment variables:

    - ALEPH_SUB_QUERY_BACKEND: Force a specific backend ("api", "claude", "codex", "aider")
    - MIMO_API_KEY or OPENAI_API_KEY: Required for API backend
    - OPENAI_BASE_URL: API endpoint (default: https://api.xiaomimimo.com/v1)
    - ALEPH_SUB_QUERY_MODEL: Model name (default: mimo-v2-flash)

    When backend="auto" (default), the priority is:
    1. API - if MIMO_API_KEY or OPENAI_API_KEY is set
    2. claude CLI - if installed
    3. codex CLI - if installed
    4. aider CLI - if installed

    Attributes:
        backend: Which backend to use. "auto" prioritizes API, then CLI.
        cli_timeout_seconds: Timeout for CLI subprocess calls.
        cli_max_output_chars: Maximum output characters from CLI.
        api_base_url_env: Environment variable for API base URL.
        api_key_env: Environment variable for API key.
        api_model: Model name for API calls.
        max_context_chars: Truncate context slices longer than this.
        include_system_prompt: Whether to include a system prompt for sub-queries.
    """
    backend: BackendType = "auto"

    # CLI options
    cli_timeout_seconds: float = 120.0
    cli_max_output_chars: int = 50_000

    # API options (preferred when credentials available)
    # Default: Xiaomi MiMo Flash V2 (free public beta until Jan 20, 2026)
    # Uses OpenAI-compatible API format at api.xiaomimimo.com
    api_base_url_env: str = "OPENAI_BASE_URL"
    api_key_env: str = "MIMO_API_KEY"  # Falls back to OPENAI_API_KEY
    api_model: str = "mimo-v2-flash"
    api_timeout_seconds: float = 60.0

    # Behavior
    max_context_chars: int = 100_000
    include_system_prompt: bool = True

    # System prompt for sub-queries
    system_prompt: str = field(default="""You are a focused sub-agent analyzing a specific portion of a larger document.
Your task is to answer the question based ONLY on the provided context.
Be concise and precise. If the context doesn't contain enough information to answer, say so.
Do not make up information not present in the context.""")


def has_api_credentials(config: SubQueryConfig | None = None) -> bool:
    """Check if API credentials are available (MIMO_API_KEY or OPENAI_API_KEY)."""
    cfg = config or DEFAULT_CONFIG
    return bool(os.environ.get(cfg.api_key_env) or os.environ.get("OPENAI_API_KEY"))


def detect_backend(config: SubQueryConfig | None = None) -> BackendType:
    """Auto-detect the best available backend.

    Priority (API-first for reliability and configurability):
    1. Check ALEPH_SUB_QUERY_BACKEND env var for explicit override
    2. api - if MIMO_API_KEY or OPENAI_API_KEY is set
    3. claude CLI - if installed
    4. codex CLI - if installed
    5. aider CLI - if installed
    6. api (fallback) - will error if no credentials, but gives helpful message

    This priority order ensures:
    - Users who configure API keys get consistent, predictable behavior
    - IDE users (Cursor, Windsurf) can still use CLI tools seamlessly
    - Clear error messages guide users to configure credentials

    Returns:
        The detected backend type.
    """
    cfg = config or DEFAULT_CONFIG

    # Check for explicit backend override
    explicit_backend = os.environ.get("ALEPH_SUB_QUERY_BACKEND", "").lower().strip()
    if explicit_backend in ("api", "claude", "codex", "aider"):
        return explicit_backend  # type: ignore

    # Check for model override (implies API backend preference)
    if os.environ.get("ALEPH_SUB_QUERY_MODEL"):
        if has_api_credentials(cfg):
            return "api"

    # Priority 1: API if credentials are available
    if has_api_credentials(cfg):
        return "api"

    # Priority 2-4: CLI backends
    if shutil.which("claude"):
        return "claude"
    if shutil.which("codex"):
        return "codex"
    if shutil.which("aider"):
        return "aider"

    # Fallback to API (will error with helpful message if no credentials)
    return "api"


DEFAULT_CONFIG = SubQueryConfig()
