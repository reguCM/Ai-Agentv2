"""
Phase D-1a: Git workspace facts（機械観測のみ）。

「リポジトリ内」「Git がある」だけでは安全・可逆と推定しない。
targets_covered と restore mechanism を分離して記録する。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

UNKNOWN = "unknown"

_PATH_HINT = re.compile(
    r"(?i)(?:[a-z]:[\\/][^\s\"']+|(?:\.{0,2}[\\/])[^\s\"']+\.[a-z0-9]{1,8})"
)


def _run_git(args: list[str], *, cwd: str | None, timeout: float = 8.0) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return (
            int(completed.returncode),
            (completed.stdout or "").strip(),
            (completed.stderr or "").strip(),
        )
    except FileNotFoundError:
        return 127, "", "git_not_found"
    except subprocess.TimeoutExpired:
        return 124, "", "git_timeout"
    except Exception as exc:
        return 1, "", f"{type(exc).__name__}:{exc}"


def extract_candidate_paths(candidate: dict | None, *, fallback_cwd: str | None = None) -> list[str]:
    """候補からパスらしい文字列を抽出（なければ cwd）。"""
    candidate = candidate or {}
    found: list[str] = []
    for key in ("targets", "paths", "files"):
        for item in candidate.get(key) or []:
            text = str(item).strip()
            if text:
                found.append(text)
    blob = " ".join(str(a) for a in (candidate.get("args") or []))
    for match in _PATH_HINT.findall(blob):
        found.append(match.strip("\"'"))
    # 重複除去
    ordered = list(dict.fromkeys(found))
    if ordered:
        return ordered
    cwd = fallback_cwd or os.getcwd()
    return [cwd]


def collect_git_workspace_facts(
    targets: list[str] | None = None,
    *,
    start_path: str | None = None,
    candidate: dict | None = None,
) -> dict[str, Any]:
    """
    対象パスについて git 事実を収集する。
    失敗・欠測は unknown。安全結論は出さない。
    """
    start = start_path or os.getcwd()
    target_list = list(targets or [])
    if not target_list:
        target_list = extract_candidate_paths(candidate, fallback_cwd=start)

    codes = ["git_facts_phase_d1a", "git_presence_is_not_safety_proof"]
    git_bin = shutil.which("git")
    if not git_bin:
        return {
            "phase": "kss-phase-d1a",
            "in_git_repo": UNKNOWN,
            "repo_root": UNKNOWN,
            "head_exists": UNKNOWN,
            "dirty": UNKNOWN,
            "diff_vs_head_summary": UNKNOWN,
            "restore_mechanism_available": UNKNOWN,
            "restore_mechanisms": [],
            "targets": target_list,
            "tracked_targets": [],
            "untracked_targets": [],
            "ignored_targets": [],
            "outside_repo_targets": [],
            "targets_covered": UNKNOWN,
            "uncovered_targets": [],
            "git_available": False,
            "rationale_codes": codes + ["git_binary_missing"],
            "note": "Git 事実を取得できませんでした。可逆とはみなしません。",
            # assess_reversibility_from_facts 互換
            "git_repo": UNKNOWN,
            "restore_via_git": False,
            "all_targets_tracked": False,
        }

    code, root, err = _run_git(["rev-parse", "--show-toplevel"], cwd=start)
    if code != 0 or not root:
        return {
            "phase": "kss-phase-d1a",
            "in_git_repo": False,
            "repo_root": UNKNOWN,
            "head_exists": False,
            "dirty": UNKNOWN,
            "diff_vs_head_summary": UNKNOWN,
            "restore_mechanism_available": False,
            "restore_mechanisms": [],
            "targets": target_list,
            "tracked_targets": [],
            "untracked_targets": [],
            "ignored_targets": [],
            "outside_repo_targets": list(target_list),
            "targets_covered": False,
            "uncovered_targets": [
                {"path": p, "reason": "outside_repo_or_not_a_git_worktree"}
                for p in target_list
            ],
            "git_available": True,
            "rationale_codes": codes + ["not_in_git_repo", f"rev_parse_error:{err or code}"],
            "note": "Git リポジトリ外です。Git restore 対象とはみなしません。",
            "git_repo": False,
            "restore_via_git": False,
            "all_targets_tracked": False,
        }

    repo_root = root
    head_code, head_sha, _ = _run_git(["rev-parse", "--verify", "HEAD"], cwd=repo_root)
    head_exists = head_code == 0 and bool(head_sha)

    status_code, status_out, _ = _run_git(
        ["status", "--porcelain"], cwd=repo_root
    )
    dirty = UNKNOWN
    if status_code == 0:
        dirty = bool(status_out.strip())

    diff_summary: Any = UNKNOWN
    if head_exists:
        d_code, d_out, _ = _run_git(
            ["diff", "--stat", "HEAD"], cwd=repo_root
        )
        if d_code == 0:
            lines = [ln for ln in d_out.splitlines() if ln.strip()]
            diff_summary = {
                "stat_lines": lines[-5:] if lines else [],
                "truncated": True,
                "empty": not bool(lines),
            }

    tracked: list[str] = []
    untracked: list[str] = []
    ignored: list[str] = []
    outside: list[str] = []
    uncovered: list[dict[str, str]] = []

    root_path = Path(repo_root).resolve()
    for raw in target_list:
        path_obj = Path(raw)
        if not path_obj.is_absolute():
            path_obj = (Path(start) / path_obj).resolve()
        else:
            path_obj = path_obj.resolve()
        path_str = str(path_obj)
        try:
            rel = path_obj.relative_to(root_path).as_posix()
        except ValueError:
            outside.append(path_str)
            uncovered.append({"path": path_str, "reason": "outside_repo"})
            continue

        # ignored?
        ig_code, ig_out, _ = _run_git(
            ["check-ignore", "-q", "--", rel], cwd=repo_root
        )
        if ig_code == 0:
            ignored.append(path_str)
            uncovered.append({"path": path_str, "reason": "ignored_not_assumed_restorable"})
            continue

        # tracked in index/HEAD?
        ls_code, ls_out, _ = _run_git(
            ["ls-files", "--error-unmatch", "--", rel], cwd=repo_root
        )
        if ls_code == 0 and ls_out.strip():
            tracked.append(path_str)
            continue

        # untracked (exists or not)
        untracked.append(path_str)
        uncovered.append({"path": path_str, "reason": "untracked_not_restorable_via_git"})

    restore_via_git = bool(head_exists)
    restore_mechanisms = ["git_restore"] if restore_via_git else []
    # メカニズム有無と、今回対象がカバーされるかは分離
    if not target_list:
        targets_covered: Any = UNKNOWN
        codes.append("no_targets_specified")
    elif outside or ignored or untracked:
        targets_covered = False
        codes.append("targets_not_fully_covered_by_git_restore")
    elif tracked and restore_via_git:
        targets_covered = True
        codes.append("all_listed_targets_tracked_with_head")
    elif tracked and not restore_via_git:
        targets_covered = False
        codes.append("tracked_but_no_head_restore")
    else:
        targets_covered = UNKNOWN

    all_tracked = bool(tracked) and not (untracked or ignored or outside)

    return {
        "phase": "kss-phase-d1a",
        "in_git_repo": True,
        "repo_root": repo_root,
        "head_exists": head_exists,
        "head_sha": head_sha if head_exists else UNKNOWN,
        "dirty": dirty,
        "diff_vs_head_summary": diff_summary,
        "restore_mechanism_available": restore_via_git,
        "restore_mechanisms": restore_mechanisms,
        "targets": target_list,
        "tracked_targets": tracked,
        "untracked_targets": untracked,
        "ignored_targets": ignored,
        "outside_repo_targets": outside,
        "targets_covered": targets_covered,
        "uncovered_targets": uncovered,
        "git_available": True,
        "rationale_codes": list(dict.fromkeys(codes)),
        "note": (
            "Git リポジトリ内であることや restore 手段の存在は、"
            "安全性や可逆性の証明ではありません。"
            "targets_covered を別途確認してください。"
        ),
        # assess_reversibility_from_facts 互換キー
        "git_repo": True,
        "restore_via_git": restore_via_git,
        "all_targets_tracked": all_tracked,
    }
