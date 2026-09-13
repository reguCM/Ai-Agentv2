"""テスト改善ループ (test_improvement_loop) — machine-readable records.

Experiment-only. Does not import production runtime.
Does not promote. Human Review Packet is derived from these records.

Former name: Auto Upgrade System v0 (package research.auto_upgrade_system).
"""
from __future__ import annotations

from typing import Any

DISPLAY_NAME = "テスト改善ループ"
INTERNAL_ID = "test_improvement_loop"
LEGACY_INTERNAL_ID = "auto_upgrade_system"
LEGACY_PACKAGE = "research.auto_upgrade_system"

UPGRADE_TYPES = (
    "adoption_gate",
    "evaluator",
    "rule",
    "contract",
    "registry",
    "help",
    "adapter",
    "runtime",
    "tool",
    "test",
    "other",
)

STAGES = ("CANARY_1", "VALIDATE_5", "TARGET", "HOLDOUT_1", "HOLDOUT_5", "STOP")

STAGE_MAX_N = {
    "CANARY_1": 1,
    "VALIDATE_5": 5,
    "TARGET": None,
    "HOLDOUT_1": 1,
    "HOLDOUT_5": 5,
}

MAX_UPGRADE_ATTEMPTS = 3

DECISION_VALUES = (
    "improved",
    "not_improved",
    "inconclusive",
)


def new_case(**fields: Any) -> dict[str, Any]:
    required = (
        "case_id",
        "source",
        "observed_failure",
        "expected_invariant",
        "target_layer",
        "severity",
        "status",
    )
    out = {k: fields.get(k) for k in required}
    out["source_test"] = fields.get("source_test")
    out["source_failure"] = fields.get("source_failure")
    out["evidence"] = list(fields.get("evidence") or [])
    out["upgrade_type"] = fields.get("upgrade_type") or "other"
    if out["upgrade_type"] not in UPGRADE_TYPES:
        raise ValueError(f"unknown upgrade_type: {out['upgrade_type']}")
    return out


def new_candidate(**fields: Any) -> dict[str, Any]:
    return {
        "case_id": fields["case_id"],
        "problem": fields.get("problem") or "",
        "generalized_cause": fields.get("generalized_cause") or "",
        "proposed_change": fields.get("proposed_change") or "",
        "why_this_layer": fields.get("why_this_layer") or "",
        "affected_assets": list(fields.get("affected_assets") or []),
        "known_risks": list(fields.get("known_risks") or []),
        "alternatives_considered": list(fields.get("alternatives_considered") or []),
        "rollback_or_revert_hint": fields.get("rollback_or_revert_hint") or "",
        "upgrade_type": fields.get("upgrade_type") or "other",
    }


def empty_run(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "stage": "CANARY_1",
        "attempt": 0,
        "max_attempts": MAX_UPGRADE_ATTEMPTS,
        "before_result": None,
        "applied_change": None,
        "validation_steps": [],
        "one_case_result": None,
        "five_case_result": None,
        "target_result": None,
        "holdout_one_result": None,
        "holdout_five_result": None,
        "regression_result": None,
        "after_result": None,
        "metrics": {},
        "artifacts": [],
        "llm_called": False,
        "production_runtime_changed": False,
        "promoted": False,
    }
