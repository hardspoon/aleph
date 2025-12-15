# Aleph RLM

> *"What my eyes beheld was simultaneous, but what I shall now write down will be successive, because language is successive."*
>
> — Jorge Luis Borges, ["The Aleph"](https://web.mit.edu/allanmc/www/borgesaleph.pdf) (1945)

MCP server for recursive LLM reasoning—load context, iterate with search/code/think tools, converge on answers.

Aleph is an MCP server that implements **recursive language model reasoning**. Instead of single-pass context processing, Aleph gives LLMs a persistent session with tools to iteratively explore, analyze, and reason over documents. Load context once, then search, slice, execute Python, and structure your thinking across multiple iterations until you converge on a high-confidence answer.

**The core insight:** LLMs are better at many small, focused operations than one giant comprehension task. Aleph operationalizes this by giving the model a REPL session where it can:
- Hold context in a variable (`ctx`)
- Slice into relevant portions on demand
- Run Python to transform/analyze
- Track its own reasoning history
- Persist variables across iterations

Inspired by research by **Alex Zhang** and **Omar Khattab (MIT)** on Recursive Language Models.

## Features

- **Provider-agnostic**: works with Anthropic or OpenAI (and any custom provider implementing the `LLMProvider` protocol)
- **Unbounded context**: context lives in a REPL variable, not in the LLM prompt
- **Helper functions**: `peek`, `lines`, `search`, `chunk`, `cite`
- **Recursive calls**:
  - `sub_query(prompt, context_slice=None)` for cheaper semantic subcalls
  - `sub_aleph(query, context=None)` for deeper recursion
- **Budgets**: hard limits on tokens/cost/iterations/time/subqueries
- **Observability**: full execution trajectory returned for debugging
- **Async-first** API with a `complete_sync()` convenience wrapper

## Installation

This repository is provided as a standard Python package.

```bash
pip install -e .
```

Optional extras:

```bash
pip install -e '.[mcp]'
pip install -e '.[yaml]'
pip install -e '.[rich]'
pip install -e '.[openai_tokens]'
```

## API keys

Aleph uses environment variables by default:

- **Anthropic**: set `ANTHROPIC_API_KEY`
- **OpenAI**: set `OPENAI_API_KEY`

## Quickstart

```python
import asyncio
from aleph import Aleph, Budget

async def main():
    aleph = Aleph(
        provider="anthropic",
        root_model="claude-sonnet-4-20250514",
        sub_model="claude-haiku-3-5-20241022",
        budget=Budget(max_cost_usd=1.0, max_iterations=20),
    )

    context = """... a very large document ..."""

    resp = await aleph.complete(
        query="What are the key risks mentioned?",
        context=context,
    )

    print(resp.answer)
    print("tokens:", resp.total_tokens)
    print("cost:  ", resp.total_cost_usd)
    print("iters: ", resp.total_iterations)

asyncio.run(main())
```

## How it works

1. Aleph stores the full context in a sandboxed REPL (`ctx`).
2. The LLM is prompted with a short metadata summary of the context.
3. The LLM writes Python code to:
   - search the context (`search(...)`)
   - inspect slices (`peek(...)`, `lines(...)`)
   - split into chunks (`chunk(...)`)
   - cite evidence (`cite(...)`) for provenance tracking
4. Aleph executes the code and feeds the (truncated) output back into the conversation.
5. The LLM can evaluate its progress and convergence using `evaluate_progress()`.
6. The LLM repeats until it outputs:
   - `FINAL(answer)` or
   - `FINAL_VAR(variable_name)`
7. Final output includes evidence citations for transparency.

## Security

The Aleph sandbox is **best-effort** and is not formally hardened.

### What the sandbox blocks

- **File I/O**: `open`, `os`, `pathlib`, and related modules
- **Network access**: `socket`, `urllib`, `requests`, and related modules
- **Process execution**: `subprocess`, `os.system`, and related functions
- **Dangerous builtins**: `eval`, `exec`, `compile`, `__import__`, `getattr`, `setattr`
- **Direct builtins access**: `__builtins__`
- **Dunder attribute access**: `__class__`, `__subclasses__`, `__globals__`, etc.
- **Catching BaseException**: `except BaseException`, `except SystemExit`, etc.
- **Imports outside allowlist**: Only `re`, `json`, `csv`, `math`, `statistics`, `collections`, `itertools`, `functools`, `datetime`, `textwrap`, `difflib` are allowed

### What the sandbox does NOT protect against

- **CPU exhaustion**: Mitigated by configurable timeout (default 30s), but cannot interrupt all CPU-bound loops on Windows
- **Memory exhaustion**: No memory limits are enforced
- **Sophisticated escape techniques**: Determined attackers may find bypasses
- **Side-channel attacks**: Not protected

### Timeout enforcement

Code execution timeout is configurable via `SandboxConfig(timeout_seconds=30.0)`.

- **Unix (Linux, macOS) main thread**: Uses `signal.SIGALRM` for reliable interruption of CPU-bound code
- **Other contexts (including worker threads)**: Uses a thread watchdog and best-effort async exception injection.
  This can interrupt typical Python CPU-bound loops, but may not interrupt native extensions or C-level blocking calls.

### Recommendations for production

- Run Aleph in a containerized environment (Docker, gVisor, Firecracker)
- Apply OS-level sandboxing (seccomp, SELinux, AppArmor)
- Set resource limits via cgroups (CPU, memory)
- **Do not expose code execution to untrusted users** without stronger isolation

## MCP Server

Install MCP support:

```bash
pip install -e '.[mcp]'
```

### API-Dependent Mode

Uses an external LLM API for sub-queries (requires API keys):

```bash
python -m aleph.mcp.server --provider anthropic --model claude-sonnet-4-20250514
```

Tools exposed:

- `load_context(context, context_id="default", format="auto")`
- `peek_context(start=0, end=None, context_id="default", unit="chars"|"lines")`
- `search_context(pattern, context_id="default", max_results=10, context_lines=2)`
- `exec_python(code, context_id="default")`
- `sub_query(prompt, context_slice=None, context_id="default")`
- `get_variable(name, context_id="default")`

### API-Free Mode (Local)

**No API keys required!** The host AI (Claude Desktop, Cursor, Windsurf, etc.) provides all reasoning.

```bash
# Via entry point
aleph-mcp-local

# Or via module
python -m aleph.mcp.local_server
```

Configure in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": ["--timeout", "30", "--max-output", "10000"]
    }
  }
}
```

Configure in Cursor (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local"
    }
  }
}
```

