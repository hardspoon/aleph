"""Tests for workspace root detection and env overrides."""

from __future__ import annotations

from pathlib import Path

from aleph.mcp.local_server import _detect_workspace_root


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    sub = repo / "sub"
    sub.mkdir()
    return repo, sub


def test_detect_workspace_root_uses_env_override(monkeypatch, tmp_path: Path) -> None:
    """ALEPH_WORKSPACE_ROOT takes precedence over everything."""
    repo, sub = _make_repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()

    monkeypatch.chdir(other)
    monkeypatch.setenv("ALEPH_WORKSPACE_ROOT", str(repo))
    monkeypatch.delenv("PWD", raising=False)
    monkeypatch.delenv("INIT_CWD", raising=False)

    assert _detect_workspace_root() == repo


def test_detect_workspace_root_uses_pwd(monkeypatch, tmp_path: Path) -> None:
    """Without ALEPH_WORKSPACE_ROOT, uses PWD and finds git root."""
    repo, sub = _make_repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()

    monkeypatch.chdir(other)
    monkeypatch.delenv("ALEPH_WORKSPACE_ROOT", raising=False)
    monkeypatch.setenv("PWD", str(sub))
    monkeypatch.delenv("INIT_CWD", raising=False)

    assert _detect_workspace_root() == repo


def test_detect_workspace_root_uses_init_cwd(monkeypatch, tmp_path: Path) -> None:
    """Without PWD, falls back to INIT_CWD and finds git root."""
    repo, sub = _make_repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()

    monkeypatch.chdir(other)
    monkeypatch.delenv("ALEPH_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("PWD", raising=False)
    monkeypatch.setenv("INIT_CWD", str(sub))

    assert _detect_workspace_root() == repo


def test_detect_workspace_root_expands_tilde(monkeypatch, tmp_path: Path) -> None:
    """Tilde expansion works in ALEPH_WORKSPACE_ROOT."""
    home = tmp_path / "home"
    home.mkdir()
    workspace = home / "myworkspace"
    workspace.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ALEPH_WORKSPACE_ROOT", "~/myworkspace")
    monkeypatch.delenv("PWD", raising=False)
    monkeypatch.delenv("INIT_CWD", raising=False)

    assert _detect_workspace_root() == workspace


def test_detect_workspace_root_falls_back_to_cwd(monkeypatch, tmp_path: Path) -> None:
    """Without any env vars, uses cwd and finds git root."""
    repo, sub = _make_repo(tmp_path)

    monkeypatch.chdir(sub)
    monkeypatch.delenv("ALEPH_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("PWD", raising=False)
    monkeypatch.delenv("INIT_CWD", raising=False)

    assert _detect_workspace_root() == repo
