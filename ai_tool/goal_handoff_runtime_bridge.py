"""Minimal bridge: Goal Handoff implementation_tasks → Production Runtime TaskRecord."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ai_tool.dev_skill_pipeline import coerce_task_string_list
from ai_tool.human_decision_premise import (
    coerce_decision_premises,
    initialize_premise_validation,
    refresh_task_revalidation,
)
from ai_tool.production_verification_acceptance import (
    attach_handoff_verification_plan,
    maybe_add_test_run_closed,
    task_row_requires_pytest_verification,
)
from tools.ai.task_runtime import GoalNode, GoalStatus, TaskRecord, TaskStatus

HANDOFF_TASK_SOURCE = "goal_handoff"
ROOT_GOAL_ID = "G1"


def runtime_task_id(source_task_id: str) -> str:
    token = str(source_task_id or "").strip()
    if not token:
        raise ValueError("source_task_id is required")
    return f"gh-{token}"


def map_handoff_dependencies(
    dependencies: Sequence[Any] | None,
    *,
    known_source_ids: set[str],
) -> list[str]:
    mapped: list[str] = []
    for item in dependencies or []:
        source_id = str(item or "").strip()
        if not source_id:
            continue
        if source_id not in known_source_ids:
            continue
        runtime_id = runtime_task_id(source_id)
        if runtime_id not in mapped:
            mapped.append(runtime_id)
    return mapped


def _goal_completion_conditions(handoff_packet: Mapping[str, Any]) -> list[str]:
    rows = handoff_packet.get("acceptance_criteria") or []
    conditions: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        statement = str(row.get("statement") or "").strip()
        if statement:
            conditions.append(statement)
    if conditions:
        return conditions
    scope = handoff_packet.get("scope") or {}
    return [
        str(item).strip()
        for item in (scope.get("in_scope") or [])
        if str(item).strip()
    ]


def _task_instruction(
    *,
    title: str,
    acceptance: Sequence[str],
    verification: Sequence[str],
    handoff_packet: Mapping[str, Any],
) -> str:
    lines = [title.strip(), ""]
    if acceptance:
        lines.append("Acceptance:")
        lines.extend(f"- {item}" for item in acceptance)
        lines.append("")
    if verification:
        lines.append("Verification:")
        lines.extend(f"- {item}" for item in verification)
        lines.append("")
    affected = (handoff_packet.get("scope") or {}).get("affected_paths") or []
    if affected:
        lines.append("Affected paths:")
        lines.extend(f"- {item}" for item in affected)
    goal_summary = str((handoff_packet.get("goal") or {}).get("summary") or "").strip()
    if goal_summary:
        lines.extend(["", "Goal summary:", goal_summary])
    return "\n".join(lines).strip()


def build_handoff_task_records(
    handoff_packet: Mapping[str, Any],
) -> tuple[GoalNode, list[TaskRecord], str]:
    """Build root goal and TaskRecord rows from a validated handoff packet."""
    goal_summary = str((handoff_packet.get("goal") or {}).get("summary") or "").strip()
    if not goal_summary:
        goal_summary = "Implement goal handoff tasks"
    completion_conditions = _goal_completion_conditions(handoff_packet)
    root_goal = GoalNode(
        ROOT_GOAL_ID,
        goal_summary,
        completion_conditions=completion_conditions or ["all handoff tasks complete"],
        status=GoalStatus.IN_PROGRESS.value,
    )

    raw_tasks = [
        row for row in (handoff_packet.get("implementation_tasks") or []) if isinstance(row, Mapping)
    ]
    source_ids = {str(row.get("id") or "").strip() for row in raw_tasks if str(row.get("id") or "").strip()}
    records: list[TaskRecord] = []
    for row in raw_tasks:
        source_task_id = str(row.get("id") or "").strip()
        if not source_task_id:
            continue
        acceptance = coerce_task_string_list(row.get("acceptance"))
        verification = coerce_task_string_list(row.get("verification"))
        title = str(row.get("title") or source_task_id).strip()
        instruction = _task_instruction(
            title=title,
            acceptance=acceptance,
            verification=verification,
            handoff_packet=handoff_packet,
        )
        completion = list(dict.fromkeys([*acceptance, *verification]))
        if not completion:
            completion = completion_conditions[:1] or ["handoff task complete"]
        completion = maybe_add_test_run_closed(
            completion,
            required=task_row_requires_pytest_verification(row, handoff_packet),
        )
        records.append(
            TaskRecord(
                task_id=runtime_task_id(source_task_id),
                goal_id=ROOT_GOAL_ID,
                title=title,
                instruction=instruction,
                completion_conditions=completion,
                depends_on=map_handoff_dependencies(
                    row.get("dependencies"),
                    known_source_ids=source_ids,
                ),
                status=TaskStatus.PENDING.value,
                source=HANDOFF_TASK_SOURCE,
                source_task_id=source_task_id,
                decision_premises=[
                    initialize_premise_validation(premise)
                    for premise in coerce_decision_premises(row.get("decision_premises"))
                ],
            )
        )

    if not records:
        raise ValueError("handoff packet has no implementation_tasks")

    first_runnable = _first_runnable_task_id(records)
    for record in records:
        if record.task_id == first_runnable:
            record.status = TaskStatus.IN_PROGRESS.value
    return root_goal, records, first_runnable


def _first_runnable_task_id(records: Sequence[TaskRecord]) -> str:
    by_id = {record.task_id: record for record in records}
    for record in records:
        deps = record.depends_on or []
        if all(by_id[dep].status == TaskStatus.COMPLETE.value for dep in deps if dep in by_id):
            return record.task_id
    return records[0].task_id


def build_handoff_acceptance_projection(
    handoff_packet: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Canonical acceptance rows (A*) without copying the full handoff packet."""
    rows: list[dict[str, str]] = []
    for row in handoff_packet.get("acceptance_criteria") or []:
        if not isinstance(row, Mapping):
            continue
        acceptance_id = str(row.get("id") or "").strip()
        if not acceptance_id:
            continue
        rows.append(
            {
                "acceptance_id": acceptance_id,
                "statement": str(row.get("statement") or "").strip(),
                "verification": str(row.get("verification") or "").strip(),
            }
        )
    return rows


