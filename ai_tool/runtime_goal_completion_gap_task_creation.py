"""Minimal, guarded Creation boundary for one Completion Gap Runtime Task.

This is not a scheduler or execution loop.  It creates one pending Runtime
Task from one fresh, identity-grounded Task Proposal and attaches the existing
Runtime Acceptance Support Relation.  It never executes the Task.
"""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.goal_handoff_runtime_bridge import (
    COMPLETION_GAP_TASK_SOURCE,
    register_completion_gap_acceptance_binding,
)
from ai_tool.runtime_goal_completion_gap_task_proposal import (
    build_runtime_goal_completion_gap_task_proposal,
)
from tools.ai.task_runtime import ReplanRecord, TaskRecord, TaskStatus


def _token(value: Any) -> str:
    return str(value or "").strip()


def _next_completion_gap_task_id(runtime: Any) -> str:
    used = {
        _token(getattr(task, "task_id", None))
        for task in (getattr(runtime, "tasks", None) or {}).values()
    }
    index = 1
    while f"cg-{index}" in used:
        index += 1
    return f"cg-{index}"


def _result(status: str, proposal_result: Mapping[str, Any], **fields: Any) -> dict[str, Any]:
    return {
        "status": status,
        "handoff_id": proposal_result.get("handoff_id"),
        "run_execution_id": proposal_result.get("run_execution_id"),
        "proposal": proposal_result.get("proposal"),
        **fields,
    }


def create_runtime_goal_completion_gap_task(
    orchestrator: Any,
    session: Mapping[str, Any],
    *,
    mission: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Create one pending, identity-bound Completion Gap Task when safe.

    The caller owns persistence and later scheduling.  This function neither
    writes the Session nor starts an Action.
    """
    proposal_result = build_runtime_goal_completion_gap_task_proposal(
        session,
        mission=mission,
        candidate=candidate,
    )
    if _token(proposal_result.get("status")) != "TASK_PROPOSAL_CANDIDATE":
        return _result(_token(proposal_result.get("status")) or "FAIL_CLOSED", proposal_result)

    proposal = proposal_result.get("proposal")
    if not isinstance(proposal, Mapping):
        return _result("FAIL_CLOSED", proposal_result, reason="missing_task_proposal")
    source_task_ids = [
        _token(item) for item in proposal.get("source_task_ids") or [] if _token(item)
    ]
    runtime_task_ids = [
        _token(item) for item in proposal.get("runtime_task_ids") or [] if _token(item)
    ]
    acceptance_id = _token(proposal.get("acceptance_id"))
    if len(source_task_ids) != 1 or len(runtime_task_ids) != 1:
        return _result(
            "HUMAN_REQUIRED",
            proposal_result,
            reason="single_source_task_required",
        )
    source_task_id = source_task_ids[0]
    source_runtime_task_id = runtime_task_ids[0]
    runtime = getattr(orchestrator, "runtime", None)
    tasks = getattr(runtime, "tasks", None) or {}
    source_task = tasks.get(source_runtime_task_id)
    if source_task is None:
        return _result("FAIL_CLOSED", proposal_result, reason="source_runtime_task_not_found")
    if _token(getattr(source_task, "source_task_id", None)) != source_task_id:
        return _result("FAIL_CLOSED", proposal_result, reason="source_runtime_task_identity_mismatch")
    if _token(getattr(source_task, "status", None)) != TaskStatus.COMPLETE.value:
        return _result("RETURN_TO_EXISTING_WORK", proposal_result, reason="source_runtime_task_incomplete")
    if not acceptance_id:
        return _result("FAIL_CLOSED", proposal_result, reason="missing_acceptance_id")
    source_conditions = [
        _token(item)
        for item in (getattr(source_task, "completion_conditions", None) or [])
        if _token(item)
    ]
    if not source_conditions:
        return _result(
            "FAIL_CLOSED",
            proposal_result,
            reason="source_runtime_task_conditions_missing",
        )

    existing = getattr(orchestrator, "completion_gap_acceptance_bindings", None) or []
    for row in existing:
        if not isinstance(row, Mapping):
            continue
        if (
            _token(row.get("source_task_id")) == source_task_id
            and _token(row.get("acceptance_id")) == acceptance_id
        ):
            return _result(
                "ALREADY_CREATED",
                proposal_result,
                runtime_task_id=_token(row.get("runtime_task_id")),
            )

    task_id = _next_completion_gap_task_id(runtime)
    task = TaskRecord(
        task_id=task_id,
        goal_id=_token(getattr(source_task, "goal_id", None)),
        title=f"Resolve completion gap for {acceptance_id}",
        instruction=(
            f"Address only the unresolved completion gap for Acceptance {acceptance_id}. "
            f"Use the referenced source Runtime Task {source_runtime_task_id} and its "
            "existing Evidence as grounding. Do not reinterpret or change Human Meaning, "
            "Requirements, Acceptance, or Constraints."
        ),
        # Reuse the source Runtime Task's existing completion contract.
        completion_conditions=source_conditions,
        depends_on=[source_runtime_task_id],
        status=TaskStatus.PENDING.value,
        source=COMPLETION_GAP_TASK_SOURCE,
        source_task_id=source_task_id,
    )
    replan = ReplanRecord(
        replan_id=f"R{len(getattr(runtime, 'replans', None) or []) + 1}",
        scope_goal_id=task.goal_id,
        reason=f"completion_gap:{acceptance_id}",
    )
    runtime.replan_add_task(replan, task)
    try:
        binding = register_completion_gap_acceptance_binding(
            orchestrator,
            runtime_task_id=task_id,
            source_task_id=source_task_id,
            acceptance_id=acceptance_id,
        )
    except Exception:
        # The relation is mandatory for this Task kind.  Revert this local
        # addition rather than leaving a runnable unbound Completion Gap Task.
        runtime.tasks.pop(task_id, None)
        goal = runtime.goals.get(task.goal_id)
        if goal is not None:
            goal.task_ids = [item for item in goal.task_ids if item != task_id]
        runtime.replans = [item for item in runtime.replans if item.replan_id != replan.replan_id]
        raise
    return _result(
        "TASK_CREATED",
        proposal_result,
        runtime_task_id=task_id,
        replan_id=replan.replan_id,
        acceptance_support_relation=binding,
        task={
            "task_id": task.task_id,
            "goal_id": task.goal_id,
            "status": task.status,
            "source": task.source,
            "source_task_id": task.source_task_id,
            "depends_on": list(task.depends_on),
        },
    )


__all__ = ["create_runtime_goal_completion_gap_task"]
