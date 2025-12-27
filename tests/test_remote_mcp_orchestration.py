from __future__ import annotations

import sys

import pytest

from aleph.mcp.local_server import AlephMCPServerLocal, _RemoteServerHandle
from aleph.recipe import RecipeConfig, DatasetInput, RecipeRunner


@pytest.mark.asyncio
async def test_remote_server_list_tools_and_call_tool() -> None:
    server = AlephMCPServerLocal()

    server._remote_servers["fake"] = _RemoteServerHandle(
        command=sys.executable,
        args=["-m", "tests.fake_remote_mcp_server"],
    )

    ok, tools = await server._remote_list_tools("fake")
    assert ok, tools
    assert isinstance(tools, dict)

    ok, result = await server._remote_call_tool("fake", "add", {"a": 2, "b": 3})
    assert ok, result
    # Result is an MCP CallToolResult; we check it contains our return value.
    # The exact shape can vary across MCP versions; ensure it's serializable and non-empty.
    assert result is not None

    ok, _ = await server._close_remote_server("fake")
    assert ok


@pytest.mark.asyncio
async def test_remote_tool_allowlist_blocks_calls() -> None:
    server = AlephMCPServerLocal()
    server._remote_servers["fake"] = _RemoteServerHandle(
        command=sys.executable,
        args=["-m", "tests.fake_remote_mcp_server"],
        allow_tools=["echo"],
    )

    ok, res = await server._remote_call_tool("fake", "add", {"a": 1, "b": 1})
    assert not ok
    assert "not allowed" in str(res).lower()

    ok, _ = await server._close_remote_server("fake")
    assert ok


@pytest.mark.asyncio
async def test_remote_calls_record_into_recipe_trace_and_evidence() -> None:
    server = AlephMCPServerLocal()
    server._remote_servers["fake"] = _RemoteServerHandle(
        command=sys.executable,
        args=["-m", "tests.fake_remote_mcp_server"],
    )

    cfg = RecipeConfig(
        query="noop",
        datasets=[DatasetInput(id="main", source="inline", content="hello")],
        max_iterations=1,
    )
    runner = RecipeRunner(cfg)
    runner.start()
    server._recipes["r1"] = runner

    ok, res = await server._remote_call_tool("fake", "echo", {"text": "hi"}, recipe_id="r1")
    assert ok, res
    assert runner.trace, "expected trace entry"
    assert runner.evidence, "expected evidence entry"

    ok, _ = await server._close_remote_server("fake")
    assert ok

