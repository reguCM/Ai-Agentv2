"""
別ファイル参照を起点とした調査連鎖の成功事例探索。

本番 Agent / Registry / Repair Loop / FA / PA Schema / 正式 Tool Mapping には接続しない。
LLM に Tool 名や catalog は渡さない。実験側が NL 要求を既存 Tool へ接続する。
Prompt は途中で変えない。Tool 結果は要約せず返す。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.problem_solving_experiment.adapters import (
    EXISTING_FILE_TOOLS,
)
from research.llm_benchmarks.problem_solving_experiment.observability import (
    chat_kwargs_snapshot,
    copy_messages,
    dump_tool_result_for_llm,
)
from research.llm_benchmarks.problem_solving_experiment.problem_solving_success_case_fixture import (
    CASE_ID,
    PROMPT_HEADER,
    build_initial_prompt,
)
from research.llm_benchmarks.problem_solving_experiment.problem_solving_success_case_mapping import (
    next_mapping,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/"
    "problem_solving_success_case"
)
MAX_TURNS = 6
COMPARE_MODELS = [
    {"ollama_name": "deepseek-coder-v2:16b", "dir_name": "deepseek"},
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _execute_tool(name, arguments):
    handler = EXISTING_FILE_TOOLS[name]
    return handler(**arguments)


def run_one(ollama_name, profile):
    built = build_initial_prompt()
    messages = [{"role": "user", "content": built["prompt"]}]
    chat_kwargs = chat_kwargs_snapshot(profile, ollama_name)
    chat_kwargs["tool_presentation"] = "none"
    turns = []
    already_done = []
    stop_reason = None
    started = _now()

    for turn_index in range(1, MAX_TURNS + 1):
        llm_input = messages[-1]["content"]
        thinking = None
        try:
            response = chat(model=ollama_name, messages=messages)
            raw = (response.message.content or "").strip()
            thinking = getattr(response.message, "thinking", None)
            timeout = None
        except LLMTimeoutError as exc:
            raw = ""
            timeout = str(exc)
            stop_reason = "timeout"
            turns.append(
                {
                    "turn_index": turn_index,
                    "llm_input": llm_input,
                    "llm_output": raw,
                    "requested_information": None,
                    "tool_selected": None,
                    "tool_arguments": None,
                    "tool_result": None,
                    "analysis_after_tool": None,
                    "mapping": None,
                    "call_ok": False,
                    "error": timeout,
                    "thinking_observed": False,
                }
            )
            break

        messages.append({"role": "assistant", "content": raw})
        selected, mapping_info = next_mapping(raw, already_done=already_done)
        turn = {
            "turn_index": turn_index,
            "llm_input": llm_input,
            "llm_output": raw,
            "requested_information": None,
            "tool_selected": None,
            "tool_arguments": None,
            "tool_result": None,
            "analysis_after_tool": None,
            "mapping": mapping_info,
            "call_ok": True,
            "error": None,
            "thinking_observed": bool(thinking),
        }
        if thinking:
            turn["thinking"] = thinking
        if selected is None:
            turn["stop_reason"] = "no_mappable_request"
            turns.append(turn)
            stop_reason = "no_mappable_request"
            break

        tool_name = selected["tool_selected"]
        arguments = selected["tool_arguments"]
        result = _execute_tool(tool_name, arguments)
        dumped = dump_tool_result_for_llm(result)
        already_done.append(selected["done_key"])
        turn["requested_information"] = selected["requested_information"]
        turn["tool_selected"] = tool_name
        turn["tool_arguments"] = arguments
        turn["tool_result"] = dumped["raw_result"]
        turn["tool_result_sent"] = dumped["sent_tool_result"]
        turn["mapping_note"] = selected["mapping_note"]
        turns.append(turn)
        messages.append({"role": "user", "content": dumped["llm_user_payload"]})
    else:
        stop_reason = "max_turns"

    for index, turn in enumerate(turns):
        if turn.get("tool_selected") and index + 1 < len(turns):
            turn["analysis_after_tool"] = turns[index + 1].get("llm_output")

    files_read = [
        turn["tool_arguments"]["path"]
        for turn in turns
        if turn.get("tool_selected") == "read_file"
    ]
    ended = _now()
    return {
        "experiment": "problem_solving_success_case",
        "model": ollama_name,
        "case_id": CASE_ID,
        "initial_failure": built["failure"],
        "initial_prompt": built["prompt"],
        "traceback": built["traceback"],
        "traceback_capture_ok": built["traceback_capture_ok"],
        "prompt_header": PROMPT_HEADER,
        "turns": turns,
        "final": {
            "cause_identified": "NOT_SCORED_IN_HARNESS",
            "repair_proposed": "NOT_SCORED_IN_HARNESS",
            "repair_executed": False,
            "test_result": "NOT_RUN",
            "solved": "NOT_SCORED_IN_HARNESS",
            "stop_reason": stop_reason,
            "tool_turns": sum(1 for turn in turns if turn.get("tool_selected")),
            "files_read": files_read,
        },
        "timestamp": started,
        "call_ok": all(turn.get("call_ok") for turn in turns) if turns else False,
        "error": next((turn.get("error") for turn in turns if turn.get("error")), None),
        "temperature": chat_kwargs["options"]["temperature"],
        "notes": [
            "success_case_search",
            "no_tool_catalog_to_llm",
            "experiment_side_mapping_only",
            "not_fa",
            "not_repair_loop",
            "helper_and_config_not_in_initial_prompt",
            f"helper_leaked_in_prompt={built['helper_leaked_in_prompt']}",
            f"config_leaked_in_prompt={built['config_leaked_in_prompt']}",
        ],
        "observability": {
            "experiment_start": started,
            "experiment_end": ended,
            "stop_reason": stop_reason,
            "max_turns": MAX_TURNS,
            "messages": copy_messages(messages),
            "chat_kwargs": chat_kwargs,
            "fixture_dir": built["fixture_dir"],
            "fixture_files": built["fixture_files"],
        },
    }


def main():
    profile = get_llm_profile()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    root.mkdir(parents=True, exist_ok=True)
    run = {
        "experiment": "problem_solving_success_case",
        "note": (
            "Cross-file investigation chain. LLM is not given helper.py or "
            "config.py initially. Mapping is experiment-side and not a schema. "
            "Repair is not executed."
        ),
        "at": _now(),
        "prompt_header": PROMPT_HEADER,
        "max_turns": MAX_TURNS,
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "models_run": [],
    }
    for item in COMPARE_MODELS:
        ollama_name = item["ollama_name"]
        model_dir = root / item["dir_name"]
        model_dir.mkdir(parents=True, exist_ok=True)
        print(f"MODEL {ollama_name}", flush=True)
        try:
            record = run_one(ollama_name, profile)
        finally:
            stop_model(ollama_name)
        path = model_dir / f"{CASE_ID}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = {
            "model": ollama_name,
            "call_ok": record["call_ok"],
            "error": record["error"],
            "turns": len(record["turns"]),
            "tool_turns": record["final"]["tool_turns"],
            "files_read": record["final"]["files_read"],
            "stop_reason": record["final"]["stop_reason"],
        }
        run["models_run"].append(summary)
        print(f"  wrote {path} {summary}", flush=True)
    (root / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {root / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
