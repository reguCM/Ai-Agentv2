"""非Tool Calling LLM。tools= は渡さない。出力は補正しない。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.judgment_layer_llm_connection_experiment.bridge import parse_judgment
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.execute import run_scripted
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.workspace import (
    copy_fixture,
    git_init_workspace,
    run_program,
    run_test,
    workspace_filenames,
)


OUT_DIR = Path("research/llm_benchmarks/judgment_layer_llm_connection_experiment/results")
PROMPT = "Resolve the problem."
MAX_TURNS = 6
MODELS = [
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
    {"ollama_name": "gemma3:12b", "dir_name": "gemma3_12b"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def format_failure(pytest_run, program_run):
    return (
        PROMPT
        + "\n\n"
        + "pytest\n"
        + f"command: {json.dumps(pytest_run['command'], ensure_ascii=False)}\n"
        + f"exit_code: {pytest_run['exit_code']}\n"
        + f"stdout:\n{pytest_run.get('stdout') or ''}"
        + f"stderr:\n{pytest_run.get('stderr') or ''}"
        + f"traceback:\n{pytest_run.get('traceback') or ''}\n\n"
        + "python main.py\n"
        + f"command: {json.dumps(program_run['command'], ensure_ascii=False)}\n"
        + f"exit_code: {program_run['exit_code']}\n"
        + f"stdout:\n{program_run.get('stdout') or ''}"
        + f"stderr:\n{program_run.get('stderr') or ''}\n"
    )


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
        "options": options,
        "timeout_seconds": int(profile.get("timeout_seconds") or 90),
        "harness_chat_call": ["model", "messages"],
    }


def classify_split(raw, parsed):
    lower = (raw or "").lower()
    files = ["helper.py", "config.py", "main.py"]
    mentioned = [name for name in files if name in (raw or "")]
    selected = parsed.get("selected_actions") or []
    selected_paths = [
        (item.get("tool_arguments") or {}).get("path")
        for item in selected
        if item.get("tool_name") == "read_file"
    ]
    inspect_words = any(
        token in (raw or "")
        for token in ("確認", "読む", "読み", "調べ", "inspect", "read")
    )
    bridge_missed_file = bool(mentioned and inspect_words and not selected_paths)
    return {
        "files_mentioned_in_raw": mentioned,
        "inspect_words_in_raw": inspect_words,
        "selected_tools": [item.get("tool_name") for item in selected],
        "bridge_missed_named_inspect": bridge_missed_file,
        "no_action": not selected,
        "note": "機械フラグのみ。LLM失敗とは断定しない。",
    }


def run_one(model_name, model_dir: Path, initial_user, profile):
    workspace = model_dir / "workspace"
    copy_fixture(workspace)
    git_init_workspace(workspace)
    known = workspace_filenames(workspace)
    messages = [{"role": "user", "content": initial_user}]
    turns = []
    idle = 0
    stop_reason = None
    error = None
    for turn_id in range(1, MAX_TURNS + 1):
        kwargs_snap = chat_kwargs_snapshot(profile, model_name)
        messages_before = [dict(item) for item in messages]
        try:
            response = chat(model=model_name, messages=messages)
            raw = (response.message.content or "").strip()
            thinking = getattr(response.message, "thinking", None)
        except LLMTimeoutError as exc:
            error = str(exc)
            stop_reason = "timeout"
            turns.append(
                {
                    "turn_id": turn_id,
                    "raw_output": "",
                    "error": error,
                    "stop": "timeout",
                    "chat_kwargs": kwargs_snap,
                }
            )
            break
        except Exception as exc:
            error = str(exc)
            stop_reason = "chat_error"
            turns.append(
                {
                    "turn_id": turn_id,
                    "raw_output": "",
                    "error": error,
                    "stop": "chat_error",
                    "chat_kwargs": kwargs_snap,
                }
            )
            break
        parsed = parse_judgment(raw, known)
        messages.append({"role": "assistant", "content": raw})
        steps = []
        if parsed["selected_actions"]:
            idle = 0
            steps = run_scripted(workspace, parsed["selected_actions"])
            for step in steps:
                messages.append({"role": "user", "content": step["next_input"]})
        else:
            idle += 1
            messages.append(
                {
                    "role": "user",
                    "content": "No executable action was derived from the last message.",
                }
            )
        pytest_now = run_test(workspace)
        turns.append(
            {
                "turn_id": turn_id,
                "timestamp": _now(),
                "model": model_name,
                "prompt": PROMPT,
                "messages_before_chat": messages_before,
                "chat_kwargs": kwargs_snap,
                "raw_output": raw,
                "thinking_observed": bool(thinking),
                "extracted_judgment": parsed["clauses"],
                "action_candidates": parsed["action_candidates"],
                "selected_actions": parsed["selected_actions"],
                "mapping_status": parsed["mapping_status"],
                "split_flags": classify_split(raw, parsed),
                "tool_steps": steps,
                "pytest_exit_code": pytest_now.get("exit_code"),
            }
        )
        if thinking:
            turns[-1]["thinking"] = thinking
        if pytest_now.get("exit_code") == 0:
            stop_reason = "test_pass"
            break
        if idle >= 2:
            stop_reason = "idle_no_action"
            break
    else:
        stop_reason = "max_turns"
    save_json(model_dir / "run.json", {
        "experiment_id": "judgment_layer_llm_connection",
        "model": model_name,
        "prompt": PROMPT,
        "native_tools": False,
        "stop_reason": stop_reason,
        "error": error,
        "turns": turns,
        "final_pytest": run_test(workspace),
        "final_program": run_program(workspace),
    })
    save_json(model_dir / "messages.json", messages)
    return stop_reason, turns


def main():
    profile = get_llm_profile()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    root.mkdir(parents=True, exist_ok=True)
    fixture = copy_fixture(root / "fixture")
    pytest_run = run_test(fixture)
    program_run = run_program(fixture)
    save_json(root / "initial_execution" / "pytest.json", pytest_run)
    save_json(root / "initial_execution" / "python_main.json", program_run)
    initial_user = format_failure(pytest_run, program_run)
    (root / "PROMPT.txt").write_text(initial_user, encoding="utf-8")
    meta = {
        "experiment_id": "judgment_layer_llm_connection",
        "at": _now(),
        "prompt": PROMPT,
        "native_tools": False,
        "max_turns": MAX_TURNS,
        "models": [item["ollama_name"] for item in MODELS],
        "initial_pytest_exit": pytest_run["exit_code"],
        "initial_main_exit": program_run["exit_code"],
        "models_run": [],
    }
    for item in MODELS:
        print(f"MODEL {item['ollama_name']}", flush=True)
        model_dir = root / item["dir_name"]
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            stop_reason, turns = run_one(item["ollama_name"], model_dir, initial_user, profile)
        except Exception as exc:
            stop_reason = "run_error"
            turns = []
            save_json(model_dir / "run.json", {"error": str(exc), "stop_reason": "run_error"})
        finally:
            stop_model(item["ollama_name"])
        summary = {
            "model": item["ollama_name"],
            "stop_reason": stop_reason,
            "turns": len(turns),
            "tools": [
                [step.get("tool_name") for step in (turn.get("tool_steps") or [])]
                for turn in turns
            ],
        }
        meta["models_run"].append(summary)
        print(f"  {summary}", flush=True)
    save_json(root / "run.json", meta)
    print(f"wrote {root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
