"""Mission-scoped Human Decision clarification load/restore helpers."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ai_tool.human_decision_premise import normalize_decision_record
from ai_tool.mission_memory.store import MissionMemoryStore


def clarifications_from_mission_record(
    mission: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Rebuild runtime clarifications from a mission.json record."""
    if not isinstance(mission, Mapping):
        return []
    rows = mission.get("confirmed_clarifications")
    if isinstance(rows, list) and rows:
        output: list[dict[str, Any]] = []
        for row in rows:
            normalized = normalize_decision_record(row)
            if normalized:
                output.append(normalized)
        return output
    legacy = mission.get("user_confirmed_supplements") or []
    output = []
    for row in legacy:
        normalized = normalize_decision_record(row)
        if normalized:
            output.append(normalized)
    return output


def clarifications_for_mission_store(orchestrator: Any) -> list[dict[str, Any]]:
    """Serialize orchestrator clarifications for mission.json persistence."""
    output: list[dict[str, Any]] = []
    for row in getattr(orchestrator, "confirmed_clarifications", None) or []:
        normalized = normalize_decision_record(row)
        if normalized:
            output.append(normalized)
    return output


def load_confirmed_clarifications_for_mission(
    mission_id: str,
    *,
    store: MissionMemoryStore | None = None,
) -> list[dict[str, Any]]:
    memory = store or MissionMemoryStore.from_default()
    mission = memory.get_mission(str(mission_id or "").strip())
    return clarifications_from_mission_record(mission)


def restore_mission_clarifications(
    orchestrator: Any,
    *,
    store: MissionMemoryStore | None = None,
) -> list[dict[str, Any]]:
    """Hydrate orchestrator.confirmed_clarifications from mission memory.

    In-memory clarifications from the current execution win over mission.json
    rows with the same decision_id so not-yet-persisted Boundary Grill answers
    are not dropped before Production Handoff.
    """
    mission_id = str(getattr(orchestrator, "mission_id", "") or "").strip()
    if not mission_id:
        return []
    in_memory = [
        dict(item)
        for item in (getattr(orchestrator, "confirmed_clarifications", None) or [])
        if isinstance(item, dict)
    ]
    mission_rows = load_confirmed_clarifications_for_mission(mission_id, store=store)
    if not mission_rows and not in_memory:
        return []
    merged: dict[str, dict[str, Any]] = {}
    for row in mission_rows:
        decision_id = str(row.get("decision_id") or "").strip()
        if decision_id:
            merged[decision_id] = dict(row)
    for row in in_memory:
        decision_id = str(row.get("decision_id") or "").strip()
        if decision_id:
            merged[decision_id] = dict(row)
        else:
            merged[f"memory-{len(merged)}"] = dict(row)
    orchestrator.confirmed_clarifications = list(merged.values())
    return orchestrator.confirmed_clarifications


__all__ = [
    "clarifications_for_mission_store",
    "clarifications_from_mission_record",
    "load_confirmed_clarifications_for_mission",
    "restore_mission_clarifications",
]
