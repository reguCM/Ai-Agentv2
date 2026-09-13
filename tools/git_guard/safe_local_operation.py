"""Git Guard v2.2 — destructive local git operation safety (explicit guard invocation)."""
from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from tools.git_guard.guard import GuardResult

LocalDecision = str  # "safe" | "block" | "need_human"


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


def parse_local_op_spec(spec: str) -> Dict[str, Any]:
    """Parse CLI ``operation|path1,path2|key=value`` into a normalized op dict."""
    parts = (spec or "").split("|")
    if len(parts) < 1 or not parts[0].strip():
        raise ValueError("local_op requires operation name")
    op = parts[0].strip().lower().replace("-", "_")
    paths: List[str] = []
    if len(parts) > 1 and parts[1].strip() and parts[1].strip() != "_":
        paths = [p.strip() for p in parts[1].split(",") if p.strip()]
    flags: Dict[str, str] = {}
    for seg in parts[2:]:
        if "=" in seg:
            k, v = seg.split("=", 1)
            flags[k.strip().lower()] = v.strip()
    return {
        "operation": op,
        "paths": paths,
        "staged": flags.get("staged", "0") in ("1", "true", "yes"),
        "worktree": flags.get("worktree", "0") in ("1", "true", "yes"),
        "source": flags.get("source") or flags.get("from") or "",
        "dry_run": flags.get("dry_run", flags.get("n", "0")) in ("1", "true", "yes"),
        "mode": (flags.get("mode") or "").lower(),
        "ref": flags.get("ref", ""),
        "force": flags.get("force", "0") in ("1", "true", "yes"),
        "directories": flags.get("directories", flags.get("d", "0")) in ("1", "true", "yes"),
        "ignored": flags.get("ignored", flags.get("x", "0")) in ("1", "true", "yes"),
    }


def _porcelain_for_paths(repo: str, paths: List[str]) -> List[str]:
    if paths:
        code, out, _err = _run_git(repo, ["status", "--porcelain", "--", *paths])
    else:
        code, out, _err = _run_git(repo, ["status", "--porcelain"])
    if code != 0:
        return []
    return [ln for ln in out.splitlines() if ln.strip()]


def _line_affects_path(line: str, path: str) -> bool:
    if len(line) < 4:
        return False
    entry = line[3:].strip()
    if " -> " in entry:
        entry = entry.split(" -> ", 1)[1].strip()
    return entry == path or entry.endswith("/" + path) or path.endswith(entry)


def _has_unstaged_change(lines: List[str], paths: List[str]) -> bool:
    for ln in lines:
        x, y = ln[0], ln[1]
        if x in ("M", "D", "R", "T") or y == "D":
            if not paths:
                return True
            for p in paths:
                if _line_affects_path(ln, p):
                    return True
    return False


def _has_staged_change(lines: List[str], paths: List[str]) -> bool:
    for ln in lines:
        x, y = ln[0], ln[1]
        if x in ("M", "A", "D", "R", "T", "C") or y in ("M", "A", "D", "R", "T"):
            if not paths:
                return True
            for p in paths:
                if _line_affects_path(ln, p):
                    return True
    return False


def _has_untracked(lines: List[str], paths: List[str]) -> bool:
    for ln in lines:
        if not ln.startswith("??"):
            continue
        if not paths:
            return True
        entry = ln[3:].strip()
        for p in paths:
            if entry == p or entry.startswith(p + "/") or p.startswith(entry + "/"):
                return True
    return False


def _diff_empty(repo: str, args: List[str]) -> bool:
    code, out, _err = _run_git(repo, args)
    return code == 0 and not (out or "").strip()


def evaluate_restore(
    repo: str, paths: List[str], *, staged: bool, worktree: bool, source: str
) -> Tuple[LocalDecision, str, str]:
    lines = _porcelain_for_paths(repo, paths)
    if staged and not worktree:
        if not _has_staged_change(lines, paths):
            return "safe", "SAFE_NO_CHANGES", "no staged changes to unstage"
        return "safe", "SAFE_INDEX_ONLY", "unstage only; working tree preserved"

    if source:
        for p in paths or ["."]:
            if _has_unstaged_change(lines, [p]) or _has_staged_change(lines, [p]):
                return (
                    "block",
                    "BLOCK_UNCOMMITTED_DATA_LOSS",
                    f"restore --source would overwrite local changes on {p}",
                )
        for p in paths:
            if not _diff_empty(repo, ["diff", "--", p]):
                return (
                    "block",
                    "BLOCK_UNCOMMITTED_DATA_LOSS",
                    f"working tree differs from index for {p}",
                )
            src = source if source != "HEAD" else "HEAD"
            if not _diff_empty(repo, ["diff", src, "--", p]):
                return "safe", "SAFE_NO_CHANGES", f"restore --source {src} is no-op for {p}"
        return "safe", "SAFE_NO_CHANGES", "restore --source would not change tracked content"

    if worktree or (not staged):
        if _has_unstaged_change(lines, paths):
            return (
                "block",
                "BLOCK_UNCOMMITTED_DATA_LOSS",
                "restore would discard unstaged working tree changes",
            )
        if not paths:
            if lines:
                return "safe", "SAFE_NO_CHANGES", "no matching path changes"
            return "safe", "SAFE_NO_CHANGES", "no-op restore"
        return "safe", "SAFE_NO_CHANGES", "no unstaged changes on target paths"

    return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", "unrecognized restore flag combination"


