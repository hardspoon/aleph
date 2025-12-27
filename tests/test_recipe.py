"""Tests for the recipe/Alephfile module."""

import json
import tempfile
from pathlib import Path

import pytest

from aleph.recipe import (
    AlephfileSchema,
    DatasetInput,
    EvidenceBundle,
    EvidenceItem,
    RecipeConfig,
    RecipeMetrics,
    RecipeResult,
    RecipeRunner,
    SCHEMA_VERSION,
    compute_baseline_tokens,
    hash_content,
    load_alephfile,
    save_alephfile,
)


class TestHashContent:
    """Tests for hash_content function."""

    def test_hash_string(self):
        """Hash a string."""
        h = hash_content("hello world")
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64  # "sha256:" + 64 hex chars

    def test_hash_bytes(self):
        """Hash bytes."""
        h = hash_content(b"hello world")
        assert h.startswith("sha256:")

    def test_hash_deterministic(self):
        """Same content produces same hash."""
        h1 = hash_content("test content")
        h2 = hash_content("test content")
        assert h1 == h2

    def test_hash_different_content(self):
        """Different content produces different hash."""
        h1 = hash_content("content a")
        h2 = hash_content("content b")
        assert h1 != h2


class TestDatasetInput:
    """Tests for DatasetInput dataclass."""

    def test_create_inline(self):
        """Create inline dataset."""
        ds = DatasetInput(
            id="test",
            source="inline",
            content="hello world",
        )
        assert ds.id == "test"
        assert ds.source == "inline"
        assert ds.content == "hello world"

    def test_compute_hash(self):
        """Compute and store content hash."""
        ds = DatasetInput(id="test", source="inline", content="hello")
        h = ds.compute_hash()
        assert h.startswith("sha256:")
        assert ds.content_hash == h

    def test_verify_hash_success(self):
        """Verify hash matches."""
        ds = DatasetInput(id="test", source="inline", content="hello")
        ds.compute_hash()
        assert ds.verify_hash() is True

    def test_verify_hash_failure(self):
        """Verify hash fails when content changed."""
        ds = DatasetInput(id="test", source="inline", content="hello")
        ds.compute_hash()
        ds.content = "modified"
        assert ds.verify_hash() is False

    def test_to_dict(self):
        """Convert to dictionary."""
        ds = DatasetInput(
            id="test",
            source="inline",
            content="hello",
            format="text",
        )
        d = ds.to_dict()
        assert d["id"] == "test"
        assert d["source"] == "inline"
        assert d["content"] == "hello"

    def test_from_dict(self):
        """Create from dictionary."""
        d = {"id": "test", "source": "file", "path": "/tmp/test.txt"}
        ds = DatasetInput.from_dict(d)
        assert ds.id == "test"
        assert ds.source == "file"
        assert ds.path == "/tmp/test.txt"


class TestRecipeConfig:
    """Tests for RecipeConfig dataclass."""

    def test_create_minimal(self):
        """Create minimal config."""
        config = RecipeConfig(query="Find errors")
        assert config.query == "Find errors"
        assert config.datasets == []
        assert config.max_iterations == 50

    def test_create_full(self):
        """Create full config."""
        ds = DatasetInput(id="main", source="inline", content="test")
        config = RecipeConfig(
            query="Analyze code",
            datasets=[ds],
            model="claude-3-opus",
            max_iterations=10,
            timeout_seconds=60.0,
        )
        assert len(config.datasets) == 1
        assert config.model == "claude-3-opus"
        assert config.max_iterations == 10

    def test_to_dict(self):
        """Convert to dictionary."""
        config = RecipeConfig(
            query="Test query",
            privacy_filter=["email@.*"],
        )
        d = config.to_dict()
        assert d["query"] == "Test query"
        assert d["privacy_filter"] == ["email@.*"]

    def test_from_dict(self):
        """Create from dictionary."""
        d = {
            "query": "Find bugs",
            "datasets": [{"id": "src", "source": "inline", "content": "code"}],
            "max_iterations": 25,
        }
        config = RecipeConfig.from_dict(d)
        assert config.query == "Find bugs"
        assert len(config.datasets) == 1
        assert config.max_iterations == 25