**Tools exposed:**

| Tool | Description |
|------|-------------|
| `load_context` | Load text/data into sandboxed REPL (as variable `ctx`) |
| `peek_context` | View character or line ranges |
| `search_context` | Regex search with surrounding context |
| `exec_python` | Execute Python code in sandbox (includes `cite()` for provenance) |
| `get_variable` | Retrieve variables from REPL namespace |
| `think` | Structure a reasoning sub-step (returns prompt for YOU to reason about) |
| `get_status` | Show current session state with convergence metrics |
| `get_evidence` | Retrieve collected evidence/citations |
| `finalize` | Mark task complete with final answer and evidence citations |
| `chunk_context` | Split context into chunks with metadata for navigation |
| `evaluate_progress` | Self-evaluate progress with convergence tracking |
| `summarize_so_far` | Compress reasoning history to manage context window |

**Recursive reasoning loop:**

```
load → search/peek → think → evaluate_progress → (repeat if needed) → finalize
```

**Example workflow:**

1. User: "Analyze this 50KB log file and find all errors"
2. AI uses `load_context` to load the file
3. AI uses `chunk_context` to map document structure
4. AI uses `search_context` to find "error" patterns (evidence tracked automatically)
5. AI uses `exec_python` to parse/aggregate results, `cite()` important findings
6. AI uses `think` to structure sub-questions
7. AI uses `evaluate_progress` to check confidence (continues if < 0.8)
8. AI reasons through each sub-question (no API call!)
9. AI uses `summarize_so_far` if context gets long
10. AI uses `finalize` to provide the answer with evidence citations

**Benefits:**

- No API costs for sub-queries
- No API keys needed
- Lower latency (no network calls)
- Works offline
- Universal MCP compatibility

## Examples

Run examples from the repo root:

```bash
python examples/needle_haystack.py
```

Other examples:

- `examples/document_qa.py`
- `examples/mcp_server.py`

## Development

Install with dev dependencies:

```bash
pip install -e '.[dev]'
```

Run tests:

```bash
pytest
```

Run type checking:

```bash
mypy aleph/
```

## License

MIT
