"""Compatibility entry point for Aleph MCP server.

This module now aliases the full-featured MCP server.
"""

from __future__ import annotations

from .local_server import AlephMCPServerLocal, main as _main

AlephMCPServer = AlephMCPServerLocal

__all__ = ["AlephMCPServer", "main"]


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
