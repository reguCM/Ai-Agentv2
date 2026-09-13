"""
Problem Analysis モデル比較。完全最小 Prompt を deepseek-coder-v2:16b と qwen3:14b に同一条件で渡す。

既存 minimal / free / guided ハーネスと結果 JSON は変更しない。
FA / Dispatcher / 本番 Agent には接続しない。
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
from research.llm_benchmarks.problem_solving_experiment.problem_analysis_bench import (
    CASES,
)
from research.llm_benchmarks.problem_solving_experiment.problem_analysis_minimal_bench import (
    PROMPT_TEMPLATE,
    build_prompt,
)


OUT_DIR = Path(
    "research/llm_benchmarks/problem_solving_experiment/results/problem_analysis_model_compare"
)

COMPARE_MODELS = [
    {
        "ollama_name": "deepseek-coder-v2:16b",
        "dir_name": "deepseek-coder-v2-16b",
    },
    {
        "ollama_name": "qwen3:14b",
        "dir_name": "qwen3-14b",
    },
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _case_file(case):
    return f"case_{case['id'][0]}.json"


def run_case(case, ollama_name):
    prompt = build_prompt(case["failure"])
    messages = [{"role": "user", "content": prompt}]
    messages_before_chat = copy_messages(messages)
    active_profile = get_llm_profile()
    chat_kwargs = chat_kwargs_snapshot(active_profile, ollama_name)
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
    call_ok = timeout is None
    record = {
        "experiment": "problem_analysis_model_compare",
        "id": case["id"],
        "case_file": _case_file(case),
        "purpose": case["purpose"],
        "model": ollama_name,
        "temperature": chat_kwargs["options"]["temperature"],
        "failure": case["failure"],
        "prompt": prompt,
        "timestamp": started,
        "raw_output": raw,
        "call_ok": call_ok,
        "notes": [
            "problem_analysis_model_compare",
            "minimal_prompt_copied_from_3c",
            "no_tools",
            "thinking_not_requested",
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
            "generation_options_source": "llm.chat setdefault from active get_llm_profile()",
        },
    }
    if thinking:
        record["observability"]["thinking_observed"] = True
        record["observability"]["thinking"] = thinking
    else:
        record["observability"]["thinking_observed"] = False
    return record


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / stamp
    out.mkdir(parents=True, exist_ok=True)
    run = {
        "experiment": "problem_analysis_model_compare",
        "note": (
            "Minimal-prompt Problem Analysis model compare. "
            "Not FA. Prompt identical for both models. Tools not used. "
            "Thinking not requested."
        ),
        "at": _now(),
        "prompt_template": PROMPT_TEMPLATE,
        "models": [item["ollama_name"] for item in COMPARE_MODELS],
        "compared_to_3c": "results/problem_analysis_minimal/20260831T234044Z",
        "models_run": [],
    }
    try:
        for item in COMPARE_MODELS:
            ollama_name = item["ollama_name"]
            model_dir = out / item["dir_name"]
            model_dir.mkdir(parents=True, exist_ok=True)
            model_summary = {"model": ollama_name, "cases": []}
            print(f"MODEL {ollama_name}", flush=True)
            try:
                for case in CASES:
                    print(f"  CASE {case['id']}", flush=True)
                    record = run_case(case, ollama_name)
                    model_summary["cases"].append(
                        {
                            "id": record["id"],
                            "call_ok": record["call_ok"],
                            "timeout": record["observability"]["timeout"],
                            "raw_chars": len(record["raw_output"] or ""),
                            "thinking_observed": record["observability"]["thinking_observed"],
                        }
                    )
                    (model_dir / _case_file(case)).write_text(
                        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    preview = (
                        record["raw_output"] or record["observability"]["timeout"] or ""
                    )[:160]
                    print(
                        f"    ok={record['call_ok']} chars={len(record['raw_output'] or '')} "
                        f"thinking={record['observability']['thinking_observed']} "
                        f"preview={preview!r}",
                        flush=True,
                    )
            finally:
                stop_model(ollama_name)
            run["models_run"].append(model_summary)
    finally:
        pass
    (out / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
