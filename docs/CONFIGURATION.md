# Aleph Configuration Guide

This guide covers all configuration options for Aleph, including environment variables, CLI flags, and programmatic configuration.

## Quick Reference

| Variable | Purpose | Default |
|----------|---------|---------|
| `ALEPH_SUB_QUERY_BACKEND` | Force sub-query backend | `auto` |
| `ALEPH_SUB_QUERY_MODEL` | Model for API backend | `mimo-v2-flash` |
| `MIMO_API_KEY` | Mimo API key | — |
| `OPENAI_API_KEY` | OpenAI-compatible API key | — |
| `OPENAI_BASE_URL` | API endpoint | `https://api.xiaomimimo.com/v1` |
| `ALEPH_MAX_ITERATIONS` | Maximum iterations per session | `100` |
| `ALEPH_MAX_COST` | Maximum cost in USD | `1.0` |

## Sub-Query Configuration

The `sub_query` tool spawns independent sub-agents for recursive reasoning. You can configure which backend it uses.

### Backend Priority (auto mode)

When `ALEPH_SUB_QUERY_BACKEND` is not set or set to `auto`:

1. **API** — if `MIMO_API_KEY` or `OPENAI_API_KEY` is available
2. **claude CLI** — if installed (uses Claude Code subscription)
3. **codex CLI** — if installed (uses OpenAI subscription)
4. **aider CLI** — if installed

### Force a Specific Backend

```bash
# Force API backend
export ALEPH_SUB_QUERY_BACKEND=api

# Force Claude CLI
export ALEPH_SUB_QUERY_BACKEND=claude

# Force Codex CLI
export ALEPH_SUB_QUERY_BACKEND=codex

# Force Aider CLI
export ALEPH_SUB_QUERY_BACKEND=aider
```

### API Backend Configuration

The API backend uses OpenAI-compatible endpoints. Default is Mimo Flash V2 (free until Jan 20, 2026).

```bash
# Mimo Flash V2 (default)
export MIMO_API_KEY=your_mimo_key
export OPENAI_BASE_URL=https://api.xiaomimimo.com/v1
export ALEPH_SUB_QUERY_MODEL=mimo-v2-flash

# OpenAI
export OPENAI_API_KEY=your_openai_key
export OPENAI_BASE_URL=https://api.openai.com/v1
export ALEPH_SUB_QUERY_MODEL=gpt-4o-mini

# Groq
export OPENAI_API_KEY=your_groq_key
export OPENAI_BASE_URL=https://api.groq.com/openai/v1
export ALEPH_SUB_QUERY_MODEL=llama-3.1-70b-versatile

# Together AI
export OPENAI_API_KEY=your_together_key
export OPENAI_BASE_URL=https://api.together.xyz/v1
export ALEPH_SUB_QUERY_MODEL=meta-llama/Llama-3-70b-chat-hf

# Local (Ollama)
export OPENAI_API_KEY=ollama  # any non-empty value
export OPENAI_BASE_URL=http://localhost:11434/v1
export ALEPH_SUB_QUERY_MODEL=llama3.1
```

### CLI Backend Notes

**Claude CLI (`claude`):**
- Requires Claude Code installed: `npm install -g @anthropic-ai/claude-code`
- Uses your existing Claude subscription (no extra API key)
- Spawns: `claude -p "prompt" --dangerously-skip-permissions`

**Codex CLI (`codex`):**
- Requires OpenAI Codex CLI installed
- Uses your existing OpenAI subscription
- Spawns: `codex -q "prompt"`

**Aider CLI (`aider`):**
- Requires Aider installed: `pip install aider-chat`
- Spawns: `aider --message "prompt" --yes --no-git --no-auto-commits`

## MCP Server Configuration

### CLI Flags

```bash
# Basic usage
aleph-mcp-local

# With action tools enabled (file/command access)
aleph-mcp-local --enable-actions

# Custom timeout and output limits
aleph-mcp-local --timeout 60 --max-output 20000

# Require confirmation for action tools
aleph-mcp-local --enable-actions --require-confirmation

# Custom workspace root
aleph-mcp-local --enable-actions --workspace-root /path/to/project

# Allow any git repo (use absolute paths in tool calls)
aleph-mcp-local --enable-actions --workspace-mode git
```

### MCP Client Configuration

