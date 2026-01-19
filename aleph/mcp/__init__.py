"""MCP server integration.

The MCP server is an optional feature. Install with:

    pip install aleph-rlm[mcp]

Then run:

    aleph
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
