"""Git Guard v2.1 — verified safe push evaluation (pre-push hook context)."""
from __future__ import annotations

import fnmatch
import subprocess
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from tools.git_guard.guard import GuardResult


def _run_git(repo: str, args: List[str], timeout: int = 60) -> Tuple[int, str, str]:
    cmd = ["git", "-C", repo, *args]
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "git not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"git timed out: {' '.join(args)}"

GIT_ZERO_SHA = "0" * 40

PushDecision = str  # "safe" | "block" | "need_human"


def _is_zero_sha(sha: str) -> bool:
    s = (sha or "").strip().lower()
    if not s:
        return True
    return s == GIT_ZERO_SHA or set(s) == {"0"}


def _branch_name_from_ref(ref: str) -> str:
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/") :]
    return ref


def _check_branch_policy(branch: str, cfg: Dict[str, Any], result: "GuardResult") -> bool:
    """Return False if branch policy blocks (and records fail on result)."""
    allow = cfg.get("allow_branches") or []
    deny = cfg.get("deny_branches") or []
    if allow:
        if not any(fnmatch.fnmatch(branch, p) for p in allow):
            result.fail(
                "push_safety",
                f"branch '{branch}' not in allow_branches",
            )
            return False
    if deny:
        if any(fnmatch.fnmatch(branch, p) for p in deny):
            result.fail(
                "push_safety",
                f"branch '{branch}' matches deny_branches",
            )
            return False
    return True


def evaluate_push_ref(
    repo: str,
    *,
    local_ref: str,
    local_sha: str,
    remote_ref: str,
    remote_sha: str,
) -> Tuple[PushDecision, str, str]:
    """Classify one pre-push stdin line. Worst-of aggregation is caller responsibility."""
    local_ref = (local_ref or "").strip()
    local_sha = (local_sha or "").strip().lower()
    remote_ref = (remote_ref or "").strip()
    remote_sha = (remote_sha or "").strip().lower()

    if _is_zero_sha(local_sha):
        return "block", "PUSH_REF_DELETE", "local_sha is zero (ref delete)"

    if not remote_ref.startswith("refs/heads/"):
        return "need_human", "PUSH_REF_UNSUPPORTED", f"unsupported remote_ref {remote_ref}"

    if _is_zero_sha(remote_sha):
        return "safe", "PUSH_NEW_BRANCH", "remote branch does not exist yet (create)"

    if local_sha == remote_sha:
        return "safe", "PUSH_ALREADY_UP_TO_DATE", "local matches remote (no objects to send)"

    code, _out, err = _run_git(repo, ["merge-base", "--is-ancestor", remote_sha, local_sha])
    if code == 0:
        return "safe", "PUSH_FAST_FORWARD", "remote_sha is ancestor of local_sha"
    if code == 1:
        return (
            "block",
            "PUSH_NON_FAST_FORWARD",
            "remote_sha is not an ancestor of local_sha (diverged or overwrite)",
        )
    detail = (err or _out or "merge-base failed").strip()
    return "need_human", "PUSH_ANCESTRY_UNVERIFIED", detail


def _worst_decision(decisions: List[PushDecision]) -> PushDecision:
    if "block" in decisions:
        return "block"
    if "need_human" in decisions:
        return "need_human"
    return "safe"


def apply_safe_push_gate(
    repo: str,
    cfg: Dict[str, Any],
    action: Dict[str, Any],
    result: "GuardResult",
) -> None:
    """Apply v2.1 push safety when config push_safety is v2_1."""
    push_refs: List[Dict[str, str]] = list(action.get("push_refs") or [])
    if not push_refs:
        result.human(
            "push_safety",
            "push safety v2_1 requires pre-push ref context (local/remote sha); use hook stdin",
        )
        return

    decisions: List[PushDecision] = []
    details: List[str] = []
    for ref in push_refs:
        branch = _branch_name_from_ref(ref.get("remote_ref") or "")
        if branch and not _check_branch_policy(branch, cfg, result):
            return
        decision, code, detail = evaluate_push_ref(
            repo,
            local_ref=str(ref.get("local_ref") or ""),
            local_sha=str(ref.get("local_sha") or ""),
            remote_ref=str(ref.get("remote_ref") or ""),
            remote_sha=str(ref.get("remote_sha") or ""),
        )
        decisions.append(decision)
        details.append(f"{code}: {detail}")

    final = _worst_decision(decisions)
    summary = "; ".join(details[:4])
    if len(details) > 4:
        summary += f" (+{len(details) - 4} more)"

    if final == "safe":
        result.ok("push_safety", summary or "verified safe push")
    elif final == "block":
        result.fail("push_safety", summary or "push blocked")
    else:
        result.human("push_safety", summary or "push intent unresolved")
