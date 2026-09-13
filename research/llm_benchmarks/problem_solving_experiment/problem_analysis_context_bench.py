"""
Problem Analysis 文脈増加実験。deepseek-coder-v2:16b、最小分析指示、A〜E × L1〜L6。

既存 PA ハーネス・結果・FA / Dispatcher は変更・接続しない。
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
from research.llm_benchmarks.problem_solving_experiment.problem_analysis_context_cases import (
    CASES,
    PROMPT_TEMPLATE,
    build_context,
    build_prompt,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/problem_analysis_context"
)
LEVELS = (1, 2, 3, 4, 5, 6)
MODEL_DIR = "deepseek-coder-v2-16b"


def _now():
    return datetime.now(timezone.utc).isoformat()


def run_case(case, level, profile, model):
    context = build_context(case, level)
    prompt = build_prompt(case, level)
    messages = [{"role": "user", "content": prompt}]
    messages_before_chat = copy_messages(messages)
    chat_kwargs = chat_kwargs_snapshot(profile, model)
    chat_kwargs["tool_presentation"] = "none"
    started = _now()
    try:
        response = chat(model=model, messages=messages)
        raw = (response.message.content or "").strip()
        timeout = None
    except LLMTimeoutError as exc:
        raw = ""
        timeout = str(exc)
    ended = _now()
    return {
        "experiment": "problem_analysis_context",
        "model": model,
        "timestamp": started,
        "case": case["letter"],
        "case_id": case["id"],
        "level": level,
        "prompt": prompt,
        "context": context,
        "temperature": chat_kwargs["options"]["temperature"],
        "call_ok": timeout is None,
        "raw_output": raw,
        "notes": [
            "problem_analysis_context",
            "no_analysis_items_in_prompt",
            "no_tools",
            "level5_6_no_invented_cause",
        ],
        "observability": {
            "experiment_start": started,
            "experiment_end": ended,
            "stop_reason": "timeout" if timeout else "single_turn",
            "timeout": timeout,
            "messages": messages_before_chat,
            "chat_kwargs": chat_kwargs,
            "tools_used": False,
            "source_available": case["has_source"],
        },
    }


def main():
    profile = get_llm_profile()
    model = profile["model"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / stamp / MODEL_DIR
    out.mkdir(parents=True, exist_ok=True)
    run = {
        "experiment": "problem_analysis_context",
        "note": (
            "Context-increase Problem Analysis. Not FA. "
            "Prompt fixed. Levels add context only. "
            "B-E L5/L6 have NOT_RECORDED where fixture/source is absent."
        ),
        "at": _now(),
        "model": model,
        "prompt_template": PROMPT_TEMPLATE,
        "compared_to": [
            "results/problem_analysis/20260831T232753Z",
            "results/problem_analysis_free/20260831T233507Z",
            "results/problem_analysis_minimal/20260831T234044Z",
        ],
        "cases": [],
    }
    try:
        for case in CASES:
            case_dir = out / case["letter"]
            case_dir.mkdir(parents=True, exist_ok=True)
            for level in LEVELS:
                label = f"{case['letter']}-L{level}"
                print(f"CASE {label}", flush=True)
                record = run_case(case, level, profile, model)
                run["cases"].append(
                    {
                        "id": label,
                        "call_ok": record["call_ok"],
                        "timeout": record["observability"]["timeout"],
                        "raw_chars": len(record["raw_output"] or ""),
                    }
                )
                (case_dir / f"L{level}.json").write_text(
                    json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                preview = (
                    record["raw_output"] or record["observability"]["timeout"] or ""
                )[:140]
                print(
                    f"  ok={record['call_ok']} chars={len(record['raw_output'] or '')} "
                    f"preview={preview!r}",
                    flush=True,
                )
    finally:
        stop_model(model)
    (out.parent / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out.parent / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
