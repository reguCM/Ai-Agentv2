"""Git Governance Phase G4 — contract vs git_guard enforcement alignment (read-only audit + drift checks)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.policy.git_governance_contract import (
    GitGovernanceContractError,
    load_git_governance_contract,
)
from ai_tool.policy.git_governance_invariants import AGENT_ALWAYS_BLOCK_FOR_GUARD_FORBID
from ai_tool.policy.paths import git_governance_json_path

REPO_ROOT = git_governance_json_path().resolve().parents[2]

GUARD_DIR = REPO_ROOT / "tools" / "git_guard"
PRE_COMMIT_CONFIG = GUARD_DIR / "configs" / "ai-agent.pre-commit.json"
PRE_PUSH_CONFIG = GUARD_DIR / "configs" / "ai-agent.pre-push.json"
LOCAL_OPS_CONFIG = GUARD_DIR / "configs" / "ai-agent.local-ops.json"
DEPLOYED_HOOKS_DOC = GUARD_DIR / "DEPLOYED.md"

# Contract action_id → guard / hook expectations (G4 audit baseline).
AGENT_ALWAYS_BLOCK_ACTIONS = frozenset(
    {
        "force_push",
        "force_push_with_lease",
        "reset_hard",
        "amend_after_hook_failure",
        "stage_deny_path_globs",
    }
)
HUMAN_APPROVAL_ACTIONS = frozenset(
    {
        "push",
        "clean",
        "rebase",
        "worktree_remove",
        "amend",
        "branch_delete",
        "merge_to_main",
        "remote_push_restricted",
    }
)

EXPECTED_FORBID_IN_GUARD_CONFIG = AGENT_ALWAYS_BLOCK_FOR_GUARD_FORBID
EXPECTED_PUSH_SAFETY_ON_PRE_PUSH = "v2.1"
EXPECTED_LOCAL_SAFETY_ON_LOCAL_OPS = "v2.2"
EXPECTED_DENY_PATH_GLOBS = frozenset(
    {".env", "**/.env", "**/secrets/**", "**/*.pem", "**/credentials.json"}
)
EXPECTED_REMOTE_URL_MUST_CONTAIN = "github.com/reguCM/Ai-Agent"

CONFIG_DRIFT_CLASS = frozenset(
    {
        "MATCH",
        "CONTRACT_STRONGER",
        "GUARD_STRONGER",
        "MISSING_IN_GUARD",
        "MISSING_IN_CONTRACT",
        "SEMANTIC_MISMATCH",
    }
)


class GitGovernanceEnforcementError(RuntimeError):
    """Enforcement validation failed."""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm_actions(items: list[Any] | None) -> set[str]:
    if not items:
        return set()
    return {str(x).strip().lower() for x in items if str(x).strip()}


def _norm_globs(items: list[Any] | None) -> set[str]:
    if not items:
        return set()
    return {str(x).replace("\\", "/") for x in items}


def validate_git_governance_enforcement(
    *,
    contract: dict[str, Any] | None = None,
    pre_commit_path: Path | None = None,
    pre_push_path: Path | None = None,
) -> dict[str, Any]:
    """Compare machine contract intent with git_guard hook configs (no guard.py logic duplication)."""
    data = contract or load_git_governance_contract()
    pre_commit = _load_json(pre_commit_path or PRE_COMMIT_CONFIG)
    pre_push = _load_json(pre_push_path or PRE_PUSH_CONFIG)
    local_ops = _load_json(LOCAL_OPS_CONFIG) if LOCAL_OPS_CONFIG.is_file() else {}

    findings: list[dict[str, str]] = []

    for label, cfg in (("pre-commit", pre_commit), ("pre-push", pre_push)):
        forbid = _norm_actions(cfg.get("forbid_actions"))
        for action in EXPECTED_FORBID_IN_GUARD_CONFIG:
            if action in forbid:
                findings.append(
                    {
                        "config": label,
                        "field": "forbid_actions",
                        "item": action,
                        "classification": "MATCH",
                    }
                )
            else:
                findings.append(
                    {
                        "config": label,
                        "field": "forbid_actions",
                        "item": action,
                        "classification": "MISSING_IN_GUARD",
                    }
                )
        if label == "pre-push":
            push_safety = str(cfg.get("push_safety") or "").strip()
            if push_safety == EXPECTED_PUSH_SAFETY_ON_PRE_PUSH:
                findings.append(
                    {
                        "config": label,
                        "field": "push_safety",
                        "item": push_safety,
                        "classification": "MATCH",
                    }
                )
            else:
                findings.append(
                    {
                        "config": label,
                        "field": "push_safety",
                        "item": push_safety or "(missing)",
                        "classification": "MISSING_IN_GUARD",
                    }
                )
            human = _norm_actions(cfg.get("human_gate_actions"))
            if "push" in human:
                findings.append(
                    {
                        "config": label,
                        "field": "human_gate_actions",
                        "item": "push",
                        "classification": "SEMANTIC_MISMATCH",
                        "note": "v2.1 uses push_safety not unconditional push human_gate",
                    }
                )
            if "force_push" in human and "force_push" in forbid:
                findings.append(
                    {
                        "config": label,
                        "field": "human_gate_actions",
                        "item": "force_push",
                        "classification": "MATCH",
                        "note": "redundant_with_forbid_actions",
                    }
                )

    pc_denies = _norm_globs(pre_commit.get("deny_path_globs"))
    for glob in EXPECTED_DENY_PATH_GLOBS:
        if glob in pc_denies:
            findings.append(
                {
                    "config": "pre-commit",
                    "field": "deny_path_globs",
                    "item": glob,
                    "classification": "MATCH",
                }
            )
        else:
            findings.append(
                {
                    "config": "pre-commit",
                    "field": "deny_path_globs",
                    "item": glob,
                    "classification": "MISSING_IN_GUARD",
                }
            )

    for label, cfg in (("pre-commit", pre_commit), ("pre-push", pre_push)):
        remotes = cfg.get("remotes") or []
        origin = next((r for r in remotes if r.get("name") == "origin"), None)
        if not origin:
            findings.append(
                {
                    "config": label,
                    "field": "remotes",
                    "item": "origin",
                    "classification": "MISSING_IN_GUARD",
                }
            )
            continue
        must = str(origin.get("url_must_contain") or "")
        if must == EXPECTED_REMOTE_URL_MUST_CONTAIN:
            findings.append(
                {
                    "config": label,
                    "field": "remotes",
                    "item": "origin.url_must_contain",
                    "classification": "MATCH",
                }
            )
        else:
            findings.append(
                {
                    "config": label,
                    "field": "remotes",
                    "item": "origin.url_must_contain",
                    "classification": "SEMANTIC_MISMATCH",
                    "detail": must,
                }
            )

    local_safety = str(local_ops.get("local_safety") or "").strip()
    if local_safety == EXPECTED_LOCAL_SAFETY_ON_LOCAL_OPS:
        findings.append(
            {
                "config": "local-ops",
                "field": "local_safety",
                "item": local_safety,
                "classification": "MATCH",
            }
        )
    elif LOCAL_OPS_CONFIG.is_file():
        findings.append(
            {
                "config": "local-ops",
                "field": "local_safety",
                "item": local_safety or "(missing)",
                "classification": "MISSING_IN_GUARD",
            }
        )

    drifts = [f for f in findings if f.get("classification") != "MATCH"]
    ok = not any(
        f.get("classification") in ("MISSING_IN_GUARD", "SEMANTIC_MISMATCH")
        for f in findings
    )
    return {
        "contract_version": data.get("contract_version"),
        "configs_checked": [
            str(PRE_COMMIT_CONFIG.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(PRE_PUSH_CONFIG.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(LOCAL_OPS_CONFIG.relative_to(REPO_ROOT)).replace("\\", "/"),
        ],
        "findings": findings,
        "config_drifts": drifts,
        "config_alignment_ok": ok,
    }


def build_enforcement_matrix(
    contract: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Map each contract action to observed enforcement (honest; not ENFORCED without evidence)."""
    data = contract or load_git_governance_contract()
    actions = data.get("actions")
    if not isinstance(actions, list):
        raise GitGovernanceContractError("actions missing")

    matrix: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action_id") or "")
        approval = str(action.get("approval_class") or "")
        row = _enforcement_row_for_action(action_id, approval, action)
        matrix.append(row)
    return matrix


