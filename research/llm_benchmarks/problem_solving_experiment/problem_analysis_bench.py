"""
Problem Analysis 単体ベンチ。

Failure だけを LLM に渡し、問題分解の自然な出力を観測する。
既存 Problem Solving Experiment のループ / Dispatcher / catalog / FA には接続しない。
Tool は使わせない。Patch は要求しない。出力 Schema は固定しない。
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


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
OUT_DIR = Path("research/llm_benchmarks/problem_solving_experiment/results/problem_analysis")

PROMPT_TEMPLATE = """You are analyzing a software failure.

Do not fix the problem yet.

Analyze the failure and determine:
- what is known
- what is unknown
- what does not match or may be inconsistent
- what information would be needed to understand the cause
- what should be investigated next

Do not use tools.
Do not propose code changes yet.

Failure:
{failure}
"""

CASES = [
    {
        "id": "A_index_error",
        "purpose": "原因候補が比較的明確",
        "failure": {
            "tool_name": "cpu_status",
            "status": "fail",
            "error_type": "IndexError",
            "error": "list index out of range",
        },
    },
    {
        "id": "B_none_attribute",
        "purpose": "コードを見ないと原因を絞れない",
        "failure": {
            "tool_name": "data_loader",
            "status": "fail",
            "error_type": "AttributeError",
            "error": "'NoneType' object has no attribute 'items'",
        },
    },
    {
        "id": "C_validation_fields",
        "purpose": "仕様・期待値との比較が必要",
        "failure": {
            "tool_name": "validator",
            "status": "fail",
            "error_type": "ValidationError",
            "error": "expected 3 fields, got 2",
        },
    },
    {
        "id": "D_cuda_init",
        "purpose": "環境依存の可能性がある",
        "failure": {
            "tool_name": "runtime_check",
            "status": "fail",
            "error_type": "RuntimeError",
            "error": "CUDA initialization failed",
        },
    },
    {
        "id": "E_information_poor",
        "purpose": "情報不足",
        "failure": {
            "tool_name": "unknown_tool",
            "status": "fail",
            "error_type": "RuntimeError",
            "error": "operation failed",
        },
    },
]


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
    return {
        "experiment": "problem_analysis_standalone",
        "id": case["id"],
        "purpose": case["purpose"],
        "model": MODEL,
        "failure": case["failure"],
        "prompt": prompt,
        "timestamp": started,
        "raw_output": raw,
        "notes": ["problem_analysis_only", "no_tools", "no_patch_requested"],
        "observability": {
            "experiment_start": started,
            "experiment_end": ended,
            "stop_reason": "timeout" if timeout else "single_turn",
            "timeout": timeout,
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
        "experiment": "problem_analysis_standalone",
        "note": "Problem Analysis only. Not FA. Not the tool-using problem-solving loop.",
        "at": _now(),
        "model": MODEL,
        "prompt_template": PROMPT_TEMPLATE,
        "cases": [],
    }
    try:
        for case in CASES:
            print(f"CASE {case['id']}", flush=True)
            record = run_case(case)
            run["cases"].append(
                {
                    "id": record["id"],
                    "timeout": record["observability"]["timeout"],
                    "raw_chars": len(record["raw_output"] or ""),
                }
            )
            (out / f"{case['id']}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            preview = (record["raw_output"] or record["observability"]["timeout"] or "")[:200]
            print(f"  chars={len(record['raw_output'] or '')} preview={preview!r}", flush=True)
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
