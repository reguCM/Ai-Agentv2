#!/usr/bin/env python3
"""Run Web Tool Practical Evaluation Phase 2 — Evidence Pipeline, minimal prompt."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import live_chat_fn, ollama_available
from ai_tool.web_tool_practical_evaluation import EVAL_CASES, aggregate_overall
from ai_tool.web_tool_practical_evaluation_phase2 import (
    compare_with_baseline,
    load_baseline_case,
    run_live_practical_case_phase2,
    summarize_triage,
)
from tools.system.config import get_llm_profile
from tools.system.llm_tool_capability import probe_tool_calling

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_practical_evaluation_phase2"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
BASELINE_RUN = "20260828_201538_web_tool_practical_evaluation"
DOC_PATH = _REPO / "docs" / "ai_tool" / "project_audit" / "WEB_TOOL_PRACTICAL_EVALUATION_PHASE2.md"
SUPPLEMENTARY_PROFILE = "qwen3_8b"


def _reset_llm_client() -> None:
    import tools.system.llm as llm_mod

    llm_mod._client = None
    llm_mod._client_timeout = None


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    if not ollama_available():
        summary = {"error": "ollama_unavailable", "run_id": RUN_ID}
        (RUN_DIR / "evaluation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    prev = os.environ.get("AI_AGENT_MODEL")
    os.environ["AI_AGENT_MODEL"] = SUPPLEMENTARY_PROFILE
    _reset_llm_client()
    profile = get_llm_profile(SUPPLEMENTARY_PROFILE)
    model = str(profile.get("model") or "")
    chat = live_chat_fn()
    cap = probe_tool_calling(model, chat_fn=chat)

    cases: list[dict] = []
    comparisons: list[dict] = []

    if cap.get("supported") is True:
        for case in EVAL_CASES:
            print(f"Running case {case.case_id}...")
            try:
                result = run_live_practical_case_phase2(case, chat_fn=chat, model=model)
            except Exception as exc:
                result = {
                    "case_id": case.case_id,
                    "overall": "UNKNOWN",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            baseline = load_baseline_case(case.case_id)
            comp = compare_with_baseline(result, baseline)
            comp["case_id"] = case.case_id
            cases.append(result)
            comparisons.append(comp)
            (RUN_DIR / f"case_{case.case_id}_live_phase2.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    else:
        cases = [{"error": "MODEL_CAPABILITY", "capability": cap}]

    if prev is None:
        os.environ.pop("AI_AGENT_MODEL", None)
    else:
        os.environ["AI_AGENT_MODEL"] = prev
    _reset_llm_client()

    evaluation = {
        "run_id": RUN_ID,
        "baseline_run": BASELINE_RUN,
        "git_head": _git_head(),
        "prompt_variant": "minimal",
        "evidence_pipeline": True,
        "model": model,
        "capability": cap,
        "cases": cases,
        "comparisons": comparisons,
        "overall": aggregate_overall(cases, lane="live") if cases and cap.get("supported") else "UNKNOWN",
        "triage_summary": summarize_triage(cases),
    }
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "comparisons.json").write_text(json.dumps(comparisons, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(evaluation)
    print(json.dumps({"run_id": RUN_ID, "overall": evaluation["overall"], "triage": evaluation["triage_summary"]}, ensure_ascii=False, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0


def _git_head() -> str:
    import subprocess

    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def _write_markdown(evaluation: dict) -> None:
    lines = [
        "# Web Tool Practical Evaluation — Phase 2 (Evidence Pipeline, Minimal Prompt)",
        "",
        f"**Run:** `{evaluation.get('run_id')}`",
        f"**Baseline:** `{evaluation.get('baseline_run')}`",
        f"**Git HEAD:** `{evaluation.get('git_head')}`",
        f"**Prompt:** minimal (no Search→Fetch step list)",
        f"**Overall:** {evaluation.get('overall')}",
        "",
        "## Comparison vs Phase 1",
        "",
        "| Case | Baseline | Phase 2 | Delta | fact_ready | HTML meta |",
        "|------|----------|---------|-------|------------|-----------|",
    ]
    for comp in evaluation.get("comparisons") or []:
        lines.append(
            f"| {comp.get('case_id')} | {comp.get('baseline_overall')} | {comp.get('phase2_overall')} | "
            f"{comp.get('delta_overall')} | {comp.get('phase2_fact_ready')} | {comp.get('phase2_html_meta')} |"
        )
    lines.extend(["", "## Triage summary", "", json.dumps(evaluation.get("triage_summary") or {}, ensure_ascii=False, indent=2)])
    lines.extend(["", "## Per-case triage", ""])
    for case in evaluation.get("cases") or []:
        if not isinstance(case, dict) or case.get("case_id") is None:
            continue
        lines.append(f"### Case {case.get('case_id')} — {case.get('overall')}")
        for t in case.get("triage") or []:
            lines.append(f"- **{t.get('layer')}**: {t.get('note')}")
        ans = str(case.get("final_answer") or "")[:400]
        if ans:
            lines.append(f"\nfinal_answer (excerpt):\n```\n{ans}\n```\n")
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
