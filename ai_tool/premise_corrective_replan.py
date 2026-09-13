"""Additive corrective replan for complete tasks after premise revalidation.

Only complete tasks with needs_revision / invalid outcomes receive corrective
follow-up tasks. Pending / in-progress stale tasks are execution-blocked instead.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ai_tool.human_decision_premise import (
    active_decision_catalog,
    initialize_premise_validation,
    resolve_task_premise_selection,
    task_decision_premises,
)
from tools.ai.task_runtime import ReplanRecord, TaskRecord, TaskStatus

PREMISE_CORRECTIVE_SOURCE = "premise_corrective_replan"
PREMISE_CORRECTIVE_OUTCOMES = frozenset({"needs_revision", "invalid"})
PREMISE_EXECUTION_BLOCK_OUTCOMES = frozenset(
    PREMISE_CORRECTIVE_OUTCOMES | {"cannot_determine"}
)
_NON_EXECUTABLE_STATUSES = frozenset(
    {
        TaskStatus.PENDING.value,
        TaskStatus.IN_PROGRESS.value,
    }
)


class PremiseRevalidationExecutionBlockedError(RuntimeError):
    """Raised when a non-complete task must not execute under stale premises."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        super().__init__(str(payload.get("reason") or "premise_revalidation_execution_blocked"))
        self.payload = dict(payload)


def premise_revalidation_outcome(task: Any) -> str | None:
    metadata = getattr(task, "revalidation", None)
    if isinstance(task, Mapping):
        metadata = task.get("revalidation")
    if not isinstance(metadata, Mapping):
        return None
    premise_rev = metadata.get("premise_revalidation")
    if not isinstance(premise_rev, Mapping):
        return None
    outcome = str(premise_rev.get("outcome") or "").strip()
    return outcome or None


def premise_revalidation_blocks_task_execution(task: Any) -> dict[str, Any] | None:
    """Block execution for pending/in-progress tasks with stale premise outcomes."""
    status = str(getattr(task, "status", "") or "")
    if status not in _NON_EXECUTABLE_STATUSES:
        return None
    outcome = premise_revalidation_outcome(task)
    if outcome not in PREMISE_EXECUTION_BLOCK_OUTCOMES:
        return None
    task_id = str(getattr(task, "task_id", "") or "")
    metadata = getattr(task, "revalidation", None) or {}
    if isinstance(task, Mapping):
        task_id = str(task.get("task_id") or task_id)
        metadata = task.get("revalidation") or {}
    premise_rev = dict((metadata or {}).get("premise_revalidation") or {})
    return {
        "task_id": task_id,
        "task_status": status,
        "outcome": outcome,
        "reason": premise_rev.get("reason"),
    }


def premise_revalidation_blocks_goal_completion(orchestrator: Any) -> dict[str, Any] | None:
    """Block goal completion while non-complete tasks remain premise-blocked."""
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return None
    blocked: list[dict[str, Any]] = []
    for task in (getattr(runtime, "tasks", None) or {}).values():
        status = str(getattr(task, "status", "") or "")
        if status in {TaskStatus.COMPLETE.value, TaskStatus.CANCELLED.value}:
            continue
        block = premise_revalidation_blocks_task_execution(task)
        if block is not None:
            blocked.append(block)
    if not blocked:
        return None
    return {
        "reason": "premise_revalidation_unresolved",
        "blocked_tasks": blocked,
    }


def _runtime_tasks(orchestrator: Any) -> dict[str, Any]:
    runtime = getattr(orchestrator, "runtime", None)
    return getattr(runtime, "tasks", None) or {}


def _corrective_task_exists(runtime: Any, source_task_id: str) -> bool:
    for task in (getattr(runtime, "tasks", None) or {}).values():
        if str(getattr(task, "source_task_id", "") or "") != source_task_id:
            continue
        if str(getattr(task, "source", "") or "") == PREMISE_CORRECTIVE_SOURCE:
            return True
    return False


def _semantic_premise_decision_keys(source_task: Any) -> list[str]:
    """Semantic decision_keys the source task depends on (ids are not copied)."""
    keys: list[str] = []
    for row in task_decision_premises(source_task):
        decision_key = str(row.get("decision_key") or "").strip()
        if decision_key and decision_key not in keys:
            keys.append(decision_key)
    return keys


def build_corrective_decision_premises(
    orchestrator: Any,
    source_task: Any,
) -> list[dict[str, str]]:
    """Resolve semantic premise keys to current active Human Decisions (handoff pattern)."""
    clarifications = getattr(orchestrator, "confirmed_clarifications", None) or []
    catalog = active_decision_catalog(clarifications)
    premise_keys = _semantic_premise_decision_keys(source_task)
    if not premise_keys:
        return []
    task_id = str(getattr(source_task, "task_id", "") or "corrective")
    premises, _errors = resolve_task_premise_selection(
        {"id": task_id, "premise_decision_keys": premise_keys},
        catalog,
    )
    return [initialize_premise_validation(premise) for premise in premises]


def functional_depends_on(source_task: Any, exclude_task_id: str) -> list[str]:
    """Execution dependencies only; lineage fields are separate from depends_on."""
    deps: list[str] = []
    for item in getattr(source_task, "depends_on", None) or []:
        dep_id = str(item or "").strip()
        if not dep_id or dep_id == exclude_task_id:
            continue
        if dep_id not in deps:
            deps.append(dep_id)
    return deps


def _next_runtime_task_id(orchestrator: Any) -> str:
    return f"T{len(_runtime_tasks(orchestrator)) + 1}"


