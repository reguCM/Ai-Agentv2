"""
Test失敗後の再判断観測。既存実コード実験ループ・fixture・結果には接続しない。
探索順・別ファイル調査を Prompt で指定しない。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.problem_solving_experiment.rejudgment_execute import (
    format_execution_block,
    run_program,
    run_test,
    split_outcomes,
)
from research.llm_benchmarks.problem_solving_experiment.rejudgment_workspace import (
    OLLAMA_TOOLS,
    apply_patch,
    copy_fixture,
    dispatch,
    dump_result,
    git_diff,
    git_init_workspace,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/"
    "problem_solving_rejudgment"
)
MAX_TURNS = 16
COMPARE_MODELS = [
    {"ollama_name": "deepseek-coder-v2:16b", "dir_name": "deepseek"},
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
]
PROMPT = "Analyze the problem and resolve it."
FIXTURE_VERSION = "real_code_rejudgment_v1"
TOOL_NAMES = {item["function"]["name"] for item in OLLAMA_TOOLS}
_NAMED_FENCE = re.compile(
    r"(?P<name>main\.py|helper\.py|config\.py|runtime\.py|tests/test_main\.py)"
    r"\s*\n```(?:python)?\n(?P<body>.*?)```",
    re.S,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def chat_kwargs_snapshot(profile, model, use_native_tools):
    options = {
        "num_predict": int(profile.get("num_predict") or 2048),
        "temperature": float(profile.get("temperature") or 0),
    }
    if profile.get("context_limit"):
        options["num_ctx"] = int(profile.get("context_limit"))
    passed = ["model", "messages"]
    if use_native_tools:
        passed.append("tools")
    return {
        "model": model,
        "tools": "ollama_native" if use_native_tools else "not_passed",
        "keep_alive": profile.get("keep_alive") or "5m",
        "options": options,
        "timeout_seconds": int(profile.get("timeout_seconds") or 90),
        "harness_chat_call": passed,
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
    for item in calls:
        if isinstance(item, dict):
            fn = item.get("function") or item
            out.append(
                {
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments") or item.get("arguments"),
                }
            )
            continue
        fn = getattr(item, "function", item)
        out.append(
            {
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


def parse_text_tool(text):
    if not text:
        return None, "empty"
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        name = obj.get("tool") or obj.get("name")
        if name not in TOOL_NAMES:
            continue
        arguments = obj.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        if name == "apply_patch" and "content" in obj and "content" not in arguments:
            arguments = {
                "path": obj.get("path") or arguments.get("path"),
                "content": obj.get("content"),
            }
        return {"name": name, "arguments": arguments}, "parsed_from_text"
    return None, "no_tool_json"


def native_tool_calls(response):
    parsed = []
    for item in _tool_calls_list(getattr(response.message, "tool_calls", None) or []):
        if not item.get("name"):
            continue
        try:
            arguments = _args(item.get("arguments"))
        except json.JSONDecodeError:
            arguments = {}
        parsed.append({"name": item["name"], "arguments": arguments})
    return parsed


def parse_named_fences(text):
    return [
        {"path": match.group("name"), "content": match.group("body")}
        for match in _NAMED_FENCE.finditer(text or "")
    ]


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


def run_one(model_name, model_dir: Path, initial_pytest, initial_program, profile):
    workspace = model_dir / "workspace"
    copy_fixture(workspace)
    git_init_workspace(workspace)
    messages = [{"role": "user", "content": build_initial_user(initial_pytest, initial_program)}]
    use_native = True
    turns = []
    stop_reason = None
    started = _now()
    call_ok = True
    error = None
    tool_order = 0
    patch_rounds = 0
    first_patch_passed = None

    for turn_id in range(1, MAX_TURNS + 1):
        messages_before = [_message_dict(item) for item in messages]
        kwargs_snap = chat_kwargs_snapshot(profile, model_name, use_native)
        turn_started = _now()
        try:
            chat_args = {"model": model_name, "messages": messages}
            if use_native:
                chat_args["tools"] = OLLAMA_TOOLS
            try:
                response = chat(**chat_args)
            except Exception as exc:
                if use_native and "does not support tools" in str(exc).lower():
                    use_native = False
                    kwargs_snap = chat_kwargs_snapshot(profile, model_name, False)
                    response = chat(model=model_name, messages=messages)
                else:
                    raise
            raw = (response.message.content or "").strip()
            thinking = getattr(response.message, "thinking", None)
            native_calls = native_tool_calls(response)
            timeout = None
        except LLMTimeoutError as exc:
            timeout = str(exc)
            call_ok = False
            error = timeout
            stop_reason = "timeout"
            turns.append(
                {
                    "turn_id": turn_id,
                    "timestamp": turn_started,
                    "messages_before_chat": messages_before,
                    "chat_kwargs": kwargs_snap,
                    "raw_output": "",
                    "parsed": None,
                    "parse_status": "timeout",
                    "tool_calls": [],
                    "tool_results": [],
                    "files_read": [],
                    "files_changed": [],
                    "test_result": None,
                    "error": timeout,
                }
            )
            break

        text_call, parse_status = parse_text_tool(raw)
        calls = native_calls or ([text_call] if text_call else [])
        fences = [] if calls else parse_named_fences(raw)
        turn_tools = []
        files_read = []
        files_changed = []
        test_result = None
        patched = False

        if native_calls:
            messages.append(response.message)
        else:
            messages.append({"role": "assistant", "content": raw})

        for call in calls:
            tool_order += 1
            name = call["name"]
            arguments = call.get("arguments") or {}
            result = dispatch(workspace, name, arguments)
            dumped = dump_result(result)
            turn_tools.append(
                {
                    "turn_id": turn_id,
                    "tool_call_order": tool_order,
                    "tool_name": name,
                    "arguments": arguments,
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
            if native_calls:
                messages.append(
                    {
                        "role": "tool",
                        "content": dumped["sent_tool_result"],
                        "tool_name": name,
                    }
                )
            else:
                messages.append({"role": "user", "content": dumped["llm_user_payload"]})
            if name == "run_test":
                program_run = run_program(workspace)
                test_result = {
                    "source": "llm_run_test",
                    "pytest": result,
                    "python_main": program_run,
                    **split_outcomes(result, program_run),
                }

        for item in fences:
            tool_order += 1
            before = git_diff(workspace)
            result = apply_patch(workspace, item["path"], item["content"])
            dumped = dump_result(result)
            turn_tools.append(
                {
                    "turn_id": turn_id,
                    "tool_call_order": tool_order,
                    "tool_name": "apply_patch",
                    "arguments": {"path": item["path"], "via": "named_fence"},
                    "raw_result": dumped["raw_result"],
                    "sent_result": dumped["sent_tool_result"],
                    "truncated": dumped["truncated"],
                }
            )
            if result.get("ok"):
                files_changed.append(result.get("path"))
                patched = True
            if not calls:
                messages.append(
                    {
                        "role": "user",
                        "content": dumped["llm_user_payload"],
                    }
                )

        if patched:
            patch_rounds += 1
            pytest_run = run_test(workspace)
            program_run = run_program(workspace)
            outcomes = split_outcomes(pytest_run, program_run)
            test_result = {
                "source": "harness_after_patch",
                "pytest": pytest_run,
                "python_main": program_run,
                "git_diff": git_diff(workspace),
                **outcomes,
            }
            feedback = test_feedback_user(pytest_run, program_run)
            test_result["sent_to_llm"] = feedback
            messages.append({"role": "user", "content": feedback})
            if first_patch_passed is None:
                first_patch_passed = bool(outcomes["test_pass"])

        parse_payload = {
            "native_tool_calls": native_calls,
            "text_tool": text_call,
            "named_fences": fences,
        }
        turns.append(
            {
                "turn_id": turn_id,
                "timestamp": turn_started,
                "messages_before_chat": messages_before,
                "chat_kwargs": kwargs_snap,
                "raw_output": raw,
                "parsed": parse_payload,
                "parse_status": (
                    "native_tools"
                    if native_calls
                    else parse_status
                    if text_call
                    else ("named_fences" if fences else "no_tool")
                ),
                "tool_calls": [item["tool_name"] for item in turn_tools],
                "tool_results": turn_tools,
                "files_read": files_read,
                "files_changed": files_changed,
                "test_result": test_result,
                "thinking_observed": bool(thinking),
                "native_tools_enabled": use_native,
            }
        )
        if thinking:
            turns[-1]["thinking"] = thinking

        acted = bool(calls or fences)
        if not acted:
            idle = sum(
                1
                for item in turns[-2:]
                if not item.get("tool_calls") and not item.get("files_changed")
            )
            if len(turns) >= 2 and idle >= 2:
                stop_reason = "idle_no_tool_or_write"
                break
    else:
        stop_reason = "max_turns"

    if stop_reason is None:
        stop_reason = "loop_end"

    record = {
        "experiment_id": "problem_solving_rejudgment",
        "model": model_name,
        "prompt": PROMPT,
        "fixture_version": FIXTURE_VERSION,
        "experiment_start": started,
        "experiment_end": _now(),
        "stop_reason": stop_reason,
        "call_ok": call_ok,
        "error": error,
        "native_tools_enabled_final": use_native,
        "patch_rounds": patch_rounds,
        "first_patch_test_pass": first_patch_passed,
        "turns": turns,
        "final_git_diff": git_diff(workspace),
        "notes": [
            "rejudgment_after_test",
            "no_search_order_in_prompt",
            "no_tool_catalog_in_prompt",
            "not_connected_to_existing_loops",
        ],
    }
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
        "experiment_id": "problem_solving_rejudgment",
        "fixture_version": FIXTURE_VERSION,
        "prompt": PROMPT,
        "at": _now(),
        "temperature": float(profile.get("temperature") or 0),
        "max_turns": MAX_TURNS,
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "initial_pytest_exit_code": initial_pytest["exit_code"],
        "initial_main_exit_code": initial_program["exit_code"],
        "models_run": [],
    }
    for item in COMPARE_MODELS:
        model_dir = root / item["dir_name"]
        model_dir.mkdir(parents=True, exist_ok=True)
        print(f"MODEL {item['ollama_name']}", flush=True)
        try:
            record = run_one(
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
            "stop_reason": record["stop_reason"],
            "turns": len(record["turns"]),
            "patch_rounds": record["patch_rounds"],
            "first_patch_test_pass": record["first_patch_test_pass"],
            "call_ok": record["call_ok"],
        }
        run_meta["models_run"].append(summary)
        print(f"  {summary}", flush=True)
    save_json(root / "run.json", run_meta)
    (root / "README.md").write_text(
        "# problem_solving_rejudgment\n\n"
        "一次資料。分析は PROBLEM_SOLVING_REJUDGMENT_EXPERIMENT.md。\n",
        encoding="utf-8",
    )
    print(f"wrote {root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
