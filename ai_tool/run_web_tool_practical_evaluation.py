#!/usr/bin/env python3
"""Web Tool Practical Evaluation Phase 1 — run harness (no production changes, no commit)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_practical_evaluation import (
    EVAL_CASES,
    aggregate_overall,
    classify_research_tool_necessity,
    run_deterministic_practical_case,
    run_live_practical_case,
)
from ai_tool.agent_integration.gpu_process_e2e import live_chat_fn, ollama_available
from tools.system.config import get_llm_profile
from tools.system.llm_tool_capability import probe_tool_calling

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_practical_evaluation"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
DOC_PATH = _REPO / "docs" / "ai_tool" / "project_audit" / "WEB_TOOL_PRACTICAL_EVALUATION.md"
SUPPLEMENTARY_PROFILE = "qwen3_8b"


def _reset_llm_client() -> None:
    import tools.system.llm as llm_mod

    llm_mod._client = None
    llm_mod._client_timeout = None


def _run_with_profile(profile_id: str) -> tuple[str, dict]:
    prev = os.environ.get("AI_AGENT_MODEL")
    os.environ["AI_AGENT_MODEL"] = profile_id
    _reset_llm_client()
    profile = get_llm_profile(profile_id)
    model = str(profile.get("model") or "")
    capability = probe_tool_calling(model, chat_fn=live_chat_fn())
    if prev is None:
        os.environ.pop("AI_AGENT_MODEL", None)
    else:
        os.environ["AI_AGENT_MODEL"] = prev
    _reset_llm_client()
    return model, capability


def _live_cases(profile_id: str) -> dict:
    prev = os.environ.get("AI_AGENT_MODEL")
    os.environ["AI_AGENT_MODEL"] = profile_id
    _reset_llm_client()
    profile = get_llm_profile(profile_id)
    model = str(profile.get("model") or "")
    chat = live_chat_fn()
    cap = probe_tool_calling(model, chat_fn=chat)
    results: list[dict] = []
    lane_status = "SKIP"
    if cap.get("supported") is True:
        lane_status = "RUN"
        for case in EVAL_CASES:
            try:
                results.append(run_live_practical_case(case, chat_fn=chat, model=model))
            except Exception as exc:
                results.append(
                    {
                        "case_id": case.case_id,
                        "mode": "live_llm",
                        "model": model,
                        "overall": "UNKNOWN",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    else:
        lane_status = "MODEL_CAPABILITY"
    if prev is None:
        os.environ.pop("AI_AGENT_MODEL", None)
    else:
        os.environ["AI_AGENT_MODEL"] = prev
    _reset_llm_client()
    return {
        "profile_id": profile_id,
        "model": model,
        "capability": cap,
        "status": lane_status,
        "cases": results,
        "overall": aggregate_overall(results, lane="live") if results else "UNKNOWN",
    }


def _write_markdown(evaluation: dict) -> None:
    det = evaluation.get("deterministic") or {}
    primary = evaluation.get("primary_live") or {}
    supplementary = evaluation.get("supplementary_live") or {}
    lines = [
        "# Web Tool Practical Evaluation Phase 1",
        "",
        f"**Date:** {evaluation.get('date')}",
        f"**Git HEAD:** `{evaluation.get('git_head')}`",
        f"**Production changes:** NONE",
        f"**Git commit:** NOT EXECUTED",
        "",
        "## Overall",
        "",
        f"| Lane | Grade |",
        f"|------|-------|",
        f"| Deterministic (mock) | {det.get('overall', 'UNKNOWN')} |",
        f"| Primary live (`{primary.get('profile_id', '?')}`) | {primary.get('overall', 'UNKNOWN')} ({primary.get('status')}) |",
        f"| Supplementary live (`{supplementary.get('profile_id', '?')}`) | {supplementary.get('overall', 'UNKNOWN')} ({supplementary.get('status')}) |",
        "",
        f"**Composite observation:** {evaluation.get('composite_overall', 'UNKNOWN')}",
        "",
        "## Model capability",
        "",
        f"- Primary: `{primary.get('model')}` — {json.dumps(primary.get('capability') or {}, ensure_ascii=False)}",
        f"- Supplementary: `{supplementary.get('model')}` — {json.dumps(supplementary.get('capability') or {}, ensure_ascii=False)}",
        "",
        "## Case results (supplementary live — tool-capable)",
        "",
    ]
    for row in supplementary.get("cases") or []:
        label = row.get("label")
        if not label:
            for c in EVAL_CASES:
                if c.case_id == row.get("case_id"):
                    label = c.label
                    break
        lines.extend(
            [
                f"### Case {row.get('case_id')} — {label or '?'}" + (" (ERROR)" if row.get("error") else ""),
                "",
            ]
        )
        if row.get("error"):
            lines.append(f"- error: `{row.get('error')}`")
            lines.append(f"- overall: **{row.get('overall')}**")
            lines.append("")
            continue
        lines.extend(
            [
                f"- user_request: {row.get('user_request')}",
                f"- selected_tools: `{row.get('selected_tools')}`",
                f"- tool_call_count: {row.get('tool_call_count')}",
                f"- search_web_calls: {row.get('search_web_calls')}",
                f"- read_url_text_calls: {row.get('read_url_text_calls')}",
                f"- tool_selection: **{row.get('tool_selection')}**",
                f"- argument_generation: **{row.get('argument_generation')}**",
                f"- result_utilization: **{row.get('result_utilization')}**",
                f"- overall: **{row.get('overall')}**",
                "",
            ]
        )
        if row.get("problems"):
            lines.append("Problems:")
            for p in row["problems"]:
                lines.append(f"- [{p.get('id')}] {p.get('class')}: {p.get('note')}")
            lines.append("")
        if row.get("final_answer"):
            ans = str(row["final_answer"])
            lines.append("final_answer (excerpt):")
            lines.append("```")
            lines.append(ans[:1200] + ("..." if len(ans) > 1200 else ""))
            lines.append("```")
            lines.append("")

    lines.extend(
        [
            "## Known problems (aggregated)",
            "",
        ]
    )
    for p in evaluation.get("known_problems") or []:
        lines.append(f"- Case {p.get('case_id')} [{p.get('id')}] {p.get('class')}: {p.get('note')}")
    lines.extend(
        [
            "",
            "## Problem classification",
            "",
            json.dumps(evaluation.get("problem_classification") or {}, ensure_ascii=False, indent=2),
            "",
            f"**Research Tool necessity:** {evaluation.get('research_tool_necessity', 'NOT_ESTABLISHED')}",
            "",
            "## Deterministic vs Live",
            "",
            "Deterministic PASS does not imply Live PASS. Recorded separately.",
            "",
            f"Run artifacts: `{evaluation.get('run_dir')}`",
        ]
    )
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()

    det_cases = [run_deterministic_practical_case(c) for c in EVAL_CASES]
    det_overall = aggregate_overall(det_cases, lane="deterministic")

    ollama_ok, ollama_err = ollama_available()
    primary_profile = os.environ.get("AI_AGENT_MODEL") or __import__(
        "tools.system.config", fromlist=["active_model_id"]
    ).active_model_id()

    primary_live: dict = {"status": "SKIP", "overall": "UNKNOWN", "error": ollama_err}
    supplementary_live: dict = {"status": "SKIP", "overall": "UNKNOWN"}

    if ollama_ok:
        try:
            primary_live = _live_cases(primary_profile)
        except KeyError as exc:
            primary_live = {"status": "ERROR", "overall": "UNKNOWN", "error": str(exc)}
        if primary_profile != SUPPLEMENTARY_PROFILE:
            try:
                supplementary_live = _live_cases(SUPPLEMENTARY_PROFILE)
            except KeyError as exc:
                supplementary_live = {"status": "ERROR", "overall": "UNKNOWN", "error": str(exc)}

    all_problems: list[dict] = []
    for row in supplementary_live.get("cases") or []:
        for p in row.get("problems") or []:
            all_problems.append({**p, "case_id": row.get("case_id")})

    problem_classes: dict[str, int] = {}
    for p in all_problems:
        cls = str(p.get("class") or "UNKNOWN")
        problem_classes[cls] = problem_classes.get(cls, 0) + 1

    composite = supplementary_live.get("overall") or primary_live.get("overall") or det_overall

    evaluation = {
        "phase": "web_tool_practical_evaluation_phase1",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "git_head": git_head,
        "run_dir": str(RUN_DIR.resolve()),
        "production_changes": False,
        "git_commit": False,
        "deterministic": {"cases": det_cases, "overall": det_overall},
        "primary_live": primary_live,
        "supplementary_live": supplementary_live,
        "composite_overall": composite,
        "known_problems": all_problems,
        "problem_classification": problem_classes,
        "research_tool_necessity": classify_research_tool_necessity(all_problems),
        "human_review": "NOT_REQUIRED",
        "stop": True,
    }

    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, indent=2, ensure_ascii=False), encoding="utf-8")
    for case in det_cases:
        cid = case.get("case_id") or "X"
        (RUN_DIR / f"case_{cid}_deterministic.json").write_text(
            json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    for case in supplementary_live.get("cases") or []:
        cid = case.get("case_id") or "X"
        (RUN_DIR / f"case_{cid}_live_supplementary.json").write_text(
            json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    _write_markdown(evaluation)
    print(json.dumps({"run_dir": str(RUN_DIR.resolve()), "composite_overall": composite}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