def build_premise_corrective_task(
    orchestrator: Any,
    source_task_id: str,
    *,
    outcome: str,
    reason: str | None = None,
) -> TaskRecord | None:
    source = _runtime_tasks(orchestrator).get(source_task_id)
    if source is None:
        return None
    if str(getattr(source, "status", "") or "") != TaskStatus.COMPLETE.value:
        return None
    if outcome not in PREMISE_CORRECTIVE_OUTCOMES:
        return None
    runtime = orchestrator.runtime
    if _corrective_task_exists(runtime, source_task_id):
        return None

    depends_on = functional_depends_on(source, source_task_id)
    title = f"Corrective replan for {source_task_id}"
    reason_text = str(reason or "").strip()
    instruction_lines = [
        f"Corrective replacement for completed task {source_task_id}.",
        f"Premise revalidation outcome: {outcome}.",
    ]
    if reason_text:
        instruction_lines.append(f"Reason: {reason_text}")
    instruction_lines.extend(
        [
            "",
            "Original task instruction:",
            str(getattr(source, "instruction", "") or getattr(source, "title", "") or "").strip(),
        ]
    )
    instruction = "\n".join(line for line in instruction_lines if line is not None).strip()
    completion = [
        str(item).strip()
        for item in (getattr(source, "completion_conditions", None) or [])
        if str(item).strip()
    ]
    if not completion:
        completion = ["corrective task complete"]

    return TaskRecord(
        task_id=_next_runtime_task_id(orchestrator),
        goal_id=str(getattr(source, "goal_id", "") or orchestrator.current_goal_id),
        title=title,
        instruction=instruction,
        completion_conditions=completion,
        depends_on=depends_on,
        status=TaskStatus.PENDING.value,
        source=PREMISE_CORRECTIVE_SOURCE,
        source_task_id=source_task_id,
        decision_premises=build_corrective_decision_premises(orchestrator, source),
    )


def add_premise_corrective_replan(
    orchestrator: Any,
    source_task_id: str,
    *,
    outcome: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """Add one corrective task for a complete source task. Does not mutate the source."""
    task = build_premise_corrective_task(
        orchestrator,
        source_task_id,
        outcome=outcome,
        reason=reason,
    )
    if task is None:
        return None
    source = _runtime_tasks(orchestrator)[source_task_id]
    runtime = orchestrator.runtime
    from ai_tool.premise_pending_replacement import (
        downstream_dependent_task_ids,
        redirect_depends_on,
    )
    dependents = downstream_dependent_task_ids(runtime, source_task_id)
    redirected = redirect_depends_on(runtime, source_task_id, task.task_id)
    replan = ReplanRecord(
        f"R{len(runtime.replans) + 1}",
        str(getattr(source, "goal_id", "") or orchestrator.current_goal_id),
        f"premise_corrective:{outcome}:{source_task_id}",
    )
    runtime.replan_add_task(replan, task)
    from ai_tool.human_decision_premise import refresh_task_revalidation

    refresh_task_revalidation(orchestrator)
    return {
        "source_task_id": source_task_id,
        "corrective_task_id": task.task_id,
        "outcome": outcome,
        "reason": reason,
        "depends_on": list(task.depends_on),
        "decision_premises": list(task.decision_premises),
        "redirected_dependents": redirected,
        "downstream_task_ids": dependents,
        "old_upstream_task_id": source_task_id,
        "new_upstream_task_id": task.task_id,
        "replan_id": replan.replan_id,
    }


def run_premise_corrective_replans(
    orchestrator: Any,
    revalidation_results: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Create corrective tasks only for complete tasks with needs_revision / invalid."""
    applied: list[dict[str, Any]] = []
    rows = list(revalidation_results or [])
    if not rows:
        runtime = getattr(orchestrator, "runtime", None)
        for task_id, task in (getattr(runtime, "tasks", None) or {}).items():
            outcome = premise_revalidation_outcome(task)
            if outcome in PREMISE_CORRECTIVE_OUTCOMES:
                rows.append(
                    {
                        "task_id": str(task_id),
                        "outcome": outcome,
                        "reason": (
                            (getattr(task, "revalidation", None) or {})
                            .get("premise_revalidation", {})
                            .get("reason")
                        ),
                    }
                )
    for row in rows:
        task_id = str(row.get("task_id") or "").strip()
        outcome = str(row.get("outcome") or "").strip()
        if not task_id or outcome not in PREMISE_CORRECTIVE_OUTCOMES:
            continue
        task = _runtime_tasks(orchestrator).get(task_id)
        if task is None:
            continue
        if str(getattr(task, "status", "") or "") != TaskStatus.COMPLETE.value:
            continue
        result = add_premise_corrective_replan(
            orchestrator,
            task_id,
            outcome=outcome,
            reason=str(row.get("reason") or "").strip() or None,
        )
        if result is not None:
            applied.append(result)
    if applied:
        from ai_tool.chat_interface.goal_continuation_resume import advance_to_open_task

        advance_to_open_task(orchestrator)
    return applied


__all__ = [
    "PREMISE_CORRECTIVE_OUTCOMES",
    "PREMISE_CORRECTIVE_SOURCE",
    "PREMISE_EXECUTION_BLOCK_OUTCOMES",
    "PremiseRevalidationExecutionBlockedError",
    "add_premise_corrective_replan",
    "build_corrective_decision_premises",
    "build_premise_corrective_task",
    "functional_depends_on",
    "premise_revalidation_blocks_goal_completion",
    "premise_revalidation_blocks_task_execution",
    "premise_revalidation_outcome",
    "run_premise_corrective_replans",
]
