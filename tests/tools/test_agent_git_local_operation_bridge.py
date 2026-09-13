"""v2.2.1 — Agent pre-execution bridge to safe local operation evaluator."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from tools.git_guard.agent_local_op_bridge import (
    command_to_local_op_spec,
    evaluate_agent_git_command,
    gate_agent_shell_command,
)
from tools.system.agent_git_execution_gate import (
    apply_git_local_pre_execution_gate,
    extract_shell_command,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def _commit_file(tmp_path: Path, name: str, text: str, msg: str) -> None:
    (tmp_path / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=tmp_path, check=True, capture_output=True)


def test_non_destructive_git_not_parsed():
    assert command_to_local_op_spec("git status") is None
    assert command_to_local_op_spec("git diff") is None
    assert command_to_local_op_spec("git fetch origin") is None


def test_s1_safe_restore_executes_once(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return {"ok": True}

    with mock.patch.dict("os.environ", {"AI_AGENT_GIT_LOCAL_GATE": "on"}):
        out = apply_git_local_pre_execution_gate(
            "run_command",
            {"command": "git restore a.txt"},
            execute,
            repo=tmp_path,
        )
    assert out == {"ok": True}
    assert calls["n"] == 1


def test_b1_modified_restore_blocks_executor(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("edit\n", encoding="utf-8")
    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return {"ok": True}

    with mock.patch.dict("os.environ", {"AI_AGENT_GIT_LOCAL_GATE": "on"}):
        out = apply_git_local_pre_execution_gate(
            "run_command",
            {"command": "git restore a.txt"},
            execute,
            repo=tmp_path,
        )
    assert calls["n"] == 0
    assert out.get("blocked_by_git_local_gate") is True
    assert out.get("decision") == "BLOCK"
    for key in ("operation_description", "target_description", "effect_description"):
        assert str(out.get(key) or "").strip()
    assert "a.txt" in out["target_description"]


def test_b2_reset_hard_dirty_blocks(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("dirty\n", encoding="utf-8")
    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return {"ok": True}

    with mock.patch.dict("os.environ", {"AI_AGENT_GIT_LOCAL_GATE": "on"}):
        out = apply_git_local_pre_execution_gate(
            "run_command",
            {"command": "git reset --hard HEAD"},
            execute,
            repo=tmp_path,
        )
    assert calls["n"] == 0
    assert out.get("blocked_by_git_local_gate") is True
    assert "uncommitted" in out["effect_description"].lower() or "discard" in out["effect_description"].lower()


def test_b3_clean_fd_blocks(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "junk.txt").write_text("x\n", encoding="utf-8")
    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return {"ok": True}

    with mock.patch.dict("os.environ", {"AI_AGENT_GIT_LOCAL_GATE": "on"}):
        out = apply_git_local_pre_execution_gate(
            "run_command",
            {"command": "git clean -fd"},
            execute,
            repo=tmp_path,
        )
    assert calls["n"] == 0
    assert out.get("blocked_by_git_local_gate") is True
    assert "untracked" in out["effect_description"].lower() or "delete" in out["effect_description"].lower()


def test_h1_need_human_emits_payload(tmp_path: Path):
    _init_repo(tmp_path)
    emitted = []

    def execute():
        return {"ok": True}

    with mock.patch.dict("os.environ", {"AI_AGENT_GIT_LOCAL_GATE": "on"}):
        out = apply_git_local_pre_execution_gate(
            "run_command",
            {"command": "git reset --mixed HEAD~1"},
            execute,
            repo=tmp_path,
            human_decision_emit=lambda ev: emitted.append(ev),
        )
    assert out.get("need_human_git_local_operation") is True
    assert out.get("resume_connected") is False
    for key in ("operation_description", "target_description", "effect_description"):
        assert str(out.get(key) or "").strip()
    assert len(emitted) == 1


def test_safe_ops_not_gated(tmp_path: Path):
    _init_repo(tmp_path)
    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return "ok"

    with mock.patch.dict("os.environ", {"AI_AGENT_GIT_LOCAL_GATE": "on"}):
        for cmd in ("git status", "git diff", "git log -1", "git show HEAD", "git fetch"):
            apply_git_local_pre_execution_gate(
                "run_command",
                {"command": cmd},
                execute,
                repo=tmp_path,
            )
    assert calls["n"] == 5


def test_gate_evaluator_invoked_once(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    with mock.patch(
        "tools.git_guard.agent_local_op_bridge.evaluate_agent_git_command",
        wraps=evaluate_agent_git_command,
    ) as spy:
        gate_agent_shell_command(tmp_path, "git restore a.txt", lambda: None)
    assert spy.call_count == 1


def test_extract_shell_command_keys():
    assert extract_shell_command("x", {"command": "git status"}) == "git status"
    assert extract_shell_command("run_command", {"cmd": "git diff"}) == "git diff"
