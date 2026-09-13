"""Supersede pending tasks after premise revalidation without destroying history."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ai_tool.premise_corrective_replan import (
    PREMISE_CORRECTIVE_OUTCOMES,
    build_corrective_decision_premises,
    functional_depends_on,
    premise_revalidation_outcome,
)
from tools.ai.task_runtime import ReplanRecord, TaskRecord, TaskStatus

PREMISE_PENDING_REPLACEMENT_SOURCE = "premise_pending_replacement"


def _runtime_tasks(orchestrator: Any) -> dict[str, Any]:
    runtime = getattr(orchestrator, "runtime", None)
    return getattr(runtime, "tasks", None) or {}


def _next_runtime_task_id(orchestrator: Any) -> str:
    return f"T{len(_runtime_tasks(orchestrator)) + 1}"


def downstream_dependent_task_ids(runtime: Any, task_id: str) -> list[str]:
    dependents: list[str] = []
    token = str(task_id or "").strip()
    if not token:
        return dependents
    for candidate_id, task in (getattr(runtime, "tasks", None) or {}).items():
        deps = [str(dep).strip() for dep in (getattr(task, "depends_on", None) or []) if str(dep).strip()]
        if token in deps and str(candidate_id) not in dependents:
            dependents.append(str(candidate_id))
    return dependents


def redirect_depends_on(runtime: Any, old_task_id: str, new_task_id: str) -> list[str]:
    """Rewrite depends_on references from a superseded task to its replacement."""
    updated: list[str] = []
    old_id = str(old_task_id or "").strip()
    new_id = str(new_task_id or "").strip()
    if not old_id or not new_id or old_id == new_id:
        return updated
    for task_id, task in (getattr(runtime, "tasks", None) or {}).items():
        deps = list(getattr(task, "depends_on", None) or [])
        if old_id not in deps:
            continue
        rewritten: list[str] = []
        for dep in deps:
            dep_id = str(dep or "").strip()
            if not dep_id:
                continue
            if dep_id == old_id:
                if new_id not in rewritten:
                    rewritten.append(new_id)
                continue
            if dep_id not in rewritten:
                rewritten.append(dep_id)
        task.depends_on = rewritten
        updated.append(str(task_id))
    return updated


def _pending_replacement_exists(runtime: Any, source_task_id: str) -> bool:
    for task in (getattr(runtime, "tasks", None) or {}).values():
        if str(getattr(task, "supersedes_task_id", "") or "") == source_task_id:
            return True
        if (
            str(getattr(task, "source", "") or "") == PREMISE_PENDING_REPLACEMENT_SOURCE
            and str(getattr(task, "source_task_id", "") or "") == source_task_id
        ):
            return True
    return False


def build_pending_replacement_task(
    orchestrator: Any,
    source_task_id: str,
    *,
    outcome: str,
    reason: str | None = None,
) -> TaskRecord | None:
    source = _runtime_tasks(orchestrator).get(source_task_id)
    if source is None:
        return None
    if str(getattr(source, "status", "") or "") != TaskStatus.PENDING.value:
        return None
    if outcome not in PREMISE_CORRECTIVE_OUTCOMES:
        return None
    if _pending_replacement_exists(orchestrator.runtime, source_task_id):
        return None

    depends_on = functional_depends_on(source, source_task_id)
    original_title = str(getattr(source, "title", "") or source_task_id).strip()
    title = f"Replacement: {original_title}"
    reason_text = str(reason or "").strip()
    instruction_lines = [
        f"Replacement for superseded pending task {source_task_id}.",
        f"Premise revalidation outcome: {outcome}.",
    ]
    if reason_text:
        instruction_lines.append(f"Reason: {reason_text}")
    instruction_lines.extend(
        [
            "",
            "Original task instruction:",
            str(getattr(source, "instruction", "") or original_title).strip(),
        ]
    )
    instruction = "\n".join(line for line in instruction_lines if line is not None).strip()
    completion = [
        str(item).strip()
        for item in (getattr(source, "completion_conditions", None) or [])
        if str(item).strip()
    ]
    if not completion:
        completion = ["replacement task complete"]

    return TaskRecord(
        task_id=_next_runtime_task_id(orchestrator),
        goal_id=str(getattr(source, "goal_id", "") or orchestrator.current_goal_id),
        title=title,
        instruction=instruction,
        completion_conditions=completion,
        depends_on=depends_on,
        status=TaskStatus.PENDING.value,
        source=PREMISE_PENDING_REPLACEMENT_SOURCE,
        source_task_id=source_task_id,
        supersedes_task_id=source_task_id,
        decision_premises=build_corrective_decision_premises(orchestrator, source),
    )


def add_pending_replacement(
    orchestrator: Any,
    source_task_id: str,
    *,
    outcome: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """Supersede one pending task with a replacement and redirect downstream depends_on."""
    replacement = build_pending_replacement_task(
        orchestrator,
        source_task_id,
        outcome=outcome,
        reason=reason,
    )
    if replacement is None:
        return None

    runtime = orchestrator.runtime
    source = _runtime_tasks(orchestrator)[source_task_id]
    dependents = downstream_dependent_task_ids(runtime, source_task_id)
    redirected = redirect_depends_on(runtime, source_task_id, replacement.task_id)
    replan = ReplanRecord(
        f"R{len(runtime.replans) + 1}",
        str(getattr(source, "goal_id", "") or orchestrator.current_goal_id),
        f"premise_pending_replacement:{outcome}:{source_task_id}",
    )
    runtime.replan_add_task(replan, replacement)

    source.superseded_by_task_id = replacement.task_id
    source.status = TaskStatus.CANCELLED.value

    if str(getattr(orchestrator, "current_task_id", "") or "") == source_task_id:
        orchestrator.current_task_id = replacement.task_id
        orchestrator.current_goal_id = replacement.goal_id

    from ai_tool.human_decision_premise import refresh_task_revalidation

    refresh_task_revalidation(orchestrator)
    return {
        "source_task_id": source_task_id,
        "replacement_task_id": replacement.task_id,
        "outcome": outcome,
        "reason": reason,
        "depends_on": list(replacement.depends_on),
        "decision_premises": list(replacement.decision_premises),
        "redirected_dependents": redirected,
        "downstream_task_ids": dependents,
        "old_upstream_task_id": source_task_id,
        "new_upstream_task_id": replacement.task_id,
        "replan_id": replan.replan_id,
    }


def run_premise_pending_replacements(
    orchestrator: Any,
    revalidation_results: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Replace pending tasks with needs_revision / invalid outcomes. Skips in_progress."""
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
        if str(getattr(task, "status", "") or "") != TaskStatus.PENDING.value:
            continue
        result = add_pending_replacement(
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
    "PREMISE_PENDING_REPLACEMENT_SOURCE",
    "add_pending_replacement",
    "build_pending_replacement_task",
    "downstream_dependent_task_ids",
    "redirect_depends_on",
    "run_premise_pending_replacements",
]
