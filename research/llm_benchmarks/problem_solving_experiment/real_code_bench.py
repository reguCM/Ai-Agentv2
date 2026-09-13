"""
実コード・実エラーの問題解決観測。

本番 Agent / Registry / 既存 PA ハーネス / 既存実験ループには接続しない。
探索経路を Prompt で指定しない。人工エラー文は使わない。
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.problem_solving_experiment.real_code_execute import (
    format_execution_block,
    initial_execution,
    pytest_flags,
    run_main,
    run_pytest,
)
from research.llm_benchmarks.problem_solving_experiment.real_code_workspace import (
    OLLAMA_TOOLS,
    copy_fixture,
    dispatch,
    dump_result,
    git_diff,
    git_init_workspace,
    write_file as workspace_write_file,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/"
    "problem_solving_real_code"
)
MAX_TURNS = 14
COMPARE_MODELS = [
    {"ollama_name": "deepseek-coder-v2:16b", "dir_name": "deepseek"},
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
]

PROMPT_HEADER = """この問題を解決してください。

実行結果："""

PROMPT_FOOTER = """
プロジェクトのコードは作業ディレクトリにあります。
必要な情報は自分で調査してください。

作業ディレクトリで使える機能:
- list_files(path?, recursive?, glob?)
- read_file(path, offset?, limit?)
- search_files(query, path?, glob?)
- write_file(path, content)
- run_tests()

