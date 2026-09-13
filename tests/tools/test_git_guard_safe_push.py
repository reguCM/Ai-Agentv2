"""Git Guard v2.1 — safe push evaluation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.git_guard.guard import EXIT_FAIL, EXIT_NEED_HUMAN, EXIT_PASS
from tools.git_guard.safe_push import GIT_ZERO_SHA, evaluate_push_ref

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "tools" / "git_guard" / "guard.py"
PRE_PUSH_CFG = REPO_ROOT / "tools" / "git_guard" / "configs" / "ai-agent.pre-push.json"


def _run_guard_push(
    cwd: Path,
    *,
    config: dict | None = None,
    config_path: Path | None = None,
    push_ref: str | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if config_path is None:
        cfg_path = cwd / "_guard_push.json"
        cfg_path.write_text(json.dumps(config or {}), encoding="utf-8")
        config_path = cfg_path
    cmd = [sys.executable, str(GUARD), "--config", str(config_path), "--json"]
    cmd.extend(["--action", "push", "--target-remote", "origin"])
    if push_ref:
        cmd.extend(["--push-ref", push_ref])
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


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/reguCM/Ai-Agent.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def _commit_file(tmp_path: Path, name: str, text: str, msg: str) -> str:
    (tmp_path / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=tmp_path, check=True, capture_output=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()


def _base_push_config() -> dict:
    return {
        "repo": ".",
        "push_safety": "v2.1",
        "remotes": [{"name": "origin", "url_must_contain": "github.com/reguCM/Ai-Agent"}],
        "forbid_actions": ["force_push", "force_push_with_lease", "reset_hard"],
        "human_gate_actions": ["force_push", "merge", "merge_ff"],
    }


def test_p1_fast_forward_safe(tmp_path: Path):
    _init_repo(tmp_path)
    base = _commit_file(tmp_path, "a.txt", "a\n", "base")
    tip = _commit_file(tmp_path, "b.txt", "b\n", "tip")
    spec = f"refs/heads/main|{tip}|refs/heads/main|{base}"
    proc = _run_guard_push(tmp_path, config=_base_push_config(), push_ref=spec)
    assert proc.returncode == EXIT_PASS, proc.stdout + proc.stderr


def test_p2_non_fast_forward_block(tmp_path: Path):
    _init_repo(tmp_path)
    a = _commit_file(tmp_path, "a.txt", "a\n", "a")
    b = _commit_file(tmp_path, "b.txt", "b\n", "b")
    # simulate remote ahead: remote at b, local tries to push a (not ancestor path)
    spec = f"refs/heads/main|{a}|refs/heads/main|{b}"
    proc = _run_guard_push(tmp_path, config=_base_push_config(), push_ref=spec)
    assert proc.returncode == EXIT_FAIL, proc.stdout + proc.stderr


def test_p3_diverged_block(tmp_path: Path):
    _init_repo(tmp_path)
    base = _commit_file(tmp_path, "base.txt", "1\n", "base")
    subprocess.run(["git", "branch", "other"], cwd=tmp_path, check=True)
    local = _commit_file(tmp_path, "local.txt", "l\n", "local")
    subprocess.run(["git", "checkout", "other"], cwd=tmp_path, check=True, capture_output=True)
    remote_tip = _commit_file(tmp_path, "remote.txt", "r\n", "remote")
    spec = f"refs/heads/main|{local}|refs/heads/main|{remote_tip}"
    proc = _run_guard_push(tmp_path, config=_base_push_config(), push_ref=spec)
    assert proc.returncode == EXIT_FAIL


def test_p4_unknown_remote_url_block(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/wrong.git"],
        cwd=tmp_path,
        check=True,
    )
    sha = "a" * 40
    spec = f"refs/heads/main|{sha}|refs/heads/main|{GIT_ZERO_SHA}"
    proc = _run_guard_push(tmp_path, config=_base_push_config(), push_ref=spec)
    assert proc.returncode == EXIT_FAIL


def test_p5_ref_delete_block(tmp_path: Path):
    _init_repo(tmp_path)
    tip = _commit_file(tmp_path, "a.txt", "a\n", "a")
    spec = f"refs/heads/main|{GIT_ZERO_SHA}|refs/heads/main|{tip}"
    proc = _run_guard_push(tmp_path, config=_base_push_config(), push_ref=spec)
    assert proc.returncode == EXIT_FAIL


def test_p6_force_push_action_still_forbid():
    proc = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--config",
            str(PRE_PUSH_CFG),
            "--action",
            "force_push",
            "--target-remote",
            "origin",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == EXIT_FAIL


def test_p7_missing_push_context_need_human(tmp_path: Path):
    _init_repo(tmp_path)
    proc = _run_guard_push(tmp_path, config=_base_push_config())
    assert proc.returncode == EXIT_NEED_HUMAN


def test_p8_new_branch_zero_remote_sha_safe(tmp_path: Path):
    _init_repo(tmp_path)
    tip = _commit_file(tmp_path, "a.txt", "a\n", "a")
    spec = f"refs/heads/dev/current|{tip}|refs/heads/dev/current|{GIT_ZERO_SHA}"
    proc = _run_guard_push(tmp_path, config=_base_push_config(), push_ref=spec)
    assert proc.returncode == EXIT_PASS


def test_p9_untracked_does_not_block_when_require_clean_false(tmp_path: Path):
    _init_repo(tmp_path)
    base = _commit_file(tmp_path, "a.txt", "a\n", "base")
    tip = _commit_file(tmp_path, "b.txt", "b\n", "tip")
    (tmp_path / "runs" / "_diag_tmp").mkdir(parents=True)
    (tmp_path / "runs" / "_diag_tmp" / "x.txt").write_text("u\n", encoding="utf-8")
    spec = f"refs/heads/main|{tip}|refs/heads/main|{base}"
    proc = _run_guard_push(tmp_path, config=_base_push_config(), push_ref=spec)
    assert proc.returncode == EXIT_PASS


def test_evaluate_push_ref_new_branch():
    decision, code, _ = evaluate_push_ref(
        ".",
        local_ref="refs/heads/x",
        local_sha="a" * 40,
        remote_ref="refs/heads/x",
        remote_sha=GIT_ZERO_SHA,
    )
    assert decision == "safe"
    assert code == "PUSH_NEW_BRANCH"


def test_pre_push_config_has_push_safety_v21():
    data = json.loads(PRE_PUSH_CFG.read_text(encoding="utf-8-sig"))
    assert data.get("push_safety") == "v2.1"
    assert "push" not in [a.lower() for a in data.get("human_gate_actions") or []]
