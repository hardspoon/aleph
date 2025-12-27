"""Alephfile (recipe) specification and runner for reproducible analysis.

An Alephfile defines a reproducible analysis run with:
- Dataset inputs (with content hashes for verification)
- Query/task to execute
- Tool configuration
- Model settings
- Budget constraints
- Token metrics (used vs baseline)

Schema: aleph.recipe.v1
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "AlephfileSchema",
    "DatasetInput",
    "RecipeConfig",
    "RecipeResult",
    "RecipeMetrics",
    "EvidenceBundle",
    "load_alephfile",
    "save_alephfile",
    "hash_content",
]


SCHEMA_VERSION = "aleph.recipe.v1"


class AlephfileSchema(str, Enum):
    """Supported Alephfile schema versions."""
    V1 = "aleph.recipe.v1"


def hash_content(content: str | bytes, algorithm: str = "sha256") -> str:
    """Compute content hash for reproducibility verification."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    h = hashlib.new(algorithm)
    h.update(content)
    return f"{algorithm}:{h.hexdigest()}"


@dataclass(slots=True)
class DatasetInput:
    """A dataset/context input for a recipe.

    Attributes:
        id: Unique identifier for this input within the recipe
        source: Where the data comes from (inline, file, url, context_id)
        content: Inline content (if source is inline)
        path: File path (if source is file)
        url: URL (if source is url)
        context_id: Reference to loaded context (if source is context_id)
        content_hash: SHA256 hash for verification
        format: Content format hint
        size_bytes: Size in bytes
        size_tokens_estimate: Estimated token count
    """
    id: str
    source: Literal["inline", "file", "url", "context_id"]
    content: str | None = None
    path: str | None = None
    url: str | None = None
    context_id: str | None = None
    content_hash: str | None = None
    format: str = "text"
    size_bytes: int = 0
    size_tokens_estimate: int = 0

    def compute_hash(self) -> str:
        """Compute and store content hash."""
        if self.content:
            self.content_hash = hash_content(self.content)
        return self.content_hash or ""

    def verify_hash(self) -> bool:
        """Verify content matches stored hash."""
        if not self.content or not self.content_hash:
            return False
        return hash_content(self.content) == self.content_hash

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        d: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "format": self.format,
        }
        if self.content:
            d["content"] = self.content
        if self.path:
            d["path"] = self.path
        if self.url:
            d["url"] = self.url
        if self.context_id:
            d["context_id"] = self.context_id
        if self.content_hash:
            d["content_hash"] = self.content_hash
        if self.size_bytes:
            d["size_bytes"] = self.size_bytes
        if self.size_tokens_estimate:
            d["size_tokens_estimate"] = self.size_tokens_estimate
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DatasetInput":
        """Create from dictionary."""
        return cls(
            id=str(d.get("id", "default")),
            source=d.get("source", "inline"),
            content=d.get("content"),
            path=d.get("path"),
            url=d.get("url"),
            context_id=d.get("context_id"),
            content_hash=d.get("content_hash"),
            format=d.get("format", "text"),
            size_bytes=int(d.get("size_bytes", 0)),
            size_tokens_estimate=int(d.get("size_tokens_estimate", 0)),
        )


