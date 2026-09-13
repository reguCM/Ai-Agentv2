"""観測ログの単体確認。実 LLM・IndexError 再実験はしない。"""

from __future__ import annotations

import json
from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import adapters, harness
from research.llm_benchmarks.problem_solving_experiment.dispatch import (
    dispatch as real_dispatch,
)
from research.llm_benchmarks.problem_solving_experiment.observability import (
    TOOL_RESULT_CHAR_LIMIT,
    chat_kwargs_snapshot,
    copy_messages,
    dump_tool_result_for_llm,
    parse_log,
    split_test_of_patch,
)


PASSING_SOURCE = "def cpu_status():\n    return {'status': 'ok'}\n"
FAILING_SOURCE = "def cpu_status():\n    rows = ['a']\n    return {'status': rows[2]}\n"


def _reply(content):
    return SimpleNamespace(message=SimpleNamespace(content=content))


def _install_chat(monkeypatch, replies):
    seen = []

    def fake_chat(**kwargs):
        seen.append(kwargs)
        assert "tools" not in kwargs
        assert "model" in kwargs
        assert "messages" in kwargs
        return _reply(replies.pop(0))

    monkeypatch.setattr(harness, "chat", fake_chat)
    return seen


def _run_scripted(monkeypatch, replies, initial_failure=None):
    seen = _install_chat(monkeypatch, list(replies))
    adapters.set_session(
        tool_name="cpu_status",
        source=FAILING_SOURCE,
        test_result={
            "status": "fail",
            "error_type": "IndexError",
            "error": "list index out of range",
            "traceback": "Traceback (unit)\n",
        },
        validation={"status": "fail", "errors": ["runtime"], "warning_items": []},
    )
    failure = initial_failure or {
        "tool_name": "cpu_status",
        "status": "fail",
        "error_type": "IndexError",
        "error": "list index out of range",
    }
    record = harness._new_record("dummy")
    record["initial_minimal"] = failure
    messages = [{"role": "system", "content": harness.SYSTEM}]
    user = (
        "Solve this test failure. Get any information you need yourself.\n"
        + json.dumps(failure, ensure_ascii=False)
    )
    harness._run_turns(messages, user, record)
    return record, seen, messages


def test_copy_messages_does_not_follow_later_mutation():
    messages = [{"role": "user", "content": "original"}]
    snap = copy_messages(messages)
    messages[0]["content"] = "changed"
    assert snap[0]["content"] == "original"


def test_dump_tool_result_identity_and_truncate():
    small = {"ok": True, "value": 1}
    packed = dump_tool_result_for_llm(small)
    assert packed["truncated"] is False
    assert packed["sent_equals_raw_json"] is True
    assert packed["llm_user_payload"] == "Tool result:\n" + packed["sent_tool_result"]
    assert packed["raw_result"] == small

    big = {"ok": True, "blob": "x" * (TOOL_RESULT_CHAR_LIMIT + 50)}
    packed_big = dump_tool_result_for_llm(big)
    raw_json = json.dumps(big, ensure_ascii=False, default=str)
    assert packed_big["truncated"] is True
    assert packed_big["sent_equals_raw_json"] is False
    assert packed_big["sent_tool_result"] == raw_json[:TOOL_RESULT_CHAR_LIMIT] + "...(truncated)"
    assert packed_big["raw_result"]["blob"] == big["blob"]
    assert packed_big["execution_error"] is None

    err = dump_tool_result_for_llm({"ok": False, "error": "unknown_experiment_tool:nope"})
    assert err["execution_error"] == "unknown_experiment_tool:nope"


def test_parse_log_success_and_failure():
    ok = parse_log('{"action":"final"}', {"action": "final"})
    assert ok["parse_success"] is True
    assert ok["parse_error"] is None
    bad = parse_log("not json", None)
    assert bad["parse_success"] is False
    assert bad["parse_error"] == "unparsed"


def test_split_test_of_patch_keeps_no_exception_meaning():
    payload = {
        "ok": True,
        "status": "pass",
        "return_value": {"status": "Index out of range"},
        "error": None,
        "error_type": None,
    }
    split = split_test_of_patch(payload)
    assert split["execution_success"] is True
    assert split["execution_success_means"] == "no_exception"
    assert split["exception"] is None
    assert split["return_value"] == {"status": "Index out of range"}
    assert "solution_correct" not in split

    failed = {
        "ok": False,
        "status": "fail",
        "return_value": None,
        "error": "list index out of range",
        "error_type": "IndexError",
    }
    split_fail = split_test_of_patch(failed)
    assert split_fail["execution_success"] is False
    assert split_fail["exception"] == {
        "error_type": "IndexError",
        "error": "list index out of range",
    }


def test_chat_kwargs_mark_tools_not_used():
    snap = chat_kwargs_snapshot(
        {"num_predict": 10, "temperature": 0, "timeout_seconds": 5},
        "dummy-model",
    )
    assert snap["tools"] == "not_used"
    assert snap["tool_presentation"] == "system_text"
    assert snap["model"] == "dummy-model"
    assert "tools" not in snap["kwargs_source"]["harness_chat_call"]
    assert "tools" in snap["kwargs_source"]["not_passed"]


