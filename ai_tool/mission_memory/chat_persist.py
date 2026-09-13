"""Write Mission / Execution / Evidence at the end of one Chat Agent execution.

Pointer placement (Session vs Grill packet) is not decided. Grill packet may
carry mission_id as a resume reference ID only. This is not Chat Session memory.
"""
from __future__ import annotations

from typing import Any

from ai_tool.mission_memory.ids import (
    new_execution_id,
    new_mission_id,
    new_persistent_evidence_id,
)
from ai_tool.mission_memory.clarifications import clarifications_for_mission_store
from ai_tool.mission_memory.task_runtime import completion_runtime_for_mission_store
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version

_PAUSED_STOP_REASONS = {"HUMAN_GRILL", "APPROVAL_REQUIRED"}


def bind_execution_identity(
    orchestrator: Any,
    *,
    resume_mission_id: str | None = None,
    new_execution: bool = True,
) -> None:
    """Mint IDs at Agent execution start. Keep mission_id when resuming."""
    if resume_mission_id:
        orchestrator.mission_id = str(resume_mission_id)
    if not str(getattr(orchestrator, "mission_id", "") or ""):
        orchestrator.mission_id = new_mission_id()
    if new_execution or not str(getattr(orchestrator, "execution_id", "") or ""):
        orchestrator.execution_id = new_execution_id()
    if getattr(orchestrator, "persistent_evidence_ids", None) is None:
        orchestrator.persistent_evidence_ids = {}


