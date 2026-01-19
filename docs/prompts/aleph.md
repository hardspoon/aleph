---
name: aleph
description: /aleph - External memory workflow for large local data.
---

# /aleph - External Memory Workflow

TL;DR: Load large data into external memory, search it, reason in loops, and persist across sessions.

## Quick Start

```
# Test if Aleph is available
list_contexts()
```

If that works, the MCP server is running.

Instant pattern:

```
load_context(content="<paste huge content here>", context_id="doc")
search_context(pattern="keyword", context_id="doc")
finalize(answer="Found X at line Y", context_id="doc")
```

Note: tool names may appear as `mcp__aleph__load_context` in your MCP client.

## Practical Defaults

- Use `output="json"` for structured results and `output="markdown"` for human-readable output.
- Action tools require starting the server with `--enable-actions` and may require `confirm=true`.
- For large docs, pair `chunk_context()` with `peek_context()` to navigate quickly.
- Save and resume long tasks with `save_session()` and `load_session()`.
- To see full tool docstrings, start with `--tool-docs full` or set `ALEPH_TOOL_DOCS=full`.

## Core Patterns

### 1) Analyze Data
```
load_context(content=data_text, context_id="doc")
search_context(pattern="important|keyword|pattern", context_id="doc")
peek_context(start=100, end=150, unit="lines", context_id="doc")
finalize(answer="Analysis complete: ...", confidence="high", context_id="doc")
```

### 2) Compare Two Contexts
```
load_context(content=doc1, context_id="v1")
load_context(content=doc2, context_id="v2")
diff_contexts(a="v1", b="v2")
search_context(pattern="difference", context_id="v1")
search_context(pattern="difference", context_id="v2")
finalize(answer="Key differences: ...", context_id="v1")
```

### 3) Deep Reasoning Loop
```
load_context(content=problem, context_id="analysis")

think(question="What is the core issue?", context_id="analysis")
search_context(pattern="relevant", context_id="analysis")
evaluate_progress(
    current_understanding="I found X...",
    remaining_questions=["What about Y?"],
    confidence_score=0.7,
    context_id="analysis"
)

finalize(answer="Conclusion: ...", confidence="high", context_id="analysis")
```

## Sub-Query Guidance

Use sub-queries for bounded, single-shot tasks. Provide a specific output format.

```
sub_query(
    prompt="Extract error codes. Format: CODE: description",
    context_slice=log_chunk
)
```

If you need to parse results in `exec_python`, prefer line-based formats like `KEY: value`.

## Tool Reference

### Loading and Querying
| Tool | Purpose |
|------|---------|
| `load_context` | Load text/data into external memory |
| `load_file` | Load file from disk (requires --enable-actions) |
| `list_contexts` | See all loaded contexts |
| `search_context` | Regex search with surrounding context |
| `peek_context` | View specific line/char ranges |
| `chunk_context` | Split into navigable chunks |
| `diff_contexts` | Compare two contexts |

### Reasoning
| Tool | Purpose |
|------|---------|
| `think` | Structure a reasoning sub-step |
| `evaluate_progress` | Self-assess and iterate |
| `summarize_so_far` | Compress reasoning history |
| `exec_python` | Run code over content |
| `get_variable` | Retrieve a variable from the sandbox |
| `get_status` | Session state |
| `get_evidence` | View citations |
| `finalize` | Complete with answer |

### Recursion
| Tool | Purpose |
|------|---------|
| `sub_query` | Spawn a sub-agent for a chunk |

### Persistence
| Tool | Purpose |
|------|---------|
| `save_session` | Save state to file |
| `load_session` | Resume from file |

### Remote Control
| Tool | Purpose |
|------|---------|
| `add_remote_server` | Register MCP server |
| `list_remote_servers` | List registered servers |
| `list_remote_tools` | Discover tools |
| `call_remote_tool` | Execute remote tool |
| `close_remote_server` | Disconnect |

### Action Tools (requires --enable-actions)
| Tool | Purpose |
|------|---------|
| `read_file` | Read file content |
| `write_file` | Write file content |
| `run_command` | Run a shell command |
| `run_tests` | Run test commands |

## exec_python Helpers

- `ctx`, `peek(start, end)`, `lines(start, end)`, `search(pattern)`, `chunk(size)`
- `cite(snippet, line_range, note)` for evidence
- `sub_query(prompt, context_slice)` for recursion
- Common extractors: `extract_emails()`, `extract_dates()`, `extract_urls()`, `extract_functions()`, `word_frequency()`

## Troubleshooting

- "Tool not found": MCP server not running; check `aleph` command.
- "Context not found": verify `context_id` and use `list_contexts()`.
- Search returns nothing: broaden your regex pattern.
- Running out of context: use `summarize_so_far()` to compress.
- Session file not found: check the path relative to the server working dir.