def test_ask_saves_messages_before_chat_mutation(monkeypatch):
    def fake_chat(**kwargs):
        kwargs["messages"][0]["content"] = "mutated-in-chat"
        return _reply('{"action":"final","summary":"x","patch_source":null,"help":false}')

    monkeypatch.setattr(harness, "chat", fake_chat)
    messages = [{"role": "system", "content": "SYSTEM-TEXT"}]
    text, err, before, kwargs = harness._ask(messages, "first-user")
    assert err is None
    assert text.startswith("{")
    assert before[0]["content"] == "SYSTEM-TEXT"
    assert before[1]["content"] == "first-user"
    assert len(before) == 2
    messages[1]["content"] = "later-user-change"
    assert before[1]["content"] == "first-user"
    assert kwargs["tools"] == "not_used"


def test_scripted_loop_saves_messages_raw_parsed_tool_sent(monkeypatch):
    replies = [
        '{"action":"tool","name":"get_current_failure","arguments":{}}',
        '{"action":"final","summary":"done","patch_source":'
        + json.dumps(PASSING_SOURCE)
        + ',"help":false}',
    ]
    record, seen, live_messages = _run_scripted(monkeypatch, replies)
    assert all("tools" not in call for call in seen)
    assert record["observability"]["stop_reason"] == "final"
    assert record["observability"]["test_returned_to_llm"] is False
    assert record["observability"]["experiment_start"]
    assert record["observability"]["experiment_end"]

    turn0 = record["turns"][0]
    messages = turn0["observability"]["messages"]
    assert messages[0]["role"] == "system"
    assert "get_current_failure" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "IndexError" in messages[1]["content"]
    assert turn0["raw"].startswith('{"action":"tool"')
    assert turn0["parsed"]["name"] == "get_current_failure"
    assert turn0["observability"]["parse_success"] is True
    tool = turn0["observability"]["tool"]
    assert tool["tool_name"] == "get_current_failure"
    assert tool["raw_result"]
    assert tool["sent_tool_result"]
    assert tool["truncated"] is False
    assert tool["sent_equals_raw_json"] is True
    assert "Tool result:\n" + tool["sent_tool_result"] == (
        "Tool result:\n" + json.dumps(tool["raw_result"], ensure_ascii=False, default=str)
    )

    live_messages[0]["content"] = "changed-after"
    assert turn0["observability"]["messages"][0]["content"] != "changed-after"

    turn1 = record["turns"][1]
    user_contents = [m["content"] for m in turn1["observability"]["messages"] if m["role"] == "user"]
    assert any(c.startswith("Tool result:\n") for c in user_contents)
    assert record["patch_source"] == PASSING_SOURCE
    assert record["final_summary"] == "done"
    assert record["help"] is False
    assert record["observability"]["repair_proposal"]["turn_id"] == 2
    assert record["test_of_patch"]["ok"] is True
    assert record["test_of_patch"]["status"] == "pass"
    split = record["test_observability"]
    assert split["execution_success"] is True
    assert split["execution_success_means"] == "no_exception"
    assert split["return_value"] == {"status": "ok"}
    assert "solution_correct" not in split


def test_truncated_tool_result_on_harness_path(monkeypatch):
    big = {"ok": True, "blob": "x" * (TOOL_RESULT_CHAR_LIMIT + 80)}

    def fake_dispatch(name, arguments=None):
        if name == "experiment_test_source":
            return real_dispatch(name, arguments)
        return big

    monkeypatch.setattr(harness, "dispatch", fake_dispatch)
    replies = [
        '{"action":"tool","name":"get_current_failure","arguments":{}}',
        '{"action":"final","summary":"s","patch_source":null,"help":false}',
    ]
    record, _, _ = _run_scripted(monkeypatch, replies)
    tool = record["turns"][0]["observability"]["tool"]
    assert tool["truncated"] is True
    assert tool["sent_equals_raw_json"] is False
    assert tool["sent_tool_result"].endswith("...(truncated)")
    assert len(tool["raw_result"]["blob"]) > TOOL_RESULT_CHAR_LIMIT


def test_parse_failure_saves_raw_and_retry_user(monkeypatch):
    replies = [
        "this is not json",
        '{"action":"final","summary":"after-retry","patch_source":null,"help":false}',
    ]
    record, _, _ = _run_scripted(monkeypatch, replies)
    turn0 = record["turns"][0]
    assert turn0["raw"] == "this is not json"
    assert turn0["parsed"] is None
    assert turn0["observability"]["parse_success"] is False
    assert turn0["observability"]["parse_error"] == "unparsed"
    retry = turn0["observability"]["retry_user"]
    assert retry == 'Reply with only JSON: {"action":"tool",...} or {"action":"final",...}'
    assert "unparsed_llm_output" in record["notes"]
    turn1 = record["turns"][1]
    last_user = [m for m in turn1["observability"]["messages"] if m["role"] == "user"][-1]
    assert last_user["content"] == retry


def test_test_of_patch_exception_split_via_sandbox(monkeypatch):
    replies = [
        '{"action":"final","summary":"still broken","patch_source":'
        + json.dumps(FAILING_SOURCE)
        + ',"help":false}',
    ]
    record, _, _ = _run_scripted(monkeypatch, replies)
    assert record["test_of_patch"]["ok"] is False
    assert record["test_of_patch"]["status"] == "fail"
    assert record["test_of_patch"]["error_type"] == "IndexError"
    split = record["test_observability"]
    assert split["execution_success"] is False
    assert split["execution_success_means"] == "no_exception"
    assert split["exception"]["error_type"] == "IndexError"
    assert split["exception"].get("traceback")
    assert split["return_value"] is None
    assert record["test_of_patch"].get("traceback")
    assert "solution_correct" not in record
    assert "solution_correct" not in split