def build_handoff_task_acceptance_mapping(
    handoff_packet: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Source T* → runtime gh-T* with maps_to_acceptance as declared in the packet."""
    mapping: list[dict[str, Any]] = []
    for row in handoff_packet.get("implementation_tasks") or []:
        if not isinstance(row, Mapping):
            continue
        source_task_id = str(row.get("id") or "").strip()
        if not source_task_id:
            continue
        maps_to_acceptance = [
            str(item).strip()
            for item in (row.get("maps_to_acceptance") or [])
            if str(item).strip()
        ]
        mapping.append(
            {
                "source_task_id": source_task_id,
                "runtime_task_id": runtime_task_id(source_task_id),
                "maps_to_acceptance": maps_to_acceptance,
            }
        )
    return mapping


def build_handoff_acceptance_runtime_trace(orchestrator: Any) -> list[dict[str, Any]]:
    """READ-ONLY: A* → statement → mapped runtime tasks (from maps_to_acceptance only)."""
    acceptance_rows = list(getattr(orchestrator, "handoff_acceptance_projection", None) or [])
    task_maps = list(getattr(orchestrator, "handoff_task_acceptance_mapping", None) or [])
    runtime_by_acceptance: dict[str, list[str]] = {}
    for item in task_maps:
        runtime_task_id_value = str(item.get("runtime_task_id") or "").strip()
        if not runtime_task_id_value:
            continue
        for acceptance_id in item.get("maps_to_acceptance") or []:
            token = str(acceptance_id or "").strip()
            if not token:
                continue
            refs = runtime_by_acceptance.setdefault(token, [])
            if runtime_task_id_value not in refs:
                refs.append(runtime_task_id_value)
    tasks = getattr(getattr(orchestrator, "runtime", None), "tasks", None) or {}
    trace: list[dict[str, Any]] = []
    for row in acceptance_rows:
        acceptance_id = str(row.get("acceptance_id") or "").strip()
        mapped: list[dict[str, Any]] = []
        for task_id in runtime_by_acceptance.get(acceptance_id, []):
            task = tasks.get(task_id)
            if task is None:
                mapped.append({"runtime_task_id": task_id})
                continue
            mapped.append(
                {
                    "runtime_task_id": task_id,
                    "source_task_id": str(getattr(task, "source_task_id", "") or "") or None,
                    "status": str(getattr(task, "status", "") or ""),
                }
            )
        trace.append(
            {
                "acceptance_id": acceptance_id,
                "statement": str(row.get("statement") or ""),
                "verification": str(row.get("verification") or ""),
                "mapped_runtime_tasks": mapped,
            }
        )
    return trace


def attach_handoff_identity_traceability(
    orchestrator: Any,
    handoff_packet: Mapping[str, Any],
) -> None:
    orchestrator.handoff_acceptance_projection = build_handoff_acceptance_projection(
        handoff_packet
    )
    orchestrator.handoff_task_acceptance_mapping = build_handoff_task_acceptance_mapping(
        handoff_packet
    )


def seed_orchestrator_from_handoff(orchestrator: Any, handoff_packet: Mapping[str, Any]) -> None:
    root_goal, records, first_task_id = build_handoff_task_records(handoff_packet)
    orchestrator.runtime.goals.clear()
    orchestrator.runtime.tasks.clear()
    orchestrator.runtime.add_goal(root_goal)
    for record in records:
        orchestrator.runtime.add_task(record)
    orchestrator.current_goal_id = ROOT_GOAL_ID
    orchestrator.current_task_id = first_task_id
    attach_handoff_identity_traceability(orchestrator, handoff_packet)
    attach_handoff_verification_plan(orchestrator, handoff_packet)
    refresh_task_revalidation(orchestrator)


def prepare_orchestrator_from_handoff(
    orchestrator: Any,
    handoff_packet: Mapping[str, Any],
) -> None:
    """Convert a handoff to Runtime records without starting task execution."""
    root_goal, records, first_task_id = build_handoff_task_records(handoff_packet)
    for record in records:
        record.status = TaskStatus.PENDING.value
    orchestrator.runtime.goals.clear()
    orchestrator.runtime.tasks.clear()
    orchestrator.runtime.add_goal(root_goal)
    for record in records:
        orchestrator.runtime.add_task(record)
    orchestrator.current_goal_id = ROOT_GOAL_ID
    orchestrator.current_task_id = first_task_id
    attach_handoff_identity_traceability(orchestrator, handoff_packet)
    refresh_task_revalidation(orchestrator)


__all__ = [
    "HANDOFF_TASK_SOURCE",
    "ROOT_GOAL_ID",
    "attach_handoff_identity_traceability",
    "build_handoff_acceptance_projection",
    "build_handoff_acceptance_runtime_trace",
    "build_handoff_task_acceptance_mapping",
    "build_handoff_task_records",
    "map_handoff_dependencies",
    "prepare_orchestrator_from_handoff",
    "runtime_task_id",
    "seed_orchestrator_from_handoff",
]
