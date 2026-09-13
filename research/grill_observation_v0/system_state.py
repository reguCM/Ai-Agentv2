"""Observation-only System State for Grill Q2 layer.

confirmed means the value is locked, not that a human confirmed it.
decided_by / human_confirmed keep the actor separate from status.
Not a production schema.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def empty_system_state(
    *,
    goal: str,
    environment_facts: dict[str, Any],
    concept: str | None = None,
) -> dict[str, Any]:
    return {
        "goal": {
            "text": goal,
            "concept": concept or goal,
        },
        "environment_facts": dict(environment_facts or {}),
        "human_requirements": [],
        "confirmed_decisions": [],
        "assumptions": [],
        "unresolved": [],
        "delegated": [],
    }


def snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(state)


def add_human_requirement(state: dict[str, Any], *, item_id: str, text: str, source: str) -> None:
    state["human_requirements"].append(
        {"id": item_id, "text": text, "source": source}
    )


def add_confirmed_decision(
    state: dict[str, Any],
    *,
    item_id: str,
    title: str,
    value: Any,
    decided_by: str,
    reason: str,
    evidence: dict[str, Any],
    human_confirmed: bool = False,
    status: str = "confirmed",
) -> dict[str, Any]:
    rec = {
        "id": item_id,
        "title": title,
        "value": value,
        "status": status,
        "decided_by": decided_by,
        "reason": reason,
        "evidence": dict(evidence or {}),
        "human_confirmed": bool(human_confirmed),
    }
    state["confirmed_decisions"].append(rec)
    drop_unresolved(state, item_id=item_id, title=title)
    return rec


def drop_unresolved(state: dict[str, Any], *, item_id: str, title: str = "") -> None:
    keys = {str(item_id), str(title)} - {""}
    state["unresolved"] = [
        u
        for u in (state.get("unresolved") or [])
        if str(u.get("id") or "") not in keys and str(u.get("title") or "") not in keys
    ]


def set_unresolved(state: dict[str, Any], regions: list[dict[str, Any]]) -> None:
    confirmed_ids = {
        str(d.get("id") or "")
        for d in (state.get("confirmed_decisions") or [])
        if d.get("id")
    }
    confirmed_titles = {
        str(d.get("title") or "")
        for d in (state.get("confirmed_decisions") or [])
        if d.get("title")
    }
    kept: list[dict[str, Any]] = []
    for region in regions or []:
        if not isinstance(region, dict):
            continue
        rid = str(region.get("id") or "")
        title = str(region.get("title") or "")
        if rid in confirmed_ids or title in confirmed_titles:
            continue
        kept.append(region)
    state["unresolved"] = kept


def public_spec_view(state: dict[str, Any]) -> dict[str, Any]:
    """Compact view for display / LLM context."""
    return {
        "goal": (state.get("goal") or {}).get("text"),
        "environment_facts": state.get("environment_facts") or {},
        "human_requirements": state.get("human_requirements") or [],
        "confirmed_decisions": state.get("confirmed_decisions") or [],
        "assumptions": state.get("assumptions") or [],
        "unresolved": state.get("unresolved") or [],
        "delegated": state.get("delegated") or [],
    }
