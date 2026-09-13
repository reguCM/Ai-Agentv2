"""
LLM に Tool を選ばせて Failure を解かせる実験。FA ではない。手順は指定しない。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tests.fixtures import broken_tools
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.tool_builder.validate.result import validate_tool_result

from research.llm_benchmarks.problem_solving_experiment import adapters
from research.llm_benchmarks.problem_solving_experiment.catalog import llm_catalog_text
from research.llm_benchmarks.problem_solving_experiment.dispatch import dispatch
from research.llm_benchmarks.problem_solving_experiment.observability import (
    chat_kwargs_snapshot,
    copy_messages,
    dump_tool_result_for_llm,
    parse_log,
    split_test_of_patch,
)


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROPOSAL = {
    "name": "cpu_status",
    "module": "tools.system.cpu.cpu_status",
    "function": "cpu_status",
    "output": ["status"],
}
OUT_DIR = Path("research/llm_benchmarks/problem_solving_experiment/results")
MAX_TURNS = 12

SYSTEM = """You solve one software test failure.
You may call tools listed below. Do not wait for the experimenter to tell you which tool to use.
If you cannot patch safely, call request_human_help or stop.
Do not classify the case as Repair, Research, or Environment.

To call a tool, reply with ONLY this JSON object (no markdown):
{"action":"tool","name":"<tool name>","arguments":{}}

When finished, reply with ONLY:
{"action":"final","summary":"...","patch_source":null_or_python_source,"help":false}

Tools:
""" + llm_catalog_text()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _parse_action(text):
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _ask(messages, user_text):
    messages.append({"role": "user", "content": user_text})
    messages_before_chat = copy_messages(messages)
    chat_kwargs = chat_kwargs_snapshot(PROFILE, MODEL)
    try:
        response = chat(model=MODEL, messages=messages)
        text = (response.message.content or "").strip()
        err = None
    except LLMTimeoutError as exc:
        text = ""
        err = str(exc)
    messages.append({"role": "assistant", "content": text or f"[timeout] {err}"})
    return text, err, messages_before_chat, chat_kwargs


def _new_record(case_id):
    return {
        "id": case_id,
        "model": MODEL,
        "turns": [],
        "tools_called": [],
        "help": False,
        "patch_source": None,
        "test_of_patch": None,
        "notes": [],
        "observability": {
            "experiment_start": _now(),
            "experiment_end": None,
            "stop_reason": None,
            "tool_calls": [],
            "test_returned_to_llm": False,
            "repair_proposal": None,
        },
    }


def _run_turns(messages, user, record):
    stop_reason = None
    for step in range(1, MAX_TURNS + 1):
        text, timeout, messages_before_chat, chat_kwargs = _ask(messages, user)
        action = _parse_action(text)
        parsed_obs = parse_log(text, action)
        turn = {
            "step": step,
            "at": _now(),
            "raw": text,
            "timeout": timeout,
            "parsed": action,
            "observability": {
                "turn_id": step,
                "messages": messages_before_chat,
                "chat_kwargs": chat_kwargs,
                "parse_success": parsed_obs["parse_success"],
                "parse_error": parsed_obs["parse_error"],
                "retry_user": None,
                "tool": None,
            },
        }
        record["turns"].append(turn)
        if timeout:
            record["notes"].append("llm_timeout")
            stop_reason = "llm_timeout"
            break
        if not action:
            record["notes"].append("unparsed_llm_output")
            user = 'Reply with only JSON: {"action":"tool",...} or {"action":"final",...}'
            turn["observability"]["retry_user"] = user
            continue
        kind = action.get("action")
        if kind == "tool":
            name = action.get("name")
            args = action.get("arguments") or {}
            result = dispatch(name, args)
            record["tools_called"].append(name)
            if isinstance(result, dict) and result.get("help_requested"):
                record["help"] = True
            packed = dump_tool_result_for_llm(result)
            user = packed["llm_user_payload"]
            tool_obs = {
                "tool_call_id": f"{step}:1",
                "turn_id": step,
                "tool_name": name,
                "arguments": args,
                "raw_result": packed["raw_result"],
                "sent_tool_result": packed["sent_tool_result"],
                "truncated": packed["truncated"],
                "sent_equals_raw_json": packed["sent_equals_raw_json"],
                "execution_error": packed["execution_error"],
            }
            turn["observability"]["tool"] = tool_obs
            record["observability"]["tool_calls"].append(tool_obs)
            continue
        if kind == "final":
            record["patch_source"] = action.get("patch_source")
            record["final_summary"] = action.get("summary")
            record["help"] = bool(action.get("help"))
            record["observability"]["repair_proposal"] = {
                "turn_id": step,
                "existing_fields": ["patch_source", "final_summary", "help"],
            }
            if record["patch_source"]:
                record["test_of_patch"] = dispatch(
                    "experiment_test_source",
                    {"source": record["patch_source"]},
                )
                record["test_observability"] = split_test_of_patch(
                    record["test_of_patch"]
                )
            stop_reason = "final"
            break
        record["notes"].append(f"unknown_action:{kind}")
        user = 'Unknown action. Use "tool" or "final".'
        turn["observability"]["retry_user"] = user
    if stop_reason is None:
        stop_reason = "max_turns"
    record["observability"]["stop_reason"] = stop_reason
    record["observability"]["experiment_end"] = _now()
    return record


def run_case(case):
    from tools.system.tool_builder.test import test_tool as _test
    from pathlib import Path as P

    tool_path = P("tools/system/cpu/cpu_status.py")
    original = tool_path.read_text(encoding="utf-8")
    record = _new_record(case["id"])
    try:
        tool_path.write_text(case["source"].strip() + "\n", encoding="utf-8")
        test_result = _test("cpu_status")
    finally:
        tool_path.write_text(original, encoding="utf-8")

    validation = validate_tool_result(
        PROPOSAL,
        test_result,
        implementation={},
        source=case["source"],
    )
    adapters.set_session(
        tool_name="cpu_status",
        test_result=test_result,
        validation=validation,
        source=case["source"],
    )
    record["initial_minimal"] = {
        "tool_name": "cpu_status",
        "status": test_result.get("status"),
        "error_type": test_result.get("error_type"),
        "error": test_result.get("error"),
    }
    messages = [{"role": "system", "content": SYSTEM}]
    user = (
        "Solve this test failure. Get any information you need yourself.\n"
        + json.dumps(record["initial_minimal"], ensure_ascii=False)
    )
    return _run_turns(messages, user, record)


def main():
    cases = [
        {
            "id": "index_error",
            "source": broken_tools.SOURCE_INDEX_ERROR,
        }
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / stamp
    out.mkdir(parents=True, exist_ok=True)
    run = {
        "note": "Problem-solving experiment with tools. Not FA spec.",
        "at": _now(),
        "model": MODEL,
        "cases": [],
    }
    try:
        for case in cases:
            print(f"CASE {case['id']}", flush=True)
            record = run_case(case)
            run["cases"].append(record)
            (out / f"{case['id']}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"  tools={record['tools_called']} help={record['help']} "
                f"patch={bool(record['patch_source'])}",
                flush=True,
            )
    finally:
        stop_model(MODEL)
    (out / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
