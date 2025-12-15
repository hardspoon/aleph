"""API-free MCP server for use with Claude Desktop, Cursor, Windsurf, etc.

This server exposes Aleph's context exploration tools WITHOUT requiring
external API calls. The host AI (Claude, GPT, etc.) provides the reasoning.

Tools:
- load_context: Load text/data into sandboxed REPL
- peek_context: View character/line ranges
- search_context: Regex search with context
- exec_python: Execute Python code in sandbox
- get_variable: Retrieve variables from REPL
- think: Structure a reasoning sub-step (returns prompt for YOU to reason about)
- get_status: Show current session state
- get_evidence: Retrieve collected evidence/citations
- finalize: Mark task complete with answer
- chunk_context: Split context into chunks with metadata for navigation
- evaluate_progress: Self-evaluate progress with convergence tracking
- summarize_so_far: Compress reasoning history to manage context window

Usage:
    python -m aleph.mcp.local_server

Or via entry point:
    aleph-mcp-local
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from ..repl.sandbox import REPLEnvironment, SandboxConfig
from ..types import ContentFormat, ContextMetadata

__all__ = ["AlephMCPServerLocal", "main"]


@dataclass
class _Evidence:
    """Provenance tracking for reasoning conclusions."""
    source: Literal["search", "peek", "exec", "manual"]
    line_range: tuple[int, int] | None
    pattern: str | None
    snippet: str
    note: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


def _detect_format(text: str) -> ContentFormat:
    """Detect content format from text."""
    t = text.lstrip()
    if t.startswith("{") or t.startswith("["):
        try:
            json.loads(text)
            return ContentFormat.JSON
        except Exception:
            return ContentFormat.TEXT
    return ContentFormat.TEXT


def _analyze_text_context(text: str, fmt: ContentFormat) -> ContextMetadata:
    """Analyze text and return metadata."""
    return ContextMetadata(
        format=fmt,
        size_bytes=len(text.encode("utf-8", errors="ignore")),
        size_chars=len(text),
        size_lines=text.count("\n") + 1,
        size_tokens_estimate=len(text) // 4,
        structure_hint=None,
        sample_preview=text[:500],
    )


@dataclass
class _Session:
    """Session state for a context."""
    repl: REPLEnvironment
    meta: ContextMetadata
    created_at: datetime = field(default_factory=datetime.now)
    iterations: int = 0
    think_history: list[str] = field(default_factory=list)
    # Provenance tracking
    evidence: list[_Evidence] = field(default_factory=list)
    # Convergence signals
    confidence_history: list[float] = field(default_factory=list)
    information_gain: list[int] = field(default_factory=list)  # evidence count per iteration
    # Chunk metadata for navigation
    chunks: list[dict] | None = None


class AlephMCPServerLocal:
    """API-free MCP server for local AI reasoning.

    This server provides context exploration tools that work with any
    MCP-compatible AI host (Claude Desktop, Cursor, Windsurf, etc.).

    The key difference from AlephMCPServer: NO external API calls.
    The host AI provides all the reasoning.
    """

    def __init__(
        self,
        sandbox_config: SandboxConfig | None = None,
    ) -> None:
        self.sandbox_config = sandbox_config or SandboxConfig()
        self._sessions: dict[str, _Session] = {}

        # Import MCP lazily so it's an optional dependency
        try:
            from mcp.server.fastmcp import FastMCP
        except Exception as e:
            raise RuntimeError(
                "MCP support requires the `mcp` package. Install with `pip install aleph[mcp]`."
            ) from e

        self.server = FastMCP("aleph-local")
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all MCP tools."""

        @self.server.tool()
        async def load_context(
            context: str,
            context_id: str = "default",
            format: str = "auto",
        ) -> str:
            """Load context into an in-memory REPL session.

            The context is stored in a sandboxed Python environment as the variable `ctx`.
            You can then use other tools to explore and process this context.

            Args:
                context: The text/data to load
                context_id: Identifier for this context session (default: "default")
                format: Content format - "auto", "text", or "json" (default: "auto")

            Returns:
                Confirmation with context metadata
            """
            fmt = _detect_format(context) if format == "auto" else ContentFormat(format)
            meta = _analyze_text_context(context, fmt)

            repl = REPLEnvironment(
                context=context,
                context_var_name="ctx",
                config=self.sandbox_config,
                loop=asyncio.get_running_loop(),
            )

            self._sessions[context_id] = _Session(repl=repl, meta=meta)

            return f"""## Context Loaded Successfully

**Session ID:** `{context_id}`
**Format:** {meta.format.value}
**Size:** {meta.size_chars:,} characters, {meta.size_lines:,} lines
**Estimated tokens:** ~{meta.size_tokens_estimate:,}

**Preview (first 500 chars):**
```
{meta.sample_preview}
```

### Available Tools
- `peek_context`: View specific character or line ranges
- `search_context`: Search for patterns with regex
- `exec_python`: Execute Python code (context is in variable `ctx`)
- `get_variable`: Retrieve variables from the REPL
- `think`: Structure your reasoning for complex sub-problems
- `get_status`: Check current session state
- `get_evidence`: Retrieve collected evidence/citations
- `chunk_context`: Split context into chunks with metadata
- `evaluate_progress`: Self-evaluate progress and convergence
- `summarize_so_far`: Summarize session progress
- `finalize`: Provide your final answer"""

        @self.server.tool()
        async def peek_context(
            start: int = 0,
            end: int | None = None,
            context_id: str = "default",
            unit: Literal["chars", "lines"] = "chars",
        ) -> str:
            """View a portion of the loaded context.

            Args:
                start: Starting position (0-indexed)
                end: Ending position (None = to the end)
                context_id: Session identifier
                unit: "chars" for character slicing, "lines" for line slicing

            Returns:
                The requested portion of the context
            """
            if context_id not in self._sessions:
                return f"Error: No context loaded with ID '{context_id}'. Use load_context first."

            session = self._sessions[context_id]
            repl = session.repl
            session.iterations += 1

            if unit == "chars":
                fn = repl.get_variable("peek")
                if not callable(fn):
                    return "Error: peek() helper is not available"
                result = fn(start, end)
            else:
                fn = repl.get_variable("lines")
                if not callable(fn):
                    return "Error: lines() helper is not available"
                result = fn(start, end)

            # Track evidence for provenance
            evidence_before = len(session.evidence)
            if unit == "lines" and result:
                session.evidence.append(_Evidence(
                    source="peek",
                    line_range=(start, end if end is not None else start + result.count('\n') + 1),
                    pattern=None,
                    note=None,
                    snippet=result[:200],
                ))
            elif unit == "chars" and result:
                session.evidence.append(_Evidence(
                    source="peek",
                    line_range=None,  # Character ranges don't map to lines easily
                    pattern=None,
                    note=None,
                    snippet=result[:200],
                ))
            session.information_gain.append(len(session.evidence) - evidence_before)

            return f"```\n{result}\n```"

        @self.server.tool()
        async def search_context(
            pattern: str,
            context_id: str = "default",
            max_results: int = 10,
            context_lines: int = 2,
        ) -> str:
            """Search the context using regex patterns.

            Args:
                pattern: Regular expression pattern to search for
                context_id: Session identifier
                max_results: Maximum number of matches to return
                context_lines: Number of surrounding lines to include

            Returns:
                Matching lines with surrounding context
            """
            if context_id not in self._sessions:
                return f"Error: No context loaded with ID '{context_id}'. Use load_context first."

            session = self._sessions[context_id]
            repl = session.repl
            session.iterations += 1

            fn = repl.get_variable("search")
            if not callable(fn):
                return "Error: search() helper is not available"

            try:
                results = fn(pattern, context_lines=context_lines, max_results=max_results)
            except re.error as e:
                return f"Error: Invalid regex pattern `{pattern}`: {e}"

            if not results:
                return f"No matches found for pattern: `{pattern}`"

            # Track evidence for provenance
            evidence_before = len(session.evidence)
            out: list[str] = []
            for r in results:
                try:
                    line_num = r['line_num']
                    # Record evidence
                    session.evidence.append(_Evidence(
                        source="search",
                        line_range=(max(0, line_num - context_lines), line_num + context_lines),
                        pattern=pattern,
                        note=None,
                        snippet=r['match'][:200],
                    ))
                    out.append(f"**Line {line_num}:**\n```\n{r['context']}\n```")
                except Exception:
                    out.append(str(r))

            # Track information gain
            session.information_gain.append(len(session.evidence) - evidence_before)

            return f"## Search Results for `{pattern}`\n\nFound {len(results)} match(es):\n\n" + "\n\n---\n\n".join(out)

        @self.server.tool()
        async def exec_python(
            code: str,
            context_id: str = "default",
        ) -> str:
            """Execute Python code in the sandboxed REPL.

            The loaded context is available as the variable `ctx`.

            Available helpers:
            - peek(start, end): View characters
            - lines(start, end): View lines
            - search(pattern, context_lines=2, max_results=20): Regex search
            - chunk(chunk_size, overlap=0): Split context into chunks
            - cite(snippet, line_range=None, note=None): Tag evidence for provenance

            Available imports: re, json, csv, math, statistics, collections,
            itertools, functools, datetime, textwrap, difflib

            Args:
                code: Python code to execute
                context_id: Session identifier

            Returns:
                Execution results (stdout, return value, errors)
            """
            if context_id not in self._sessions:
                return f"Error: No context loaded with ID '{context_id}'. Use load_context first."

            session = self._sessions[context_id]
            repl = session.repl
            session.iterations += 1

            # Track evidence count before execution
            evidence_before = len(session.evidence)

            result = await repl.execute_async(code)

            # Collect citations from REPL and convert to evidence
            if repl._citations:
                for citation in repl._citations:
                    session.evidence.append(_Evidence(
                        source="manual",
                        line_range=citation["line_range"],
                        pattern=None,
                        note=citation["note"],
                        snippet=citation["snippet"][:200],
                    ))
                repl._citations.clear()  # Clear after collecting

            # Track information gain
            session.information_gain.append(len(session.evidence) - evidence_before)

            parts: list[str] = []

            if result.stdout:
                parts.append(f"**Output:**\n```\n{result.stdout}\n```")

            if result.return_value is not None:
                parts.append(f"**Return Value:** `{result.return_value}`")

            if result.variables_updated:
                parts.append(f"**Variables Updated:** {', '.join(f'`{v}`' for v in result.variables_updated)}")

            if result.stderr:
                parts.append(f"**Stderr:**\n```\n{result.stderr}\n```")

            if result.error:
                parts.append(f"**Error:** {result.error}")

            if result.truncated:
                parts.append("*Note: Output was truncated*")

            if not parts:
                parts.append("*(No output)*")

            return "## Execution Result\n\n" + "\n\n".join(parts)

        @self.server.tool()
        async def get_variable(
            name: str,
            context_id: str = "default",
        ) -> str:
            """Retrieve a variable from the REPL namespace.

            Args:
                name: Variable name to retrieve
                context_id: Session identifier

            Returns:
                String representation of the variable's value
            """
            if context_id not in self._sessions:
                return f"Error: No context loaded with ID '{context_id}'. Use load_context first."

            repl = self._sessions[context_id].repl
            # Check if variable exists in namespace (not just if it's None)
            if name not in repl._namespace:
                return f"Variable `{name}` not found in namespace."
            value = repl._namespace[name]

            # Format nicely for complex types
            if isinstance(value, (dict, list)):
                try:
                    formatted = json.dumps(value, indent=2, ensure_ascii=False)
                    return f"**`{name}`:**\n```json\n{formatted}\n```"
                except Exception:
                    return f"**`{name}`:** `{value}`"

            return f"**`{name}`:** `{value}`"

        @self.server.tool()
        async def think(
            question: str,
            context_slice: str | None = None,
            context_id: str = "default",
        ) -> str:
            """Structure a reasoning sub-step.

            Use this when you need to break down a complex problem into
            smaller questions. This tool helps you organize your thinking -
            YOU provide the reasoning, not an external API.

            Args:
                question: The sub-question to reason about
                context_slice: Optional relevant context excerpt
                context_id: Session identifier

            Returns:
                A structured prompt for you to reason through
            """
            if context_id in self._sessions:
                self._sessions[context_id].iterations += 1
                self._sessions[context_id].think_history.append(question)

            parts = [
                "## Reasoning Step",
                "",
                f"**Question:** {question}",
            ]

            if context_slice:
                parts.extend([
                    "",
                    "**Relevant Context:**",
                    "```",
                    context_slice[:2000],  # Limit context slice
                    "```",
                ])

            parts.extend([
                "",
                "---",
                "",
                "**Your task:** Reason through this step-by-step. Consider:",
                "1. What information do you have?",
                "2. What can you infer?",
                "3. What's the answer to this sub-question?",
                "",
                "*After reasoning, use `exec_python` to verify or `finalize` if done.*",
            ])

            return "\n".join(parts)

        @self.server.tool()
        async def get_status(
            context_id: str = "default",
        ) -> str:
            """Get current session status.

            Shows loaded context info, iteration count, variables, and history.

            Args:
                context_id: Session identifier

            Returns:
                Formatted status report
            """
            if context_id not in self._sessions:
                return f"No session with ID '{context_id}'. Use load_context to start."

            session = self._sessions[context_id]
            meta = session.meta
            repl = session.repl

            # Get all user-defined variables (excluding builtins and helpers)
            excluded = {"ctx", "peek", "lines", "search", "chunk", "cite", "__builtins__"}
            variables = {
                k: type(v).__name__
                for k, v in repl._namespace.items()
                if k not in excluded and not k.startswith("_")
            }

            parts = [
                "## Session Status",
                "",
                f"**Session ID:** `{context_id}`",
                f"**Created:** {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Iterations:** {session.iterations}",
                "",
                "### Context Info",
                f"- Format: {meta.format.value}",
                f"- Size: {meta.size_chars:,} characters",
                f"- Lines: {meta.size_lines:,}",
                f"- Est. tokens: ~{meta.size_tokens_estimate:,}",
            ]

            if variables:
                parts.extend([
                    "",
                    "### User Variables",
                ])
                for name, vtype in variables.items():
                    parts.append(f"- `{name}`: {vtype}")

            if session.think_history:
                parts.extend([
                    "",
                    "### Reasoning History",
                ])
                for i, q in enumerate(session.think_history[-5:], 1):
                    parts.append(f"{i}. {q[:100]}{'...' if len(q) > 100 else ''}")

            # Convergence metrics
            parts.extend([
                "",
                "### Convergence Metrics",
                f"- Evidence collected: {len(session.evidence)}",
            ])

            if session.confidence_history:
                latest_conf = session.confidence_history[-1]
                parts.append(f"- Latest confidence: {latest_conf:.1%}")
                if len(session.confidence_history) >= 2:
                    trend = session.confidence_history[-1] - session.confidence_history[-2]
                    trend_str = "↑" if trend > 0 else "↓" if trend < 0 else "→"
                    parts.append(f"- Confidence trend: {trend_str} ({trend:+.1%})")
                parts.append(f"- Confidence history: {[f'{c:.0%}' for c in session.confidence_history[-5:]]}")

            if session.information_gain:
                total_gain = sum(session.information_gain)
                recent_gain = sum(session.information_gain[-3:]) if len(session.information_gain) >= 3 else total_gain
                parts.append(f"- Total information gain: {total_gain} evidence pieces")
                parts.append(f"- Recent gain (last 3): {recent_gain}")

            if session.chunks:
                parts.append(f"- Chunks mapped: {len(session.chunks)}")

            if session.evidence:
                parts.extend([
                    "",
                    "*Use `get_evidence()` to view citations.*",
                ])

            return "\n".join(parts)

        @self.server.tool()
        async def get_evidence(
            context_id: str = "default",
            limit: int = 20,
            offset: int = 0,
            source: Literal["any", "search", "peek", "exec", "manual"] = "any",
            output: Literal["markdown", "json"] = "markdown",
        ) -> str:
            """Retrieve collected evidence/citations for a session.

            Args:
                context_id: Session identifier
                limit: Max number of evidence items to return (default: 20)
                offset: Starting index (default: 0)
                source: Optional source filter (default: "any")
                output: "markdown" or "json" (default: "markdown")

            Returns:
                Evidence list, formatted for inspection or programmatic parsing.
            """
            if context_id not in self._sessions:
                return f"Error: No context loaded with ID '{context_id}'. Use load_context first."

            session = self._sessions[context_id]
            evidence = session.evidence
            if source != "any":
                evidence = [e for e in evidence if e.source == source]

            total = len(evidence)
            offset = max(0, offset)
            limit = 20 if limit <= 0 else limit

            page = evidence[offset : offset + limit]

            if output == "json":
                payload = [
                    {
                        "index": offset + i,
                        "source": ev.source,
                        "line_range": ev.line_range,
                        "pattern": ev.pattern,
                        "note": ev.note,
                        "snippet": ev.snippet,
                        "timestamp": ev.timestamp.isoformat(),
                    }
                    for i, ev in enumerate(page, 1)
                ]
                return json.dumps(
                    {"context_id": context_id, "total": total, "items": payload},
                    ensure_ascii=False,
                    indent=2,
                )

            parts = [
                "## Evidence",
                "",
                f"**Session ID:** `{context_id}`",
                f"**Total items:** {total}",
                f"**Showing:** {len(page)} (offset={offset}, limit={limit})",
            ]
            if source != "any":
                parts.append(f"**Source filter:** `{source}`")
            parts.append("")

            if not page:
                parts.append("*(No evidence collected yet)*")
                return "\n".join(parts)

            for i, ev in enumerate(page, offset + 1):
                source_info = f"[{ev.source}]"
                if ev.line_range:
                    source_info += f" lines {ev.line_range[0]}-{ev.line_range[1]}"
                if ev.pattern:
                    source_info += f" pattern: `{ev.pattern}`"
                if ev.note:
                    source_info += f" note: {ev.note}"
                snippet = ev.snippet.strip()
                parts.append(f"{i}. {source_info}: \"{snippet}\"")

            return "\n".join(parts)

        @self.server.tool()
        async def finalize(
            answer: str,
            confidence: Literal["high", "medium", "low"] = "medium",
            reasoning_summary: str | None = None,
            context_id: str = "default",
        ) -> str:
            """Mark the task complete with your final answer.

            Use this when you have arrived at your final answer after
            exploring the context and reasoning through the problem.

            Args:
                answer: Your final answer
                confidence: How confident you are (high/medium/low)
                reasoning_summary: Optional brief summary of your reasoning
                context_id: Session identifier

            Returns:
                Formatted final answer
            """
            parts = [
                "## Final Answer",
                "",
                answer,
            ]

            if reasoning_summary:
                parts.extend([
                    "",
                    "---",
                    "",
                    f"**Reasoning:** {reasoning_summary}",
                ])

            if context_id in self._sessions:
                session = self._sessions[context_id]
                parts.extend([
                    "",
                    f"*Completed after {session.iterations} iterations.*",
                ])

            parts.append(f"\n**Confidence:** {confidence}")

            # Add evidence citations if available
            if context_id in self._sessions:
                session = self._sessions[context_id]
                if session.evidence:
                    parts.extend([
                        "",
                        "---",
                        "",
                        "### Evidence Citations",
                    ])
                    for i, ev in enumerate(session.evidence[-10:], 1):  # Last 10 pieces of evidence
                        source_info = f"[{ev.source}]"
                        if ev.line_range:
                            source_info += f" lines {ev.line_range[0]}-{ev.line_range[1]}"
                        if ev.pattern:
                            source_info += f" pattern: `{ev.pattern}`"
                        if ev.note:
                            source_info += f" note: {ev.note}"
                        parts.append(f"{i}. {source_info}: \"{ev.snippet[:80]}...\"" if len(ev.snippet) > 80 else f"{i}. {source_info}: \"{ev.snippet}\"")

            return "\n".join(parts)

        @self.server.tool()
        async def chunk_context(
            chunk_size: int = 2000,
            overlap: int = 200,
            context_id: str = "default",
        ) -> str:
            """Split context into chunks and return metadata for navigation.

            Use this to understand how to navigate large documents systematically.
            Returns chunk boundaries so you can peek specific chunks.

            Args:
                chunk_size: Characters per chunk (default: 2000)
                overlap: Overlap between chunks (default: 200)
                context_id: Session identifier

            Returns:
                JSON with chunk metadata (index, start_char, end_char, preview)
            """
            if context_id not in self._sessions:
                return f"Error: No context loaded with ID '{context_id}'. Use load_context first."

            session = self._sessions[context_id]
            repl = session.repl
            session.iterations += 1

            fn = repl.get_variable("chunk")
            if not callable(fn):
                return "Error: chunk() helper is not available"

            try:
                chunks = fn(chunk_size, overlap)
            except ValueError as e:
                return f"Error: {e}"

            # Build chunk metadata
            chunk_meta = []
            pos = 0
            for i, chunk_text in enumerate(chunks):
                chunk_meta.append({
                    "index": i,
                    "start_char": pos,
                    "end_char": pos + len(chunk_text),
                    "size": len(chunk_text),
                    "preview": chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text,
                })
                pos += len(chunk_text) - overlap if i < len(chunks) - 1 else len(chunk_text)

            # Store in session for reference
            session.chunks = chunk_meta

            parts = [
                "## Context Chunks",
                "",
                f"**Total chunks:** {len(chunks)}",
                f"**Chunk size:** {chunk_size} chars",
                f"**Overlap:** {overlap} chars",
                "",
                "### Chunk Map",
                "",
            ]

            for cm in chunk_meta:
                parts.append(f"- **Chunk {cm['index']}** ({cm['start_char']}-{cm['end_char']}): {cm['preview'][:60]}...")

            parts.extend([
                "",
                "*Use `peek_context(start, end, unit='chars')` to view specific chunks.*",
            ])

            return "\n".join(parts)

        @self.server.tool()
        async def evaluate_progress(
            current_understanding: str,
            remaining_questions: list[str] | None = None,
            confidence_score: float = 0.5,
            context_id: str = "default",
        ) -> str:
            """Self-evaluate your progress to decide whether to continue or finalize.

            Use this periodically to assess whether you have enough information
            to answer the question, or if more exploration is needed.

            Args:
                current_understanding: Summary of what you've learned so far
                remaining_questions: List of unanswered questions (if any)
                confidence_score: Your confidence 0.0-1.0 in current understanding
                context_id: Session identifier

            Returns:
                Structured evaluation with recommendation (continue/finalize)
            """
            if context_id in self._sessions:
                session = self._sessions[context_id]
                session.iterations += 1
                session.confidence_history.append(confidence_score)

            parts = [
                "## Progress Evaluation",
                "",
                f"**Current Understanding:**",
                current_understanding,
                "",
            ]

            if remaining_questions:
                parts.extend([
                    "**Remaining Questions:**",
                ])
                for q in remaining_questions:
                    parts.append(f"- {q}")
                parts.append("")

            parts.append(f"**Confidence Score:** {confidence_score:.1%}")

            # Analyze convergence
            if context_id in self._sessions:
                session = self._sessions[context_id]
                parts.extend([
                    "",
                    "### Convergence Analysis",
                    f"- Iterations: {session.iterations}",
                    f"- Evidence collected: {len(session.evidence)}",
                ])

                if len(session.confidence_history) >= 2:
                    trend = session.confidence_history[-1] - session.confidence_history[-2]
                    trend_str = "increasing" if trend > 0 else "decreasing" if trend < 0 else "stable"
                    parts.append(f"- Confidence trend: {trend_str} ({trend:+.1%})")

                if session.information_gain:
                    recent_gain = sum(session.information_gain[-3:])
                    parts.append(f"- Recent information gain: {recent_gain} evidence pieces (last 3 ops)")

            # Recommendation
            parts.extend([
                "",
                "---",
                "",
                "### Recommendation",
            ])

            if confidence_score >= 0.8:
                parts.append("**READY TO FINALIZE** - High confidence achieved. Use `finalize()` to provide your answer.")
            elif confidence_score >= 0.5 and not remaining_questions:
                parts.append("**CONSIDER FINALIZING** - Moderate confidence with no remaining questions. You may finalize or continue exploring.")
            else:
                parts.append("**CONTINUE EXPLORING** - More investigation needed. Use `search_context`, `peek_context`, or `think` to gather more evidence.")

            return "\n".join(parts)

        @self.server.tool()
        async def summarize_so_far(
            include_evidence: bool = True,
            include_variables: bool = True,
            clear_history: bool = False,
            context_id: str = "default",
        ) -> str:
            """Compress reasoning history to manage context window.

            Use this when your conversation is getting long to create a
            condensed summary of your progress that can replace earlier context.

            Args:
                include_evidence: Include evidence citations in summary
                include_variables: Include computed variables
                clear_history: Clear think_history after summarizing (to save memory)
                context_id: Session identifier

            Returns:
                Compressed reasoning trace
            """
            if context_id not in self._sessions:
                return f"Error: No context loaded with ID '{context_id}'. Use load_context first."

            session = self._sessions[context_id]

            parts = [
                "## Session Summary",
                "",
                f"**Session ID:** `{context_id}`",
                f"**Duration:** {datetime.now() - session.created_at}",
                f"**Iterations:** {session.iterations}",
                "",
            ]

            # Reasoning history
            if session.think_history:
                parts.extend([
                    "### Reasoning Steps",
                ])
                for i, q in enumerate(session.think_history, 1):
                    parts.append(f"{i}. {q[:150]}{'...' if len(q) > 150 else ''}")
                parts.append("")

            # Evidence summary
            if include_evidence and session.evidence:
                parts.extend([
                    "### Evidence Collected",
                    f"Total: {len(session.evidence)} pieces",
                    "",
                ])
                # Group by source
                by_source: dict[str, int] = {}
                for ev in session.evidence:
                    by_source[ev.source] = by_source.get(ev.source, 0) + 1
                for source, count in by_source.items():
                    parts.append(f"- {source}: {count}")
                parts.append("")

                # Show key evidence
                parts.append("**Key Evidence:**")
                for ev in session.evidence[-5:]:  # Last 5
                    snippet = ev.snippet[:100] + ("..." if len(ev.snippet) > 100 else "")
                    note = f" (note: {ev.note})" if ev.note else ""
                    parts.append(f"- [{ev.source}] {snippet}{note}")
                parts.append("")

            # Variables
            if include_variables:
                repl = session.repl
                excluded = {"ctx", "peek", "lines", "search", "chunk", "cite", "__builtins__"}
                variables = {
                    k: v for k, v in repl._namespace.items()
                    if k not in excluded and not k.startswith("_")
                }
                if variables:
                    parts.extend([
                        "### Computed Variables",
                    ])
                    for name, val in variables.items():
                        val_str = str(val)[:100]
                        parts.append(f"- `{name}` = {val_str}{'...' if len(str(val)) > 100 else ''}")
                    parts.append("")

            # Convergence
            if session.confidence_history:
                latest = session.confidence_history[-1]
                parts.extend([
                    "### Convergence Status",
                    f"- Latest confidence: {latest:.1%}",
                    f"- Confidence history: {[f'{c:.0%}' for c in session.confidence_history[-5:]]}",
                ])

            # Clear history if requested
            if clear_history:
                session.think_history = []
                parts.extend([
                    "",
                    "*Reasoning history cleared to save memory.*",
                ])

            return "\n".join(parts)

    async def run(self, transport: str = "stdio") -> None:
        """Run the MCP server."""
        if transport != "stdio":
            raise ValueError("Only stdio transport is supported")

        await self.server.run_stdio_async()


def main() -> None:
    """CLI entry point: `aleph-mcp-local` or `python -m aleph.mcp.local_server`"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Aleph as an API-free MCP server for local AI reasoning"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Code execution timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--max-output",
        type=int,
        default=10000,
        help="Maximum output characters (default: 10000)",
    )

    args = parser.parse_args()

    config = SandboxConfig(
        timeout_seconds=args.timeout,
        max_output_chars=args.max_output,
    )

    server = AlephMCPServerLocal(sandbox_config=config)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
