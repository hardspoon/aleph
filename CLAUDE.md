# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Aleph is a production-oriented implementation of **Recursive Language Models (RLMs)**. Instead of cramming context into LLM prompts, Aleph stores context in a sandboxed Python REPL (as variable `ctx`) and lets the model write code to explore and process it.

## Commands

```bash
# Install (development)
pip install -e .

# Install with optional dependencies
pip install -e '.[mcp]'      # MCP server support
pip install -e '.[yaml]'     # YAML config files
pip install -e '.[rich]'     # Better logging
pip install -e '.[openai_tokens]'  # tiktoken for token counting

# Run examples
python examples/needle_haystack.py
python examples/document_qa.py

# Run MCP server
python -m aleph.mcp.server --provider anthropic --model claude-sonnet-4-20250514
```

## Architecture

### Core Loop (`aleph/core.py`)

The `Aleph` class implements the RLM execution loop:
1. Context is stored in a sandboxed REPL namespace (`ctx`)
2. LLM receives metadata about context (format, size, preview) - not the full context
3. LLM writes Python code blocks to explore context via helper functions
4. Aleph executes code, feeds truncated output back
5. Loop continues until LLM emits `FINAL(answer)` or `FINAL_VAR(variable_name)`

### Key Components

- **`aleph/core.py`**: Main `Aleph` class, RLM loop, message handling, sub-query/sub-aleph injection
- **`aleph/types.py`**: All dataclasses and type definitions (`Budget`, `AlephResponse`, `TrajectoryStep`, `ExecutionResult`, etc.)
- **`aleph/config.py`**: `AlephConfig` for loading from env/YAML/JSON, `create_aleph()` factory
- **`aleph/repl/sandbox.py`**: `REPLEnvironment` - sandboxed code execution with AST validation
- **`aleph/repl/helpers.py`**: REPL helper functions (`peek`, `lines`, `search`, `chunk`)
- **`aleph/providers/`**: Provider implementations (`anthropic.py`, `openai.py`) following `LLMProvider` protocol
- **`aleph/prompts/system.py`**: Default system prompt template with placeholders

### Provider Protocol (`aleph/providers/base.py`)

Custom providers must implement:
- `complete()` → `tuple[response_text, input_tokens, output_tokens, cost_usd]`
- `count_tokens(text, model)` → `int`
- `get_context_limit(model)` → `int`
- `get_output_limit(model)` → `int`

### Sandbox Security

The sandbox (`aleph/repl/sandbox.py`) is best-effort, not hardened:
- AST validation blocks dunder access, forbidden builtins (`eval`, `exec`, `open`, etc.)
- Import whitelist: `re`, `json`, `csv`, `math`, `statistics`, `collections`, `itertools`, `functools`, `datetime`, `textwrap`, `difflib`
- Output truncation to prevent token explosions

### Budget System

`Budget` dataclass controls resource limits:
- `max_tokens`, `max_cost_usd`, `max_iterations`, `max_depth`, `max_wall_time_seconds`, `max_sub_queries`

`BudgetStatus` tracks consumption and is checked at each iteration.

### Sub-calls

Two recursion mechanisms available in REPL:
- `sub_query(prompt, context_slice)`: Cheaper model call for semantic sub-questions
- `sub_aleph(query, context)`: Full recursive Aleph call at depth+1

## Environment Variables

- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`: Provider API keys
- `ALEPH_PROVIDER`: "anthropic" or "openai"
- `ALEPH_MODEL`, `ALEPH_SUB_MODEL`: Model names
- `ALEPH_MAX_COST`, `ALEPH_MAX_ITERATIONS`, `ALEPH_MAX_DEPTH`: Budget limits
