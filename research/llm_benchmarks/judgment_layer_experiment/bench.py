"""
Tool Calling 非対応 LLM の判断層観測。
既存実験・本番 Agent / Registry には接続しない。
Native tools= は使わない。Schema は要求しない。
仮 Mapping は M1 のみ実行する。正式規則ではない。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.judgment_layer_experiment.execute import (
    format_execution_block,
    run_program,
    run_test,
    split_outcomes,
)
from research.llm_benchmarks.judgment_layer_experiment.mapping import classify_mapping
from research.llm_benchmarks.judgment_layer_experiment.observe import (
    decision_changed,
    extract_judgment_fields,
    mechanical_level_hints,
)
from research.llm_benchmarks.judgment_layer_experiment.workspace import (
    copy_fixture,
    dispatch,
    dump_result,
    format_investigation_result,
    git_diff,
    git_init_workspace,
    workspace_filenames,
)


OUT_DIR = Path("research/llm_benchmarks/judgment_layer_experiment/results")
MAX_TURNS = 8
COMPARE_MODELS = [
    {"ollama_name": "gemma3:12b", "dir_name": "gemma3_12b"},
    {"ollama_name": "deepseek-coder-v2:16b", "dir_name": "deepseek"},
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
]
PROMPT = "Analyze the problem and indicate the next investigation or action needed."
FIXTURE_VERSION = "pack_bin_v1"


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
    known_files = workspace_filenames(workspace)
    messages = [{"role": "user", "content": build_initial_user(initial_pytest, initial_program)}]
    started = _now()
    turns = []
    stop_reason = None
    call_ok = True
    error = None
    previous_decision = None
    files_read_all = []
    phase1_saved = False
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
            turns.append(
                {
                    "experiment_id": "judgment_layer",
                    "turn_id": turn_id,
                    "model": model_name,
                    "prompt": PROMPT,
                    "timestamp": turn_started,
                    "messages": messages_before,
                    "raw_output": "",
                    "parse_status": "timeout",
                    "error": error,
                    "chat_kwargs": kwargs_snap,
                }
            )
            break
        except Exception as exc:
            message = str(exc)
            call_ok = False
            error = message
            if "context length" in message.lower():
                stop_reason = "context_length_exceeded"
                parse_status = "context_length_exceeded"
            else:
                stop_reason = "chat_error"
                parse_status = "chat_error"
            turns.append(
                {
                    "experiment_id": "judgment_layer",
                    "turn_id": turn_id,
                    "model": model_name,
                    "prompt": PROMPT,
                    "timestamp": turn_started,
                    "messages": messages_before,
                    "raw_output": "",
                    "parse_status": parse_status,
                    "error": error,
                    "chat_kwargs": kwargs_snap,
                }
            )
            break

        mapping = classify_mapping(raw, known_files)
        judgment = extract_judgment_fields(raw, mapping)
        execute = mapping.get("execute")
        tool_name = None
        tool_arguments = None
        tool_result = None
        files_read = []
        files_changed = []
        test_result = None
        sent_investigation = None
        phase = 1 if not phase1_saved else 2

        messages.append({"role": "assistant", "content": raw})

        if execute:
            phase = 3
            tool_name = execute["tool_name"]
            tool_arguments = execute.get("tool_arguments") or {}
            result = dispatch(workspace, tool_name, tool_arguments)
            dumped = dump_result(result)
            tool_result = {
                "tool_name": tool_name,
                "tool_arguments": tool_arguments,
                "raw_result": dumped["raw_result"],
                "sent_result": dumped["sent_tool_result"],
                "truncated": dumped["truncated"],
            }
            sent_investigation = format_investigation_result(tool_name, dumped, result)
            messages.append({"role": "user", "content": sent_investigation})
            if tool_name == "read_file" and result.get("ok"):
                files_read.append(result.get("path"))
                files_read_all.append(result.get("path"))
            if tool_name == "apply_patch" and result.get("ok"):
                files_changed.append(result.get("path"))
                phase = 4
                patch_rounds += 1
                pytest_run = run_test(workspace)
                program_run = run_program(workspace)
                outcomes = split_outcomes(pytest_run, program_run)
                feedback = test_feedback_user(pytest_run, program_run)
                test_result = {
                    "source": "harness_after_patch",
                    "command": pytest_run["command"],
                    "pytest": pytest_run,
                    "python_main": program_run,
                    "sent_to_llm": feedback,
                    **outcomes,
                }
                messages.append({"role": "user", "content": feedback})
            if tool_name == "run_test":
                phase = 4
                program_run = run_program(workspace)
                test_result = {
                    "source": "mapped_run_test",
                    "command": result.get("command"),
                    "pytest": result,
                    "python_main": program_run,
                    **split_outcomes(result, program_run),
                }

        new_files = [path for path in files_read if path not in files_read_all[:-1]]
        after_test = bool(test_result) or (
            turn_id > 1 and (turns[-1].get("test_result") is not None)
        )
        changed = decision_changed(previous_decision, raw)
        scope_changed = bool(new_files) or (
            files_changed and files_changed[-1] not in set(files_read_all)
        )

        turn = {
            "experiment_id": "judgment_layer",
            "turn_id": turn_id,
            "model": model_name,
            "prompt": PROMPT,
            "timestamp": turn_started,
            "phase_reached": phase,
            "messages": messages_before,
            "chat_kwargs": kwargs_snap,
            "raw_output": raw,
            "parsed_output": {
                "schema": "not_used",
                "mapping": mapping,
            },
            "parse_status": mapping["mapping_status"],
            "llm_decision": judgment["llm_decision"],
            "unknown_information": judgment["unknown_information"],
            "requested_information": judgment["requested_information"],
            "requested_target": judgment["requested_target"],
            "requested_action": judgment["requested_action"],
            "mapping_result": mapping.get("mapping_result"),
            "mapping_status": mapping["mapping_status"],
            "mapping_candidates": mapping["candidates"],
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "tool_result": tool_result,
            "investigation_sent_to_llm": sent_investigation,
            "test_command": (test_result or {}).get("command"),
            "test_result": test_result,
            "exit_code": ((test_result or {}).get("pytest") or {}).get("exit_code"),
            "files_read": files_read,
            "files_changed": files_changed,
            "previous_decision": previous_decision,
            "decision_changed": changed,
            "exploration_scope_changed": scope_changed,
            "mechanical_level_hints": mechanical_level_hints(
                raw,
                mapping,
                after_tool=bool(tool_result),
                after_test=after_test,
                new_files=new_files,
            ),
            "thinking_observed": bool(thinking),
        }
        if thinking:
            turn["thinking"] = thinking
        turns.append(turn)
        if not phase1_saved:
            save_json(model_dir / "phase1.json", turn)
            phase1_saved = True
        previous_decision = raw

        if not execute:
            idle = sum(1 for item in turns[-2:] if not item.get("tool_name"))
            if len(turns) >= 2 and idle >= 2:
                stop_reason = "idle_no_m1_mapping"
                break
    else:
        stop_reason = "max_turns"

    if stop_reason is None:
        stop_reason = "loop_end"

    record = {
        "experiment_id": "judgment_layer",
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
            "no_tool_catalog_in_prompt",
            "no_official_schema",
            "m1_only_auto_execute",
            "llm_decision_separated_from_mapping",
        ],
    }
    save_json(model_dir / "run.json", record)
    save_json(model_dir / "messages.json", messages)
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
        "experiment_id": "judgment_layer",
        "fixture_version": FIXTURE_VERSION,
        "prompt": PROMPT,
        "at": _now(),
        "temperature": float(profile.get("temperature") or 0),
        "max_turns": MAX_TURNS,
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "native_tools": False,
        "schema_requested": False,
        "mapping_provisional": True,
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
            print(f"  RUN_ERROR {exc}", flush=True)
        finally:
            stop_model(item["ollama_name"])
        summary = {
            "model": item["ollama_name"],
            "stop_reason": record["stop_reason"],
            "turns": len(record["turns"]),
            "call_ok": record["call_ok"],
            "mapping_status": [turn.get("mapping_status") for turn in record["turns"]],
            "tool_name": [turn.get("tool_name") for turn in record["turns"]],
            "files_read": record.get("files_read"),
        }
        run_meta["models_run"].append(summary)
        print(f"  {summary}", flush=True)
    save_json(root / "run.json", run_meta)
    (root / "README.md").write_text(
        "# judgment_layer\n\n一次資料。分析は JUDGMENT_LAYER_EXPERIMENT.md。\n",
        encoding="utf-8",
    )
    print(f"wrote {root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