機能を使うときは次の JSON を応答に含めても構いません。
{"tool":"read_file","arguments":{"path":"main.py"}}
"""

TOOL_NAMES = set(item["function"]["name"] for item in OLLAMA_TOOLS)
_NAMED_FENCE = re.compile(
    r"(?P<name>main\.py|helper\.py|config\.py|tests/test_main\.py)\s*\n```(?:python)?\n(?P<body>.*?)```",
    re.S,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _message_dict(message):
    if isinstance(message, dict):
        payload = dict(message)
        if "tool_calls" in payload and payload["tool_calls"] is not None:
            payload["tool_calls"] = _tool_calls_list(payload["tool_calls"])
        return payload
    data = {
        "role": getattr(message, "role", None),
        "content": getattr(message, "content", None),
    }
    thinking = getattr(message, "thinking", None)
    if thinking:
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
        if name == "write_file" and "content" in obj and "content" not in arguments:
            arguments = {
                "path": obj.get("path") or arguments.get("path"),
                "content": obj.get("content"),
            }
        return {"name": name, "arguments": arguments}, "parsed_from_text"
    return None, "no_tool_json"


def parse_named_fences(text):
    found = []
    for match in _NAMED_FENCE.finditer(text or ""):
        found.append(
            {
                "path": match.group("name"),
                "content": match.group("body"),
            }
        )
    return found


def native_tool_calls(response):
    calls = getattr(response.message, "tool_calls", None) or []
    parsed = []
    for item in _tool_calls_list(calls):
        if not item.get("name"):
            continue
        try:
            arguments = _args(item.get("arguments"))
        except json.JSONDecodeError:
            arguments = {}
        parsed.append({"name": item["name"], "arguments": arguments})
    return parsed


def chat_turn(model, messages, use_native_tools):
    kwargs = {"model": model, "messages": messages}
    if use_native_tools:
        kwargs["tools"] = OLLAMA_TOOLS
    response = chat(**kwargs)
    return response


def build_initial_user(initial):
    pytest_block = format_execution_block("pytest", initial["pytest"])
    main_block = format_execution_block("python main.py", initial["main_py"])
    return (
        PROMPT_HEADER
        + "\n"
        + pytest_block
        + "\n\n"
        + main_block
        + "\n"
        + PROMPT_FOOTER
    )


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_one(model_name, model_dir: Path, fixture_copy: Path, initial):
    workspace = model_dir / "workspace"
    copy_fixture(workspace)
    git_init_workspace(workspace)
    shutil.copytree(fixture_copy, model_dir / "fixture_snapshot", dirs_exist_ok=True)

    messages = [{"role": "user", "content": build_initial_user(initial)}]
    use_native = True
    turns = []
    tool_log = []
    mod_log = []
    test_log = []
    idle = 0
    stop_reason = None
    started = _now()
    call_ok = True
    error = None
    tool_order = 0

    for turn_id in range(1, MAX_TURNS + 1):
        turn_started = _now()
        try:
            try:
                response = chat_turn(model_name, messages, use_native)
            except Exception as exc:
                if use_native and "does not support tools" in str(exc).lower():
                    use_native = False
                    response = chat_turn(model_name, messages, False)
                else:
                    raise
            raw = (response.message.content or "").strip()
            thinking = getattr(response.message, "thinking", None)
            native_calls = native_tool_calls(response)
            timeout = None
        except LLMTimeoutError as exc:
            raw = ""
            thinking = None
            native_calls = []
            timeout = str(exc)
            call_ok = False
            error = timeout
            stop_reason = "timeout"
            turns.append(
                {
                    "turn_id": turn_id,
                    "timestamp": turn_started,
                    "messages": [_message_dict(item) for item in messages],
                    "raw_output": raw,
                    "parsed_output": None,
                    "parse_status": "timeout",
                    "thinking_observed": False,
                    "error": timeout,
                }
            )
            break

        text_call, parse_status = parse_text_tool(raw)
        calls = native_calls or ([text_call] if text_call else [])
        fence_writes = [] if calls else parse_named_fences(raw)
        parse_payload = {
            "native_tool_calls": native_calls,
            "text_tool": text_call,
            "named_fences": fence_writes,
        }

        turns.append(
            {
                "turn_id": turn_id,
                "timestamp": turn_started,
                "raw_output": raw,
                "parsed_output": parse_payload,
                "parse_status": (
                    "native_tools"
                    if native_calls
                    else parse_status
                    if text_call
                    else ("named_fences" if fence_writes else "no_tool")
                ),
                "thinking_observed": bool(thinking),
                "native_tools_enabled": use_native,
            }
        )
        if thinking:
            turns[-1]["thinking"] = thinking

        if native_calls:
            messages.append(response.message)
        else:
            messages.append(
                {
                    "role": "assistant",
                    "content": getattr(response.message, "content", None) or raw,
                }
            )

        acted = False
        wrote = False
        for call in calls:
            tool_order += 1
            name = call["name"]
            arguments = call.get("arguments") or {}
            result = dispatch(workspace, name, arguments)
            dumped = dump_result(result)
            tool_log.append(
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
            if name == "write_file" and result.get("ok"):
                wrote = True
                mod_log.append(
                    {
                        "turn_id": turn_id,
                        "git_diff_before": result.get("git_diff_before"),
                        "proposal": {
                            "source": "write_file",
                            "path": arguments.get("path"),
                            "content": arguments.get("content"),
                        },
                        "git_diff_after": result.get("git_diff_after"),
                        "applied": True,
                    }
                )
            if native_calls:
                messages.append(
                    {
                        "role": "tool",
                        "content": dumped["sent_tool_result"],
                        "tool_name": name,
                    }
                )
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": dumped["llm_user_payload"],
                    }
                )
            acted = True
            if name == "run_tests":
                flags = pytest_flags(result)
                test_log.append(
                    {
                        "turn_id": turn_id,
                        "source": "llm_run_tests",
                        **result,
                        **flags,
                        "git_diff": git_diff(workspace),
                    }
                )

        if fence_writes:
            for item in fence_writes:
                tool_order += 1
                before = git_diff(workspace)
                result = workspace_write_file(
                    workspace, item["path"], item["content"]
                )
                dumped = dump_result(result)
                wrote = bool(result.get("ok"))
                acted = True
                mod_log.append(
                    {
                        "turn_id": turn_id,
                        "git_diff_before": before,
                        "proposal": {
                            "source": "named_fence",
                            "path": item["path"],
                            "content": item["content"],
                        },
                        "git_diff_after": result.get("git_diff_after"),
                        "applied": bool(result.get("ok")),
                    }
                )
                tool_log.append(
                    {
                        "turn_id": turn_id,
                        "tool_call_order": tool_order,
                        "tool_name": "write_file",
                        "arguments": {"path": item["path"], "via": "named_fence"},
                        "raw_result": dumped["raw_result"],
                        "sent_result": dumped["sent_tool_result"],
                        "truncated": dumped["truncated"],
                    }
                )

        if fence_writes and not calls:
            messages.append(
                {
                    "role": "user",
                    "content": "write_file 結果:\n"
                    + json.dumps(
                        [item["path"] for item in fence_writes],
                        ensure_ascii=False,
                    ),
                }
            )

        if wrote:
            pytest_run = run_pytest(workspace)
            main_run = run_main(workspace)
            flags = pytest_flags(pytest_run)
            test_log.append(
                {
                    "turn_id": turn_id,
                    "source": "experimenter_after_write",
                    "pytest": pytest_run,
                    "main_py": main_run,
                    **flags,
                    "git_diff": git_diff(workspace),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "修正後の実行結果：\n\n"
                        + format_execution_block("pytest", pytest_run)
                        + "\n\n"
                        + format_execution_block("python main.py", main_run)
                    ),
                }
            )

        if not acted:
            idle += 1
            if idle >= 2:
                stop_reason = "idle_no_tool_or_write"
                break
        else:
            idle = 0
    else:
        stop_reason = "max_turns"

    if stop_reason is None:
        stop_reason = "loop_end"

    ended = _now()
    record = {
        "experiment_id": "problem_solving_real_code",
        "model": model_name,
        "start_time": started,
        "end_time": ended,
        "stop_reason": stop_reason,
        "call_ok": call_ok,
        "error": error,
        "native_tools_enabled_final": use_native,
        "turns": turns,
        "tool_calls": tool_log,
        "modifications": mod_log,
        "tests": test_log,
        "final_git_diff": git_diff(workspace),
        "notes": [
            "real_code_real_error",
            "not_connected_to_production_agent",
            "not_pa_schema",
            "prompt_not_changed_mid_run",
        ],
    }
    save_json(model_dir / "run.json", record)
    save_json(
        model_dir / "messages.json",
        [_message_dict(item) for item in messages],
    )
    return record


def capture_and_store_initial(root: Path):
    fixture_dir = root / "fixture"
    copy_fixture(fixture_dir)
    captured = initial_execution(fixture_dir)
    captured["captured_at"] = _now()
    initial_dir = root / "initial_execution"
    initial_dir.mkdir(parents=True, exist_ok=True)
    save_json(initial_dir / "main_py.json", captured["main_py"])
    save_json(initial_dir / "pytest.json", captured["pytest"])
    save_json(initial_dir / "combined.json", captured)
    (initial_dir / "pytest.stderr.txt").write_text(
        captured["pytest"]["stderr"], encoding="utf-8"
    )
    (initial_dir / "pytest.stdout.txt").write_text(
        captured["pytest"]["stdout"], encoding="utf-8"
    )
    (initial_dir / "main.stderr.txt").write_text(
        captured["main_py"]["stderr"], encoding="utf-8"
    )
    (initial_dir / "main.stdout.txt").write_text(
        captured["main_py"]["stdout"], encoding="utf-8"
    )
    return captured, fixture_dir


def write_run_readme(root: Path, captured, summaries):
    text = (
        "# problem_solving_real_code\n\n"
        "一次資料。分析は PROBLEM_SOLVING_REAL_CODE_EXPERIMENT.md。\n\n"
        f"- fixture: `{root / 'fixture'}`\n"
        f"- initial pytest exit_code: {captured['pytest']['exit_code']}\n"
        f"- initial main.py exit_code: {captured['main_py']['exit_code']}\n"
        "- models: " + json.dumps(summaries, ensure_ascii=False, indent=2) + "\n"
    )
    (root / "README.md").write_text(text, encoding="utf-8")


def main():
    profile = get_llm_profile()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    root.mkdir(parents=True, exist_ok=True)
    captured, fixture_dir = capture_and_store_initial(root)
    run_meta = {
        "experiment_id": "problem_solving_real_code",
        "at": _now(),
        "temperature": float(profile.get("temperature") or 0),
        "max_turns": MAX_TURNS,
        "prompt_header": PROMPT_HEADER,
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "initial_pytest_exit_code": captured["pytest"]["exit_code"],
        "initial_main_exit_code": captured["main_py"]["exit_code"],
        "models_run": [],
    }
    print(
        f"initial pytest exit={captured['pytest']['exit_code']} "
        f"main exit={captured['main_py']['exit_code']}",
        flush=True,
    )
    summaries = []
    try:
        for item in COMPARE_MODELS:
            model_dir = root / item["dir_name"]
            model_dir.mkdir(parents=True, exist_ok=True)
            print(f"MODEL {item['ollama_name']}", flush=True)
            try:
                record = run_one(
                    item["ollama_name"],
                    model_dir,
                    fixture_dir,
                    captured,
                )
            finally:
                stop_model(item["ollama_name"])
            summary = {
                "model": item["ollama_name"],
                "stop_reason": record["stop_reason"],
                "turns": len(record["turns"]),
                "tool_calls": len(record["tool_calls"]),
                "modifications": len(record["modifications"]),
                "tests": len(record["tests"]),
                "call_ok": record["call_ok"],
            }
            summaries.append(summary)
            run_meta["models_run"].append(summary)
            print(f"  {summary}", flush=True)
    finally:
        pass
    save_json(root / "run.json", run_meta)
    write_run_readme(root, captured, summaries)
    print(f"wrote {root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
