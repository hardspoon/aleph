# Aleph

> *"What my eyes beheld was simultaneous, but what I shall now write down will be successive, because language is successive."*
> — Jorge Luis Borges, ["The Aleph"](https://web.mit.edu/allanmc/www/borgesaleph.pdf) (1945)

**MCP server for iterative document analysis.** Aleph stores context externally and lets the AI explore it with search, code execution, and recursive sub-queries—avoiding the limitations of context stuffing.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/aleph-rlm.svg)](https://pypi.org/project/aleph-rlm/)

## What Aleph Does

Instead of pasting an entire document into a prompt, Aleph:

1. **Stores context externally** as a variable (`ctx`) in a sandboxed Python environment
2. **Provides tools** for the AI to search, slice, and compute over the context
3. **Enables recursive sub-queries** to break large documents into chunks and analyze them independently
4. **Tracks citations** so conclusions link back to specific text ranges

This follows the [Recursive Language Model](https://arxiv.org/abs/2512.24601) (RLM) paradigm, which treats prompts as environment variables rather than context window contents.

## When to Use Aleph

| Good fit | Not the right tool |
|----------|-------------------|
| Documents >10 pages or >30k tokens | Short texts that fit easily in context |
| Need precise citations with line numbers | Simple Q&A without citation requirements |
| Analysis requiring regex/code execution | Latency-critical applications |
| Iterative exploration across turns | Single-shot queries |
| Multi-document comparison | Tasks where context stuffing works fine |

## Quick Start

```bash
pip install aleph-rlm[mcp]
aleph-rlm install        # auto-detects Claude Desktop, Cursor, Windsurf, VS Code, Codex CLI
aleph-rlm doctor         # verify installation
```

<details>
<summary>Manual MCP configuration</summary>

Add to your MCP client config (Claude Desktop, Cursor, etc.):
```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local"
    }
  }
}
```
</details>

<details>
<summary>Codex CLI configuration</summary>

Add to `~/.codex/config.toml`:
```toml
[mcp_servers.aleph]
command = "aleph-mcp-local"
args = []
```

Or run: `aleph-rlm install codex`
</details>

## For AI Assistants

If you're an AI using Aleph, see **[ALEPH.md](ALEPH.md)** for the skill guide. The key idea:

> **Don't stuff the document into your context window.** Load it into Aleph, search for what you need, cite what you find, and finalize with a grounded answer.

The skill guide covers the full process: `load_context` → `search_context` → `cite()` → `finalize`.

## How It Works

```
Document (any size)
        │
        ▼
┌──────────────────────────────────────┐
│  load_context(document)              │
│  → stores as `ctx` variable          │
│  → AI sees metadata only             │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│  Tools for exploration:              │
│  • search_context(regex)             │
│  • peek_context(start, end)          │
│  • exec_python(code)                 │
│  • sub_query(prompt, chunk)          │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│  Evidence accumulates automatically  │
│  → cite() tracks provenance          │
│  → finalize() returns answer + cites │
└──────────────────────────────────────┘
```

The AI never receives the full document in its context window. Instead, it iteratively explores with tools—similar to how a human would search and read through a long document.

## Example Session

```
User: Load this contract and find all liability exclusions

AI: [calls load_context with document]
    [calls search_context with "liabil|indemn|exclud"]
    [calls peek_context on matched sections]
    [calls finalize with structured answer]

AI: Found 3 liability exclusions:
    1. Section 4.2: Consequential damages excluded (lines 142-158)
    2. Section 7.1: Force majeure carve-out (lines 289-301)
    3. Section 9.3: Cap at contract value (lines 445-452)

    Evidence: [4 citations with line ranges]
```

## Recursive Sub-Queries

For documents too large to analyze in one pass, Aleph supports RLM-style decomposition:

```python
# Inside exec_python tool
chunks = chunk(100000)  # Split context into 100k char chunks
summaries = []

for c in chunks:
    result = sub_query("Extract key findings:", context_slice=c)
    summaries.append(result)

# Aggregate
final = sub_query(f"Synthesize these {len(summaries)} summaries:")
```

The `sub_query` tool spawns an independent sub-agent for each chunk. Backend priority:

1. **API** (if `MIMO_API_KEY` or `OPENAI_API_KEY` set) — most reliable
2. **claude CLI** (if installed) — uses existing subscription
3. **codex CLI** (if installed) — uses existing subscription
4. **aider CLI** (if installed)

Configure via environment:
```bash
# Use Mimo Flash V2 (free until Jan 20, 2026)
export MIMO_API_KEY=your_key
export OPENAI_BASE_URL=https://api.xiaomimimo.com/v1

# Or use OpenAI
export OPENAI_API_KEY=your_key
export OPENAI_BASE_URL=https://api.openai.com/v1
export ALEPH_SUB_QUERY_MODEL=gpt-4o-mini

# Or force a specific CLI backend
export ALEPH_SUB_QUERY_BACKEND=claude
```

## MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `load_context` | Load document into sandboxed REPL as `ctx` |
| `peek_context` | View character or line ranges |
| `search_context` | Regex search with surrounding context |
| `exec_python` | Run Python code against context |
| `sub_query` | Spawn sub-agent for chunk analysis |
| `chunk_context` | Split into navigable chunks with metadata |
| `think` | Structure reasoning sub-steps |
| `evaluate_progress` | Check confidence and convergence |
| `get_evidence` | Retrieve citation trail |
| `finalize` | Complete with answer and citations |

## REPL Helpers

80+ functions available inside `exec_python`:

**Navigation:** `peek`, `lines`, `search`, `chunk`

**Extraction:** `extract_emails`, `extract_urls`, `extract_money`, `extract_dates`, `extract_ips`, `extract_functions`, `extract_todos`...

**Text operations:** `grep`, `head`, `tail`, `sort_lines`, `uniq`, `word_frequency`, `ngrams`...

**Validation:** `is_email`, `is_url`, `is_json`, `is_ip`...

**Citation:** `cite(snippet, line_range, note)` — tracks evidence for provenance

<details>
<summary>Full helper list</summary>

**Extraction (16):** `extract_numbers`, `extract_money`, `extract_percentages`, `extract_dates`, `extract_times`, `extract_timestamps`, `extract_emails`, `extract_urls`, `extract_ips`, `extract_phones`, `extract_paths`, `extract_env_vars`, `extract_versions`, `extract_uuids`, `extract_hashes`, `extract_hex`

**Code analysis (6):** `extract_functions`, `extract_classes`, `extract_imports`, `extract_comments`, `extract_strings`, `extract_todos`

**Log analysis (3):** `extract_log_levels`, `extract_exceptions`, `extract_json_objects`

**Statistics (8):** `word_count`, `char_count`, `line_count`, `sentence_count`, `paragraph_count`, `unique_words`, `word_frequency`, `ngrams`

**Line operations (12):** `head`, `tail`, `grep`, `grep_v`, `grep_c`, `uniq`, `sort_lines`, `number_lines`, `strip_lines`, `blank_lines`, `non_blank_lines`, `columns`

**Text manipulation (15):** `replace_all`, `split_by`, `between`, `before`, `after`, `truncate`, `wrap_text`, `indent_text`, `dedent_text`, `normalize_whitespace`, `remove_punctuation`, `to_lower`, `to_upper`, `to_title`

**Pattern matching (6):** `contains`, `contains_any`, `contains_all`, `count_matches`, `find_all`, `first_match`

**Comparison (4):** `diff`, `similarity`, `common_lines`, `diff_lines`

**Collections (11):** `dedupe`, `flatten`, `first`, `last`, `take`, `drop`, `partition`, `group_by`, `frequency`, `sample_items`, `shuffle_items`

**Validation (7):** `is_numeric`, `is_email`, `is_url`, `is_ip`, `is_uuid`, `is_json`, `is_blank`

**Conversion (11):** `to_json`, `from_json`, `to_csv_row`, `from_csv_row`, `to_int`, `to_float`, `to_snake_case`, `to_camel_case`, `to_pascal_case`, `to_kebab_case`, `slugify`
</details>

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ALEPH_SUB_QUERY_BACKEND` | Force backend: `api`, `claude`, `codex`, `aider` | auto |
| `ALEPH_SUB_QUERY_MODEL` | Model for API backend | `mimo-v2-flash` |
| `MIMO_API_KEY` | Mimo API key | — |
| `OPENAI_API_KEY` | OpenAI-compatible API key | — |
| `OPENAI_BASE_URL` | API endpoint | `https://api.xiaomimimo.com/v1` |
| `ALEPH_MAX_ITERATIONS` | Iteration limit | 100 |

### CLI Commands

```bash
aleph-rlm install              # Interactive installer
aleph-rlm install <client>     # Install to specific client
aleph-rlm uninstall <client>   # Remove from client
aleph-rlm doctor               # Verify installation
```

Supported clients: `claude-desktop`, `cursor`, `windsurf`, `vscode`, `claude-code`, `codex`

## Security

The Python sandbox is **best-effort, not hardened**:

- **Blocked:** `open`, `os`, `subprocess`, `socket`, `eval`, `exec`, dunder access
- **Allowed imports:** `re`, `json`, `csv`, `math`, `statistics`, `collections`, `itertools`, `functools`, `datetime`, `textwrap`, `difflib`, `random`, `string`, `hashlib`, `base64`

For production with untrusted input, run Aleph in a container with resource limits.

## Research Background

Aleph implements ideas from the [Recursive Language Model](https://arxiv.org/abs/2512.24601) paper (Zhang & Khattab, 2024):

1. **Context as environment variable:** Instead of stuffing documents into prompts, treat them as external state the model can query
2. **Iterative exploration:** Models search, read, and compute incrementally rather than processing everything at once
3. **Recursive decomposition:** Large tasks break into sub-problems, each handled by independent sub-agents
4. **Task-agnostic:** The approach works for any document analysis task without task-specific prompting

Key findings from the paper:
- LLMs struggle with long contexts even within their window ("lost in the middle")
- Treating prompts as environment variables enables 10M+ token handling
- Cost is comparable to baseline when accounting for reduced errors
- Recursive sub-calls let the model decompose and aggregate effectively

## Development

```bash
git clone https://github.com/Hmbown/aleph.git
cd aleph
pip install -e '.[dev,mcp]'
pytest  # 230 tests
```

## Documentation

| Document | Purpose |
|----------|---------|
| [ALEPH.md](ALEPH.md) | **AI skill guide** — how to use Aleph properly |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Architecture and development |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | All configuration options |

## Changelog

### v0.5.0 (December 2025)
- Alephfiles/recipes with token-efficiency metrics and evidence bundles
- Remote MCP orchestration for multi-server workflows
- 230 tests passing

### v0.2.0 (December 2025)
- 80+ REPL helpers for document analysis
- Extraction, statistics, grep-like operations, validation, conversion

### v0.1.0 (December 2025)
- Initial release with core RLM loop
- MCP server implementation
- Sub-query support

## License

MIT
