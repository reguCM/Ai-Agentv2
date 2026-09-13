"""Mission-canonical Task runtime snapshot for cross-execution resume."""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.mission_memory.store import MissionMemoryStore


def completion_runtime_for_mission_store(orchestrator: Any) -> dict[str, Any] | None:
    """Serialize the latest mission-scoped completion runtime when handoff tasks exist."""
    from ai_tool.production_handoff_bridge import orchestrator_has_goal_handoff_seed

    if not orchestrator_has_goal_handoff_seed(orchestrator):
        return None
    slice_row = orchestrator.completion_runtime_slice()
    if not list(slice_row.get("tasks") or []):
        return None
    return dict(slice_row)


def load_mission_completion_runtime(
    mission_id: str,
    *,
    store: MissionMemoryStore | None = None,
) -> dict[str, Any] | None:
    token = str(mission_id or "").strip()
    if not token:
        return None
    memory = store or MissionMemoryStore.from_default()
    mission = memory.get_mission(token)
    if not isinstance(mission, Mapping):
        return None
    runtime = mission.get("completion_runtime")
    if not isinstance(runtime, Mapping):
        return None
    if not list(runtime.get("tasks") or []):
        return None
    return dict(runtime)


def resolve_canonical_completion_runtime(
    mission_id: str,
    carrier_runtime: Mapping[str, Any] | None,
    *,
    store: MissionMemoryStore | None = None,
) -> dict[str, Any]:
    """Prefer mission.json completion_runtime over session-only carriers."""
    mission_runtime = load_mission_completion_runtime(mission_id, store=store)
    if mission_runtime is not None:
        return dict(mission_runtime)
    if isinstance(carrier_runtime, Mapping):
        return dict(carrier_runtime)
    return {}


def apply_orchestrator_completion_runtime(
    orchestrator: Any,
    snapshot: Mapping[str, Any] | None,
    *,
    replace_graph: bool = False,
) -> None:
    """Restore Task runtime after Human Decisions are already on the orchestrator."""
    from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator

    row = dict(snapshot or {})
    if replace_graph or ChatTaskOrchestrator.completion_runtime_requires_graph_restore(row):
        orchestrator.apply_completion_runtime(row, replace_graph=True)
        return
    if not (getattr(orchestrator, "runtime", None) and orchestrator.runtime.tasks):
        orchestrator.initialize()
    orchestrator.apply_completion_runtime(row)


__all__ = [
    "apply_orchestrator_completion_runtime",
    "completion_runtime_for_mission_store",
    "load_mission_completion_runtime",
    "resolve_canonical_completion_runtime",
]
