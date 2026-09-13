"""Unified runtime guards: superseded tasks and stale premise execution blocks."""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.premise_corrective_replan import premise_revalidation_blocks_task_execution
from ai_tool.task_upstream_supersession_revalidation import upstream_supersession_blocks_task_execution
from tools.ai.task_runtime import TaskStatus


class TaskExecutionBlockedError(RuntimeError):
    """Raised when the current task must not execute."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        super().__init__(str(payload.get("reason") or "task_execution_blocked"))
        self.payload = dict(payload)


def task_superseded(task: Any) -> bool:
    """True when a task was superseded and must not execute."""
    superseded_by = str(getattr(task, "superseded_by_task_id", "") or "").strip()
    if superseded_by:
        return True
    if isinstance(task, Mapping):
        return bool(str(task.get("superseded_by_task_id") or "").strip())
    return False


def task_execution_blocked(task: Any) -> dict[str, Any] | None:
    """Return block metadata when a task must not execute."""
    task_id = str(getattr(task, "task_id", "") or "")
    if isinstance(task, Mapping):
        task_id = str(task.get("task_id") or task_id)
    if task_superseded(task):
        superseded_by = str(
            getattr(task, "superseded_by_task_id", "")
            or (task.get("superseded_by_task_id") if isinstance(task, Mapping) else "")
            or ""
        ).strip()
        return {
            "task_id": task_id,
            "reason": "task_superseded",
            "superseded_by_task_id": superseded_by,
            "task_status": str(
                getattr(task, "status", "")
                or (task.get("status") if isinstance(task, Mapping) else "")
                or ""
            ),
        }
    upstream_block = upstream_supersession_blocks_task_execution(task)
    if upstream_block is not None:
        return upstream_block
    premise_block = premise_revalidation_blocks_task_execution(task)
    if premise_block is not None:
        premise_block = dict(premise_block)
        premise_block["reason"] = "premise_revalidation_execution_blocked"
        return premise_block
    return None


__all__ = [
    "TaskExecutionBlockedError",
    "task_execution_blocked",
    "task_superseded",
]
