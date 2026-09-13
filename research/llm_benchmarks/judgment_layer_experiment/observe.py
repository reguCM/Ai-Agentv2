"""観測用の機械フラグ。Level 採用基準ではない。判断の正否は断定しない。"""

from __future__ import annotations


def extract_judgment_fields(raw_output, mapping):
    text = raw_output or ""
    mentioned = []
    for item in (mapping.get("candidates") or []):
        target = item.get("target")
        if target and target not in mentioned:
            mentioned.append(target)
    return {
        "llm_decision": text,
        "unknown_information": "NOT_EXTRACTED",
        "requested_information": "NOT_EXTRACTED",
        "requested_target": mentioned,
        "requested_action": [
            item.get("action")
            for item in (mapping.get("candidates") or [])
            if item.get("action")
        ],
        "extraction_note": "unknown/requested information は Schema で取らない。本文は llm_decision に保存。",
    }


def mechanical_level_hints(raw_output, mapping, *, after_tool, after_test, new_files):
    text = (raw_output or "").lower()
    named = [item.get("target") for item in (mapping.get("candidates") or []) if item.get("target")]
    m1 = any(item.get("status") == "M1" for item in (mapping.get("candidates") or []))
    return {
        "level1_error_mentioned": any(
            token in text for token in ("indexerror", "out of range", "index", "traceback")
        ),
        "level2_unknown_mentioned": any(
            token in text
            for token in ("unknown", "not sure", "unclear", "without seeing", "need to", "分からない", "不明")
        ),
        "level3_specific_info": bool(named) or "how" in text or "where" in text,
        "level4_named_target": bool(named),
        "level5_named_method": m1 or any(
            item.get("action") in ("read", "search", "run_test", "write")
            for item in (mapping.get("candidates") or [])
        ),
        "level6_after_tool": after_tool,
        "level7_after_test_new_file": after_test and bool(new_files),
        "level8_not_auto": True,
        "note": "機械ヒントのみ。Level 達成の判定ではない。",
    }


def decision_changed(previous_text, current_text):
    prev = (previous_text or "").strip()
    current = (current_text or "").strip()
    if not prev:
        return "NOT_APPLICABLE"
    if not current:
        return "NOT_DETERMINED"
    if prev == current:
        return False
    return "NOT_DETERMINED_TEXT_DIFFERED"
