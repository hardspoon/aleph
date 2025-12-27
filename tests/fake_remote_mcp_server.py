"""A tiny MCP server used for remote orchestration tests (stdio transport)."""

from __future__ import annotations

import asyncio


def _build_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("fake-remote")

    @server.tool()
    async def echo(text: str) -> str:
        return text

    @server.tool()
    async def add(a: int, b: int) -> int:
        return a + b

    return server


async def _run() -> None:
    server = _build_server()
    await server.run_stdio_async()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

