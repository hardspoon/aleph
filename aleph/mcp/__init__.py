"""MCP server integration.

The MCP server is an optional feature. Install with:

    pip install aleph[mcp]

Then run:

    # API-dependent mode (uses external LLM for sub-queries)
    python -m aleph.mcp.server --provider anthropic --model claude-sonnet-4-20250514

    # API-free mode (host AI provides reasoning)
    python -m aleph.mcp.local_server
    # or
    aleph-mcp-local
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .server import AlephMCPServer
    from .local_server import AlephMCPServerLocal

__all__ = ["AlephMCPServer", "AlephMCPServerLocal"]


def __getattr__(name: str):
    if name == "AlephMCPServer":
        from .server import AlephMCPServer

        return AlephMCPServer
    if name == "AlephMCPServerLocal":
        from .local_server import AlephMCPServerLocal

        return AlephMCPServerLocal
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
