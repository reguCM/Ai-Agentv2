"""Git Guard v2.2 — destructive local operation safety."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.git_guard.guard import EXIT_FAIL, EXIT_NEED_HUMAN, EXIT_PASS
from tools.git_guard.safe_local_operation import (
    build_local_op_human_explanation,
    evaluate_local_op,
    parse_local_op_spec,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "tools" / "git_guard" / "guard.py"
LOCAL_OPS_CFG = REPO_ROOT / "tools" / "git_guard" / "configs" / "ai-agent.local-ops.json"


def _run_guard_local(cwd: Path, local_op: str, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(GUARD),
        "--config",
        str(LOCAL_OPS_CFG),
        "--json",
        "--action",
        "local_git",
        "--local-op",
        local_op,
    ]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=120)


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def _commit_file(tmp_path: Path, name: str, text: str, msg: str) -> None:
    (tmp_path / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=tmp_path, check=True, capture_output=True)


# --- restore ---


def test_r1_restore_clean_file_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    d, code, _ = evaluate_local_op(tmp_path, parse_local_op_spec("restore|a.txt"))
    assert d == "safe" and code == "SAFE_NO_CHANGES"


def test_r2_restore_modified_file_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("local edit\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(tmp_path, parse_local_op_spec("restore|a.txt"))
    assert d == "block" and code == "BLOCK_UNCOMMITTED_DATA_LOSS"
    proc = _run_guard_local(tmp_path, "restore|a.txt")
    assert proc.returncode == EXIT_FAIL


def test_r3_staged_only_unstage_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("v2\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True, capture_output=True)
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("restore|a.txt|staged=1|worktree=0")
    )
    assert d == "safe" and code == "SAFE_INDEX_ONLY"


def test_r4_restore_worktree_with_changes_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("wip\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("restore|a.txt|worktree=1")
    )
    assert d == "block"


def test_r5_restore_source_no_effective_diff_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "same\n", "init")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("restore|a.txt|source=HEAD")
    )
    assert d == "safe"


def test_r6_restore_source_overwrite_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("wip\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("restore|a.txt|source=HEAD")
    )
    assert d == "block"


def test_checkout_path_modified_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(tmp_path, parse_local_op_spec("checkout_path|a.txt"))
    assert d == "block"


# --- reset ---


def test_rs1_reset_path_unstage_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("v2\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True, capture_output=True)
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("reset|a.txt|mode=mixed|ref=HEAD")
    )
    assert d == "safe" and code == "SAFE_INDEX_ONLY"


def test_rs2_reset_hard_head_clean_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("reset||mode=hard|ref=HEAD")
    )
    assert d == "safe"


def test_rs3_reset_hard_dirty_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("dirty\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("reset||mode=hard|ref=HEAD")
    )
    assert d == "block"
    proc = _run_guard_local(tmp_path, "reset||mode=hard|ref=HEAD")
    assert proc.returncode == EXIT_FAIL


def test_rs4_reset_hard_other_commit_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "c1")
    first = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    _commit_file(tmp_path, "b.txt", "v2\n", "c2")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec(f"reset||mode=hard|ref={first}")
    )
    assert d == "block" and code == "BLOCK_HISTORY_REWRITE"


def test_rs5_reset_soft_moves_ref_need_human(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "c1")
    first = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    _commit_file(tmp_path, "b.txt", "v2\n", "c2")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec(f"reset||mode=soft|ref={first}")
    )
    assert d == "need_human"


# --- clean ---


def test_c1_clean_dry_run_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "junk.txt").write_text("x\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(tmp_path, parse_local_op_spec("clean||dry_run=1"))
    assert d == "safe" and code == "SAFE_DRY_RUN"


def test_c2_clean_nothing_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("clean||dry_run=0|force=1")
    )
    assert d == "safe"


def test_c3_clean_deletes_untracked_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "junk.txt").write_text("x\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("clean||force=1|directories=0")
    )
    assert d == "block" and code == "BLOCK_UNTRACKED_DATA_DELETE"


def test_c4_clean_deletes_directory_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "x.txt").write_text("x\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("clean||force=1|directories=1")
    )
    assert d == "block"


def test_c5_clean_ignored_block(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("tmp/\n", encoding="utf-8")
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "x.txt").write_text("x\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec("clean||force=1|directories=1|ignored=1")
    )
    assert d == "block"


# --- worktree ---


def test_w1_clean_worktree_remove_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    wt = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", str(wt), "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec(f"worktree_remove|{wt}|force=0")
    )
    assert d == "safe"


def test_w2_dirty_worktree_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    wt = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", str(wt), "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (wt / "dirty.txt").write_text("x\n", encoding="utf-8")
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec(f"worktree_remove|{wt}|force=0")
    )
    assert d == "block"


def test_w3_worktree_force_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    wt = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", str(wt), "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec(f"worktree_remove|{wt}|force=1")
    )
    assert d == "block"


def test_w4_unregistered_worktree_need_human(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    ghost = tmp_path / "not-a-worktree"
    ghost.mkdir()
    d, code, _ = evaluate_local_op(
        tmp_path, parse_local_op_spec(f"worktree_remove|{ghost}|force=0")
    )
    assert d == "need_human"


def test_guard_without_local_op_need_human(tmp_path: Path):
    _init_repo(tmp_path)
    cmd = [
        sys.executable,
        str(GUARD),
        "--config",
        str(LOCAL_OPS_CFG),
        "--json",
        "--action",
        "local_git",
    ]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert proc.returncode == EXIT_NEED_HUMAN


def _explanation_fields_nonempty(exp: dict) -> None:
    for key in ("operation_description", "target_description", "effect_description"):
        assert key in exp
        assert str(exp[key]).strip()


def _guard_local_check(payload: dict) -> dict:
    for chk in payload.get("checks") or []:
        if chk.get("name") == "local_safety":
            return chk
    raise AssertionError("local_safety check missing")


# --- Human explanation 3 fields (closure scenarios A–E) ---


def test_explain_a_modified_restore_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("local edit\n", encoding="utf-8")
    op = parse_local_op_spec("restore|a.txt")
    d, code, detail = evaluate_local_op(tmp_path, op)
    assert d == "block"
    exp = build_local_op_human_explanation(op, d, code, detail)
    _explanation_fields_nonempty(exp)
    assert "restore" in exp["operation_description"].lower()
    assert "a.txt" in exp["target_description"]
    assert "uncommitted" in exp["effect_description"].lower() or "discard" in exp["effect_description"].lower()
    proc = _run_guard_local(tmp_path, "restore|a.txt")
    chk = _guard_local_check(json.loads(proc.stdout))
    _explanation_fields_nonempty(chk)


def test_explain_b_clean_restore_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    op = parse_local_op_spec("restore|a.txt")
    d, code, detail = evaluate_local_op(tmp_path, op)
    assert d == "safe"
    exp = build_local_op_human_explanation(op, d, code, detail)
    _explanation_fields_nonempty(exp)
    assert "a.txt" in exp["target_description"]
    assert "loss" in exp["effect_description"].lower() or "no " in exp["effect_description"].lower()


def test_explain_c_reset_hard_dirty_block(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "a.txt").write_text("dirty\n", encoding="utf-8")
    op = parse_local_op_spec("reset||mode=hard|ref=HEAD")
    d, code, detail = evaluate_local_op(tmp_path, op)
    assert d == "block"
    exp = build_local_op_human_explanation(op, d, code, detail)
    _explanation_fields_nonempty(exp)
    assert "reset" in exp["operation_description"].lower()
    assert "uncommitted" in exp["effect_description"].lower() or "discard" in exp["effect_description"].lower()


def test_explain_d_clean_dry_run_safe(tmp_path: Path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "a.txt", "v1\n", "init")
    (tmp_path / "junk.txt").write_text("x\n", encoding="utf-8")
    op = parse_local_op_spec("clean||dry_run=1")
    d, code, detail = evaluate_local_op(tmp_path, op)
    assert d == "safe" and code == "SAFE_DRY_RUN"
    exp = build_local_op_human_explanation(op, d, code, detail)
    _explanation_fields_nonempty(exp)
    assert "dry" in exp["operation_description"].lower() or "dry-run" in exp["operation_description"].lower()
    assert "delet" not in exp["effect_description"].lower() or "no files" in exp["effect_description"].lower()


def test_explain_e_missing_context_need_human(tmp_path: Path):
    _init_repo(tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--config",
            str(LOCAL_OPS_CFG),
            "--json",
            "--action",
            "local_git",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == EXIT_NEED_HUMAN
    chk = _guard_local_check(json.loads(proc.stdout))
    _explanation_fields_nonempty(chk)
    assert "unknown" in chk["effect_description"].lower() or "cannot" in chk["effect_description"].lower()