@dataclass(slots=True)
class RecipeConfig:
    """Configuration for a recipe run.

    Attributes:
        query: The analysis query/task
        datasets: List of dataset inputs
        tools_allowed: Which tools can be used (None = all)
        tools_required: Which tools must be used
        model: Model identifier
        model_version: Specific model version for reproducibility
        max_iterations: Maximum iterations allowed
        max_tokens: Maximum tokens to use
        max_cost_usd: Maximum cost in USD
        timeout_seconds: Maximum wall time
        require_evidence: Whether evidence must be collected
        require_citations: Whether citations are required in output
        privacy_filter: Regex patterns to redact from evidence
        metadata: Arbitrary metadata
    """
    query: str
    datasets: list[DatasetInput] = field(default_factory=list)
    tools_allowed: list[str] | None = None
    tools_required: list[str] | None = None
    model: str = "default"
    model_version: str | None = None
    max_iterations: int = 50
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    timeout_seconds: float = 300.0
    require_evidence: bool = True
    require_citations: bool = True
    privacy_filter: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "datasets": [d.to_dict() for d in self.datasets],
            "tools_allowed": self.tools_allowed,
            "tools_required": self.tools_required,
            "model": self.model,
            "model_version": self.model_version,
            "max_iterations": self.max_iterations,
            "max_tokens": self.max_tokens,
            "max_cost_usd": self.max_cost_usd,
            "timeout_seconds": self.timeout_seconds,
            "require_evidence": self.require_evidence,
            "require_citations": self.require_citations,
            "privacy_filter": self.privacy_filter,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RecipeConfig":
        """Create from dictionary."""
        datasets = [DatasetInput.from_dict(ds) for ds in d.get("datasets", [])]
        return cls(
            query=str(d.get("query", "")),
            datasets=datasets,
            tools_allowed=d.get("tools_allowed"),
            tools_required=d.get("tools_required"),
            model=d.get("model", "default"),
            model_version=d.get("model_version"),
            max_iterations=int(d.get("max_iterations", 50)),
            max_tokens=d.get("max_tokens"),
            max_cost_usd=d.get("max_cost_usd"),
            timeout_seconds=float(d.get("timeout_seconds", 300.0)),
            require_evidence=bool(d.get("require_evidence", True)),
            require_citations=bool(d.get("require_citations", True)),
            privacy_filter=d.get("privacy_filter"),
            metadata=d.get("metadata", {}),
        )


@dataclass(slots=True)
class RecipeMetrics:
    """Token and efficiency metrics for a recipe run.

    Attributes:
        tokens_used: Actual tokens consumed
        tokens_baseline: Estimated tokens if using context-stuffing approach
        tokens_saved: tokens_baseline - tokens_used
        efficiency_ratio: tokens_saved / tokens_baseline (0-1)
        iterations: Number of iterations
        evidence_count: Number of evidence pieces collected
        wall_time_seconds: Total execution time
        cost_usd: Total cost
    """
    tokens_used: int = 0
    tokens_baseline: int = 0
    tokens_saved: int = 0
    efficiency_ratio: float = 0.0
    iterations: int = 0
    evidence_count: int = 0
    wall_time_seconds: float = 0.0
    cost_usd: float = 0.0

    def compute_efficiency(self) -> None:
        """Compute tokens_saved and efficiency_ratio from tokens_used and tokens_baseline."""
        self.tokens_saved = max(0, self.tokens_baseline - self.tokens_used)
        if self.tokens_baseline > 0:
            self.efficiency_ratio = self.tokens_saved / self.tokens_baseline
        else:
            self.efficiency_ratio = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tokens_used": self.tokens_used,
            "tokens_baseline": self.tokens_baseline,
            "tokens_saved": self.tokens_saved,
            "efficiency_ratio": round(self.efficiency_ratio, 4),
            "iterations": self.iterations,
            "evidence_count": self.evidence_count,
            "wall_time_seconds": round(self.wall_time_seconds, 3),
            "cost_usd": round(self.cost_usd, 6),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RecipeMetrics":
        """Create from dictionary."""
        return cls(
            tokens_used=int(d.get("tokens_used", 0)),
            tokens_baseline=int(d.get("tokens_baseline", 0)),
            tokens_saved=int(d.get("tokens_saved", 0)),
            efficiency_ratio=float(d.get("efficiency_ratio", 0.0)),
            iterations=int(d.get("iterations", 0)),
            evidence_count=int(d.get("evidence_count", 0)),
            wall_time_seconds=float(d.get("wall_time_seconds", 0.0)),
            cost_usd=float(d.get("cost_usd", 0.0)),
        )


