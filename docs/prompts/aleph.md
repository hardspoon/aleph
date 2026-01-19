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
- Use `rg_search()` for fast repo search and `semantic_search()` for meaning-based lookup.
- `load_file()` handles PDFs, Word docs, HTML, and compressed logs (.gz/.bz2/.xz).
- Save and resume long tasks with `save_session()` and `load_session()`.
- Memory packs auto-save to `.aleph/memory_pack.json` and auto-load on startup (actions enabled).
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

### 4) Fast Repo Search (rg)
```
rg_search(pattern="TODO|FIXME", paths=["."], load_context_id="rg_hits", confirm=true)
search_context(pattern="TODO", context_id="rg_hits")
```

### 5) Semantic Search
```
semantic_search(query="login failure", context_id="doc", top_k=3)
peek_context(start=1200, end=1600, unit="chars", context_id="doc")
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

### Core Tools (always available)

**Context Management:**
| Tool | Purpose |
|------|---------|
| `load_context` | Load text/data into external memory |
| `list_contexts` | See all loaded contexts |
| `diff_contexts` | Compare two contexts |

**Search & Navigation:**
| Tool | Purpose |
|------|---------|
| `search_context` | Regex search with surrounding context |
| `semantic_search` | Meaning-based search over the context |
| `peek_context` | View specific line/char ranges |
| `chunk_context` | Split into navigable chunks |

**Reasoning & Execution:**
| Tool | Purpose |
|------|---------|
| `think` | Structure a reasoning sub-step |
| `evaluate_progress` | Self-assess and decide whether to continue |
| `summarize_so_far` | Compress reasoning history |
| `exec_python` | Run code over content (100+ built-in helpers) |
| `get_variable` | Retrieve a variable from the sandbox |
| `get_status` | Session state |
| `get_evidence` | View citations |
| `finalize` | Complete with answer |
| `tasks` | Track tasks attached to a context |
| `sub_query` | Spawn a sub-agent for a chunk |

### Action Tools (requires `--enable-actions`)

**Filesystem:**
| Tool | Purpose |
|------|---------|
| `load_file` | Load file from disk (PDFs, Word, HTML, .gz, etc.) |
| `read_file` | Read file content (raw) |
| `write_file` | Write file content |

**Shell & Search:**
| Tool | Purpose |
|------|---------|
| `run_command` | Run a shell command |
| `run_tests` | Run test commands |
| `rg_search` | Fast repo-wide search (ripgrep) |

**Persistence:**
| Tool | Purpose |
|------|---------|
| `save_session` | Save state to file (memory packs) |
| `load_session` | Resume from file |

**Remote MCP Orchestration:**
| Tool | Purpose |
|------|---------|
| `add_remote_server` | Register MCP server |
| `list_remote_servers` | List registered servers |
| `list_remote_tools` | Discover tools |
| `call_remote_tool` | Execute remote tool |
| `close_remote_server` | Disconnect |

## exec_python Helpers

**Core:**
- `ctx`, `peek(start, end)`, `lines(start, end)`, `search(pattern)`, `chunk(size)`
- `semantic_search(query, ...)` for meaning-based search
- `embed_text(text, dim)` for lightweight embeddings
- `extract_routes(lang="auto")` for route extraction
- `cite(snippet, line_range, note)` for evidence
- `sub_query(prompt, context_slice)` for recursion

**100+ built-in helpers** including:
- Extractors: `extract_emails()`, `extract_urls()`, `extract_dates()`, `extract_ips()`, `extract_functions()`
- Statistics: `word_count()`, `line_count()`, `word_frequency()`, `ngrams()`
- Line ops: `head()`, `tail()`, `grep()`, `sort_lines()`, `columns()`
- Validation: `is_email()`, `is_url()`, `is_json()`, `is_numeric()`

Extractors return `list[dict]` with keys: `value`, `line_num`, `start`, `end`.

## Troubleshooting

- "Tool not found": MCP server not running; check `aleph` command.
- "Context not found": verify `context_id` and use `list_contexts()`.
- Search returns nothing: broaden your regex pattern.
- `rg_search` slow: install ripgrep (`rg`) for best performance.
- Running out of context: use `summarize_so_far()` to compress.
- Session file not found: check the path relative to the server working dir.