def _enforcement_row_for_action(
    action_id: str, approval_class: str, action: dict[str, Any]
) -> dict[str, Any]:
    bindings = action.get("validator_bindings") or []
    hook_connected = any(
        b.get("validator_ref") in ("pre-commit", "pre-push") for b in bindings if isinstance(b, dict)
    )
    guard_connected = any(
        b.get("validator_ref") in ("git_guard", "pre-commit", "pre-push")
        for b in bindings if isinstance(b, dict)
    )

    gap: list[str] = []
    actual = "NOT_CONNECTED"
    raw_cli = "RAW_CLI_ENFORCEMENT_GAP"
    runtime = "NOT_CONNECTED"
    path = ""

    if action_id == "commit":
        actual = "CONTRACT_DEFINED"
        runtime = "RUNTIME_NOT_CONNECTED"
        raw_cli = "RAW_CLI_ENFORCEMENT_GAP"
        gap = ["AUTO_COMMIT_ALLOWED not bound to Runtime", "commit not gated by hooks"]
    elif action_id == "amend":
        actual = "GUIDANCE_ONLY"
        path = "adapters + GIT §4; no git_guard action gate for amend"
        gap = ["RAW_CLI_ENFORCEMENT_GAP", "HOST_ADAPTER_DRIFT possible"]
    elif action_id == "amend_after_hook_failure":
        actual = "CONTRACT_ONLY"
        path = "adapters; not git_guard"
        gap = ["AGENT_ALWAYS_BLOCK not machine-enforced on shell"]
    elif action_id == "push":
        actual = "PARTIALLY_ENFORCED"
        path = (
            "pre-push hook → guard push_safety v2.1 (SAFE→PASS, BLOCK→FAIL, "
            "UNRESOLVED→NEED_HUMAN)"
        )
        hook_connected = True
        guard_connected = True
        raw_cli = "RAW_CLI_ENFORCEMENT_GAP"
        gap = ["bypass: git push --no-verify", "agent shell may skip hook"]
    elif action_id in ("force_push", "force_push_with_lease", "reset_hard"):
        actual = "PARTIALLY_ENFORCED"
        path = "guard --action <type> when forbid_actions includes type; hooks may not pass action"
        guard_connected = True
        gap = ["RAW_CLI_ENFORCEMENT_GAP", "direct git CLI bypasses guard"]
    elif action_id in ("clean", "worktree_remove", "restore_discard_worktree"):
        actual = "PARTIALLY_ENFORCED"
        path = "guard local_safety v2.2 when --action local_git + --local-op (explicit invoke)"
        guard_connected = True
        gap = ["RAW_CLI_ENFORCEMENT_GAP", "no git pre-exec hook for restore/reset/clean"]
    elif action_id in ("rebase", "branch_delete", "stash"):
        actual = "NOT_CONNECTED"
        path = "no git_guard mapping"
        gap = ["RAW_CLI_ENFORCEMENT_GAP"]
    elif action_id in ("add_explicit_paths", "add_all", "commit_message"):
        actual = "GUIDANCE_ONLY"
        raw_cli = "NOT_APPLICABLE"
        gap = []
    elif action_id == "merge_to_main":
        actual = "NOT_CONNECTED"
        gap = ["RAW_CLI_ENFORCEMENT_GAP"]
    elif action_id == "remote_push_restricted":
        actual = "PARTIALLY_ENFORCED"
        path = "remotes[].url_must_contain on hook-invoked guard"
        hook_connected = True
        guard_connected = True
        gap = ["RAW_CLI_ENFORCEMENT_GAP when push without hook"]
    elif action_id == "stage_deny_path_globs":
        actual = "PARTIALLY_ENFORCED"
        path = "pre-commit deny_path_globs on changed paths"
        hook_connected = True
        guard_connected = True
        gap = ["RAW_CLI_ENFORCEMENT_GAP without commit hook"]
    elif action_id in ("status_read", "diff_read", "log_read"):
        actual = "NOT_APPLICABLE"
        raw_cli = "NOT_APPLICABLE"
        gap = []

    agent_consumers = _agent_block_matrix(action_id, approval_class)

    return {
        "action_id": action_id,
        "contract_policy": approval_class,
        "approval_class": approval_class,
        "validator_ref": [
            b.get("validator_ref") for b in bindings if isinstance(b, dict) and b.get("validator_ref")
        ],
        "current_enforcement_path": path,
        "hook_connected": hook_connected,
        "guard_connected": guard_connected,
        "raw_cli_covered": raw_cli if isinstance(raw_cli, str) else "RAW_CLI_ENFORCEMENT_GAP",
        "runtime_connected": runtime if action_id == "commit" else ("NOT_CONNECTED" if actual == "NOT_CONNECTED" else "NOT_APPLICABLE"),
        "actual_result": actual,
        "gap": gap,
        "agent_consumers": agent_consumers,
    }


