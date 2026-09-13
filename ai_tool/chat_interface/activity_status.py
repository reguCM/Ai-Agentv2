"""Thread-safe, non-semantic UI activity for an in-flight chat turn."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from threading import RLock
import time
from typing import Callable


class ActivityStatus(str, Enum):
    GOAL_CREATING = "GOAL_CREATING"
    GOAL_DECOMPOSING = "GOAL_DECOMPOSING"
    TASK_PLANNING = "TASK_PLANNING"
    TASK_RUNNING = "TASK_RUNNING"
    LLM_WAITING = "LLM_WAITING"
    TOOL_RUNNING = "TOOL_RUNNING"
    RESULT_AUDITING = "RESULT_AUDITING"
    EVIDENCE_UPDATING = "EVIDENCE_UPDATING"
    COMPLETION_CHECKING = "COMPLETION_CHECKING"
    RECOVERY_PLANNING = "RECOVERY_PLANNING"
    REPLANNING = "REPLANNING"
    FINAL_SYNTHESIS = "FINAL_SYNTHESIS"
    LONG_RUNNING = "LONG_RUNNING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    AWAITING_USER = "AWAITING_USER"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


_LABELS = {
    ActivityStatus.GOAL_CREATING: "Goalを整理しています…",
    ActivityStatus.GOAL_DECOMPOSING: "作業を分解しています…",
    ActivityStatus.TASK_PLANNING: "次の作業を整理しています…",
    ActivityStatus.TASK_RUNNING: "Current Taskを進めています…",
    ActivityStatus.LLM_WAITING: "LLMの応答を待っています…",
    ActivityStatus.TOOL_RUNNING: "Toolを実行しています",
    ActivityStatus.RESULT_AUDITING: "Tool結果を確認しています…",
    ActivityStatus.EVIDENCE_UPDATING: "Evidenceを整理しています…",
    ActivityStatus.COMPLETION_CHECKING: "完了条件を確認しています…",
    ActivityStatus.RECOVERY_PLANNING: "別の進め方を検討しています…",
    ActivityStatus.REPLANNING: "作業計画を見直しています…",
    ActivityStatus.FINAL_SYNTHESIS: "最終回答をまとめています…",
    ActivityStatus.LONG_RUNNING: "処理は継続中です。長時間処理になっています。",
    ActivityStatus.CANCEL_REQUESTED: "停止を要求しています…",
    ActivityStatus.CANCELLED: "処理を停止しました。",
    ActivityStatus.AWAITING_USER: "返信を待っています…",
    ActivityStatus.BLOCKED: "処理は未完了のまま停止しました。",
    ActivityStatus.FAILED: "処理中にエラーが発生しました。",
    ActivityStatus.COMPLETED: "処理が完了しました。",
}


@dataclass
class TurnActivity:
    session_id: str
    turn_id: str
    correlation_id: str
    status: str
    message: str
    started_monotonic: float
    updated_monotonic: float
    tool_name: str | None = None
    current_goal: str | None = None
    current_task: str | None = None
    task_status: str | None = None
    progress_state: str | None = None


_ACTIVE: dict[str, TurnActivity] = {}
_LOCK = RLock()


def activity_message(status: ActivityStatus, *, tool_name: str | None = None) -> str:
    base = _LABELS[status]
    if status is ActivityStatus.TOOL_RUNNING and tool_name:
        # Arguments are deliberately excluded from the public activity message.
        return f"{base}: {tool_name}"
    return base


def begin_turn(
    session_id: str,
    turn_id: str,
    correlation_id: str,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> TurnActivity:
    now = clock()
    row = TurnActivity(
        session_id=session_id,
        turn_id=turn_id,
        correlation_id=correlation_id,
        status=ActivityStatus.TASK_PLANNING.value,
        message=activity_message(ActivityStatus.TASK_PLANNING),
        started_monotonic=now,
        updated_monotonic=now,
    )
    with _LOCK:
        _ACTIVE[session_id] = row
    return row


def update_activity(
    session_id: str,
    turn_id: str,
    status: ActivityStatus,
    *,
    tool_name: str | None = None,
    current_goal: str | None = None,
    current_task: str | None = None,
    task_status: str | None = None,
    progress_state: str | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    with _LOCK:
        row = _ACTIVE.get(session_id)
        if row is None or row.turn_id != turn_id:
            return False
        row.status = status.value
        row.message = activity_message(status, tool_name=tool_name)
        row.tool_name = tool_name
        row.current_goal = current_goal or row.current_goal
        row.current_task = current_task or row.current_task
        row.task_status = task_status or row.task_status
        row.progress_state = progress_state or row.progress_state
        row.updated_monotonic = clock()
        return True


def request_cancel(session_id: str, turn_id: str) -> bool:
    return update_activity(session_id, turn_id, ActivityStatus.CANCEL_REQUESTED)


def response_is_current(session_id: str, turn_id: str) -> bool:
    with _LOCK:
        row = _ACTIVE.get(session_id)
        return bool(
            row
            and row.turn_id == turn_id
            and row.status
            not in {ActivityStatus.CANCEL_REQUESTED.value, ActivityStatus.CANCELLED.value}
        )


def snapshot_activity(
    session_id: str,
    *,
    long_running_after: float = 30.0,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, object] | None:
    with _LOCK:
        row = _ACTIVE.get(session_id)
        if row is None:
            return None
        data = asdict(row)
    elapsed = max(0.0, clock() - row.started_monotonic)
    data["elapsed_seconds"] = round(elapsed, 1)
    terminal = {
        ActivityStatus.CANCEL_REQUESTED.value,
        ActivityStatus.CANCELLED.value,
        ActivityStatus.AWAITING_USER.value,
        ActivityStatus.BLOCKED.value,
        ActivityStatus.FAILED.value,
        ActivityStatus.COMPLETED.value,
    }
    if elapsed >= long_running_after and row.status not in terminal:
        data["status"] = ActivityStatus.LONG_RUNNING.value
        data["message"] = activity_message(ActivityStatus.LONG_RUNNING)
    elif elapsed >= 10 and row.status == ActivityStatus.LLM_WAITING.value:
        data["message"] = "処理を続けています…"
    return data


def finish_turn(
    session_id: str,
    turn_id: str,
    *,
    cancelled: bool = False,
    terminal_status: ActivityStatus | None = None,
) -> bool:
    status = terminal_status or (
        ActivityStatus.CANCELLED if cancelled else ActivityStatus.COMPLETED
    )
    return update_activity(session_id, turn_id, status)


__all__ = [
    "ActivityStatus",
    "activity_message",
    "begin_turn",
    "finish_turn",
    "request_cancel",
    "response_is_current",
    "snapshot_activity",
    "update_activity",
]
