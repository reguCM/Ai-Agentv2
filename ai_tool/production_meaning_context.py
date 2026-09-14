"""Deterministic execution view over Mission and Goal Handoff canonical records."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from ai_tool.dev_skill_pipeline import validate_handoff_packet
from ai_tool.goal_handoff_source_binding import validate_handoff_source_binding
from ai_tool.mission_memory.validate import validate_mission


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "registry"
    / "schema"
    / "meaning_context_v0.schema.json"
)


class MeaningContextError(ValueError):
    """Fail-closed error for invalid canonical inputs or identity binding."""


def canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_meaning_context(context: Mapping[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return sorted(
        error.message for error in Draft202012Validator(schema).iter_errors(dict(context))
    )


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in (value or []) if isinstance(row, Mapping)]


def resume_meaning_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    """Return the existing Meaning Context fields relevant to Run resume.

    This is a read-only projection, not another Meaning source of truth.  It
    deliberately excludes record-wide hashes and diagnostic completeness fields:
    those can change as Runtime state is persisted without changing the Human or
    Implementation Meaning that a Run is authorized to resume.
    """
    identity = context.get("identity") if isinstance(context.get("identity"), Mapping) else {}
    decisions = (
        context.get("decision_context")
        if isinstance(context.get("decision_context"), Mapping)
        else {}
    )
    human = context.get("human_meaning") if isinstance(context.get("human_meaning"), Mapping) else {}
    implementation = (
        context.get("implementation_meaning")
        if isinstance(context.get("implementation_meaning"), Mapping)
        else {}
    )
    return {
        "identity": {
            "mission_id": str(identity.get("mission_id") or ""),
            "handoff_id": str(identity.get("handoff_id") or ""),
            "binding_status": str(identity.get("binding_status") or ""),
            "requirement_ids": list(identity.get("requirement_ids") or []),
        },
        "human_meaning": dict(human),
        "decision_context": {
            "active_decisions": _mapping_rows(decisions.get("active_decisions")),
        },
        "implementation_meaning": dict(implementation),
    }


def build_meaning_context_v0(
    mission: Mapping[str, Any],
    handoff: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a stable snapshot without an LLM or semantic inference."""
    mission_record = dict(mission)
    handoff_packet = dict(handoff)
    mission_id = str(mission_record.get("mission_id") or "").strip()
    handoff_id = str(handoff_packet.get("handoff_id") or "").strip()
    original_goal = str(mission_record.get("original_goal") or "")
    handoff_errors = validate_handoff_packet(handoff_packet)
    mission_errors = validate_mission(mission_record).schema_errors
    if mission_errors:
        raise MeaningContextError("invalid_mission:" + ";".join(mission_errors))
    if handoff_errors:
        raise MeaningContextError("invalid_handoff:" + ";".join(handoff_errors))
    if not mission_id:
        raise MeaningContextError("missing_mission_id")
    if not handoff_id:
        raise MeaningContextError("missing_handoff_id")
    binding_errors = validate_handoff_source_binding(handoff_packet, mission_record)
    if binding_errors:
        raise MeaningContextError("invalid_source_binding:" + ";".join(binding_errors))

    requirements = _mapping_rows(mission_record.get("structured_requirements"))
    decisions = _mapping_rows(mission_record.get("confirmed_clarifications"))
    active_decisions = [
        row for row in decisions if str(row.get("status") or "confirmed") == "confirmed"
    ]
    active_by_id = {
        str(row.get("decision_id") or ""): row
        for row in active_decisions
        if str(row.get("decision_id") or "").strip()
    }
    tasks = _mapping_rows(handoff_packet.get("implementation_tasks"))
    premise_ids = {
        str(premise.get("derived_from_decision_id") or "")
        for task in tasks
        for premise in _mapping_rows(task.get("decision_premises"))
        if str(premise.get("derived_from_decision_id") or "").strip()
    }
    unresolved_premises = sorted(premise_ids - set(active_by_id))
    if unresolved_premises:
        raise MeaningContextError(
            "inactive_or_missing_decision_premises:" + ",".join(unresolved_premises)
        )

    missing: list[str] = []
    if not requirements:
        missing.append("human_meaning.structured_requirements")
    if not decisions:
        missing.append("decision_context.confirmed_clarifications")
    if any("revision" not in row for row in decisions):
        missing.append("decision_context.revision")
    if not any(task.get("maps_to_acceptance") for task in tasks):
        missing.append("implementation_meaning.task_acceptance_mapping")
    missing.extend(
        [
            "human_meaning.request_owner",
            "decision_context.decision_authority",
            "execution_context.execution_actor",
            "execution_context.allowed_capabilities",
            "execution_context.allowed_tools",
        ]
    )
    context = {
        "schema_version": "0",
        "kind": "execution_meaning_context",
        "status": "partial" if missing else "ready",
        "identity": {
            "mission_id": mission_id,
            "handoff_id": handoff_id,
            "mission_canonical_hash": canonical_hash(mission_record),
            "handoff_canonical_hash": canonical_hash(handoff_packet),
            "binding_status": "BOUND",
            "requirement_ids": list(
                (handoff_packet.get("source_binding") or {}).get("requirement_ids")
                or []
            ),
            "decision_ids": [str(row.get("decision_id") or "") for row in decisions],
            "task_ids": [str(row.get("id") or "") for row in tasks],
            "acceptance_ids": [
                str(row.get("id") or "")
                for row in _mapping_rows(handoff_packet.get("acceptance_criteria"))
            ],
        },
        "human_meaning": {
            "original_goal": original_goal,
            "structured_requirements": requirements,
            "explicit_conditions": list(mission_record.get("explicit_conditions") or []),
            "explicit_constraints": list(mission_record.get("explicit_constraints") or []),
        },
        "decision_context": {
            "confirmed_clarifications": decisions,
            "active_decisions": active_decisions,
        },
        "implementation_meaning": {
            "goal": dict(handoff_packet.get("goal") or {}),
            "scope": dict(handoff_packet.get("scope") or {}),
            "preconditions": _mapping_rows(handoff_packet.get("preconditions")),
            "implementation_tasks": tasks,
            "acceptance_criteria": _mapping_rows(handoff_packet.get("acceptance_criteria")),
            "test_plan": dict(handoff_packet.get("test_plan") or {}),
            "human_gates": list(handoff_packet.get("human_gates") or []),
            "runtime_boundary": dict(handoff_packet.get("runtime_boundary") or {}),
        },
        "missing": sorted(set(missing)),
    }
    errors = validate_meaning_context(context)
    if errors:
        raise MeaningContextError("invalid_meaning_context:" + ";".join(errors))
    return context


__all__ = [
    "MeaningContextError",
    "build_meaning_context_v0",
    "canonical_hash",
    "resume_meaning_projection",
    "validate_meaning_context",
]
