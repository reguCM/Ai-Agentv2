"""
調査連鎖の条件探索。

本番 Agent / Registry / Dispatcher / Repair / FA / PA Schema には接続しない。
LLM 出力は書き換えない。Mapping は別ログ。search_files は使わない。
既存実験結果は変更しない。
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
from research.llm_benchmarks.problem_solving_experiment.chain_conditions_cases import (
    PROMPT_HEADER,
    RUN_CASES,
    build_prompt,
)
from research.llm_benchmarks.problem_solving_experiment.chain_conditions_mapping import (
    llm_investigation_record,
    next_read_mapping,
    observation_flags,
)
from research.llm_benchmarks.problem_solving_experiment.observability import (
    chat_kwargs_snapshot,
    copy_messages,
    dump_tool_result_for_llm,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/"
    "problem_solving_chain_conditions"
)
MAX_TURNS = 5
COMPARE_MODELS = [
    {"ollama_name": "deepseek-coder-v2:16b", "dir_name": "deepseek"},
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _execute_tool(name, arguments):
    handler = EXISTING_FILE_TOOLS[name]
    return handler(**arguments)


def run_one(case, ollama_name, profile):
    built = build_prompt(case)
    messages = [{"role": "user", "content": built["prompt"]}]
    chat_kwargs = chat_kwargs_snapshot(profile, ollama_name)
    chat_kwargs["tool_presentation"] = "none"
    turns = []
    already_read = []
    chain = []
    stop_reason = None
    started = _now()

    for turn_index in range(1, MAX_TURNS + 1):
        llm_input = messages[-1]["content"]
        try:
            response = chat(model=ollama_name, messages=messages)
            raw = (response.message.content or "").strip()
            thinking = getattr(response.message, "thinking", None)
            timeout = None
        except LLMTimeoutError as exc:
            raw = ""
            thinking = None
            timeout = str(exc)
            stop_reason = "timeout"
            turns.append(
                {
                    "turn_index": turn_index,
                    "llm_input": llm_input,
                    "llm_output": raw,
                    "llm_investigation": llm_investigation_record(raw),
                    "mapping": None,
                    "requested_information": None,
                    "tool_selected": None,
                    "tool_arguments": None,
                    "tool_result": None,
                    "call_ok": False,
                    "error": timeout,
                    "thinking_observed": False,
                }
            )
            break

        messages.append({"role": "assistant", "content": raw})
        investigation = llm_investigation_record(raw)
        selected, mapping_info = next_read_mapping(
            raw,
            fixture_files=built["fixture_files"],
            already_read=already_read,
            source_already_given=built["source_files"],
        )
        turn = {
            "turn_index": turn_index,
            "llm_input": llm_input,
            "llm_output": raw,
            "llm_investigation": investigation,
            "mapping": mapping_info,
            "requested_information": investigation["raw_request_excerpts"],
            "tool_selected": None,
            "tool_arguments": None,
            "tool_result": None,
            "call_ok": True,
            "error": None,
            "thinking_observed": bool(thinking),
        }
        if thinking:
            turn["thinking"] = thinking
        chain.append(
            {
                "step": f"llm_output_{turn_index}",
                "text": raw,
            }
        )
        if selected is None:
            turn["stop_reason"] = "no_mappable_file_request"
            turns.append(turn)
            stop_reason = "no_mappable_file_request"
            break

        result = _execute_tool(selected["tool_selected"], selected["tool_arguments"])
        dumped = dump_tool_result_for_llm(result)
        already_read.append(selected["tool_arguments"]["path"])
        turn["tool_selected"] = selected["tool_selected"]
        turn["tool_arguments"] = selected["tool_arguments"]
        turn["tool_result"] = dumped["raw_result"]
        turn["tool_result_sent"] = dumped["sent_tool_result"]
        turn["mapping_input_excerpt"] = selected["mapping_input_excerpt"]
        turns.append(turn)
        chain.append(
            {
                "step": f"mapping_{turn_index}",
                "tool_selected": selected["tool_selected"],
                "tool_arguments": selected["tool_arguments"],
                "mapping_input_excerpt": selected["mapping_input_excerpt"],
            }
        )
        chain.append(
            {
                "step": f"tool_result_{turn_index}",
                "result": dumped["raw_result"],
            }
        )
        messages.append({"role": "user", "content": dumped["llm_user_payload"]})
    else:
        stop_reason = "max_turns"

    ended = _now()
    return {
        "experiment": "problem_solving_chain_conditions",
        "model": ollama_name,
        "case_id": built["case_id"],
        "family": built["family"],
        "source_level": built["source_level"],
        "fixture": built["fixture"],
        "case_note": built["note"],
        "initial_failure": built["failure"],
        "initial_prompt": built["prompt"],
        "traceback": built["traceback"],
        "source_files_in_prompt": built["source_files"],
        "prompt_header": PROMPT_HEADER,
        "turns": turns,
        "investigation_chain": chain,
        "observation_flags": observation_flags(turns),
        "stop_reason": stop_reason,
        "timestamp": started,
        "call_ok": all(turn.get("call_ok") for turn in turns) if turns else False,
        "error": next((turn.get("error") for turn in turns if turn.get("error")), None),
        "temperature": chat_kwargs["options"]["temperature"],
        "notes": [
            "chain_conditions",
            "llm_text_not_rewritten",
            "mapping_logged_separately",
            "no_search_files_mapping",
            "not_a_success_schema",
            f"bodies_leaked={built['bodies_leaked_that_should_not']}",
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
            "traceback_capture_ok": built["traceback_capture_ok"],
        },
    }


def main():
    profile = get_llm_profile()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    root.mkdir(parents=True, exist_ok=True)
    run = {
        "experiment": "problem_solving_chain_conditions",
        "note": (
            "When does investigation start and follow file references. "
            "Not FA. Mapping is not a spec. Existing results not modified."
        ),
        "at": _now(),
        "prompt_header": PROMPT_HEADER,
        "max_turns": MAX_TURNS,
        "cases": [item["id"] for item in RUN_CASES],
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "models_run": [],
    }
    for item in COMPARE_MODELS:
        ollama_name = item["ollama_name"]
        model_dir = root / item["dir_name"]
        model_dir.mkdir(parents=True, exist_ok=True)
        summary = {"model": ollama_name, "cases": []}
        print(f"MODEL {ollama_name}", flush=True)
        try:
            for case in RUN_CASES:
                print(f"  {case['id']}", flush=True)
                record = run_one(case, ollama_name, profile)
                path = model_dir / f"{case['id']}.json"
                path.write_text(
                    json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                flags = record["observation_flags"]
                case_summary = {
                    "id": case["id"],
                    "call_ok": record["call_ok"],
                    "turns": len(record["turns"]),
                    "tool_turns": sum(
                        1 for turn in record["turns"] if turn.get("tool_selected")
                    ),
                    "stop_reason": record["stop_reason"],
                    "investigation_started": flags["investigation_started"],
                    "file_request_observed": flags["file_request_observed"],
                    "multi_step_investigation": flags["multi_step_investigation"],
                    "premature_repair": flags["premature_repair"],
                }
                summary["cases"].append(case_summary)
                print(f"    {case_summary}", flush=True)
        finally:
            stop_model(ollama_name)
        run["models_run"].append(summary)
    (root / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {root / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
