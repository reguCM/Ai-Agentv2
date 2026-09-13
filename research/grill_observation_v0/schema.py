"""Grill observation v0 — spec state (experiment only).

Not a production schema. '任せる' is delegated, not confirmed.
"""
from __future__ import annotations

from typing import Any


def empty_spec(goal: str) -> dict[str, Any]:
    return {
        "goal": goal,
        "confirmed": [],
        "assumptions": [],
        "unresolved": [],
        "delegated": [],
    }


def item(kind: str, text: str, *, item_id: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"text": text}
    if item_id:
        out["id"] = item_id
    if kind:
        out["kind"] = kind
    return out


def apply_choice(
    spec: dict[str, Any],
    *,
    focus_id: str,
    focus_title: str,
    choice: dict[str, Any],
    human_raw: str,
) -> dict[str, Any]:
    """Record a human choice. Does not invent remaining unresolved items."""
    next_spec = {
        "goal": spec.get("goal"),
        "confirmed": list(spec.get("confirmed") or []),
        "assumptions": list(spec.get("assumptions") or []),
        "unresolved": list(spec.get("unresolved") or []),
        "delegated": list(spec.get("delegated") or []),
    }
    choice_id = str(choice.get("id") or "")
    label = str(choice.get("label") or choice.get("description") or choice_id)
    if choice.get("delegate") is True or str(choice.get("kind") or "").lower() == "delegate":
        next_spec["delegated"].append(
            {
                "id": focus_id,
                "title": focus_title,
                "human_said": human_raw,
                "note": "delegated; concrete value not yet confirmed",
            }
        )
    else:
        next_spec["confirmed"].append(
            {
                "id": focus_id,
                "title": focus_title,
                "value": label,
                "option_id": choice_id,
                "human_said": human_raw,
            }
        )
    next_spec["unresolved"] = [
        u
        for u in next_spec["unresolved"]
        if str(u.get("id") or u.get("title") or "") not in {focus_id, focus_title}
    ]
    return next_spec