**Claude Desktop / Cursor / Windsurf:**

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": ["--enable-actions"]
    }
  }
}
```

**With environment variables:**

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": ["--enable-actions"],
      "env": {
        "MIMO_API_KEY": "your_key",
        "OPENAI_BASE_URL": "https://api.xiaomimimo.com/v1"
      }
    }
  }
}
```

**Codex CLI (`~/.codex/config.toml`):**

```toml
[mcp_servers.aleph]
command = "aleph-mcp-local"
args = ["--enable-actions"]
```

## Sandbox Configuration

The Python sandbox can be configured programmatically:

```python
from aleph.repl.sandbox import SandboxConfig, REPLEnvironment

config = SandboxConfig(
    timeout_seconds=30.0,      # Code execution timeout
    max_output_chars=10000,    # Truncate output after this
)

repl = REPLEnvironment(
    context="your document here",
    context_var_name="ctx",
    config=config,
)
```

### Sandbox Security

The sandbox blocks:
- File system access (`open`, `os`, `pathlib`)
- Network access (`socket`, `urllib`, `requests`)
- Process spawning (`subprocess`, `os.system`)
- Dangerous builtins (`eval`, `exec`, `compile`)
- Dunder attribute access (`__class__`, `__globals__`, etc.)

Allowed imports:
- `re`, `json`, `csv`
- `math`, `statistics`
- `collections`, `itertools`, `functools`
- `datetime`, `textwrap`, `difflib`
- `random`, `string`
- `hashlib`, `base64`
- `urllib.parse`, `html`

## Budget Configuration

Control resource usage programmatically:

```python
from aleph.types import Budget

budget = Budget(
    max_tokens=100_000,        # Total token limit
    max_cost_usd=1.0,          # Cost limit
    max_iterations=100,        # Iteration limit
    max_depth=5,               # Sub-query recursion depth
    max_wall_time_seconds=300, # Wall clock timeout
    max_sub_queries=50,        # Sub-query count limit
)
```

## Recipe/Alephfile Configuration

Alephfiles define reproducible analysis runs:

```yaml
# aleph.yaml
schema: aleph.recipe.v1
query: "Find all security vulnerabilities in this codebase"

datasets:
  - id: source
    path: ./src
    type: directory
  - id: tests
    path: ./tests
    type: directory

model: mimo-v2-flash
max_iterations: 50
timeout_seconds: 600
max_tokens: 500000

tools:
  enabled:
    - search_context
    - exec_python
    - sub_query
  disabled:
    - run_command  # Disable shell access
```

Load and run:

```python
from aleph.recipe import load_alephfile, RecipeRunner

config = load_alephfile("aleph.yaml")
runner = RecipeRunner(config)
runner.start()
# ... execute tools ...
result = runner.finalize(answer="Found 3 issues", success=True)
```

## Environment File

Create a `.env` file in your project root:

```bash
# Sub-query API configuration
MIMO_API_KEY=your_mimo_key
OPENAI_BASE_URL=https://api.xiaomimimo.com/v1
ALEPH_SUB_QUERY_MODEL=mimo-v2-flash

# Or force CLI backend
# ALEPH_SUB_QUERY_BACKEND=claude

# Resource limits
ALEPH_MAX_ITERATIONS=100
ALEPH_MAX_COST=1.0
```

Load with your shell or tool of choice (e.g., `source .env`, `dotenv`, or IDE integration).

## Troubleshooting

### Sub-query not working

1. Check backend detection:
   ```bash
   # Which CLI tools are available?
   which claude codex aider

   # Are API credentials set?
   echo $MIMO_API_KEY $OPENAI_API_KEY
   ```

2. Force a specific backend to test:
   ```bash
   export ALEPH_SUB_QUERY_BACKEND=api
   export MIMO_API_KEY=your_key
   ```

3. Check logs for errors in the MCP client.

### Sandbox timeout

Increase the timeout:
```bash
aleph-mcp-local --timeout 120
```

### Output truncated

Increase the output limit:
```bash
aleph-mcp-local --max-output 50000
```

### Actions disabled

Enable action tools:
```bash
aleph-mcp-local --enable-actions
```

## See Also

- [README.md](../README.md) — Overview and quick start
- [DEVELOPMENT.md](../DEVELOPMENT.md) — Architecture and development
- [ALEPH.md](../ALEPH.md) — AI skill guide
