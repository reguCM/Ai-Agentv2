import json
from pathlib import Path

import pytest

from tools.ai.sandbox_workspace import (
    SANDBOX_PARENT_ENV,
    SandboxIdentityError,
    resolve_configured_sandbox_parent,
)

V2_SANDBOX_RELATIVE = "Ai-Agent_v2-worktrees/sandboxes"


def test_env_override_wins_over_config(tmp_path, monkeypatch):
    cfg = tmp_path / "sandbox_workspace.json"
    cfg.write_text(
        json.dumps({"sandbox_parent": V2_SANDBOX_RELATIVE, "relative_to": "volume_root"}),
        encoding="utf-8",
    )
    override = tmp_path / "from-env"
    monkeypatch.setenv(SANDBOX_PARENT_ENV, str(override))
    resolved = resolve_configured_sandbox_parent(
        tmp_path / "dev",
        config_path=cfg,
        environ={SANDBOX_PARENT_ENV: str(override)},
    )
    assert resolved == override.resolve()


def test_absolute_config_path_is_used(tmp_path):
    parent = tmp_path / "sandboxes"
    cfg = tmp_path / "sandbox_workspace.json"
    cfg.write_text(json.dumps({"sandbox_parent": str(parent)}), encoding="utf-8")
    resolved = resolve_configured_sandbox_parent(
        tmp_path / "dev",
        config_path=cfg,
        environ={},
    )
    assert resolved == parent.resolve()


def test_volume_root_relative_config_uses_worktree_drive(tmp_path):
    cfg = tmp_path / "sandbox_workspace.json"
    cfg.write_text(
        json.dumps(
            {
                "sandbox_parent": V2_SANDBOX_RELATIVE,
                "relative_to": "volume_root",
            }
        ),
        encoding="utf-8",
    )
    worktree = tmp_path / "current-dev"
    worktree.mkdir()
    resolved = resolve_configured_sandbox_parent(
        worktree,
        config_path=cfg,
        environ={},
    )
    assert resolved == (
        Path(worktree.resolve().anchor) / "Ai-Agent_v2-worktrees" / "sandboxes"
    ).resolve()


def test_missing_config_fails_closed(tmp_path):
    with pytest.raises(SandboxIdentityError, match="unreadable"):
        resolve_configured_sandbox_parent(
            tmp_path,
            config_path=tmp_path / "missing.json",
            environ={},
        )


def test_repo_config_points_at_v2_worktrees_sandboxes():
    resolved = resolve_configured_sandbox_parent(
        Path(r"D:\Ai-Agent_v2"),
        environ={},
    )
    assert resolved == Path(r"D:\Ai-Agent_v2-worktrees\sandboxes")