class TestRecipeMetrics:
    """Tests for RecipeMetrics dataclass."""

    def test_compute_efficiency(self):
        """Compute efficiency ratio."""
        metrics = RecipeMetrics(
            tokens_used=1000,
            tokens_baseline=10000,
        )
        metrics.compute_efficiency()
        assert metrics.tokens_saved == 9000
        assert metrics.efficiency_ratio == 0.9

    def test_compute_efficiency_zero_baseline(self):
        """Handle zero baseline."""
        metrics = RecipeMetrics(tokens_used=100, tokens_baseline=0)
        metrics.compute_efficiency()
        assert metrics.efficiency_ratio == 0.0

    def test_to_dict(self):
        """Convert to dictionary."""
        metrics = RecipeMetrics(tokens_used=500, iterations=5)
        d = metrics.to_dict()
        assert d["tokens_used"] == 500
        assert d["iterations"] == 5


class TestEvidenceBundle:
    """Tests for EvidenceBundle dataclass."""

    def test_create_empty(self):
        """Create empty bundle."""
        bundle = EvidenceBundle()
        assert bundle.schema == SCHEMA_VERSION
        assert bundle.evidence == []

    def test_add_evidence(self):
        """Add evidence items."""
        bundle = EvidenceBundle()
        item = EvidenceItem(
            source="search",
            line_range=(10, 20),
            pattern="error",
            snippet="found error",
            note="Important",
            timestamp="2024-01-01T00:00:00",
        )
        bundle.evidence.append(item)
        assert len(bundle.evidence) == 1

    def test_compute_hash(self):
        """Compute bundle hash."""
        bundle = EvidenceBundle()
        bundle.evidence.append(EvidenceItem(
            source="search",
            line_range=None,
            pattern=None,
            snippet="test",
            note=None,
            timestamp="2024-01-01",
        ))
        h = bundle.compute_hash()
        assert h.startswith("sha256:")

    def test_hash_deterministic(self):
        """Same evidence produces same hash."""
        b1 = EvidenceBundle()
        b1.evidence.append(EvidenceItem(
            source="search", line_range=None, pattern=None,
            snippet="test", note=None, timestamp="2024-01-01",
        ))

        b2 = EvidenceBundle()
        b2.evidence.append(EvidenceItem(
            source="search", line_range=None, pattern=None,
            snippet="test", note=None, timestamp="2024-01-01",
        ))

        assert b1.compute_hash() == b2.compute_hash()


