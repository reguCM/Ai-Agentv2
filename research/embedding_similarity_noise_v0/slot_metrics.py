"""Slot metrics for Goal / Meaning / Focus / Target Role candidates. Experimental only."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None or value != value:
        return None
    return round(value, digits)


def annotate_ranked(
    ranked: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    meta = {str(item["id"]): item for item in candidates}
    out = []
    for row in ranked:
        info = meta.get(str(row["candidate_id"])) or {}
        item = dict(row)
        item["slot_type"] = info.get("slot_type")
        item["object_id"] = info.get("object_id")
        out.append(item)
    return out


def evaluate_slots(
    query: dict[str, Any],
    ranked: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = annotate_ranked(ranked, candidates)
    intended_id = str(query.get("intended_slot_id") or query.get("gold_id"))
    object_id = str(query.get("anchor_id"))
    intended = next((row for row in rows if row["candidate_id"] == intended_id), None)
    top = rows[0] if rows else None
    same_object = [row for row in rows if row.get("object_id") == object_id]
    same_object_top = same_object[0] if same_object else None
    meaning_of_object = next(
        (row for row in rows if row.get("object_id") == object_id and row.get("slot_type") == "meaning"),
        None,
    )
    role_of_object = next(
        (row for row in rows if row.get("object_id") == object_id and row.get("slot_type") == "target_role"),
        None,
    )
    focus_of_object = next(
        (row for row in rows if row.get("object_id") == object_id and row.get("slot_type") == "focus"),
        None,
    )
    goal_of_object = next(
        (row for row in rows if row.get("object_id") == object_id and row.get("slot_type") == "goal"),
        None,
    )
    intended_is_top = bool(intended and intended.get("rank") == 1)
    correct_object_is_top = bool(top and top.get("object_id") == object_id)
    return {
        "query_id": query["id"],
        "noise_type": query.get("noise_type"),
        "object_id": object_id,
        "intended_slot_id": intended_id,
        "intended_slot_type": (intended or {}).get("slot_type"),
        "intended_rank": (intended or {}).get("rank"),
        "intended_cosine": (intended or {}).get("cosine"),
        "intended_is_top": intended_is_top,
        "top_id": (top or {}).get("candidate_id"),
        "top_slot_type": (top or {}).get("slot_type"),
        "top_object_id": (top or {}).get("object_id"),
        "top_cosine": (top or {}).get("cosine"),
        "correct_object_is_top": correct_object_is_top,
        "same_object_best_id": (same_object_top or {}).get("candidate_id"),
        "same_object_best_slot_type": (same_object_top or {}).get("slot_type"),
        "same_object_best_rank": (same_object_top or {}).get("rank"),
        "meaning_rank": (meaning_of_object or {}).get("rank"),
        "role_rank": (role_of_object or {}).get("rank"),
        "focus_rank": (focus_of_object or {}).get("rank"),
        "goal_rank": (goal_of_object or {}).get("rank"),
        "confusion": _confusion(top, object_id, intended_id),
    }


def _confusion(top: dict[str, Any] | None, object_id: str, intended_id: str) -> str:
    if not top:
        return "empty"
    if top.get("candidate_id") == intended_id:
        return "intended_slot"
    if top.get("object_id") == object_id:
        return f"same_object_other_slot:{top.get('slot_type')}"
    if top.get("object_id") == "unrelated":
        return f"unrelated:{top.get('slot_type')}"
    return f"other_object:{top.get('object_id')}:{top.get('slot_type')}"


def summarize_slots(rows: list[dict[str, Any]]) -> dict[str, Any]:
    noisy = [row for row in rows if row.get("noise_type") != "clean"]
    target = noisy if noisy else rows
    intended_top = [row for row in target if row.get("intended_is_top")]
    object_top = [row for row in target if row.get("correct_object_is_top")]
    by_conf: dict[str, int] = defaultdict(int)
    by_top_slot: dict[str, int] = defaultdict(int)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in target:
        by_conf[str(row.get("confusion"))] += 1
        by_top_slot[str(row.get("top_slot_type"))] += 1
        by_type[str(row.get("noise_type"))].append(row)
    failed = [row for row in target if not row.get("intended_is_top")]
    return {
        "n": len(target),
        "intended_slot_top_n": len(intended_top),
        "intended_slot_top_rate": _round(len(intended_top) / len(target), 4) if target else None,
        "correct_object_top_n": len(object_top),
        "correct_object_top_rate": _round(len(object_top) / len(target), 4) if target else None,
        "confusion_counts": dict(by_conf),
        "top_slot_type_counts": dict(by_top_slot),
        "failed_query_ids": [row["query_id"] for row in failed],
        "failed": [
            {
                "query_id": row["query_id"],
                "noise_type": row["noise_type"],
                "intended_slot_id": row["intended_slot_id"],
                "intended_rank": row["intended_rank"],
                "top_id": row["top_id"],
                "top_slot_type": row["top_slot_type"],
                "top_object_id": row["top_object_id"],
                "confusion": row["confusion"],
            }
            for row in failed
        ],
    }


def attach_slot_metrics(
    cases: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = list(cases.get("candidates") or [])
    if not any(item.get("slot_type") for item in candidates):
        return {}
    query_by_id = {str(item["id"]): item for item in cases.get("queries") or []}
    rows = []
    for item in results:
        query = query_by_id.get(str(item.get("query_id")))
        if not query:
            continue
        rows.append(evaluate_slots(query, list(item.get("ranked") or []), candidates))
    return {
        "per_query": rows,
        "summary": summarize_slots(rows),
        "schema_status": cases.get("slot_schema_status"),
        "mapping_note": cases.get("slot_mapping_note"),
    }
