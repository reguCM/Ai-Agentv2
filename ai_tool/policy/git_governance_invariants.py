"""Git Governance semantic invariants and known enforcement gaps (G2/G4.1/G5 regression source)."""
from __future__ import annotations

# Bump when human decisions or gap registry intentionally changes.
EXPECTED_CONTRACT_VERSION = "2026-09-12.3"

SEMANTIC_INVARIANTS: dict[str, str] = {
    "commit": "TASK_AUTHORIZATION_REQUIRED",
    "push": "HUMAN_APPROVAL_REQUIRED",
    "force_push": "AGENT_ALWAYS_BLOCK",
    "force_push_with_lease": "AGENT_ALWAYS_BLOCK",
    "reset_hard": "AGENT_ALWAYS_BLOCK",
    "clean": "HUMAN_APPROVAL_REQUIRED",
    "rebase": "HUMAN_APPROVAL_REQUIRED",
    "worktree_remove": "HUMAN_APPROVAL_REQUIRED",
    "amend": "HUMAN_APPROVAL_REQUIRED",
    "amend_after_hook_failure": "AGENT_ALWAYS_BLOCK",
}

AGENT_ALWAYS_BLOCK_FOR_GUARD_FORBID = frozenset(
    {"force_push", "force_push_with_lease", "reset_hard"}
)

KNOWN_ENFORCEMENT_GAPS: dict[str, dict[str, str]] = {
    "commit": {
        "status": "KNOWN",
        "classification": "RUNTIME_NOT_CONNECTED",
        "note": "AUTO_COMMIT_ALLOWED not bound; hooks do not gate commit",
    },
    "amend": {
        "status": "KNOWN",
        "classification": "ENFORCEMENT_SCOPE_GAP",
        "note": "No git_guard action gate; adapter/policy only",
    },
    "amend_after_hook_failure": {
        "status": "KNOWN",
        "classification": "CONTRACT_ONLY",
        "note": "Agent block via adapters; not shell-enforced",
    },
    "clean": {
        "status": "KNOWN",
        "classification": "RAW_CLI_ENFORCEMENT_GAP",
        "note": "No guard mapping",
    },
    "rebase": {
        "status": "KNOWN",
        "classification": "RAW_CLI_ENFORCEMENT_GAP",
        "note": "No guard mapping",
    },
    "worktree_remove": {
        "status": "KNOWN",
        "classification": "RAW_CLI_ENFORCEMENT_GAP",
        "note": "No guard mapping",
    },
    "branch_delete": {
        "status": "KNOWN",
        "classification": "ENFORCEMENT_SCOPE_GAP",
        "note": "Human approval in policy; no guard gate",
    },
    "merge_to_main": {
        "status": "KNOWN",
        "classification": "ENFORCEMENT_SCOPE_GAP",
        "note": "No guard mapping",
    },
}

SEMANTIC_POLICY_ANCHORS = (
    "ai_tool/policy/git_governance.json",
    "AUTO_COMMIT_ALLOWED",
    "Machine Contract Reference",
)
