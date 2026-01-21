"""Aleph MCP server for use with Claude Desktop, Cursor, Windsurf, etc.

This server exposes Aleph's context exploration tools and optional action tools.

Tools:
- load_context: Load text/data into sandboxed REPL
- peek_context: View character/line ranges
- search_context: Regex search with context
- semantic_search: Meaning-based search over the context
- exec_python: Execute Python code in sandbox
- get_variable: Retrieve variables from REPL
- sub_query: RLM-style recursive sub-agent queries (CLI or API backend)
- think: Structure a reasoning sub-step (returns prompt for YOU to reason about)
- tasks: Lightweight task tracking per context
- get_status: Show current session state
- get_evidence: Retrieve collected evidence/citations
- finalize: Mark task complete with answer
- chunk_context: Split context into chunks with metadata for navigation
- evaluate_progress: Self-evaluate progress with convergence tracking
- summarize_so_far: Compress reasoning history to manage context window
- rg_search: Fast repo search via ripgrep (action tool)

Usage:
    aleph
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Literal, cast

from ..repl.sandbox import SandboxConfig
from ..sub_query import SubQueryConfig
from .actions import ActionConfig
from .env_utils import DEFAULT_REMOTE_TOOL_TIMEOUT_SECONDS
from .formatting import _to_jsonable
from .io_utils import _detect_format
from .remote import RemoteOrchestrator, _RemoteServerHandle
from .session import (
    MEMORY_PACK_RELATIVE_PATH,
    _Evidence,
    _Session,
    _analyze_text_context,
    _session_from_payload,
)
from .tool_registry import register_tools
from .workspace import WorkspaceMode, DEFAULT_WORKSPACE_MODE, _detect_workspace_root

__all__ = ["AlephMCPServerLocal", "main", "mcp"]


ToolDocsMode = Literal["concise", "full"]
DEFAULT_TOOL_DOCS_MODE: ToolDocsMode = "concise"




class AlephMCPServerLocal:
    """MCP server for local AI reasoning.

    This server provides context exploration tools that work with any
    MCP-compatible AI host (Claude Desktop, Cursor, Windsurf, etc.).
    """

    def __init__(
        self,
        sandbox_config: SandboxConfig | None = None,
        action_config: ActionConfig | None = None,
        sub_query_config: SubQueryConfig | None = None,
        tool_docs_mode: ToolDocsMode = DEFAULT_TOOL_DOCS_MODE,
    ) -> None:
        self.sandbox_config = sandbox_config or SandboxConfig()
        self.action_config = action_config or ActionConfig()
        self.sub_query_config = sub_query_config or SubQueryConfig()
        self.tool_docs_mode = tool_docs_mode
        self._sessions: dict[str, _Session] = {}
        self._remote_servers: dict[str, _RemoteServerHandle] = {}
        self._remote_orchestrator = RemoteOrchestrator(
            self._remote_servers,
            _to_jsonable,
            default_timeout_seconds=DEFAULT_REMOTE_TOOL_TIMEOUT_SECONDS,
        )
        self._auto_pack_loaded = False
        self._streamable_http_task: asyncio.Task | None = None
        self._streamable_http_url: str | None = None
        self._streamable_http_host: str | None = None
        self._streamable_http_port: int | None = None
        self._streamable_http_path: str | None = None
        self._streamable_http_lock = asyncio.Lock()

        # Import MCP lazily so it's an optional dependency
        try:
            from mcp.server.fastmcp import FastMCP
        except Exception as e:
            raise RuntimeError(
                "MCP support requires the `mcp` package. Install with `pip install \"aleph-rlm[mcp]\"`."
            ) from e

        self.server = FastMCP("aleph-local")
        self._register_tools()

        if self.action_config.enabled:
            self._auto_load_memory_pack()

    async def _remote_list_tools(self, server_id: str) -> tuple[bool, Any]:
        return await self._remote_orchestrator.remote_list_tools(server_id)

    async def _remote_call_tool(
        self,
        server_id: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[bool, Any]:
        return await self._remote_orchestrator.remote_call_tool(
            server_id,
            tool,
            arguments=arguments,
            timeout_seconds=timeout_seconds,
        )

    async def _close_remote_server(self, server_id: str) -> tuple[bool, str]:
        return await self._remote_orchestrator.close_remote_server(server_id)

    def _auto_load_memory_pack(self) -> None:
        if self._auto_pack_loaded:
            return
        self._auto_pack_loaded = True
        pack_path = self.action_config.workspace_root / MEMORY_PACK_RELATIVE_PATH
        if not pack_path.exists() or not pack_path.is_file():
            return
        try:
            if pack_path.stat().st_size > self.action_config.max_read_bytes:
                return
        except Exception:
            return
        try:
            data = pack_path.read_bytes()
            obj = json.loads(data.decode("utf-8", errors="replace"))
        except Exception:
            return

        if not isinstance(obj, dict):
            return
        if obj.get("schema") != "aleph.memory_pack.v1":
            return
        sessions = obj.get("sessions")
        if not isinstance(sessions, list):
            return
        for payload in sessions:
            if not isinstance(payload, dict):
                continue
            session_id = payload.get("context_id") or payload.get("session_id")
            resolved_id = str(session_id) if session_id else f"session_{len(self._sessions) + 1}"
            if resolved_id in self._sessions:
                continue
            try:
                session = _session_from_payload(payload, resolved_id, self.sandbox_config, loop=None)
            except Exception:
                continue
            self._sessions[resolved_id] = session

    def _normalize_streamable_http_path(self, path: str) -> str:
        if not path:
            return "/mcp"
        return path if path.startswith("/") else f"/{path}"

    def _format_streamable_http_url(self, host: str, port: int, path: str) -> str:
        connect_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        return f"http://{connect_host}:{port}{path}"

    async def _wait_for_streamable_http_ready(
        self,
        host: str,
        port: int,
        timeout_seconds: float = 2.0,
    ) -> tuple[bool, str]:
        deadline = time.monotonic() + timeout_seconds
        connect_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host

        while time.monotonic() < deadline:
            if self._streamable_http_task and self._streamable_http_task.done():
                exc = self._streamable_http_task.exception()
                if exc:
                    return False, f"Streamable HTTP server failed to start: {exc}"
                return False, "Streamable HTTP server stopped unexpectedly."
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(connect_host, port),
                    timeout=0.2,
                )
                writer.close()
                await writer.wait_closed()
                return True, ""
            except Exception:
                await asyncio.sleep(0.05)

        return False, f"Timed out waiting for streamable HTTP server on {connect_host}:{port}."

    async def _run_streamable_http_server(self, host: str, port: int) -> None:
        try:
            import uvicorn
        except Exception as exc:
            raise RuntimeError(
                "uvicorn is required for streamable HTTP transport. "
                "Install with: pip install uvicorn"
            ) from exc

        app = self.server.streamable_http_app()
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            lifespan="on",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def _ensure_streamable_http_server(
        self,
        host: str,
        port: int,
        path: str,
    ) -> tuple[bool, str]:
        normalized_path = self._normalize_streamable_http_path(path)
        async with self._streamable_http_lock:
            if self._streamable_http_task and not self._streamable_http_task.done():
                url = self._streamable_http_url or self._format_streamable_http_url(
                    host,
                    port,
                    normalized_path,
                )
                return True, url
            if self._streamable_http_task and self._streamable_http_task.done():
                self._streamable_http_task = None
                self._streamable_http_url = None

            self.server.settings.host = host
            self.server.settings.port = port
            self.server.settings.streamable_http_path = normalized_path

            self._streamable_http_task = asyncio.create_task(
                self._run_streamable_http_server(host, port)
            )
            self._streamable_http_host = host
            self._streamable_http_port = port
            self._streamable_http_path = normalized_path
            self._streamable_http_url = self._format_streamable_http_url(
                host,
                port,
                normalized_path,
            )

        ok, err = await self._wait_for_streamable_http_ready(host, port)
        if not ok:
            return False, err
        return True, self._streamable_http_url or self._format_streamable_http_url(
            host,
            port,
            normalized_path,
        )

    def _register_tools(self) -> None:
        register_tools(self)
    async def run(self, transport: str = "stdio") -> None:
        """Run the MCP server."""
        if transport != "stdio":
            raise ValueError("Only stdio transport is supported")

        await self.server.run_stdio_async()


_mcp_instance: Any | None = None


def _get_mcp_instance() -> Any:
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = AlephMCPServerLocal().server
    return _mcp_instance


def __getattr__(name: str) -> Any:
    if name == "mcp":
        return _get_mcp_instance()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    """CLI entry point: `aleph` or `python -m aleph.mcp.local_server`"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Aleph as an MCP server for local AI reasoning"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Code execution timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--max-output",
        type=int,
        default=50000,
        help="Maximum output characters (default: 50000)",
    )
    parser.add_argument(
        "--enable-actions",
        action="store_true",
        help="Enable action tools (run_command/read_file/write_file/run_tests)",
    )
    parser.add_argument(
        "--workspace-root",
        type=str,
        default=None,
        help="Workspace root for action tools (default: ALEPH_WORKSPACE_ROOT or auto-detect git root from invocation cwd)",
    )
    parser.add_argument(
        "--workspace-mode",
        type=str,
        choices=["fixed", "git", "any"],
        default=DEFAULT_WORKSPACE_MODE,
        help="Path scope for action tools: fixed (workspace root only), git (any git repo), any (no path restriction)",
    )
    parser.add_argument(
        "--require-confirmation",
        action="store_true",
        help="Require confirm=true for action tools",
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=1_000_000_000,
        help="Max file size in bytes for load_file/read_file (default: 1GB). Increase based on your RAM—the LLM only sees query results.",
    )
    parser.add_argument(
        "--max-write-bytes",
        type=int,
        default=100_000_000,
        help="Max file size in bytes for write_file/save_session (default: 100MB).",
    )
    env_tool_docs = os.environ.get("ALEPH_TOOL_DOCS")
    default_tool_docs = env_tool_docs if env_tool_docs in {"concise", "full"} else DEFAULT_TOOL_DOCS_MODE
    parser.add_argument(
        "--tool-docs",
        type=str,
        choices=["concise", "full"],
        default=default_tool_docs,
        help="Tool description verbosity for MCP clients: concise (default) or full",
    )

    args = parser.parse_args()

    config = SandboxConfig(
        timeout_seconds=args.timeout,
        max_output_chars=args.max_output,
    )

    action_cfg = ActionConfig(
        enabled=bool(args.enable_actions),
        workspace_root=Path(args.workspace_root).resolve() if args.workspace_root else _detect_workspace_root(),
        workspace_mode=cast(WorkspaceMode, args.workspace_mode),
        require_confirmation=bool(args.require_confirmation),
        max_read_bytes=args.max_file_size,
        max_write_bytes=args.max_write_bytes,
    )

    server = AlephMCPServerLocal(
        sandbox_config=config,
        action_config=action_cfg,
        tool_docs_mode=cast(ToolDocsMode, args.tool_docs),
    )
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
