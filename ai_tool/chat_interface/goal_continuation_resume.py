"""Goal Continuation resume (Phase 2+) and winner execution (Phase 3).

Restore a prior execution's completion runtime into a new execution on the same
mission when the user explicitly requests continuation, then connect the stored
Router winner to existing Recovery / Replan / Tool Evidence capabilities.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ai_tool.chat_interface.gap_resolution_router import (
    CONTINUATION_WINNERS,
    CapabilityId,
)
from ai_tool.chat_interface.requirement_resolution import sync_canonical_requirements_from_mission
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.mission_memory.chat_persist import bind_execution_identity
from ai_tool.mission_memory.clarifications import restore_mission_clarifications
from ai_tool.mission_memory.task_runtime import (
    apply_orchestrator_completion_runtime,
    resolve_canonical_completion_runtime,
)
from tools.ai.task_runtime import FailureRecord, TaskStatus

_REPLAN_TITLE = "Try an alternative recovery path"
_REPLAN_INSTRUCTION = (
    "Use a different safe observation to satisfy the current goal."
)

_GOAL_CONTINUATION_KIND = "goal_continuation_v0"

_EXACT_CONTINUATION_TRIGGERS = frozenset(
    {
        "継続",
        "続けて",
        "続行",
        "継続してください",
        "続けてください",
        "continue",
        "resume",
        "goal continuation",
        "continue goal",
    }
)

_SHORT_PREFIX_RE = re.compile(
    r"^(継続|continue|resume)\b",
    re.IGNORECASE,
)


class GoalContinuationRestoreError(Exception):
    """Raised when a continuation packet cannot be restored safely."""

    def __init__(self, reason: str, errors: list[str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.errors = list(errors or [])


def is_explicit_continuation_trigger(text: str) -> bool:
    """True only for explicit continuation phrases — not arbitrary follow-ups."""
    normalized = str(text or "").strip()
    if not normalized:
        return False
    lower = normalized.casefold()
    if lower in _EXACT_CONTINUATION_TRIGGERS:
        return True
    if len(normalized) <= 24 and _SHORT_PREFIX_RE.match(normalized):
        remainder = _SHORT_PREFIX_RE.sub("", normalized).strip(" .。!！?？,，")
        if not remainder or remainder.casefold() in {"してください", "please"}:
            return True
    return False


def validate_goal_continuation_packet(packet: Mapping[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, Mapping):
        return ["packet_not_mapping"]
    if str(packet.get("kind") or "") != _GOAL_CONTINUATION_KIND:
        errors.append("invalid_kind")
    if not str(packet.get("mission_id") or "").strip():
        errors.append("missing_mission_id")
    if not str(packet.get("original_request") or "").strip():
        errors.append("missing_original_request")
    runtime = packet.get("completion_runtime")
    if not isinstance(runtime, Mapping):
        errors.append("missing_completion_runtime")
    elif not list(runtime.get("tasks") or []):
        mission_id = str(packet.get("mission_id") or "").strip()
        if mission_id:
            from ai_tool.mission_memory.task_runtime import load_mission_completion_runtime

            if load_mission_completion_runtime(mission_id) is None:
                errors.append("empty_completion_runtime_tasks")
        else:
            errors.append("empty_completion_runtime_tasks")
    return errors


def apply_failure_tail(runtime: Any, failure_tail: Any) -> None:
    """Restore recent failure records needed for recovery-oriented resume."""
    if not failure_tail:
        return
    existing_ids = {str(item.failure_id) for item in runtime.failures}
    for row in failure_tail:
        if not isinstance(row, Mapping):
            continue
        failure_id = str(row.get("failure_id") or "")
        if not failure_id or failure_id in existing_ids:
            continue
        task_id = str(row.get("task_id") or "")
        if task_id not in runtime.tasks:
            continue
        record = FailureRecord(
            failure_id=failure_id,
            task_id=task_id,
            action_id=str(row.get("action_id") or ""),
            tool_name=row.get("tool_name"),
            arguments=dict(row.get("arguments") or {}),
            failure_code=str(row.get("failure_code") or ""),
            evidence_gain=bool(row.get("evidence_gain")),
            created_at=str(row.get("created_at") or ""),
        )
        runtime.failures.append(record)
        task = runtime.tasks[task_id]
        if failure_id not in task.failure_history:
            task.failure_history.append(failure_id)
        existing_ids.add(failure_id)


def advance_to_open_task(orchestrator: ChatTaskOrchestrator) -> str:
    """Point the orchestrator at the first incomplete replan or base task."""
    from ai_tool.task_execution_guard import task_execution_blocked

    runtime = orchestrator.runtime
    replan_task_ids: list[str] = []
    for replan in runtime.replans:
        replan_task_ids.extend(list(replan.added_task_ids or []))
    seen: set[str] = set()
    for task_id in replan_task_ids:
        if task_id in seen:
            continue
        seen.add(task_id)
        task = runtime.tasks.get(task_id)
        if task is not None and task.status != "complete":
            if task_execution_blocked(task):
                continue
            orchestrator.current_task_id = task_id
            orchestrator.current_goal_id = task.goal_id
            return task_id
    for task_id in sorted(runtime.tasks.keys()):
        task = runtime.tasks[task_id]
        if task.status != "complete":
            if task_execution_blocked(task):
                continue
            orchestrator.current_task_id = task_id
            orchestrator.current_goal_id = task.goal_id
            return task_id
    return orchestrator.current_task_id


def restore_orchestrator_from_goal_continuation(
    correlation_id: str,
    packet: Mapping[str, Any],
) -> ChatTaskOrchestrator:
    """Rebuild orchestrator state for a new execution on the same mission."""
    errors = validate_goal_continuation_packet(packet)
    if errors:
        raise GoalContinuationRestoreError("invalid_packet", errors)
    original_request = str(packet.get("original_request") or "")
    orchestrator = ChatTaskOrchestrator(correlation_id, original_request)
    mission_id = str(packet.get("mission_id") or "")
    bind_execution_identity(
        orchestrator,
        resume_mission_id=mission_id,
        new_execution=True,
    )
    restore_mission_clarifications(orchestrator)
    sync_canonical_requirements_from_mission(orchestrator, mission_id=mission_id)
    completion_runtime = resolve_canonical_completion_runtime(
        mission_id,
        packet.get("completion_runtime") or {},
    )
    apply_orchestrator_completion_runtime(
        orchestrator,
        completion_runtime,
        replace_graph=ChatTaskOrchestrator.completion_runtime_requires_graph_restore(
            completion_runtime
        ),
    )
    apply_failure_tail(orchestrator.runtime, packet.get("failure_tail"))
    advance_to_open_task(orchestrator)
    return orchestrator


@dataclass
class ContinuationCapabilityApplication:
    router_winner: str
    capability_applied: str
    open_task_id: str | None = None
    replan_task_id: str | None = None
    replan_created: bool = False
    recovery_hint_applied: bool = False
    recovery_hint: str | None = None
    skipped: bool = False
    skip_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_continuation_winner(
    orchestrator: ChatTaskOrchestrator,
    packet: Mapping[str, Any],
) -> ContinuationCapabilityApplication:
    """Connect the stored Router winner to existing Runtime capabilities."""
    winner = str(packet.get("winner") or "")
    if winner not in CONTINUATION_WINNERS:
        return ContinuationCapabilityApplication(
            router_winner=winner,
            capability_applied="none",
            skipped=True,
            skip_reason="non_continuation_winner",
        )

    if winner == CapabilityId.TOOL_EVIDENCE.value:
        task_id = advance_to_open_task(orchestrator)
        task = orchestrator.runtime.tasks.get(task_id)
        if task is not None and task.status != TaskStatus.COMPLETE.value:
            task.status = TaskStatus.IN_PROGRESS.value
        return ContinuationCapabilityApplication(
            router_winner=winner,
            capability_applied=CapabilityId.TOOL_EVIDENCE.value,
            open_task_id=task_id,
        )

    if winner == CapabilityId.RECOVERY.value:
        task_id = advance_to_open_task(orchestrator)
        hint = orchestrator.recovery_hint()
        replan_task_id = None
        replan_created = False
        if hint and not orchestrator.runtime.replans:
            replan_task = orchestrator.add_local_replan(
                _REPLAN_TITLE,
                _REPLAN_INSTRUCTION,
            )
            replan_task_id = replan_task.task_id
            replan_created = True
            orchestrator.current_task_id = replan_task.task_id
            orchestrator.current_goal_id = replan_task.goal_id
            task_id = replan_task.task_id
        return ContinuationCapabilityApplication(
            router_winner=winner,
            capability_applied=CapabilityId.RECOVERY.value if hint else "recovery_unavailable",
            open_task_id=task_id,
            replan_task_id=replan_task_id,
            replan_created=replan_created,
            recovery_hint_applied=bool(hint),
            recovery_hint=hint,
        )

    if winner == CapabilityId.REPLAN.value:
        replan_created = False
        replan_task_id = None
        if not orchestrator.runtime.replans:
            replan_task = orchestrator.add_local_replan(
                _REPLAN_TITLE,
                _REPLAN_INSTRUCTION,
            )
            replan_task_id = replan_task.task_id
            replan_created = True
            orchestrator.current_task_id = replan_task.task_id
            orchestrator.current_goal_id = replan_task.goal_id
        task_id = advance_to_open_task(orchestrator)
        return ContinuationCapabilityApplication(
            router_winner=winner,
            capability_applied=CapabilityId.REPLAN.value,
            open_task_id=task_id,
            replan_task_id=replan_task_id or task_id,
            replan_created=replan_created,
        )

    return ContinuationCapabilityApplication(
        router_winner=winner,
        capability_applied="none",
        skipped=True,
        skip_reason="unknown_winner",
    )


def goal_continuation_context_from_packet(
    packet: Mapping[str, Any],
    *,
    capability: ContinuationCapabilityApplication | None = None,
) -> dict[str, Any]:
    context = {
        "mission_id": str(packet.get("mission_id") or ""),
        "prior_execution_id": packet.get("prior_execution_id") or packet.get("execution_id"),
        "prior_correlation_id": packet.get("correlation_id"),
        "winner": packet.get("winner"),
        "gap_kind": packet.get("gap_kind"),
        "gap_snapshot": packet.get("gap_snapshot"),
        "continuation_stagnation_count": int(packet.get("continuation_stagnation_count") or 0),
    }
    if capability is not None:
        context.update(capability.as_dict())
    return context
