"""機械的に取れる観測だけ。判断の有無は断定しない。"""

from __future__ import annotations


def visible_analysis_present(raw_output):
    return bool((raw_output or "").strip())


def mechanical_turn_flags(turn):
    native = (turn.get("parsed") or {}).get("native_tool_calls") or []
    content = visible_analysis_present(turn.get("raw_output"))
    return {
        "analysis_observable": content,
        "tool_selection_observable": bool(native) or bool(turn.get("tool_calls")),
        "visible_content_with_tool_call": content and bool(native),
        "tool_call_without_visible_content": (not content) and bool(native),
        "thinking_observed": bool(turn.get("thinking_observed")),
        "thinking_not_used_as_analysis": True,
    }


def _file_set(turns, key):
    names = []
    for turn in turns:
        for path in turn.get(key) or []:
            if path:
                names.append(str(path))
    return names


def search_scope_events(turns):
    seen = []
    events = []
    for turn in turns:
        current = [str(path) for path in (turn.get("files_read") or []) if path]
        new = [path for path in current if path not in seen]
        after_test = bool((turn.get("test_result") or {}).get("sent_to_llm"))
        prev_failed = False
        if turn["turn_id"] > 1:
            prev = turns[turn["turn_id"] - 2]
            prev_test = prev.get("test_result") or {}
            prev_failed = prev_test.get("test_pass") is False
        if new:
            events.append(
                {
                    "turn_id": turn["turn_id"],
                    "new_files_read": new,
                    "immediately_after_test_failure": prev_failed,
                    "same_turn_has_test_result": after_test,
                }
            )
        seen.extend(current)
    return events


def same_file_repatch_events(turns):
    last_changed = None
    events = []
    for turn in turns:
        changed = [str(path) for path in (turn.get("files_changed") or []) if path]
        test = turn.get("test_result") or {}
        if last_changed and changed and set(changed) == {last_changed}:
            events.append(
                {
                    "turn_id": turn["turn_id"],
                    "file": last_changed,
                    "after_test_fail": test.get("test_pass") is False,
                }
            )
        if changed:
            last_changed = changed[-1]
    return events


def summarize_run(record):
    turns = record.get("turns") or []
    turn_flags = [mechanical_turn_flags(turn) for turn in turns]
    tool_seq = []
    for turn in turns:
        for name in turn.get("tool_calls") or []:
            tool_seq.append({"turn_id": turn["turn_id"], "tool_name": name})
    test_rounds = [
        {
            "turn_id": turn["turn_id"],
            "test_pass": (turn.get("test_result") or {}).get("test_pass"),
            "execution_success": (turn.get("test_result") or {}).get("execution_success"),
            "application_behavior": (turn.get("test_result") or {}).get("application_behavior"),
        }
        for turn in turns
        if turn.get("test_result")
    ]
    any_test_sent = any(
        (turn.get("test_result") or {}).get("sent_to_llm") for turn in turns
    )
    return {
        "model": record.get("model"),
        "path": record.get("tool_calling_path"),
        "tool_calling_mode": record.get("tool_calling_mode"),
        "analysis_observable": any(item["analysis_observable"] for item in turn_flags),
        "tool_selection_observable": any(item["tool_selection_observable"] for item in turn_flags),
        "tool_call_without_visible_content_any": any(
            item["tool_call_without_visible_content"] for item in turn_flags
        ),
        "visible_content_with_tool_call_any": any(
            item["visible_content_with_tool_call"] for item in turn_flags
        ),
        "files_read": _file_set(turns, "files_read"),
        "files_changed": _file_set(turns, "files_changed"),
        "tool_name_sequence": tool_seq,
        "search_scope_events": search_scope_events(turns),
        "same_file_repatch_events": same_file_repatch_events(turns),
        "test_rounds": test_rounds,
        "test_feedback_sent": any_test_sent,
        "final_test_pass": bool(test_rounds and test_rounds[-1].get("test_pass")),
        "turn_flags": turn_flags,
        "hypothesis_updated": "NOT_DETERMINED",
        "tool_result_used": "NOT_DETERMINED",
        "search_scope_changed": bool(search_scope_events(turns)),
        "test_feedback_used": "NOT_DETERMINED",
    }