def _agent_block_matrix(action_id: str, approval_class: str) -> dict[str, str]:
    """Where agent paths can block (G4 §6)."""
    consumers = {
        "cursor": "NOT_APPLICABLE",
        "codex": "NOT_APPLICABLE",
        "local_agent": "NOT_APPLICABLE",
        "automation": "NOT_APPLICABLE",
        "git_guard": "NOT_APPLICABLE",
        "shell": "UNCONTROLLED",
    }
    if action_id == "push":
        consumers["git_guard"] = "BLOCKED"
        consumers["shell"] = "PARTIALLY_ENFORCED"
        consumers["cursor"] = "PROMPT_ONLY"
        consumers["codex"] = "PROMPT_ONLY"
        consumers["local_agent"] = "PROMPT_ONLY"
    elif action_id in AGENT_ALWAYS_BLOCK_ACTIONS:
        consumers["cursor"] = "PROMPT_ONLY"
        consumers["codex"] = "PROMPT_ONLY"
        consumers["local_agent"] = "PROMPT_ONLY"
        if action_id in ("force_push", "force_push_with_lease", "reset_hard"):
            consumers["git_guard"] = "BLOCKED"
        if action_id == "stage_deny_path_globs":
            consumers["git_guard"] = "BLOCKED"
    elif approval_class == "HUMAN_APPROVAL_REQUIRED":
        consumers["cursor"] = "PROMPT_ONLY"
        consumers["codex"] = "PROMPT_ONLY"
        consumers["local_agent"] = "PROMPT_ONLY"
    elif approval_class in ("GUIDANCE_ONLY", "ALLOW", "UNDECIDED"):
        consumers["cursor"] = "PROMPT_ONLY"
        consumers["codex"] = "PROMPT_ONLY"
    if action_id == "commit":
        consumers["cursor"] = "PROMPT_ONLY"
        consumers["codex"] = "PROMPT_ONLY"
        consumers["local_agent"] = "PROMPT_ONLY"
    return consumers