def persist_chat_execution(
    orchestrator: Any,
    *,
    stop_reason: str,
    determined: bool,
    answer: str,
    correlation_id: str | None = None,
    store: MissionMemoryStore | None = None,
    extra_evidence_refs: list[str] | None = None,
    execution_end_state: str | None = None,
    goal_achievement_performed: bool | None = None,
    goal_achievement_result: str | None = None,
) -> dict[str, Any]:
    """Persist one execution. Does not search the store to guess the mission."""
    if goal_achievement_performed is None:
        from ai_tool.production_verification_acceptance import resolve_mission_achievement

        resolved = resolve_mission_achievement(
            orchestrator,
            final_answer=answer,
        )
        if resolved and resolved.get("goal_achievement_performed"):
            goal_achievement_performed = True
            goal_achievement_result = str(resolved.get("goal_achievement_result") or "PASS")
            if execution_end_state is None:
                execution_end_state = str(resolved.get("execution_end_state") or "achieved")
    bind_execution_identity(orchestrator, new_execution=False)
    memory = store or MissionMemoryStore.from_default()
    mission_id = str(orchestrator.mission_id)
    execution_id = str(orchestrator.execution_id)
    mapping: dict[str, str] = dict(getattr(orchestrator, "persistent_evidence_ids", {}) or {})
    orchestrator.persistent_evidence_ids = mapping

    supplements = _human_supplements(orchestrator)
    extra_conditions = [
        str(item)
        for item in (getattr(orchestrator, "user_explicit_conditions", None) or [])
        if str(item)
    ]
    runtime_snapshot = completion_runtime_for_mission_store(orchestrator)
    existing = memory.get_mission(mission_id)
    if existing is None:
        mission_record: dict[str, Any] = {
            "schema_version": schema_version(),
            "mission_id": mission_id,
            "original_goal": str(orchestrator.request or ""),
            "explicit_conditions": extra_conditions,
            "explicit_constraints": [],
            "user_confirmed_supplements": supplements,
            "confirmed_clarifications": clarifications_for_mission_store(orchestrator),
        }
        structured = getattr(orchestrator, "structured_requirements", None)
        if structured is not None:
            mission_record["structured_requirements"] = list(structured)
        phase = getattr(orchestrator, "requirement_resolution_phase", None)
        if phase:
            mission_record["requirement_resolution_phase"] = str(phase)
        projected_constraints = getattr(orchestrator, "projected_explicit_constraints", None)
        if projected_constraints:
            mission_record["explicit_constraints"] = list(projected_constraints)
        if runtime_snapshot is not None:
            mission_record["completion_runtime"] = runtime_snapshot
        memory.put_mission(mission_record)
    else:
        merged_supplements = list(existing.get("user_confirmed_supplements") or [])
        have = {str(item.get("text") or "") for item in merged_supplements if isinstance(item, dict)}
        for item in supplements:
            if item["text"] not in have:
                merged_supplements.append(item)
                have.add(item["text"])
        merged_conditions = list(existing.get("explicit_conditions") or [])
        for item in extra_conditions:
            if item not in merged_conditions:
                merged_conditions.append(item)
        updated = dict(existing)
        updated["user_confirmed_supplements"] = merged_supplements
        updated["explicit_conditions"] = merged_conditions
        updated["confirmed_clarifications"] = clarifications_for_mission_store(orchestrator)
        structured = getattr(orchestrator, "structured_requirements", None)
        if structured is not None:
            updated["structured_requirements"] = list(structured)
        phase = getattr(orchestrator, "requirement_resolution_phase", None)
        if phase:
            updated["requirement_resolution_phase"] = str(phase)
        projected_constraints = getattr(orchestrator, "projected_explicit_constraints", None)
        if projected_constraints:
            merged_constraints = list(updated.get("explicit_constraints") or [])
            for item in projected_constraints:
                if item not in merged_constraints:
                    merged_constraints.append(item)
            updated["explicit_constraints"] = merged_constraints
        if runtime_snapshot is not None:
            updated["completion_runtime"] = runtime_snapshot
        memory.put_mission(updated)

    evidence_refs: list[str] = []
    created_evidence: list[str] = []
    for record in (orchestrator.runtime.evidence or {}).values():
        runtime_id = str(getattr(record, "evidence_id", "") or "")
        persistent_id = mapping.get(runtime_id)
        if persistent_id and memory.get_evidence(persistent_id) is None:
            mapping.pop(runtime_id, None)
            persistent_id = None
        if persistent_id:
            if persistent_id not in evidence_refs:
                evidence_refs.append(persistent_id)
            continue
        persistent_id = new_persistent_evidence_id()
        source_type = str(getattr(record, "source_type", "") or "unknown")
        observed_at = str(getattr(record, "created_at", "") or "").strip() or "unknown"
        memory.put_evidence(
            {
                "schema_version": schema_version(),
                "persistent_evidence_id": persistent_id,
                "created_in_mission_id": mission_id,
                "created_by_execution_id": execution_id,
                "source_type": source_type,
                "source": str(getattr(record, "source", "") or ""),
                "summary": str(getattr(record, "summary", "") or ""),
                "observed_at": observed_at,
            }
        )
        mapping[runtime_id] = persistent_id
        evidence_refs.append(persistent_id)
        created_evidence.append(persistent_id)

    for ref in extra_evidence_refs or []:
        item = str(ref or "")
        if item and item not in evidence_refs:
            evidence_refs.append(item)

    judged = bool(execution_end_state)
    performed = (
        bool(goal_achievement_performed)
        if goal_achievement_performed is not None
        else False
    )
    execution: dict[str, Any] = {
        "schema_version": schema_version(),
        "execution_id": execution_id,
        "mission_id": mission_id,
        "execution_sequence": memory.next_execution_sequence(mission_id),
        "result_determination": "determined" if determined else "undetermined",
        "execution_end_state_judgment": (
            "judged"
            if judged
            or (determined and stop_reason in _PAUSED_STOP_REASONS)
            else "not_judged"
        ),
        "goal_achievement_performed": performed,
        "stop_reason": str(stop_reason or "UNKNOWN"),
        "unresolved_items": [],
        "evidence_refs": evidence_refs,
    }
    if determined:
        execution["determined_result"] = str(answer or "")
    if execution["execution_end_state_judgment"] == "judged":
        execution["execution_end_state"] = str(
            execution_end_state or "paused"
        )
    if performed:
        execution["goal_achievement_result"] = str(goal_achievement_result or "")
    if correlation_id:
        execution["correlation_id"] = str(correlation_id)
    memory.put_execution(execution)
    return {
        "ok": True,
        "mission_id": mission_id,
        "execution_id": execution_id,
        "execution_sequence": execution["execution_sequence"],
        "result_determination": execution["result_determination"],
        "execution_end_state_judgment": execution["execution_end_state_judgment"],
        "execution_end_state": execution.get("execution_end_state"),
        "goal_achievement_performed": execution["goal_achievement_performed"],
        "new_evidence_ids": created_evidence,
        "evidence_refs": list(evidence_refs),
    }


def _human_supplements(orchestrator: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in getattr(orchestrator, "confirmed_clarifications", None) or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "confirmed") == "superseded":
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        source = str(row.get("source") or "grill")
        if source == "boundary_grill":
            mapped_source = "boundary_grill"
        else:
            mapped_source = "grill"
        dedupe_key = str(row.get("decision_id") or f"{mapped_source}:{text}")
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        payload: dict[str, Any] = {"text": text, "source": mapped_source}
        decision_id = str(row.get("decision_id") or "").strip()
        decision_key = str(row.get("decision_key") or "").strip()
        if decision_id:
            payload["decision_id"] = decision_id
        if decision_key:
            payload["decision_key"] = decision_key
        status = str(row.get("status") or "confirmed").strip()
        if status:
            payload["status"] = status
        supersedes = str(row.get("supersedes") or "").strip()
        if supersedes:
            payload["supersedes"] = supersedes
        dimension = str(row.get("dimension") or "").strip()
        if dimension:
            payload["dimension"] = dimension
        items.append(payload)
    for row in getattr(orchestrator, "goal_completion_supplements", None) or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append({"text": text, "source": "goal_completion"})
    return items
