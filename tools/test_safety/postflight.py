"""S5c — Postflight checks and run closure (TEST_EXECUTION runner only)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from test_safety.git_snapshot import git_worktree_snapshot, porcelain_paths

POSTFLIGHT_PASS = "PASS"
POSTFLIGHT_INCOMPLETE = "INCOMPLETE"
POSTFLIGHT_FAILED = "FAILED"

CHECK_GIT_REPOSITORY_STATE = "git_repository_state"

PostflightFn = Callable[
    [],
    dict[str, Any],
]


def path_matches_declared_write_scope(path: str, declared_write_scope: Sequence[str]) -> bool:
    """Match changed paths against plan declared_write_scope (no new write policy)."""
    norm = path.replace("\\", "/").casefold()
    for entry in declared_write_scope:
        low = str(entry).casefold()
        if "runs/" in low and "runs/" in norm:
            return True
        if "runs/chat_ui" in low and "runs/chat_ui" in norm:
            return True
        if any(tok in low for tok in ("tmp", "pytest", "conftest", "tmp_path")):
            if any(tok in norm for tok in ("tmp", "pytest-cache", ".pytest_cache")):
                return True
        if "repository" in low and norm.startswith("runs/"):
            return True
    return False


def compare_git_postflight(
    baseline: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    declared_write_scope: Sequence[str],
) -> dict[str, Any]:
    """Compare before/after git snapshots; flag undeclared path changes."""
    base_lines = list(baseline.get("porcelain_lines") or [])
    after_lines = list(after.get("porcelain_lines") or [])
    base_paths = porcelain_paths(base_lines)
    after_paths = porcelain_paths(after_lines)
    changed_paths = sorted(after_paths - base_paths)
    new_or_modified = sorted(after_paths | base_paths)
    unexpected: list[str] = []
    warnings: list[str] = []

    if baseline.get("head") and after.get("head") and baseline.get("head") != after.get("head"):
        warnings.append("head_changed")

    for path in changed_paths:
        if not path_matches_declared_write_scope(path, declared_write_scope):
            unexpected.append(path)

    if baseline.get("porcelain") != after.get("porcelain"):
        for path in sorted(after_paths):
            if path not in base_paths and not path_matches_declared_write_scope(path, declared_write_scope):
                if path not in unexpected:
                    unexpected.append(path)

    status = POSTFLIGHT_PASS if not unexpected else POSTFLIGHT_FAILED
    return {
        "postflight_status": status,
        "required_checks": [CHECK_GIT_REPOSITORY_STATE],
        "completed_checks": [CHECK_GIT_REPOSITORY_STATE],
        "warnings": warnings,
        "unexpected_changes": unexpected,
        "git": {
            "baseline_head": baseline.get("head"),
            "after_head": after.get("head"),
            "baseline_branch": baseline.get("branch"),
            "after_branch": after.get("branch"),
            "baseline_porcelain_lines": base_lines,
            "after_porcelain_lines": after_lines,
        },
    }


def run_git_postflight(
    *,
    repo_root: Path,
    baseline: Mapping[str, Any] | None,
    declared_write_scope: Sequence[str],
) -> dict[str, Any]:
    if baseline is None:
        return _incomplete_git_postflight(reason="missing_baseline_snapshot")
    after = git_worktree_snapshot(repo_root)
    return compare_git_postflight(baseline, after, declared_write_scope=declared_write_scope)


def run_required_postflight(
    required_postflight: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    baseline_git: Mapping[str, Any] | None = None,
    declared_write_scope: Sequence[str] | None = None,
    postflight_fn: PostflightFn | None = None,
) -> dict[str, Any] | None:
    """Execute required postflight from authorization; do not re-infer requirements."""
    if not required_postflight.get("postflight_git_check_required"):
        return None

    if postflight_fn is not None:
        return postflight_fn()

    if repo_root is not None:
        return run_git_postflight(
            repo_root=repo_root,
            baseline=baseline_git,
            declared_write_scope=list(declared_write_scope or []),
        )

    return _incomplete_git_postflight(reason="postflight_not_executed_no_repo_root")


def _incomplete_git_postflight(reason: str) -> dict[str, Any]:
    return {
        "postflight_status": POSTFLIGHT_INCOMPLETE,
        "required_checks": [CHECK_GIT_REPOSITORY_STATE],
        "completed_checks": [],
        "warnings": [reason],
        "unexpected_changes": [],
    }


def evaluate_run_closure(
    *,
    executor_called: bool,
    safety_outcome: str,
    execution_result: Mapping[str, Any] | None,
    required_postflight: Mapping[str, Any],
    postflight_result: Mapping[str, Any] | None,
) -> tuple[bool, str]:
    """
    pytest PASS ≠ run CLOSED.
    """
    if not executor_called or safety_outcome in (
        "SAFETY_AUTHORIZATION_FAILURE",
        "EXECUTION_ALREADY_CONSUMED",
    ):
        return False, "SAFETY_AUTHORIZATION_NOT_EXECUTED"

    if execution_result is None:
        return False, "EXECUTION_RESULT_MISSING"

    git_required = bool(required_postflight.get("postflight_git_check_required"))
    if not git_required:
        return True, "NO_REQUIRED_POSTFLIGHT"

    if postflight_result is None:
        return False, "POSTFLIGHT_NOT_RUN"

    status = str(postflight_result.get("postflight_status") or POSTFLIGHT_INCOMPLETE)
    if status == POSTFLIGHT_INCOMPLETE:
        return False, "POSTFLIGHT_INCOMPLETE"
    if status == POSTFLIGHT_FAILED:
        return False, "POSTFLIGHT_FAILED"
    if postflight_result.get("unexpected_changes"):
        return False, "UNEXPECTED_REPOSITORY_CHANGES"

    return True, "ALL_REQUIRED_POSTFLIGHT_PASS"