class TestRecipeRunner:
    """Tests for RecipeRunner class."""

    def test_create(self):
        """Create runner."""
        config = RecipeConfig(query="Test")
        runner = RecipeRunner(config)
        assert runner.config == config
        assert runner.metrics.tokens_used == 0

    def test_start(self):
        """Start run."""
        config = RecipeConfig(query="Test")
        runner = RecipeRunner(config)
        runner.start()
        assert runner.started_at is not None

    def test_load_inline_datasets(self):
        """Load inline datasets."""
        ds = DatasetInput(id="main", source="inline", content="hello world")
        config = RecipeConfig(query="Test", datasets=[ds])
        runner = RecipeRunner(config)
        loaded = runner.load_datasets()
        assert "main" in loaded
        assert loaded["main"] == "hello world"
        assert ds.content_hash is not None
        assert runner.metrics.tokens_baseline > 0

    def test_verify_datasets(self):
        """Verify dataset hashes."""
        ds = DatasetInput(id="main", source="inline", content="hello")
        config = RecipeConfig(query="Test", datasets=[ds])
        runner = RecipeRunner(config)
        runner.load_datasets()
        failures = runner.verify_datasets()
        assert failures == []

    def test_add_evidence(self):
        """Add evidence."""
        config = RecipeConfig(query="Test")
        runner = RecipeRunner(config)
        runner.add_evidence(
            source="search",
            snippet="found something",
            line_range=(1, 5),
        )
        assert len(runner.evidence) == 1
        assert runner.metrics.evidence_count == 1

    def test_privacy_filter(self):
        """Apply privacy filter."""
        config = RecipeConfig(
            query="Test",
            privacy_filter=[r"\b\d{4}-\d{4}\b"],  # Credit card pattern
        )
        runner = RecipeRunner(config)
        filtered = runner.apply_privacy_filter("Card: 1234-5678")
        assert "[REDACTED]" in filtered
        assert "1234-5678" not in filtered

    def test_finalize(self):
        """Finalize run."""
        ds = DatasetInput(id="main", source="inline", content="test content")
        config = RecipeConfig(query="Test", datasets=[ds])
        runner = RecipeRunner(config)
        runner.start()
        runner.load_datasets()
        runner.add_evidence(source="search", snippet="found")
        result = runner.finalize("The answer is 42")

        assert result.success is True
        assert result.answer == "The answer is 42"
        assert result.metrics.wall_time_seconds >= 0
        assert len(result.evidence_bundle.evidence) == 1

    def test_recipe_hash(self):
        """Compute recipe hash."""
        config = RecipeConfig(query="Test")
        runner = RecipeRunner(config)
        h = runner.compute_recipe_hash()
        assert h.startswith("sha256:")


class TestAlephfileIO:
    """Tests for loading and saving Alephfiles."""

    def test_save_load_json(self):
        """Save and load JSON Alephfile."""
        config = RecipeConfig(
            query="Find errors",
            datasets=[DatasetInput(id="src", source="inline", content="code")],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recipe.json"
            save_alephfile(config, path, format="json")

            loaded = load_alephfile(path)
            assert loaded.query == config.query
            assert len(loaded.datasets) == 1

    def test_load_nonexistent(self):
        """Load nonexistent file."""
        with pytest.raises(FileNotFoundError):
            load_alephfile("/nonexistent/path.json")

    def test_load_invalid_json(self):
        """Load invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.json"
            path.write_text("not json")

            with pytest.raises(Exception):
                load_alephfile(path)


class TestComputeBaselineTokens:
    """Tests for baseline token computation."""

    def test_empty_datasets(self):
        """Empty datasets."""
        baseline = compute_baseline_tokens([])
        assert baseline == 1500  # Just overhead (500 * 3 turns)

    def test_single_dataset(self):
        """Single dataset."""
        ds = DatasetInput(id="main", source="inline")
        ds.size_tokens_estimate = 1000
        baseline = compute_baseline_tokens([ds])
        # 1000 tokens * 3 turns + 500 overhead * 3 turns
        assert baseline == 4500

    def test_multiple_datasets(self):
        """Multiple datasets."""
        ds1 = DatasetInput(id="a", source="inline")
        ds1.size_tokens_estimate = 500
        ds2 = DatasetInput(id="b", source="inline")
        ds2.size_tokens_estimate = 500
        baseline = compute_baseline_tokens([ds1, ds2])
        # (500 + 500) * 3 + 500 * 3 = 4500
        assert baseline == 4500


class TestRecipeResult:
    """Tests for RecipeResult dataclass."""

    def test_to_dict(self):
        """Convert result to dict."""
        result = RecipeResult(
            answer="Test answer",
            success=True,
        )
        d = result.to_dict()
        assert d["answer"] == "Test answer"
        assert d["success"] is True
        assert d["schema"] == SCHEMA_VERSION

    def test_from_dict(self):
        """Create result from dict."""
        d = {
            "schema": SCHEMA_VERSION,
            "answer": "Answer",
            "success": True,
            "metrics": {"tokens_used": 100},
            "evidence_bundle": {"evidence": []},
        }
        result = RecipeResult.from_dict(d)
        assert result.answer == "Answer"
        assert result.success is True
        assert result.metrics.tokens_used == 100
