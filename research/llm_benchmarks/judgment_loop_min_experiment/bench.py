"""
判断テキスト → 暫定 Mapping → Tool。Native tools= は使わない。
既存実験・本番 Agent には接続しない。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.judgment_loop_min_experiment.execute import (
    build_initial_user,
    format_execution_block,
    format_file_result,
    format_test_failure,
    run_program,
    run_test,
    split_outcomes,
)
from research.llm_benchmarks.judgment_loop_min_experiment.mapping import classify_mapping
from research.llm_benchmarks.judgment_loop_min_experiment.workspace import (
    copy_fixture,
    dispatch,
    dump_result,
    git_diff,
    git_init_workspace,
    workspace_filenames,
)


OUT_DIR = Path("research/llm_benchmarks/judgment_loop_min_experiment/results")
MAX_TURNS = 10
COMPARE_MODELS = [
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
    {"ollama_name": "gemma3:12b", "dir_name": "gemma3_12b"},
]
PROMPT = "Analyze the current problem and determine what should be done next."
FIXTURE_VERSION = "order_live_v1"


def _now():
    return datetime.now(timezone.utc).isoformat()


def chat_kwargs_snapshot(profile, model):
    options = {
        "num_predict": int(profile.get("num_predict") or 2048),
        "temperature": float(profile.get("temperature") or 0),
    }
    if profile.get("context_limit"):
        options["num_ctx"] = int(profile.get("context_limit"))
    return {
        "model": model,
        "tools": "not_passed",
        "keep_alive": profile.get("keep_alive") or "5m",
        "options": options,
        "timeout_seconds": int(profile.get("timeout_seconds") or 90),
        "harness_chat_call": ["model", "messages"],
    }


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sent_for_tool(name, result, dumped):
    if name == "read_file" and result.get("ok"):
        return format_file_result(result.get("path"), result.get("text") or "")
    if name == "list_files" and result.get("ok"):
        names = [item["path"] for item in result.get("entries") or []]
        return "You asked to list files.\n\n" + "\n".join(names) + "\n"
    if name == "search_files":
        return "Search result:\n" + dumped["sent_tool_result"] + "\n"
    if name in ("run_test", "run_program"):
        return format_execution_block(name, result) + "\n"
    return "Result:\n" + dumped["sent_tool_result"] + "\n"


def run_one(model_name, model_dir: Path, initial_pytest, initial_program, profile):
    workspace = model_dir / "workspace"
    copy_fixture(workspace)
    git_init_workspace(workspace)
    known_files = workspace_filenames(workspace)
    messages = [{"role": "user", "content": build_initial_user(initial_pytest, initial_program)}]
    started = _now()
    turns = []
    stop_reason = None
    call_ok = True
    error = None
    files_read_all = []
    last_read = None
    patch_rounds = 0

    for turn_id in range(1, MAX_TURNS + 1):
        kwargs_snap = chat_kwargs_snapshot(profile, model_name)
        turn_started = _now()
        messages_before = [dict(item) for item in messages]
        try:
            response = chat(model=model_name, messages=messages)
            raw = (response.message.content or "").strip()
            thinking = getattr(response.message, "thinking", None)
        except LLMTimeoutError as exc:
            call_ok = False
            error = str(exc)
            stop_reason = "timeout"
            turns.append(_error_turn(turn_id, turn_started, model_name, messages_before, kwargs_snap, "timeout", error))
            break
        except Exception as exc:
            call_ok = False
            error = str(exc)
            stop_reason = "context_length_exceeded" if "context length" in error.lower() else "chat_error"
            turns.append(_error_turn(turn_id, turn_started, model_name, messages_before, kwargs_snap, stop_reason, error))
            break

        mapping = classify_mapping(raw, known_files)
        execute = mapping.get("execute")
        messages.append({"role": "assistant", "content": raw})
        tool_name = None
        tool_arguments = None
        tool_raw = None
        tool_sent = None
        files_read = []
        files_changed = []
        test_result = None
        scope = "none"

        if execute:
            tool_name = execute["tool_name"]
            tool_arguments = execute.get("tool_arguments") or {}
            result = dispatch(workspace, tool_name, tool_arguments)
            dumped = dump_result(result)
            tool_raw = dumped["raw_result"]
            tool_sent = sent_for_tool(tool_name, result, dumped)
            messages.append({"role": "user", "content": tool_sent})
            if tool_name == "read_file" and result.get("ok"):
                path = result.get("path")
                files_read.append(path)
                files_read_all.append(path)
                if last_read and last_read != path:
                    scope = "changed_file"
                elif last_read == path:
                    scope = "same_file"
                else:
                    scope = "first_file"
                last_read = path
            if tool_name == "apply_patch" and result.get("ok"):
                files_changed.append(result.get("path"))
                patch_rounds += 1
                pytest_run = run_test(workspace)
                program_run = run_program(workspace)
                outcomes = split_outcomes(pytest_run, program_run)
                if outcomes["test_pass"]:
                    feedback = (
                        "The tests passed.\n\n"
                        + format_execution_block("pytest", pytest_run)
                        + "\n\n"
                        + format_execution_block("python main.py", program_run)
                        + "\n"
                    )
                    stop_reason = "test_pass"
                else:
                    feedback = format_test_failure(pytest_run, program_run)
                test_result = {
                    "source": "harness_after_patch",
                    "command": pytest_run["command"],
                    "pytest": pytest_run,
                    "python_main": program_run,
                    "sent_to_llm": feedback,
                    **outcomes,
                }
                messages.append({"role": "user", "content": feedback})

        turns.append(
            {
                "experiment_id": "judgment_loop_min",
                "turn_id": turn_id,
                "timestamp": turn_started,
                "model": model_name,
                "prompt": PROMPT,
                "messages_before_chat": messages_before,
                "chat_kwargs": kwargs_snap,
                "raw_output": raw,
                "judgment_interpretation": {
                    "schema_not_requested": True,
                    "current_problem": "NOT_EXTRACTED",
                    "current_hypothesis": "NOT_EXTRACTED",
                    "known_information": "NOT_EXTRACTED",
                    "missing_information": "NOT_EXTRACTED",
                    "next_action": execute.get("action") if execute else "NOT_MAPPED",
                    "raw_judgment": raw,
                },
                "mapping_input": raw,
                "mapping_output": mapping.get("mapping_output"),
                "mapping_status": mapping.get("mapping_status"),
                "mapping_candidates": mapping.get("candidates"),
                "tool_name": tool_name,
                "tool_arguments": tool_arguments,
                "tool_raw_result": tool_raw,
                "tool_sent_result": tool_sent,
                "files_read": files_read,
                "files_changed": files_changed,
                "test_command": (test_result or {}).get("command"),
                "test_exit_code": ((test_result or {}).get("pytest") or {}).get("exit_code"),
                "test_stdout": ((test_result or {}).get("pytest") or {}).get("stdout"),
                "test_stderr": ((test_result or {}).get("pytest") or {}).get("stderr"),
                "test_result": test_result,
                "exploration_scope": scope,
                "thinking_observed": bool(thinking),
            }
        )
        if thinking:
            turns[-1]["thinking"] = thinking
        if stop_reason == "test_pass":
            break
        if not execute:
            idle = sum(1 for item in turns[-2:] if not item.get("tool_name"))
            if len(turns) >= 2 and idle >= 2:
                stop_reason = "idle_no_mapping"
                break
    else:
        stop_reason = "max_turns"

    if stop_reason is None:
        stop_reason = "loop_end"

    record = {
        "experiment_id": "judgment_loop_min",
        "model": model_name,
        "prompt": PROMPT,
        "fixture_version": FIXTURE_VERSION,
        "experiment_start": started,
        "experiment_end": _now(),
        "stop_reason": stop_reason,
        "call_ok": call_ok,
        "error": error,
        "native_tools": False,
        "schema_requested": False,
        "mapping_provisional": True,
        "patch_rounds": patch_rounds,
        "files_read": files_read_all,
        "turns": turns,
        "final_git_diff": git_diff(workspace),
        "notes": [
            "not_connected_to_existing_loops",
            "no_tools_param",
            "no_official_schema",
            "judgment_mapping_execution_separated",
        ],
    }
    save_json(model_dir / "run.json", record)
    save_json(model_dir / "messages.json", messages)
    return record


def _error_turn(turn_id, timestamp, model, messages_before, kwargs_snap, status, error):
    return {
        "experiment_id": "judgment_loop_min",
        "turn_id": turn_id,
        "timestamp": timestamp,
        "model": model,
        "messages_before_chat": messages_before,
        "chat_kwargs": kwargs_snap,
        "raw_output": "",
        "parse_status": status,
        "error": error,
        "mapping_status": status,
        "tool_name": None,
        "files_read": [],
        "files_changed": [],
        "test_result": None,
    }


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
    (initial_dir / "main.stderr.txt").write_text(initial_program["stderr"], encoding="utf-8")
    print(
        f"initial pytest={initial_pytest['exit_code']} main={initial_program['exit_code']}",
        flush=True,
    )
    run_meta = {
        "experiment_id": "judgment_loop_min",
        "fixture_version": FIXTURE_VERSION,
        "prompt": PROMPT,
        "at": _now(),
        "temperature": float(profile.get("temperature") or 0),
        "max_turns": MAX_TURNS,
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "native_tools": False,
        "schema_requested": False,
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
        except Exception as exc:
            record = {
                "stop_reason": "run_error",
                "call_ok": False,
                "turns": [],
                "error": str(exc),
                "files_read": [],
            }
            save_json(model_dir / "run.json", record)
        finally:
            stop_model(item["ollama_name"])
        summary = {
            "model": item["ollama_name"],
            "stop_reason": record.get("stop_reason"),
            "turns": len(record.get("turns") or []),
            "call_ok": record.get("call_ok"),
            "mapping_status": [turn.get("mapping_status") for turn in record.get("turns") or []],
            "tool_name": [turn.get("tool_name") for turn in record.get("turns") or []],
            "files_read": record.get("files_read"),
        }
        run_meta["models_run"].append(summary)
        print(f"  {summary}", flush=True)
    save_json(root / "run.json", run_meta)
    (root / "README.md").write_text(
        "# judgment_loop_min\n\n一次資料。分析は JUDGMENT_LOOP_MIN_EXPERIMENT.md。\n",
        encoding="utf-8",
    )
    print(f"wrote {root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