@dataclass(slots=True)
class EvidenceItem:
    """A single piece of evidence in the bundle."""
    source: str
    line_range: tuple[int, int] | None
    pattern: str | None
    snippet: str
    note: str | None
    timestamp: str
    dataset_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source,
            "line_range": list(self.line_range) if self.line_range else None,
            "pattern": self.pattern,
            "snippet": self.snippet,
            "note": self.note,
            "timestamp": self.timestamp,
            "dataset_id": self.dataset_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvidenceItem":
        """Create from dictionary."""
        lr = d.get("line_range")
        line_range = tuple(lr) if lr and len(lr) == 2 else None
        return cls(
            source=d.get("source", "manual"),
            line_range=line_range,  # type: ignore
            pattern=d.get("pattern"),
            snippet=d.get("snippet", ""),
            note=d.get("note"),
            timestamp=d.get("timestamp", ""),
            dataset_id=d.get("dataset_id"),
        )


@dataclass(slots=True)
class EvidenceBundle:
    """A signed bundle of evidence from a recipe run.

    Attributes:
        schema: Schema version
        recipe_hash: Hash of the recipe config for verification
        evidence: List of evidence items
        signature: Cryptographic signature (optional, for signed bundles)
        signed_at: Timestamp of signing
        signed_by: Identity that signed (optional)
    """
    schema: str = SCHEMA_VERSION
    recipe_hash: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)
    signature: str | None = None
    signed_at: str | None = None
    signed_by: str | None = None

    def compute_hash(self) -> str:
        """Compute hash of the evidence bundle content."""
        content = json.dumps(
            {"evidence": [e.to_dict() for e in self.evidence]},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hash_content(content)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "schema": self.schema,
            "recipe_hash": self.recipe_hash,
            "evidence": [e.to_dict() for e in self.evidence],
            "signature": self.signature,
            "signed_at": self.signed_at,
            "signed_by": self.signed_by,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvidenceBundle":
        """Create from dictionary."""
        evidence = [EvidenceItem.from_dict(e) for e in d.get("evidence", [])]
        return cls(
            schema=d.get("schema", SCHEMA_VERSION),
            recipe_hash=d.get("recipe_hash", ""),
            evidence=evidence,
            signature=d.get("signature"),
            signed_at=d.get("signed_at"),
            signed_by=d.get("signed_by"),
        )


@dataclass(slots=True)
class RecipeResult:
    """Complete result of running a recipe.

    This is the reproducible output that captures everything about the run.
    """
    schema: str = SCHEMA_VERSION
    recipe: RecipeConfig | None = None
    recipe_hash: str = ""

    # Result
    answer: str = ""
    success: bool = False
    error: str | None = None

    # Metrics
    metrics: RecipeMetrics = field(default_factory=RecipeMetrics)

    # Evidence
    evidence_bundle: EvidenceBundle = field(default_factory=EvidenceBundle)

    # Timestamps
    started_at: str = ""
    completed_at: str = ""

    # Execution trace (tool calls, for full reproducibility)
    trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "schema": self.schema,
            "recipe": self.recipe.to_dict() if self.recipe else None,
            "recipe_hash": self.recipe_hash,
            "answer": self.answer,
            "success": self.success,
            "error": self.error,
            "metrics": self.metrics.to_dict(),
            "evidence_bundle": self.evidence_bundle.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "trace": self.trace,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RecipeResult":
        """Create from dictionary."""
        recipe = RecipeConfig.from_dict(d["recipe"]) if d.get("recipe") else None
        return cls(
            schema=d.get("schema", SCHEMA_VERSION),
            recipe=recipe,
            recipe_hash=d.get("recipe_hash", ""),
            answer=d.get("answer", ""),
            success=d.get("success", False),
            error=d.get("error"),
            metrics=RecipeMetrics.from_dict(d.get("metrics", {})),
            evidence_bundle=EvidenceBundle.from_dict(d.get("evidence_bundle", {})),
            started_at=d.get("started_at", ""),
            completed_at=d.get("completed_at", ""),
            trace=d.get("trace", []),
        )


def load_alephfile(path: str | Path) -> RecipeConfig:
    """Load a recipe from an Alephfile (JSON or YAML).

    Args:
        path: Path to the Alephfile

    Returns:
        Parsed RecipeConfig

    Raises:
        ValueError: If the file format is invalid
        FileNotFoundError: If the file doesn't exist
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Alephfile not found: {path}")

    content = p.read_text(encoding="utf-8")

    # Try YAML first (if available), then JSON
    data: dict[str, Any] | None = None

    if p.suffix in {".yaml", ".yml"}:
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            raise ValueError("YAML support requires PyYAML. Install with: pip install PyYAML")
    else:
        # Assume JSON
        data = json.loads(content)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid Alephfile format: expected object, got {type(data).__name__}")

    # Validate schema version
    schema = data.get("schema", SCHEMA_VERSION)
    if schema not in {s.value for s in AlephfileSchema}:
        raise ValueError(f"Unknown schema version: {schema}")

    return RecipeConfig.from_dict(data)


def save_alephfile(config: RecipeConfig, path: str | Path, format: Literal["json", "yaml"] = "json") -> None:
    """Save a recipe to an Alephfile.

    Args:
        config: Recipe configuration to save
        path: Output path
        format: Output format (json or yaml)
    """
    p = Path(path)

    data = {
        "schema": SCHEMA_VERSION,
        **config.to_dict(),
    }

    if format == "yaml":
        try:
            import yaml
            content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        except ImportError:
            raise ValueError("YAML support requires PyYAML. Install with: pip install PyYAML")
    else:
        content = json.dumps(data, indent=2, ensure_ascii=False)

    p.write_text(content, encoding="utf-8")


def compute_baseline_tokens(datasets: list[DatasetInput]) -> int:
    """Compute baseline token estimate for context-stuffing approach.

    This estimates how many tokens would be needed if the entire context
    was stuffed into the prompt (the "naive" approach Aleph improves upon).

    The baseline is:
    - All dataset content loaded into context
    - Multiplied by estimated iterations (assume 3 for simple queries)
    - Plus overhead for system prompts, etc.
    """
    total_tokens = sum(d.size_tokens_estimate for d in datasets)

    # Baseline approach would re-send context each turn
    # Estimate 3 turns for a simple query
    estimated_turns = 3

    # Add overhead for system prompt, user message, assistant response
    overhead_per_turn = 500

    return (total_tokens * estimated_turns) + (overhead_per_turn * estimated_turns)


class RecipeRunner:
    """Runs an Alephfile recipe and produces a reproducible result.

    This class coordinates:
    1. Loading and verifying datasets
    2. Setting up the execution environment
    3. Running the query with tool access
    4. Collecting evidence and metrics
    5. Producing the final result bundle
    """

    def __init__(self, config: RecipeConfig) -> None:
        self.config = config
        self.started_at: datetime | None = None
        self.metrics = RecipeMetrics()
        self.evidence: list[EvidenceItem] = []
        self.trace: list[dict[str, Any]] = []

    def compute_recipe_hash(self) -> str:
        """Compute hash of the recipe configuration."""
        content = json.dumps(self.config.to_dict(), sort_keys=True, ensure_ascii=False)
        return hash_content(content)

    def load_datasets(self) -> dict[str, str]:
        """Load all datasets and return id -> content mapping.

        Also computes baseline token estimate.
        """
        loaded: dict[str, str] = {}

        for ds in self.config.datasets:
            content: str | None = None

            if ds.source == "inline":
                content = ds.content or ""
            elif ds.source == "file":
                if ds.path:
                    p = Path(ds.path)
                    if p.exists():
                        content = p.read_text(encoding="utf-8")
                    else:
                        raise FileNotFoundError(f"Dataset file not found: {ds.path}")
            elif ds.source == "url":
                # URL loading would require httpx, defer to caller
                raise NotImplementedError("URL dataset loading not yet implemented")
            elif ds.source == "context_id":
                # Reference to already-loaded context, handled by caller
                pass

            if content is not None:
                loaded[ds.id] = content
                ds.content = content
                ds.size_bytes = len(content.encode("utf-8"))
                ds.size_tokens_estimate = len(content) // 4
                ds.compute_hash()

        # Compute baseline
        self.metrics.tokens_baseline = compute_baseline_tokens(self.config.datasets)

        return loaded

    def verify_datasets(self) -> list[str]:
        """Verify all dataset hashes match.

        Returns list of dataset IDs that failed verification.
        """
        failures: list[str] = []
        for ds in self.config.datasets:
            if ds.content_hash and ds.content:
                if not ds.verify_hash():
                    failures.append(ds.id)
        return failures

    def record_trace(self, tool: str, args: dict[str, Any], result: Any) -> None:
        """Record a tool call in the execution trace."""
        self.trace.append({
            "timestamp": datetime.now().isoformat(),
            "tool": tool,
            "args": args,
            "result_preview": str(result)[:500] if result else None,
        })

    def add_evidence(
        self,
        source: str,
        snippet: str,
        line_range: tuple[int, int] | None = None,
        pattern: str | None = None,
        note: str | None = None,
        dataset_id: str | None = None,
    ) -> None:
        """Add an evidence item."""
        self.evidence.append(EvidenceItem(
            source=source,
            line_range=line_range,
            pattern=pattern,
            snippet=snippet[:500],  # Truncate for storage
            note=note,
            timestamp=datetime.now().isoformat(),
            dataset_id=dataset_id,
        ))
        self.metrics.evidence_count = len(self.evidence)

    def apply_privacy_filter(self, text: str) -> str:
        """Apply privacy filters to redact sensitive content."""
        if not self.config.privacy_filter:
            return text

        import re
        result = text
        for pattern in self.config.privacy_filter:
            try:
                result = re.sub(pattern, "[REDACTED]", result)
            except re.error:
                pass  # Skip invalid patterns
        return result

    def finalize(self, answer: str, success: bool = True, error: str | None = None) -> RecipeResult:
        """Finalize the run and produce the result bundle."""
        completed_at = datetime.now()

        if self.started_at:
            self.metrics.wall_time_seconds = (completed_at - self.started_at).total_seconds()

        # Compute efficiency
        self.metrics.compute_efficiency()

        # Apply privacy filter to evidence
        filtered_evidence = []
        for ev in self.evidence:
            filtered_ev = EvidenceItem(
                source=ev.source,
                line_range=ev.line_range,
                pattern=ev.pattern,
                snippet=self.apply_privacy_filter(ev.snippet),
                note=ev.note,
                timestamp=ev.timestamp,
                dataset_id=ev.dataset_id,
            )
            filtered_evidence.append(filtered_ev)

        # Build evidence bundle
        bundle = EvidenceBundle(
            recipe_hash=self.compute_recipe_hash(),
            evidence=filtered_evidence,
        )

        return RecipeResult(
            recipe=self.config,
            recipe_hash=self.compute_recipe_hash(),
            answer=self.apply_privacy_filter(answer),
            success=success,
            error=error,
            metrics=self.metrics,
            evidence_bundle=bundle,
            started_at=self.started_at.isoformat() if self.started_at else "",
            completed_at=completed_at.isoformat(),
            trace=self.trace,
        )

    def start(self) -> None:
        """Mark the run as started."""
        self.started_at = datetime.now()

    def update_tokens(self, tokens_used: int, cost_usd: float = 0.0) -> None:
        """Update token metrics."""
        self.metrics.tokens_used += tokens_used
        self.metrics.cost_usd += cost_usd

    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.metrics.iterations += 1
