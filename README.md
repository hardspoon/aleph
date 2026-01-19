# Aleph

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/aleph-rlm.svg)](https://pypi.org/project/aleph-rlm/)

Aleph is an MCP (Model Context Protocol) server that lets an LLM search and compute over large local data without loading the full data into the model context.

It keeps loaded content in a long-lived Python process (RAM) and exposes tools like regex search, slicing, and sandboxed Python execution. Only tool results are returned to the model.

Works with any text (and JSON): logs, codebases, data dumps, API responses, and other large outputs.

## Quickstart

### 1) Install

```bash
pip install "aleph-rlm[mcp]"
```

### 2) Configure your MCP client

Automatic (recommended):

```bash
aleph-rlm install
```

Manual (works in any MCP client that supports `mcpServers`):

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph",
      "args": ["--enable-actions", "--tool-docs", "concise", "--workspace-root", "/absolute/path/to/your/project"]
    }
  }
}
```

Client-specific setup (Cursor/VS Code/Claude Desktop/Codex/Windsurf): see [MCP_SETUP.md](MCP_SETUP.md).

### 3) Verify

In your assistant, call `list_contexts()` (tool names may be prefixed by your client).

## How it works (high level)

```
┌───────────────┐    tool calls     ┌────────────────────────┐
│   LLM client  │ ────────────────► │  Aleph (Python, RAM)   │
│ (limited ctx) │ ◄──────────────── │  search/peek/exec      │
└───────────────┘    small results  └────────────────────────┘
```

Load data into Aleph (via `load_context` or `load_file`), then explore it with `search_context` / `peek_context`, and optionally compute over it with `exec_python`.

## Actions and scope

Start the server with `--enable-actions` to allow:
- File tools: `load_file`, `read_file`, `write_file`, `save_session`, `load_session`
- Command tools: `run_command`, `run_tests`
- Remote orchestration: `add_remote_server`, `call_remote_tool`, etc.

`exec_python` runs in a restricted sandbox (no filesystem, no network, no subprocess).

Workspace controls:
- `--workspace-root`: root directory for relative paths (default: auto-detect git root or cwd)
- `--workspace-mode`: `fixed` (workspace only), `git` (any git repo), `any` (no path restriction)
- `--require-confirmation`: require `confirm=true` for action tool calls

Default limits:
- `--max-file-size`: 1GB for `load_file`/`read_file`
- `--max-write-bytes`: 100MB for `write_file`/`save_session`
- `--timeout`: 30s for sandbox/commands
- `--max-output`: 10,000 chars per command

## Recursion (`sub_query`)

`sub_query` runs a single sub-agent over a slice of content (often produced via `chunk_context` or `chunk()` in `exec_python`). Backends:
1. OpenAI-compatible API (if credentials are set)
2. `claude` CLI (if installed)
3. `codex` CLI (if installed)
4. `gemini` CLI (if installed)

Configuration: see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Tool overview

Core:
- `load_context`, `list_contexts`
- `search_context`, `peek_context`, `chunk_context`, `diff_contexts`
- `exec_python`, `get_variable`
- `think`, `evaluate_progress`, `summarize_so_far`
- `get_status`, `get_evidence`, `finalize`

Requires `--enable-actions`:
- `load_file`, `read_file`, `write_file`
- `run_command`, `run_tests`
- `save_session`, `load_session`
- `add_remote_server`, `list_remote_servers`, `list_remote_tools`, `call_remote_tool`, `close_remote_server`

## Configuration

For full configuration options (limits, budgets, and backend details), see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Documentation

- [MCP_SETUP.md](MCP_SETUP.md) — client configuration and workspace scoping
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — CLI flags and environment variables
- [docs/prompts/aleph.md](docs/prompts/aleph.md) — concise workflow prompt + tool reference
- [CHANGELOG.md](CHANGELOG.md) — release notes
- [DEVELOPMENT.md](DEVELOPMENT.md) — architecture and development

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Development

```bash
git clone https://github.com/Hmbown/aleph.git
cd aleph
pip install -e ".[dev,mcp]"
pytest
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture details.

## References

Aleph implements the Recursive Language Model (RLM) architecture described in:

> **Recursive Language Models**
> Zhang, A. L., Kraska, T., & Khattab, O. (2025)
> [arXiv:2512.24601](https://arxiv.org/abs/2512.24601)

## License

MIT
