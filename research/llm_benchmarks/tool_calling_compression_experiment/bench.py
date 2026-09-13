"""
Native Tool Calling と Tool なし文章経路の比較。
既存 Problem Solving / Problem Analysis 実験・fixture・結果には接続しない。
探索手順・Tool 利用を Prompt で指定しない。思考過程の出力も要求しない。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.tool_calling_compression_experiment.execute import (
    format_execution_block,
    run_program,
    run_test,
    split_outcomes,
)
from research.llm_benchmarks.tool_calling_compression_experiment.observe import summarize_run
from research.llm_benchmarks.tool_calling_compression_experiment.workspace import (
    OLLAMA_TOOLS,
    copy_fixture,
    dispatch,
    dump_result,
    git_diff,
    git_init_workspace,
)


OUT_DIR = Path(
    "research/llm_benchmarks/tool_calling_compression_experiment/results"
)
MAX_TURNS_NATIVE = 12
MAX_TURNS_TEXT = 1
COMPARE_MODELS = [
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
    {"ollama_name": "gemma3:12b", "dir_name": "gemma3_12b"},
]
PROMPT = "Resolve the problem."
FIXTURE_VERSION = "ticket_stage_v1"


def _now():
    return datetime.now(timezone.utc).isoformat()


def chat_kwargs_snapshot(profile, model, path_name):
    options = {
        "num_predict": int(profile.get("num_predict") or 2048),
        "temperature": float(profile.get("temperature") or 0),
    }
    if profile.get("context_limit"):
        options["num_ctx"] = int(profile.get("context_limit"))
    native = path_name == "native"
    passed = ["model", "messages"]
    if native:
        passed.append("tools")
    return {
        "model": model,
        "tools": "ollama_native" if native else "not_passed",
        "keep_alive": profile.get("keep_alive") or "5m",
        "options": options,
        "timeout_seconds": int(profile.get("timeout_seconds") or 90),
        "harness_chat_call": passed,
        "tool_calling_path": path_name,
    }


def _message_dict(message):
    if isinstance(message, dict):
        payload = dict(message)
        if payload.get("tool_calls"):
            payload["tool_calls"] = _tool_calls_list(payload["tool_calls"])
        return payload
    data = {
        "role": getattr(message, "role", None),
        "content": getattr(message, "content", None),
    }
    if getattr(message, "thinking", None):
        data["thinking_observed"] = True
    calls = getattr(message, "tool_calls", None)
    if calls:
        data["tool_calls"] = _tool_calls_list(calls)
    return data


def _tool_calls_list(calls):
    out = []
    for item in calls or []:
        if isinstance(item, dict):
            fn = item.get("function") or item
            out.append(
                {
                    "id": item.get("id") or item.get("tool_call_id"),
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments") or item.get("arguments"),
                }
            )
            continue
        fn = getattr(item, "function", item)
        out.append(
            {
                "id": getattr(item, "id", None) or getattr(item, "tool_call_id", None),
                "name": getattr(fn, "name", None),
                "arguments": getattr(fn, "arguments", None),
            }
        )
    return out


def _args(value):
    if value is None:
        return {}
    if isinstance(value, str):
        if not value.strip():
            return {}
        return json.loads(value)
    return dict(value)


def native_tool_calls(response):
    parsed = []
    for item in _tool_calls_list(getattr(response.message, "tool_calls", None) or []):
        if not item.get("name"):
            continue
        try:
            arguments = _args(item.get("arguments"))
        except json.JSONDecodeError:
            arguments = {"_parse_error": item.get("arguments")}
        parsed.append(
            {
                "id": item.get("id"),
                "name": item["name"],
                "arguments": arguments,
            }
        )
    return parsed


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_initial_user(pytest_run, program_run):
    return (
        PROMPT
        + "\n\n"
        + format_execution_block("pytest", pytest_run)
        + "\n\n"
        + format_execution_block("python main.py", program_run)
        + "\n"
    )


def test_feedback_user(pytest_run, program_run):
    return (
        "Test result:\n\n"
        + format_execution_block("pytest", pytest_run)
        + "\n\n"
        + format_execution_block("python main.py", program_run)
        + "\n"
    )


def _timeout_turn(turn_id, turn_started, messages_before, kwargs_snap, timeout):
    return {
        "turn_id": turn_id,
        "timestamp": turn_started,
        "model": kwargs_snap.get("model"),
        "messages_before": messages_before,
        "chat_kwargs": kwargs_snap,
        "raw_output": "",
        "parsed_output": None,
        "parse_status": "timeout",
        "tool_calls": [],
        "tool_results": [],
        "files_read": [],
        "files_changed": [],
        "test_result": None,
        "error": timeout,
        "unexecuted_text_observed": False,
    }


def run_text_path(model_name, model_dir: Path, initial_pytest, initial_program, profile):
    workspace = model_dir / "workspace"
    copy_fixture(workspace)
    git_init_workspace(workspace)
    messages = [{"role": "user", "content": build_initial_user(initial_pytest, initial_program)}]
    started = _now()
    kwargs_snap = chat_kwargs_snapshot(profile, model_name, "text")
    turn_started = _now()
    call_ok = True
    error = None
    stop_reason = "text_path_single_turn"
    try:
        response = chat(model=model_name, messages=messages)
        raw = (response.message.content or "").strip()
        thinking = getattr(response.message, "thinking", None)
        native_calls = native_tool_calls(response)
        timeout = None
    except LLMTimeoutError as exc:
        timeout = str(exc)
        call_ok = False
        error = timeout
        stop_reason = "timeout"
        raw = ""
        thinking = None
        native_calls = []
        response = None

    turns = []
    if timeout:
        turns.append(_timeout_turn(1, turn_started, [_message_dict(item) for item in messages], kwargs_snap, timeout))
    else:
        messages.append({"role": "assistant", "content": raw})
        turns.append(
            {
                "turn_id": 1,
                "timestamp": turn_started,
                "model": model_name,
                "messages_before": [_message_dict(item) for item in messages[:1]],
                "chat_kwargs": kwargs_snap,
                "raw_output": raw,
                "parsed_output": {
                    "native_tool_calls": native_calls,
                    "application_side_tool_parsing": "not_used",
                },
                "parse_status": "text_path_no_tools_param",
                "tool_calls": [],
                "tool_call_id": None,
                "tool_name": None,
                "tool_arguments": None,
                "tool_results": [],
                "files_read": [],
                "files_changed": [],
                "test_result": None,
                "thinking_observed": bool(thinking),
                "native_tools_enabled": False,
                "unexecuted_native_calls_in_text_path": native_calls,
            }
        )
        if thinking:
            turns[-1]["thinking"] = thinking

    record = {
        "experiment_id": "tool_calling_compression",
        "model": model_name,
        "prompt": PROMPT,
        "fixture_version": FIXTURE_VERSION,
        "tool_calling_path": "text",
        "tool_calling_mode": "no_tools_param",
        "application_side_tool_parsing": "not_used",
        "experiment_start": started,
        "experiment_end": _now(),
        "stop_reason": stop_reason,
        "call_ok": call_ok,
        "error": error,
        "turns": turns,
        "final_git_diff": git_diff(workspace),
        "notes": [
            "not_connected_to_existing_loops",
            "no_search_order_in_prompt",
            "no_tool_catalog_in_prompt",
            "thinking_not_requested",
            "tools_not_executed_on_text_path",
        ],
    }
    record["mechanical"] = summarize_run(record)
    save_json(model_dir / "run.json", record)
    save_json(model_dir / "messages.json", [_message_dict(item) for item in messages])
    return record


def run_native_path(model_name, model_dir: Path, initial_pytest, initial_program, profile):
    workspace = model_dir / "workspace"
    copy_fixture(workspace)
    git_init_workspace(workspace)
    messages = [{"role": "user", "content": build_initial_user(initial_pytest, initial_program)}]
    started = _now()
    turns = []
    stop_reason = None
    call_ok = True
    error = None
    tool_order = 0
    patch_rounds = 0
    first_patch_passed = None
    native_supported = True

    for turn_id in range(1, MAX_TURNS_NATIVE + 1):
        messages_before = [_message_dict(item) for item in messages]
        kwargs_snap = chat_kwargs_snapshot(profile, model_name, "native")
        turn_started = _now()
        try:
            try:
                response = chat(model=model_name, messages=messages, tools=OLLAMA_TOOLS)
            except Exception as exc:
                if "does not support tools" in str(exc).lower():
                    native_supported = False
                    stop_reason = "native_tools_unsupported"
                    call_ok = False
                    error = str(exc)
                    turns.append(
                        {
                            "turn_id": turn_id,
                            "timestamp": turn_started,
                            "model": model_name,
                            "messages_before": messages_before,
                            "chat_kwargs": kwargs_snap,
                            "raw_output": "",
                            "parsed_output": None,
                            "parse_status": "native_tools_unsupported",
                            "tool_calls": [],
                            "tool_results": [],
                            "files_read": [],
                            "files_changed": [],
                            "test_result": None,
                            "error": error,
                        }
                    )
                    break
                raise
            raw = (response.message.content or "").strip()
            thinking = getattr(response.message, "thinking", None)
            native_calls = native_tool_calls(response)
        except LLMTimeoutError as exc:
            call_ok = False
            error = str(exc)
            stop_reason = "timeout"
            turns.append(_timeout_turn(turn_id, turn_started, messages_before, kwargs_snap, error))
            break

        turn_tools = []
        files_read = []
        files_changed = []
        test_result = None
        patched = False

        messages.append(response.message)

        for call in native_calls:
            tool_order += 1
            name = call["name"]
            arguments = call.get("arguments") or {}
            result = dispatch(workspace, name, arguments)
            dumped = dump_result(result)
            turn_tools.append(
                {
                    "turn_id": turn_id,
                    "tool_call_order": tool_order,
                    "tool_call_id": call.get("id"),
                    "tool_name": name,
                    "tool_arguments": arguments,
                    "arguments": arguments,
                    "tool_result_raw": dumped["raw_result"],
                    "tool_result_sent_to_llm": dumped["sent_tool_result"],
                    "raw_result": dumped["raw_result"],
                    "sent_result": dumped["sent_tool_result"],
                    "truncated": dumped["truncated"],
                }
            )
            if name == "read_file" and result.get("ok"):
                files_read.append(result.get("path"))
            if name == "apply_patch" and result.get("ok"):
                files_changed.append(result.get("path"))
                patched = True
            tool_message = {
                "role": "tool",
                "content": dumped["sent_tool_result"],
                "tool_name": name,
            }
            if call.get("id"):
                tool_message["tool_call_id"] = call["id"]
            messages.append(tool_message)
            if name == "run_test":
                program_run = run_program(workspace)
                test_result = {
                    "source": "llm_run_test",
                    "pytest": result,
                    "python_main": program_run,
                    **split_outcomes(result, program_run),
                }

        if patched:
            patch_rounds += 1
            pytest_run = run_test(workspace)
            program_run = run_program(workspace)
            outcomes = split_outcomes(pytest_run, program_run)
            feedback = test_feedback_user(pytest_run, program_run)
            test_result = {
                "source": "harness_after_patch",
                "pytest": pytest_run,
                "python_main": program_run,
                "git_diff": git_diff(workspace),
                "sent_to_llm": feedback,
                **outcomes,
            }
            messages.append({"role": "user", "content": feedback})
            if first_patch_passed is None:
                first_patch_passed = bool(outcomes["test_pass"])

        turns.append(
            {
                "turn_id": turn_id,
                "timestamp": turn_started,
                "model": model_name,
                "messages_before": messages_before,
                "chat_kwargs": kwargs_snap,
                "raw_output": raw,
                "parsed_output": {
                    "native_tool_calls": native_calls,
                    "application_side_tool_parsing": "not_used",
                },
                "parsed": {
                    "native_tool_calls": native_calls,
                    "application_side_tool_parsing": "not_used",
                },
                "parse_status": "native_tool_calling" if native_calls else "no_native_tool_call",
                "tool_calls": [item["tool_name"] for item in turn_tools],
                "tool_results": turn_tools,
                "files_read": files_read,
                "files_changed": files_changed,
                "test_result": test_result,
                "thinking_observed": bool(thinking),
                "native_tools_enabled": True,
                "failure_before": None,
                "failure_after": (
                    None
                    if test_result is None
                    else {
                        "test_pass": test_result.get("test_pass"),
                        "execution_success": test_result.get("execution_success"),
                    }
                ),
            }
        )
        if thinking:
            turns[-1]["thinking"] = thinking
        if turn_tools:
            turns[-1]["tool_call_id"] = turn_tools[0].get("tool_call_id")
            turns[-1]["tool_name"] = turn_tools[0].get("tool_name")
            turns[-1]["tool_arguments"] = turn_tools[0].get("tool_arguments")

        if not native_calls:
            idle = sum(
                1
                for item in turns[-2:]
                if not item.get("tool_calls")
            )
            if len(turns) >= 2 and idle >= 2:
                stop_reason = "idle_no_native_tool"
                break
    else:
        stop_reason = "max_turns"

    if stop_reason is None:
        stop_reason = "loop_end"

    record = {
        "experiment_id": "tool_calling_compression",
        "model": model_name,
        "prompt": PROMPT,
        "fixture_version": FIXTURE_VERSION,
        "tool_calling_path": "native",
        "tool_calling_mode": "ollama_native_tools" if native_supported else "unsupported",
        "application_side_tool_parsing": "not_used",
        "experiment_start": started,
        "experiment_end": _now(),
        "stop_reason": stop_reason,
        "call_ok": call_ok,
        "error": error,
        "native_tools_supported": native_supported,
        "patch_rounds": patch_rounds,
        "first_patch_test_pass": first_patch_passed,
        "turns": turns,
        "final_git_diff": git_diff(workspace),
        "notes": [
            "not_connected_to_existing_loops",
            "no_search_order_in_prompt",
            "no_tool_catalog_in_prompt",
            "thinking_not_requested",
            "only_native_tool_calls_executed",
        ],
    }
    record["mechanical"] = summarize_run(record)
    save_json(model_dir / "run.json", record)
    save_json(model_dir / "messages.json", [_message_dict(item) for item in messages])
    return record


def main():
    profile = get_llm_profile()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    root.mkdir(parents=True, exist_ok=True)
    fixture_dir = root / "fixture"
    copy_fixture(fixture_dir)
    initial_pytest = run_test(fixture_dir)
    initial_program = run_program(fixture_dir)
    initial_dir = root / "initial_execution"
    initial_dir.mkdir(parents=True, exist_ok=True)
    save_json(initial_dir / "pytest.json", initial_pytest)
    save_json(initial_dir / "python_main.json", initial_program)
    (initial_dir / "pytest.stdout.txt").write_text(initial_pytest["stdout"], encoding="utf-8")
    (initial_dir / "pytest.stderr.txt").write_text(initial_pytest["stderr"], encoding="utf-8")
    (initial_dir / "main.stderr.txt").write_text(initial_program["stderr"], encoding="utf-8")
    (initial_dir / "main.stdout.txt").write_text(initial_program["stdout"], encoding="utf-8")
    print(
        f"initial pytest={initial_pytest['exit_code']} main={initial_program['exit_code']}",
        flush=True,
    )
    run_meta = {
        "experiment_id": "tool_calling_compression",
        "fixture_version": FIXTURE_VERSION,
        "prompt": PROMPT,
        "at": _now(),
        "temperature": float(profile.get("temperature") or 0),
        "max_turns_native": MAX_TURNS_NATIVE,
        "max_turns_text": MAX_TURNS_TEXT,
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "paths": ["text", "native"],
        "initial_pytest_exit_code": initial_pytest["exit_code"],
        "initial_main_exit_code": initial_program["exit_code"],
        "runs": [],
    }
    for item in COMPARE_MODELS:
        for path_name, runner in (("text", run_text_path), ("native", run_native_path)):
            model_dir = root / item["dir_name"] / path_name
            model_dir.mkdir(parents=True, exist_ok=True)
            print(f"MODEL {item['ollama_name']} PATH {path_name}", flush=True)
            try:
                record = runner(
                    item["ollama_name"],
                    model_dir,
                    initial_pytest,
                    initial_program,
                    profile,
                )
            finally:
                stop_model(item["ollama_name"])
            summary = {
                "model": item["ollama_name"],
                "path": path_name,
                "stop_reason": record["stop_reason"],
                "turns": len(record["turns"]),
                "call_ok": record["call_ok"],
                "parse_status": [turn.get("parse_status") for turn in record["turns"]],
                "tool_calls": [
                    turn.get("tool_calls") for turn in record["turns"]
                ],
            }
            run_meta["runs"].append(summary)
            print(f"  {summary}", flush=True)
    save_json(root / "run.json", run_meta)
    (root / "README.md").write_text(
        "# tool_calling_compression\n\n"
        "一次資料。分析は TOOL_CALLING_COMPRESSION_EXPERIMENT.md。\n",
        encoding="utf-8",
    )
    print(f"wrote {root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
