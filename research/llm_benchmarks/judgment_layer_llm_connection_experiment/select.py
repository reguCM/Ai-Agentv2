"""実行する Action を選ぶ。代替候補は残す。"""

from __future__ import annotations


def select_actions(validated):
    selected = []
    for item in validated:
        if item.get("execute") and item.get("tool_name") and item.get("validated"):
            chosen = dict(item)
            chosen["selected"] = True
            selected.append(chosen)
    selected.sort(key=lambda item: item.get("order") or 0)
    if selected:
        mapping_status = "selected"
    elif any(item.get("status") in ("needs_clarification", "unresolved") for item in validated):
        mapping_status = "needs_clarification"
    else:
        mapping_status = "mapping_gap"
    return selected, mapping_status
