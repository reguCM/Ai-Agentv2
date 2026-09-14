"""Minimal immutable-at-start contract for one Production Runtime continuation."""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.human_decision_premise import active_decision_id_for_key
from ai_tool.production_meaning_context import canonical_hash, resume_meaning_projection


REQUIRED_FIELDS = {
    "started_execution_id",
    "mission_id",
    "requirement_ids",
    "handoff_id",
    "handoff_canonical_hash",
    "starting_task_id",
    "meaning_context",
    "meaning_context_hash",
    "decision_premises",
}


def _decision_premises(
    mission: Mapping[str, Any], handoff: Mapping[str, Any]
) -> list[dict[str, str]]:
    clarifications = [
        dict(row)
        for row in (mission.get("confirmed_clarifications") or [])
        if isinstance(row, Mapping)
    ]
    rows: dict[str, dict[str, str]] = {}
    for task in handoff.get("implementation_tasks") or []:
        if not isinstance(task, Mapping):
            continue
        for premise in task.get("decision_premises") or []:
            if not isinstance(premise, Mapping):
                continue
            key = str(premise.get("decision_key") or "").strip()
            if not key:
                continue
            active_id = active_decision_id_for_key(clarifications, key) or ""
            validated_id = str(
                premise.get("validated_against_decision_id")
                or premise.get("derived_from_decision_id")
                or ""
            ).strip()
            rows[key] = {
                "decision_key": key,
                "active_decision_id": active_id,
                "validated_against_decision_id": validated_id,
            }
    return [rows[key] for key in sorted(rows)]


def build_production_run_contract(
    *,
    started_execution_id: str,
    mission: Mapping[str, Any],
    handoff: Mapping[str, Any],
    meaning_context: Mapping[str, Any],
    starting_task_id: str,
    handoff_canonical_hash: str,
) -> dict[str, Any]:
    """Build a Session-carried reference/snapshot bundle without new meaning."""
    binding = handoff.get("source_binding") or {}
    return {
        "started_execution_id": str(started_execution_id or "").strip(),
        "mission_id": str(mission.get("mission_id") or "").strip(),
        "requirement_ids": list(binding.get("requirement_ids") or []),
        "handoff_id": str(handoff.get("handoff_id") or "").strip(),
        "handoff_canonical_hash": str(handoff_canonical_hash or "").strip(),
        "starting_task_id": str(starting_task_id or "").strip(),
        "meaning_context": dict(meaning_context),
        "meaning_context_hash": canonical_hash(resume_meaning_projection(meaning_context)),
        "decision_premises": _decision_premises(mission, handoff),
    }


def validate_production_run_contract(
    contract: Mapping[str, Any] | None,
    *,
    mission: Mapping[str, Any],
    handoff: Mapping[str, Any],
    meaning_context: Mapping[str, Any],
    handoff_canonical_hash: str,
    runtime_snapshot: Mapping[str, Any] | None = None,
) -> list[str]:
    """Compare the immutable start contract with current canonical inputs."""
    if not isinstance(contract, Mapping):
        return ["missing_run_contract"]
    errors: list[str] = []
    missing = sorted(field for field in REQUIRED_FIELDS if field not in contract)
    if missing:
        errors.extend(f"missing_run_contract_field:{field}" for field in missing)
        return errors
    if not str(contract.get("started_execution_id") or "").strip():
        errors.append("invalid_started_execution_id")
    if str(contract.get("mission_id") or "") != str(mission.get("mission_id") or ""):
        errors.append("run_contract_mission_mismatch")
    current_ids = list((handoff.get("source_binding") or {}).get("requirement_ids") or [])
    if list(contract.get("requirement_ids") or []) != current_ids:
        errors.append("run_contract_requirement_mismatch")
    if str(contract.get("handoff_id") or "") != str(handoff.get("handoff_id") or ""):
        errors.append("run_contract_handoff_id_mismatch")
    if str(contract.get("handoff_canonical_hash") or "") != str(handoff_canonical_hash or ""):
        errors.append("run_contract_handoff_hash_mismatch")
    stored_meaning = contract.get("meaning_context")
    if not isinstance(stored_meaning, Mapping):
        errors.append("invalid_run_contract_meaning_context")
    elif str(contract.get("meaning_context_hash") or "") != canonical_hash(
        resume_meaning_projection(stored_meaning)
    ):
        errors.append("run_contract_meaning_snapshot_tampered")
    elif str(contract.get("meaning_context_hash") or "") != canonical_hash(
        resume_meaning_projection(meaning_context)
    ):
        errors.append("run_contract_meaning_mismatch")
    if list(contract.get("decision_premises") or []) != _decision_premises(mission, handoff):
        errors.append("run_contract_decision_premise_mismatch")
    if isinstance(runtime_snapshot, Mapping):
        task_ids = {
            str(row.get("task_id") or "")
            for row in (runtime_snapshot.get("tasks") or [])
            if isinstance(row, Mapping)
        }
        if str(contract.get("starting_task_id") or "") not in task_ids:
            errors.append("run_contract_starting_task_missing")
    return errors


__all__ = [
    "build_production_run_contract",
    "validate_production_run_contract",
]
