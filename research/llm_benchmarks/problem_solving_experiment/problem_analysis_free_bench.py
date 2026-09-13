"""
Problem Analysis 自由分析。項目名・Schema を Prompt に載せない。

Failure・モデル条件は problem_analysis_bench.CASES と同一。
既存 Problem Solving Experiment / FA / Dispatcher には接続しない。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools.system.llm import LLMTimeoutError, chat, stop_model

from research.llm_benchmarks.problem_solving_experiment.observability import (
    chat_kwargs_snapshot,
    copy_messages,
)
from research.llm_benchmarks.problem_solving_experiment.problem_analysis_bench import (
    CASES,
    MODEL,
    PROFILE,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/problem_analysis_free"
)

PROMPT_TEMPLATE = """You are analyzing a software failure.

Do not fix the problem yet.

Analyze the failure carefully.
Determine what can be understood from the information currently available, what cannot be determined, and what would need to be understood or investigated before the problem can be safely resolved.

Do not use tools.
Do not propose code changes yet.

Failure:
{failure}
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def build_prompt(failure):
    return PROMPT_TEMPLATE.format(
        failure=json.dumps(failure, ensure_ascii=False, indent=2)
    )


def run_case(case):
    prompt = build_prompt(case["failure"])
    messages = [{"role": "user", "content": prompt}]
    messages_before_chat = copy_messages(messages)
    chat_kwargs = chat_kwargs_snapshot(PROFILE, MODEL)
    chat_kwargs["tool_presentation"] = "none"
    started = _now()
    try:
        response = chat(model=MODEL, messages=messages)
        raw = (response.message.content or "").strip()
        timeout = None
    except LLMTimeoutError as exc:
        raw = ""
        timeout = str(exc)
    ended = _now()
    call_ok = timeout is None
    return {
        "experiment": "problem_analysis_free",
        "id": case["id"],
        "purpose": case["purpose"],
        "model": MODEL,
        "temperature": chat_kwargs["options"]["temperature"],
        "failure": case["failure"],
        "prompt": prompt,
        "timestamp": started,
        "raw_output": raw,
        "call_ok": call_ok,
        "notes": [
            "problem_analysis_free",
            "no_category_list_in_prompt",
            "no_tools",
            "no_patch_requested",
        ],
        "observability": {
            "experiment_start": started,
            "experiment_end": ended,
            "stop_reason": "timeout" if timeout else "single_turn",
            "timeout": timeout,
            "call_ok": call_ok,
            "messages": messages_before_chat,
            "chat_kwargs": chat_kwargs,
            "tools_used": False,
        },
    }


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / stamp
    out.mkdir(parents=True, exist_ok=True)
    run = {
        "experiment": "problem_analysis_free",
        "note": (
            "Free-form Problem Analysis. Categories not listed in prompt. "
            "Not FA. Not the tool-using problem-solving loop. "
            "Same A-E failures as problem_analysis_standalone."
        ),
        "at": _now(),
        "model": MODEL,
        "prompt_template": PROMPT_TEMPLATE,
        "compared_to": "results/problem_analysis/20260831T232753Z",
        "cases": [],
    }
    try:
        for case in CASES:
            print(f"CASE {case['id']}", flush=True)
            record = run_case(case)
            run["cases"].append(
                {
                    "id": record["id"],
                    "call_ok": record["call_ok"],
                    "timeout": record["observability"]["timeout"],
                    "raw_chars": len(record["raw_output"] or ""),
                }
            )
            (out / f"{case['id']}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            preview = (record["raw_output"] or record["observability"]["timeout"] or "")[:200]
            print(
                f"  ok={record['call_ok']} chars={len(record['raw_output'] or '')} "
                f"preview={preview!r}",
                flush=True,
            )
    finally:
        stop_model(MODEL)
    (out / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
