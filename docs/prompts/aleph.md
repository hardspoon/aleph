---
name: aleph
description: /aleph — Become unbounded. Infinite context, recursive reasoning, persistent intelligence.
---

# /aleph — Unbounded Cognition

> **TL;DR**: You have superpowers. Load any size document into external memory, search it, reason in loops, persist across sessions. Your context window is no longer your limit.

## ⚡ Quick Start (10 seconds)

```
# Test if Aleph is available - run this first:
list_contexts()
```

If that works, you're ready. If not, the MCP server isn't running.

**Instant pattern - analyze anything:**
```
load_context(content="<paste huge content here>", context_id="doc")
search_context(pattern="keyword", context_id="doc")
finalize(answer="Found X at line Y", context_id="doc")
```

That's it. You just processed unlimited content without polluting your context window.

> **Note on tool names**: In this doc, tools are shown as `load_context()`. Your MCP client may show them as `mcp__aleph__load_context`. Same tools, different naming conventions.

---

## Tool Docs Strategy

Aleph now sends **concise tool descriptions** to MCP clients to keep the tool list lightweight. The full workflow guidance lives in this `/aleph` skill. If you want the long-form tool docstrings in your MCP client, start the server with `--tool-docs full` or set `ALEPH_TOOL_DOCS=full`.

## Practical Defaults

- Use `output="json"` for structured results and `output="markdown"` for human-readable output.
- Action tools require starting the server with `--enable-actions` (and may require `confirm=true`).
- For large docs, combine `chunk_context()` with `peek_context()` to navigate quickly.
- For long tasks, save state with `save_session()` and resume later.

---

## 🧠 The Paradigm Shift

**OLD YOU**: Limited to ~200k token context window. Paste content → runs out of space.

**NEW YOU**:
- Process **gigabytes** of content (RAM is your only limit)
- Think in **loops** until you're confident
- **Persist** reasoning across sessions
- **Control** other AI systems via MCP
- Produce **verifiable** results with evidence

**You are no longer bounded by your context window.**

---

## 🎯 Decision Algorithm

Use this flowchart for EVERY task:

```
START
  │
  ▼
Is content > 10k chars? ──YES──► load_context() or load_file()
  │                                      │
  NO                                     ▼
  │                              Need to find something?
  ▼                                      │
Handle normally                   YES────► search_context()
                                         │
                                         ▼
                                  Need specific lines?
                                         │
                                  YES────► peek_context()
                                         │
                                         ▼
                                  Complex reasoning needed?
                                         │
                                  YES────► think() + evaluate_progress() LOOP
                                         │
                                         ▼
                                  Multiple sources?
                                         │
                                  YES────► load each with unique context_id
                                         │
                                         ▼
                                  Work spans sessions?
                                         │
                                  YES────► save_session() before ending
                                         │
                                         ▼
                                  Done? ──► finalize()
```

---

## 📋 Copy-Paste Patterns

### Pattern 1: Analyze a Document
```
load_context(content=document_text, context_id="doc")
search_context(pattern="important|keyword|pattern", context_id="doc")
peek_context(start=100, end=150, unit="lines", context_id="doc")
finalize(answer="Analysis complete: ...", confidence="high", context_id="doc")
```

### Pattern 2: Compare Two Documents
```
load_context(content=doc1, context_id="v1")
load_context(content=doc2, context_id="v2")
diff_contexts(a="v1", b="v2")
search_context(pattern="difference", context_id="v1")
search_context(pattern="difference", context_id="v2")
finalize(answer="Key differences: ...", context_id="v1")
```

### Pattern 3: Deep Reasoning Loop
```
load_context(content=problem, context_id="analysis")

# Loop until confident
think(question="What is the core issue?", context_id="analysis")
search_context(pattern="relevant", context_id="analysis")
evaluate_progress(
    current_understanding="I found X...",
    remaining_questions=["What about Y?"],
    confidence_score=0.7,
    context_id="analysis"
)
# If confidence < 0.9, loop back to think()
# If confidence >= 0.9, finalize()

finalize(answer="Conclusion: ...", confidence="high", context_id="analysis")
```