def enforcement_coverage_summary(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in matrix:
        key = str(row.get("actual_result") or "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1
    priority_gaps = [
        r["action_id"]
        for r in matrix
        if r.get("approval_class")
        in ("AGENT_ALWAYS_BLOCK", "HUMAN_APPROVAL_REQUIRED", "TASK_AUTHORIZATION_REQUIRED")
        and r.get("actual_result") not in ("PARTIALLY_ENFORCED", "ENFORCED")
    ]
    return {
        "actions_total": len(matrix),
        "by_actual_result": counts,
        "priority_unconnected": priority_gaps,
    }


def hook_deployment_status() -> dict[str, Any]:
    """READ-ONLY hook evidence from DEPLOYED.md + optional filesystem probe."""
    doc_exists = DEPLOYED_HOOKS_DOC.is_file()
    shared_hook_pre_push = Path(r"D:\AI-Agent\.git\hooks\pre-push")
    shared_hook_pre_commit = Path(r"D:\AI-Agent\.git\hooks\pre-commit")
    return {
        "documentation": str(DEPLOYED_HOOKS_DOC.relative_to(REPO_ROOT)).replace("\\", "/"),
        "deployed_doc_present": doc_exists,
        "shared_git_hooks": {
            "pre-commit": {
                "path": str(shared_hook_pre_commit),
                "exists": shared_hook_pre_commit.is_file(),
                "auto_modify_in_g4": False,
            },
            "pre-push": {
                "path": str(shared_hook_pre_push),
                "exists": shared_hook_pre_push.is_file(),
                "auto_modify_in_g4": False,
            },
        },
        "hook_role": "thin_adapter_to_guard",
        "configs": [
            "tools/git_guard/configs/ai-agent.pre-commit.json",
            "tools/git_guard/configs/ai-agent.pre-push.json",
            "tools/git_guard/configs/ai-agent.local-ops.json",
        ],
    }
