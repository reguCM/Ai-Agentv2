"""G4 — git_guard vs git_governance contract (negative + scope-gap tests)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_tool.policy.git_governance_enforcement import (
    build_enforcement_matrix,
    enforcement_coverage_summary,
    hook_deployment_status,
    validate_git_governance_enforcement,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "tools" / "git_guard" / "guard.py"
PRE_PUSH_CFG = REPO_ROOT / "tools" / "git_guard" / "configs" / "ai-agent.pre-push.json"
PRE_COMMIT_CFG = REPO_ROOT / "tools" / "git_guard" / "configs" / "ai-agent.pre-commit.json"


def _run_guard(
    *,
    config: Path,
    cwd: Path,
    action: str | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(GUARD), "--config", str(config), "--json"]
    if action:
        cmd.extend(["--action", action, "--target-remote", "origin"])
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def test_contract_guard_config_alignment():
    result = validate_git_governance_enforcement()
    assert result["config_alignment_ok"] is True
    drifts = result["config_drifts"]
    assert not any(d.get("classification") == "MISSING_IN_GUARD" for d in drifts)


def test_enforcement_matrix_covers_all_contract_actions():
    matrix = build_enforcement_matrix()
    assert len(matrix) == 22
    summary = enforcement_coverage_summary(matrix)
    assert summary["actions_total"] == 22
    assert "commit" in summary["priority_unconnected"]
    assert "force_push_with_lease" in [r["action_id"] for r in matrix]


def test_push_without_hook_context_need_human():
    """Manual guard without --push-ref must not auto-allow (v2.1)."""
    proc = _run_guard(config=PRE_PUSH_CFG, cwd=REPO_ROOT, action="push")
    assert proc.returncode == 3, proc.stdout + proc.stderr


def test_force_push_guard_action_blocked():
    proc = _run_guard(config=PRE_PUSH_CFG, cwd=REPO_ROOT, action="force_push")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_force_push_with_lease_guard_action_blocked():
    proc = _run_guard(config=PRE_PUSH_CFG, cwd=REPO_ROOT, action="force_push_with_lease")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_reset_hard_guard_action_forbidden_fail():
    proc = _run_guard(config=PRE_COMMIT_CFG, cwd=REPO_ROOT, action="reset_hard")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_secret_path_denied_on_staged_env(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    subprocess.run(["git", "add", ".env"], cwd=tmp_path, check=True, capture_output=True)
    cfg = {
        "repo": ".",
        "deny_path_globs": [".env", "**/.env"],
    }
    cfg_path = tmp_path / "guard.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    proc = _run_guard(config=cfg_path, cwd=tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_remote_url_mismatch_fails(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/wrong/repo.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    cfg = {
        "repo": ".",
        "remotes": [{"name": "origin", "url_must_contain": "github.com/reguCM/Ai-Agent"}],
    }
    cfg_path = tmp_path / "guard.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    proc = _run_guard(config=cfg_path, cwd=tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_raw_cli_gap_not_marked_enforced():
    matrix = build_enforcement_matrix()
    clean = next(r for r in matrix if r["action_id"] == "clean")
    assert clean["actual_result"] == "PARTIALLY_ENFORCED"
    assert "RAW_CLI_ENFORCEMENT_GAP" in clean["gap"]


def test_hook_deployment_read_only_status():
    status = hook_deployment_status()
    assert status["deployed_doc_present"] is True
    assert status["shared_git_hooks"]["pre-push"]["auto_modify_in_g4"] is False
