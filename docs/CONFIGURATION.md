# Aleph Configuration Guide

This guide covers all configuration options for Aleph, including environment variables, CLI flags, and programmatic configuration.

## Quick Reference

| Variable | Purpose | Default |
|----------|---------|---------|
| `ALEPH_SUB_QUERY_BACKEND` | Force sub-query backend | `auto` |
| `ALEPH_SUB_QUERY_API_KEY` | API key (fallback: `OPENAI_API_KEY`) | -- |
| `ALEPH_SUB_QUERY_URL` | API base URL (fallback: `OPENAI_BASE_URL`) | `https://api.openai.com/v1` |
| `ALEPH_SUB_QUERY_MODEL` | Model name (required for API) | -- |
| `ALEPH_MAX_ITERATIONS` | Maximum iterations per session | `100` |
| `ALEPH_MAX_COST` | Maximum cost in USD | `1.0` |

## Sub-Query Configuration

The `sub_query` tool spawns independent sub-agents for recursive reasoning. It uses **OpenAI-compatible APIs only**.

### Backend Priority (auto mode)

When `ALEPH_SUB_QUERY_BACKEND` is not set or set to `auto`:

1. **API** -- if any API credentials are available
2. **claude CLI** -- if installed (uses Claude Code subscription)
3. **codex CLI** -- if installed (uses OpenAI subscription)
4. **aider CLI** -- if installed

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

The API backend supports any **OpenAI-compatible** endpoint. Configure with these environment variables:

| Variable | Purpose | Fallback |
|----------|---------|----------|
| `ALEPH_SUB_QUERY_API_KEY` | API key | `OPENAI_API_KEY` |
| `ALEPH_SUB_QUERY_URL` | Base URL | `OPENAI_BASE_URL` or `https://api.openai.com/v1` |
| `ALEPH_SUB_QUERY_MODEL` | Model name | (required) |

**Examples:**

```bash
# OpenAI
export ALEPH_SUB_QUERY_API_KEY=sk-...
export ALEPH_SUB_QUERY_MODEL=gpt-5.2-codex

# Groq (fast inference)
export ALEPH_SUB_QUERY_API_KEY=gsk_...
export ALEPH_SUB_QUERY_URL=https://api.groq.com/openai/v1
export ALEPH_SUB_QUERY_MODEL=llama-3.3-70b-versatile

# Together AI
export ALEPH_SUB_QUERY_API_KEY=...
export ALEPH_SUB_QUERY_URL=https://api.together.xyz/v1
export ALEPH_SUB_QUERY_MODEL=meta-llama/Llama-3-70b-chat-hf

# DeepSeek
export ALEPH_SUB_QUERY_API_KEY=...
export ALEPH_SUB_QUERY_URL=https://api.deepseek.com/v1
export ALEPH_SUB_QUERY_MODEL=deepseek-chat

# Ollama (local)
export ALEPH_SUB_QUERY_API_KEY=ollama  # any non-empty value
export ALEPH_SUB_QUERY_URL=http://localhost:11434/v1
export ALEPH_SUB_QUERY_MODEL=llama3.2

# LM Studio (local)
export ALEPH_SUB_QUERY_API_KEY=lm-studio  # any non-empty value
export ALEPH_SUB_QUERY_URL=http://localhost:1234/v1
export ALEPH_SUB_QUERY_MODEL=local-model
```

**Using OPENAI_* fallbacks:**

If you already have `OPENAI_API_KEY` and `OPENAI_BASE_URL` set, you only need to set the model:

```bash
export ALEPH_SUB_QUERY_MODEL=gpt-5.2-codex
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
aleph

# With action tools enabled (file/command access)
aleph --enable-actions --tool-docs concise

# Custom timeout and output limits
aleph --timeout 60 --max-output 20000

# Require confirmation for action tools
aleph --enable-actions --tool-docs concise --require-confirmation

# Custom workspace root
aleph --enable-actions --tool-docs concise --workspace-root /path/to/project

# Allow any git repo (use absolute paths in tool calls)
aleph --enable-actions --tool-docs concise --workspace-mode git

# Full tool docs (larger MCP tool list payload)
aleph --tool-docs full
```

### MCP Client Configuration

**Claude Desktop / Cursor / Windsurf:**

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph",
      "args": ["--enable-actions", "--tool-docs", "concise"],
      "env": {
        "ALEPH_SUB_QUERY_API_KEY": "${ALEPH_SUB_QUERY_API_KEY}",
        "ALEPH_SUB_QUERY_MODEL": "${ALEPH_SUB_QUERY_MODEL}"
      }
    }
  }
}
```

**Codex CLI (`~/.codex/config.toml`):**

```toml
[mcp_servers.aleph]
command = "aleph"
args = ["--enable-actions", "--tool-docs", "concise"]
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

model: gpt-5.2-codex  # or any OpenAI-compatible model
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
# Sub-query API configuration (OpenAI-compatible)
ALEPH_SUB_QUERY_API_KEY=sk-...
ALEPH_SUB_QUERY_MODEL=gpt-5.2-codex

# Optional: custom endpoint
# ALEPH_SUB_QUERY_URL=https://api.groq.com/openai/v1

# Or use CLI backend (no API key needed)
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
   echo $ALEPH_SUB_QUERY_API_KEY $OPENAI_API_KEY
   ```

2. Force a specific backend to test:
   ```bash
   export ALEPH_SUB_QUERY_BACKEND=api
   export ALEPH_SUB_QUERY_API_KEY=sk-...
   export ALEPH_SUB_QUERY_MODEL=gpt-5.2-codex
   ```

3. Check logs for errors in the MCP client.

### Sandbox timeout

Increase the timeout:
```bash
aleph --timeout 120
```

### Output truncated

Increase the output limit:
```bash
aleph --max-output 50000
```

### Actions disabled

Enable action tools:
```bash
aleph --enable-actions --tool-docs concise
```

## See Also

- [README.md](../README.md) -- Overview and quick start
- [DEVELOPMENT.md](../DEVELOPMENT.md) -- Architecture and development
- [ALEPH.md](../ALEPH.md) -- AI skill guide
