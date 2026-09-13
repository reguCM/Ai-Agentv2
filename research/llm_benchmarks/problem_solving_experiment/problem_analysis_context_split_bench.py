"""
Problem Analysis 切り分け実験。F1〜F5 × A〜E × deepseek / qwen3:14b。

既存 PA ハーネス・結果は変更しない。FA / Dispatcher / Tool Mapping は接続しない。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.problem_solving_experiment.observability import (
    chat_kwargs_snapshot,
    copy_messages,
)
from research.llm_benchmarks.problem_solving_experiment.problem_analysis_context_split_cases import (
    CONDITIONS,
    PROMPT_HEADER,
    build_input,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/problem_analysis_context_split"
)
LETTERS = ("A", "B", "C", "D", "E")
COMPARE_MODELS = [
    {"ollama_name": "deepseek-coder-v2:16b", "dir_name": "deepseek"},
    {"ollama_name": "qwen3:14b", "dir_name": "qwen3_14b"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def run_one(letter, condition, ollama_name, profile):
    built = build_input(letter, condition)
    prompt = built["prompt"]
    messages = [{"role": "user", "content": prompt}]
    messages_before = copy_messages(messages)
    chat_kwargs = chat_kwargs_snapshot(profile, ollama_name)
    chat_kwargs["tool_presentation"] = "none"
    started = _now()
    thinking = None
    try:
        response = chat(model=ollama_name, messages=messages)
        raw = (response.message.content or "").strip()
        thinking = getattr(response.message, "thinking", None)
        timeout = None
    except LLMTimeoutError as exc:
        raw = ""
        timeout = str(exc)
    ended = _now()
    record = {
        "experiment": "problem_analysis_context_split",
        "model": ollama_name,
        "case_id": built["case_id"],
        "condition": condition,
        "input": prompt,
        "raw_output": raw,
        "timestamp": started,
        "call_ok": timeout is None,
        "error": timeout,
        "temperature": chat_kwargs["options"]["temperature"],
        "failure": built["failure"],
        "prompt_header": PROMPT_HEADER,
        "notes": [
            "context_split",
            "no_analysis_taxonomy",
            "no_tools",
            "no_invented_traceback_or_source",
            "f5_conversation_from_previous_fixture",
        ],
        "observability": {
            "experiment_start": started,
            "experiment_end": ended,
            "stop_reason": "timeout" if timeout else "single_turn",
            "messages": messages_before,
            "chat_kwargs": chat_kwargs,
            "tools_used": False,
            "extras": built["extras"],
            "thinking_observed": bool(thinking),
        },
    }
    if thinking:
        record["observability"]["thinking"] = thinking
    return record


def main():
    profile = get_llm_profile()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    root.mkdir(parents=True, exist_ok=True)
    run = {
        "experiment": "problem_analysis_context_split",
        "note": (
            "Split Failure / traceback / source / conversation. "
            "Not FA. Prompt fixed. No invented traceback/source. "
            "F5 conversation copied from previous context experiment fixture."
        ),
        "at": _now(),
        "prompt_header": PROMPT_HEADER,
        "conditions": list(CONDITIONS),
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "models_run": [],
    }
    try:
        for item in COMPARE_MODELS:
            ollama_name = item["ollama_name"]
            model_dir = root / item["dir_name"]
            model_dir.mkdir(parents=True, exist_ok=True)
            summary = {"model": ollama_name, "cases": []}
            print(f"MODEL {ollama_name}", flush=True)
            try:
                for letter in LETTERS:
                    for condition in CONDITIONS:
                        label = f"{letter}_{condition}"
                        print(f"  {label}", flush=True)
                        record = run_one(letter, condition, ollama_name, profile)
                        summary["cases"].append(
                            {
                                "id": label,
                                "call_ok": record["call_ok"],
                                "error": record["error"],
                                "raw_chars": len(record["raw_output"] or ""),
                                "thinking_observed": record["observability"][
                                    "thinking_observed"
                                ],
                            }
                        )
                        (model_dir / f"{label}.json").write_text(
                            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8",
                        )
                        preview = (
                            record["raw_output"] or record["error"] or ""
                        )[:120]
                        print(
                            f"    ok={record['call_ok']} chars={len(record['raw_output'] or '')} "
                            f"preview={preview!r}",
                            flush=True,
                        )
            finally:
                stop_model(ollama_name)
            run["models_run"].append(summary)
    finally:
        pass
    (root / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {root / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