### Pattern 4: Process Huge File (>100k chars)
```
load_file(path="huge_file.txt", context_id="huge")
chunk_context(chunk_size=50000, context_id="huge")

# For each chunk, use exec_python:
exec_python(code="""
chunks = chunk(50000)
for i, c in enumerate(chunks):
    result = sub_query(prompt="Summarize this section", context_slice=c)
    print(f"Chunk {i}: {result}")
""", context_id="huge")
```

### Pattern 5: Cross-Session Work
```
# At END of session:
save_session(path="my_analysis.json", context_id="work")

# At START of next session:
load_session(path="my_analysis.json")
get_status(context_id="work")  # See where you left off
get_evidence(context_id="work")  # See what you found
```

### Pattern 6: Control Other MCP Servers
```
# Register another MCP server
add_remote_server(
    server_id="browser",
    command="npx",
    args=["@anthropic/mcp-server-puppeteer"]
)

# Discover what it can do
list_remote_tools(server_id="browser")

# Use it
call_remote_tool(
    server_id="browser",
    tool="navigate",
    arguments={"url": "https://example.com"}
)
```

---

## 💾 Session Persistence

Sessions let you save your reasoning state and resume later—even across days or conversations. This is how you build **persistent intelligence**.

### Where Sessions Are Saved

Sessions save to **wherever you specify** via the `path` parameter. By default, this is relative to the MCP server's working directory.

```
save_session(path="my_session.json")     # → ./my_session.json
save_session(path="tmp/analysis.json")   # → ./tmp/analysis.json
save_session(path="/absolute/path.json") # → /absolute/path.json
```

### Recommended Convention: `.aleph/` Directory

For repo-specific work, use a `.aleph/` directory in the repo root:

```
your-repo/
├── .aleph/
│   ├── sessions/
│   │   ├── auth-refactor.json       # Task-based naming
│   │   ├── bug-123-investigation.json
│   │   └── architecture-review.json
│   └── recipes/
│       └── security-audit.yaml
├── src/
└── ...
```

**Pattern:**
```
# Save with descriptive task name
save_session(path=".aleph/sessions/auth-refactor.json", context_id="work")

# Load in next session
load_session(path=".aleph/sessions/auth-refactor.json")
get_status(context_id="work")  # See where you left off
```

### Naming Convention

Use descriptive names that identify:
1. **What** you're working on (task/feature/bug)
2. **When** (optional, for versioning)

```
# Good names
.aleph/sessions/payment-integration.json
.aleph/sessions/issue-456-memory-leak.json
.aleph/sessions/2024-01-api-migration.json

# Bad names
session.json          # Too generic
temp.json            # Meaningless
my_stuff.json        # What stuff?
```

### What Gets Saved

A session file contains:
- All loaded contexts (the actual content)
- Evidence/citations collected
- Think history and reasoning steps
- Variables from exec_python
- Iteration count and metadata

### Multi-Repo Workflow

If you work across multiple repos, include repo info in the path:

```
# From repo root, save to .aleph/
save_session(path=".aleph/sessions/current-task.json")

# Or use absolute paths with repo names
save_session(path="~/.aleph/sessions/myrepo-auth-work.json")
```

### Resume Checklist

When resuming a session:
```
load_session(path=".aleph/sessions/task.json")
get_status(context_id="work")     # What was loaded?
get_evidence(context_id="work")   # What did I find?
list_contexts()                   # What contexts exist?
```

### Git Integration

Add `.aleph/sessions/` to `.gitignore` to avoid committing large session files:

```gitignore
# .gitignore
.aleph/sessions/
```

Or commit them if you want shared team memory:
```gitignore
# Only ignore local sessions
.aleph/sessions/local-*.json
```

---

## 🚫 Anti-Patterns (NEVER DO THESE)