def evaluate_checkout_paths(repo: str, paths: List[str]) -> Tuple[LocalDecision, str, str]:
    return evaluate_restore(repo, paths, staged=False, worktree=True, source="")


def evaluate_reset(
    repo: str, paths: List[str], *, mode: str, ref: str
) -> Tuple[LocalDecision, str, str]:
    mode = (mode or "mixed").lower()
    ref = (ref or "HEAD").strip()
    lines = _porcelain_for_paths(repo, [])

    if paths:
        if mode in ("", "mixed", "mixed_reset") or not mode:
            if not _has_staged_change(lines, paths):
                return "safe", "SAFE_NO_CHANGES", "paths not staged"
            return "safe", "SAFE_INDEX_ONLY", "unstage paths only (mixed/path reset)"
        return "need_human", "NEED_HUMAN_INTENT", f"reset with paths and mode={mode}"

    if mode == "hard":
        if ref.upper() not in ("HEAD", "@", "@{0}"):
            _hc, head, _he = _run_git(repo, ["rev-parse", "HEAD"])
            target_code, target_sha, _e2 = _run_git(repo, ["rev-parse", ref])
            if target_code != 0:
                return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", f"cannot resolve ref {ref}"
            if head and target_sha and head != target_sha:
                return (
                    "block",
                    "BLOCK_HISTORY_REWRITE",
                    "reset --hard to commit other than HEAD",
                )
        if _has_unstaged_change(lines, []) or _has_staged_change(lines, []):
            return (
                "block",
                "BLOCK_UNCOMMITTED_DATA_LOSS",
                "reset --hard would discard local changes",
            )
        return "safe", "SAFE_NO_CHANGES", "reset --hard HEAD on clean tree (no-op)"

    if mode in ("soft", "mixed"):
        _hc, head, _he = _run_git(repo, ["rev-parse", "HEAD"])
        target_code, target_sha, _e2 = _run_git(repo, ["rev-parse", ref or "HEAD"])
        if target_code != 0:
            return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", f"cannot resolve ref {ref}"
        if head and target_sha and head != target_sha:
            return (
                "need_human",
                "NEED_HUMAN_INTENT",
                f"reset --{mode} moves branch ref (intent not provable safe)",
            )
        return "safe", "SAFE_NO_CHANGES", f"reset --{mode} at HEAD (no ref movement)"

    return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", f"unsupported reset mode {mode}"


def evaluate_clean(
    repo: str, *, dry_run: bool, force: bool, directories: bool, ignored: bool
) -> Tuple[LocalDecision, str, str]:
    if dry_run:
        return "safe", "SAFE_DRY_RUN", "git clean dry-run is read-only"

    if not force:
        return "need_human", "NEED_HUMAN_INTENT", "git clean without -f is interactive; not auto-run"

    args = ["clean", "-f"]
    if directories:
        args.append("-d")
    if ignored:
        args.extend(["-x"])
    args.append("-n")
    code, out, err = _run_git(repo, args)
    if code != 0:
        detail = (err or out or "git clean -n failed").strip()
        return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", detail
    targets = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not targets:
        return "safe", "SAFE_NO_CHANGES", "clean would remove nothing"
    return (
        "block",
        "BLOCK_UNTRACKED_DATA_DELETE",
        f"clean would delete {len(targets)} untracked path(s)",
    )


