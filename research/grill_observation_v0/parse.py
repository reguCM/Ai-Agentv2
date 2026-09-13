"""Parse Grill observation JSON. Observation-only; does not invent missing fields."""
from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return None, "empty_response"
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj, None
        return None, "json_not_object"
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        return None, "no_json_object"
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        return None, f"json_decode:{exc}"
    if not isinstance(obj, dict):
        return None, "json_not_object"
    return obj, None


def normalize_turn(parsed: dict[str, Any] | None) -> dict[str, Any]:
    src = parsed or {}
    focus = src.get("focus_item") if isinstance(src.get("focus_item"), dict) else {}
    rec = src.get("recommendation") if isinstance(src.get("recommendation"), dict) else {}
    options = src.get("options") if isinstance(src.get("options"), list) else []
    spec = src.get("spec_state") if isinstance(src.get("spec_state"), dict) else {}
    clean_opts = []
    for opt in options:
        if not isinstance(opt, dict):
            continue
        clean_opts.append(
            {
                "id": str(opt.get("id") or ""),
                "label": str(opt.get("label") or ""),
                "description": str(opt.get("description") or ""),
            }
        )
    return {
        "focus_item": {
            "id": str(focus.get("id") or ""),
            "title": str(focus.get("title") or ""),
            "why_now": str(focus.get("why_now") or ""),
        },
        "question": str(src.get("question") or ""),
        "options": clean_opts,
        "recommendation": {
            "id": str(rec.get("id") or ""),
            "reason": str(rec.get("reason") or ""),
        },
        "spec_state": {
            "goal": spec.get("goal"),
            "confirmed": spec.get("confirmed") if isinstance(spec.get("confirmed"), list) else [],
            "assumptions": spec.get("assumptions") if isinstance(spec.get("assumptions"), list) else [],
            "unresolved": spec.get("unresolved") if isinstance(spec.get("unresolved"), list) else [],
            "delegated": spec.get("delegated") if isinstance(spec.get("delegated"), list) else [],
        },
    }
