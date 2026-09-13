"""NH13-7 failure classification F1-F7."""

from __future__ import annotations

from typing import Any


def classify_nh13_7_failures(
    *,
    selection: dict[str, Any],
    diagnosis: dict[str, Any],
    gold_terms: list[str],
) -> list[str]:
    tags: list[str] = []
    if selection.get("missed_terms"):
        tags.append("F1 Selection Miss")
    if len(selection.get("unnecessary_terms") or []) >= 4:
        tags.append("F2 Selection Overload")
    sel_ok = (selection.get("recall") or 0) >= 0.7
    slot_acc = (diagnosis.get("slot_eval") or {}).get("slot_accuracy", 0)
    fp_acc = (diagnosis.get("fingerprint_eval") or {}).get("field_accuracy", 0)
    if sel_ok and slot_acc < 0.55:
        tags.append("F3 Knowledge Correct / Reasoning Failure")
    missed = set(selection.get("missed_terms") or [])
    if missed and slot_acc < 0.5:
        tags.append("F4 Knowledge Insufficient")
    if (selection.get("precision") or 1) < 0.5 and slot_acc < 0.55:
        tags.append("F5 Context Conflict")
    if diagnosis.get("terminology_confusion_count", 0) > 0:
        tags.append("F6 Boundary Confusion")
    if not diagnosis.get("llm_parse_ok", True):
        tags.append("F7 Parse Failure")
    return tags