def _parse_worktree_porcelain(out: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    cur: Dict[str, str] = {}
    for line in out.splitlines():
        if line == "":
            if cur:
                entries.append(cur)
                cur = {}
            continue
        if line.startswith("worktree "):
            cur["worktree"] = line[len("worktree ") :].strip()
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch ") :].strip()
        elif line.startswith("detached"):
            cur["detached"] = "1"
    if cur:
        entries.append(cur)
    return entries


def evaluate_worktree_remove(
    repo: str, wt_path: str, *, force: bool
) -> Tuple[LocalDecision, str, str]:
    if force:
        return "block", "BLOCK_DIRTY_WORKTREE_DELETE", "worktree remove --force not auto-allowed"

    code, out, err = _run_git(repo, ["worktree", "list", "--porcelain"])
    if code != 0:
        return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", err or out or "worktree list failed"

    entries = _parse_worktree_porcelain(out)
    match: Optional[Dict[str, str]] = None
    norm = wt_path.replace("\\", "/").rstrip("/")
    for e in entries:
        p = (e.get("worktree") or "").replace("\\", "/").rstrip("/")
        if p == norm or p.endswith("/" + norm.split("/")[-1]):
            match = e
            break
    if not match:
        return (
            "need_human",
            "NEED_HUMAN_UNSUPPORTED_CONTEXT",
            "path is not a registered git worktree; do not use filesystem recursive delete",
        )

    wt = match["worktree"]
    st_code, st_out, _st_err = _run_git(wt, ["status", "--porcelain"])
    if st_code != 0:
        return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", f"cannot probe worktree status at {wt}"
    lines = [ln for ln in st_out.splitlines() if ln.strip()]
    if lines:
        return "block", "BLOCK_DIRTY_WORKTREE_DELETE", "worktree has modified or untracked content"
    return "safe", "SAFE_NO_CHANGES", "registered clean worktree can be removed"


def evaluate_local_op(repo: str, op: Dict[str, Any]) -> Tuple[LocalDecision, str, str]:
    operation = str(op.get("operation") or "").lower()
    paths = list(op.get("paths") or [])

    if operation in ("restore",):
        staged = bool(op.get("staged"))
        worktree = bool(op.get("worktree"))
        source = str(op.get("source") or "")
        if not staged and not worktree and not source:
            worktree = True
        return evaluate_restore(
            repo,
            paths,
            staged=staged,
            worktree=worktree,
            source=source,
        )
    if operation in ("checkout_path", "checkout_paths", "checkout"):
        return evaluate_checkout_paths(repo, paths)
    if operation == "reset":
        return evaluate_reset(
            repo,
            paths,
            mode=str(op.get("mode") or ""),
            ref=str(op.get("ref") or "HEAD"),
        )
    if operation == "clean":
        return evaluate_clean(
            repo,
            dry_run=bool(op.get("dry_run")),
            force=bool(op.get("force")),
            directories=bool(op.get("directories")),
            ignored=bool(op.get("ignored")),
        )
    if operation in ("worktree_remove", "worktree_rm"):
        if not paths:
            return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", "worktree_remove requires path"
        return evaluate_worktree_remove(repo, paths[0], force=bool(op.get("force")))
    return "need_human", "NEED_HUMAN_UNSUPPORTED_CONTEXT", f"unknown operation {operation}"


def _worst_decision(decisions: List[LocalDecision]) -> LocalDecision:
    if "block" in decisions:
        return "block"
    if "need_human" in decisions:
        return "need_human"
    return "safe"


def _format_target_paths(op: Dict[str, Any]) -> str:
    paths = list(op.get("paths") or [])
    operation = str(op.get("operation") or "").lower()
    if paths:
        return ", ".join(paths)
    if operation == "clean":
        return "untracked paths in repository working tree"
    if operation == "reset":
        ref = str(op.get("ref") or "HEAD").strip() or "HEAD"
        return f"branch ref and index (reset target ref: {ref})"
    return "repository working tree (no path filter)"


def _operation_description(op: Dict[str, Any]) -> str:
    operation = str(op.get("operation") or "").lower()
    staged = bool(op.get("staged"))
    worktree = bool(op.get("worktree"))
    source = str(op.get("source") or "")
    mode = str(op.get("mode") or "").lower()
    if operation == "restore":
        if staged and not worktree:
            return "git restore --staged: unstage indexed changes without rewriting the working tree"
        if source:
            return f"git restore --source {source}: replace working tree content from another Git revision"
        return "git restore: reset tracked file(s) in the working tree to match the index or HEAD"
    if operation in ("checkout_path", "checkout_paths", "checkout"):
        return "git checkout -- <path>: discard unstaged working tree changes on tracked path(s)"
    if operation == "reset":
        if mode == "hard":
            return "git reset --hard: move HEAD and align index and working tree to a commit"
        if mode in ("soft", "mixed"):
            return f"git reset --{mode}: move branch ref and change index/history layout"
        return "git reset: change index staging state for path(s) or branch"
    if operation == "clean":
        if bool(op.get("dry_run")):
            return "git clean -n / --dry-run: list untracked paths that would be removed (read-only)"
        return "git clean: permanently delete untracked files and/or directories"
    if operation in ("worktree_remove", "worktree_rm"):
        return "git worktree remove: unregister and remove a linked working tree directory"
    return f"local git operation: {operation or '(unspecified)'}"


def build_local_op_human_explanation(
    op: Dict[str, Any],
    decision: LocalDecision,
    reason_code: str,
    detail: str,
) -> Dict[str, str]:
    """Human-readable fields for a single evaluated op (does not affect decision)."""
    target = _format_target_paths(op)
    code = (reason_code or "").upper()
    effect = (detail or "").strip()

    if code == "BLOCK_UNCOMMITTED_DATA_LOSS":
        effect = (
            "Uncommitted working tree or index changes on the target path(s) would be discarded. "
            f"Probe detail: {detail}"
        )
    elif code == "BLOCK_UNTRACKED_DATA_DELETE":
        effect = (
            "Untracked files (not in Git history) would be permanently deleted. "
            f"Probe detail: {detail}"
        )
    elif code == "BLOCK_HISTORY_REWRITE":
        effect = (
            "Branch history and/or checked-out commit would change; local uncommitted work may be lost. "
            f"Probe detail: {detail}"
        )
    elif code == "BLOCK_DIRTY_WORKTREE_DELETE":
        effect = (
            "Worktree directory or its contents would be removed while dirty or forced. "
            f"Probe detail: {detail}"
        )
    elif code in ("SAFE_NO_CHANGES", "SAFE_INDEX_ONLY"):
        effect = (
            "No uncommitted data loss on the target: "
            + ("index-only change; working tree preserved." if code == "SAFE_INDEX_ONLY" else detail)
        )
    elif code == "SAFE_DRY_RUN":
        effect = "No files are deleted; only candidate untracked paths are reported."
    elif code.startswith("NEED_HUMAN"):
        effect = (
            "Safety or user intent cannot be determined from probes alone. "
            f"Known: {detail}. Unknown: whether the operation should proceed given policy intent."
        )
    elif decision == "safe" and not effect:
        effect = "No data loss identified for the probed target."

    return {
        "operation_description": _operation_description(op),
        "target_description": target,
        "effect_description": effect,
    }


def apply_local_git_gate(
    repo: str,
    cfg: Dict[str, Any],
    action: Dict[str, Any],
    result: "GuardResult",
) -> None:
    """Apply v2.2 local safety when config local_safety is v2_2."""
    ops: List[Dict[str, Any]] = list(action.get("local_ops") or [])
    if not ops and action.get("local_op"):
        raw = action.get("local_op")
        if isinstance(raw, dict):
            ops = [raw]
        elif isinstance(raw, str):
            ops = [parse_local_op_spec(raw)]

    if not ops:
        result.human(
            "local_safety",
            "local safety v2_2 requires --local-op or action.local_ops context",
        )
        missing = {
            "operation_description": "local_git guard evaluation (unspecified operation)",
            "target_description": "(no --local-op provided)",
            "effect_description": (
                "Cannot classify safety: operation, target paths, and data-loss impact are unknown."
            ),
        }
        if result.checks:
            result.checks[-1].update(missing)
        return

    decisions: List[LocalDecision] = []
    details: List[str] = []
    traced: List[Tuple[Dict[str, Any], LocalDecision, str, str]] = []
    for raw in ops:
        op = parse_local_op_spec(raw) if isinstance(raw, str) else dict(raw)
        decision, code, detail = evaluate_local_op(repo, op)
        decisions.append(decision)
        details.append(f"{code}: {detail}")
        traced.append((op, decision, code, detail))

    final = _worst_decision(decisions)
    summary = "; ".join(details[:4])
    if len(details) > 4:
        summary += f" (+{len(details) - 4} more)"

    if final == "safe":
        result.ok("local_safety", summary or "verified safe local operation")
    elif final == "block":
        result.fail("local_safety", summary or "local operation blocked")
    else:
        result.human("local_safety", summary or "local operation intent unresolved")

    explain_op: Optional[Dict[str, Any]] = None
    explain_code = ""
    explain_detail = ""
    for op, decision, code, detail in traced:
        if decision == final:
            explain_op, explain_code, explain_detail = op, code, detail
            break
    if explain_op is None and traced:
        explain_op, _, explain_code, explain_detail = traced[0]
    if explain_op is not None and result.checks:
        result.checks[-1].update(
            build_local_op_human_explanation(explain_op, final, explain_code, explain_detail)
        )