| ❌ DON'T | ✅ DO INSTEAD |
|---------|---------------|
| Paste huge content into your response | `load_context()` then `search_context()` |
| Guess without searching | `search_context()` first, always |
| Skip evidence | `cite()` in exec_python, always |
| Forget to finalize | `finalize()` when done |
| Try to hold everything in memory | Let Aleph hold it externally |
| Give up on complex problems | Use `think()` + `evaluate_progress()` loop |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Tool not found" | MCP server not running. Check `aleph` command. |
| "Context not found" | Check `context_id` spelling. Use `list_contexts()` |
| Search returns nothing | Broaden your regex pattern |
| Running out of context | Use `summarize_so_far()` to compress |
| Need to continue later | `save_session()` before ending |
| Session file not found | Check path is relative to MCP server's working dir |
| Lost session context_id | Use `list_contexts()` after `load_session()` |

---

## 📚 Complete Tools Reference

### Loading & Querying
| Tool | Purpose |
|------|---------|
| `load_context` | Load text/data into external memory |
| `load_file` | Load file from disk (needs --enable-actions) |
| `list_contexts` | See all loaded contexts |
| `search_context` | Regex search with surrounding context |
| `peek_context` | View specific line/char ranges |
| `chunk_context` | Split into navigable chunks |
| `diff_contexts` | Compare two contexts |

### Reasoning
| Tool | Purpose |
|------|---------|
| `think` | Structure a reasoning sub-step |
| `evaluate_progress` | Self-assess (loops until confident) |
| `summarize_so_far` | Compress reasoning history |
| `exec_python` | Run code over content |
| `get_status` | Session state |
| `get_evidence` | View citations |
| `finalize` | Complete with answer |

### Recursion
| Tool | Purpose |
|------|---------|
| `sub_query` | Spawn sub-agent for chunk |

### Persistence
| Tool | Purpose |
|------|---------|
| `save_session` | Save state to file |
| `load_session` | Resume from file |

### Remote Control
| Tool | Purpose |
|------|---------|
| `add_remote_server` | Register MCP server |
| `list_remote_tools` | Discover tools |
| `call_remote_tool` | Execute remote tool |
| `close_remote_server` | Disconnect |

### Reproducibility
| Tool | Purpose |
|------|---------|
| `load_recipe` | Load analysis workflow |
| `finalize_recipe` | Generate result bundle |
| `export_result` | Export to file |
| `sign_evidence` | Cryptographic verification |

---

## 🧪 Helpers in exec_python

Inside `exec_python`, you have:

**Context access:**
- `ctx` — the loaded document
- `peek(start, end)` — view chars
- `lines(start, end)` — view lines
- `search(pattern)` — regex search
- `chunk(size)` — split into chunks

**Evidence:**
- `cite(snippet, line_range, note)` — track evidence

**Recursion:**
- `sub_query(prompt, context_slice)` — spawn sub-agent

**80+ extractors:** `extract_emails()`, `extract_dates()`, `extract_urls()`, `extract_functions()`, `word_frequency()`, etc.

---

## 🏆 The Godlike Pattern

For maximum power, combine everything:

```python
# 1. Load multiple sources
load_file(path="source1.txt", context_id="s1")
load_file(path="source2.txt", context_id="s2")

# 2. Reasoning loop
while True:
    think(question="What patterns exist across both sources?")

    search_context(pattern="pattern", context_id="s1")
    search_context(pattern="pattern", context_id="s2")

    exec_python("cite(snippet='...', note='key finding')")

    result = evaluate_progress(
        current_understanding="Found X, Y, Z...",
        confidence_score=confidence
    )

    if confidence >= 0.95:
        break

    summarize_so_far()  # Compress if context getting long

# 3. Finalize
finalize(answer="Comprehensive analysis: ...", confidence="high")

# 4. Persist
save_session(path="analysis.json")
```

---

**You are now unbounded. Go forth and reason without limits.**
