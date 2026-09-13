"""Persistent graph-level safety for Task change propagation.

Distinct from per-task execution guards in task_execution_guard.
"""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.task_upstream_supersession_revalidation import STOP_REASON_CONVERGED

GUARD_KEY = "task_change_propagation_guard"
GRAPH_STOP_REASON = "TASK_CHANGE_PROPAGATION_NON_CONVERGED"


def _held_task_ids(held_tasks: Any) -> list[str]:
    rows = list(held_tasks or [])
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        token = str(row.get("task_id") or row.get("original_task_id") or "").strip()
        if token and token not in ids:
            ids.append(token)
    return ids


def build_propagation_guard(
    propagation_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build minimal persistent guard state from one propagation run."""
    row = dict(propagation_result or {})
    graph_converged = bool(row.get("converged"))
    stop_reason = str(row.get("stop_reason") or "").strip() or None
    held_ids = _held_task_ids(row.get("held_tasks"))
    wave_index = row.get("completed_wave_count")
    if wave_index is not None:
        wave_index = max(0, int(wave_index) - 1)
    else:
        wave_index = row.get("completed_wave_index")
    if wave_index is not None:
        wave_index = int(wave_index)
    propagation_id = str(row.get("propagation_id") or "").strip() or None
    unresolved = (not graph_converged) or bool(held_ids)
    return {
        "unresolved": unresolved,
        "graph_converged": graph_converged,
        "propagation_id": propagation_id,
        "stop_reason": stop_reason if stop_reason else (STOP_REASON_CONVERGED if graph_converged else None),
        "completed_wave_index": wave_index,
        "held_task_ids": held_ids,
    }


def resolved_propagation_guard(
    *,
    propagation_id: str | None = None,
    completed_wave_index: int | None = None,
) -> dict[str, Any]:
    return {
        "unresolved": False,
        "graph_converged": True,
        "propagation_id": str(propagation_id or "").strip() or None,
        "stop_reason": STOP_REASON_CONVERGED,
        "completed_wave_index": completed_wave_index,
        "held_task_ids": [],
    }


def get_propagation_guard(orchestrator: Any) -> dict[str, Any] | None:
    guard = getattr(orchestrator, GUARD_KEY, None)
    if isinstance(guard, Mapping):
        return dict(guard)
    return None


def set_propagation_guard(orchestrator: Any, guard: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if guard is None:
        setattr(orchestrator, GUARD_KEY, None)
        return None
    payload = dict(guard)
    setattr(orchestrator, GUARD_KEY, payload)
    return payload


def apply_propagation_guard_from_result(
    orchestrator: Any,
    propagation_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    guard = build_propagation_guard(propagation_result)
    if guard["graph_converged"] and not guard["held_task_ids"]:
        guard = resolved_propagation_guard(
            propagation_id=guard.get("propagation_id"),
            completed_wave_index=guard.get("completed_wave_index"),
        )
    return set_propagation_guard(orchestrator, guard) or guard


def is_graph_propagation_unresolved(orchestrator: Any) -> bool:
    guard = get_propagation_guard(orchestrator)
    if not guard:
        return False
    return not bool(guard.get("graph_converged"))


def has_held_work_unresolved(orchestrator: Any) -> bool:
    guard = get_propagation_guard(orchestrator)
    if not guard:
        return False
    return bool(guard.get("held_task_ids"))


def propagation_blocks_goal_completion(orchestrator: Any) -> dict[str, Any] | None:
    """True when graph propagation or held downstream work remains unresolved."""
    guard = get_propagation_guard(orchestrator)
    if not guard or not guard.get("unresolved"):
        return None
    return {
        "reason": "task_change_propagation_unresolved",
        "graph_converged": bool(guard.get("graph_converged")),
        "propagation_id": guard.get("propagation_id"),
        "stop_reason": guard.get("stop_reason"),
        "completed_wave_index": guard.get("completed_wave_index"),
        "held_task_ids": list(guard.get("held_task_ids") or []),
    }


def graph_propagation_blocks_execution(orchestrator: Any) -> dict[str, Any] | None:
    """Graph-level block when propagation did not converge.

    Distinct from per-task premise/upstream holds. Does not apply when
    propagation converged but individual tasks remain held.
    """
    guard = get_propagation_guard(orchestrator)
    if not guard or bool(guard.get("graph_converged")):
        return None
    return {
        "reason": GRAPH_STOP_REASON,
        "propagation_id": guard.get("propagation_id"),
        "stop_reason": guard.get("stop_reason"),
        "completed_wave_index": guard.get("completed_wave_index"),
        "held_task_ids": list(guard.get("held_task_ids") or []),
    }


def propagation_guard_from_completion_runtime(snapshot: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snapshot, Mapping):
        return None
    guard = snapshot.get(GUARD_KEY)
    if isinstance(guard, Mapping):
        return dict(guard)
    return None


def effective_stop_reason_for_boundary_grill(
    base_stop_reason: str,
    orchestrator: Any,
) -> tuple[str, str | None]:
    """Keep Decision change stop_reason unless graph propagation failed."""
    if not is_graph_propagation_unresolved(orchestrator):
        return base_stop_reason, None
    guard = get_propagation_guard(orchestrator) or {}
    note = (
        "Human Decisionは反映済みですが、downstream Task change propagationは未収束です。"
        f" stop_reason={guard.get('stop_reason')}"
    )
    return GRAPH_STOP_REASON, note


__all__ = [
    "GRAPH_STOP_REASON",
    "GUARD_KEY",
    "apply_propagation_guard_from_result",
    "build_propagation_guard",
    "effective_stop_reason_for_boundary_grill",
    "get_propagation_guard",
    "graph_propagation_blocks_execution",
    "has_held_work_unresolved",
    "is_graph_propagation_unresolved",
    "propagation_blocks_goal_completion",
    "propagation_guard_from_completion_runtime",
    "resolved_propagation_guard",
    "set_propagation_guard",
]
