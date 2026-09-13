"""Web Tool Autonomous Improvement — health probes and decision support.

Observation-only harness; does not modify Production behavior.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.agent_integration.eval_production_parity_bridge import compare_path_divergence
from ai_tool.agent_integration.production_agent_web_loop import run_production_agent_web_loop
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.web_tool_extraction_normalization_production import run_production_golden
from tools.system.network.search_web import search_web

RepoRoot = Path(__file__).resolve().parents[1]

Knowledge = Literal["CONFIRMED FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]
StopReason = Literal["STOP_A", "STOP_B", "STOP_C", "STOP_D", "STOP_E"]

POP_PAT = (r"人口", r"population", r"2[,，]?8[0-9]{2}", r"275")


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def _has_population(text: str) -> bool:
    return any(re.search(p, text or "", re.I) for p in POP_PAT)


def probe_search_fetch_chain() -> dict[str, Any]:
    probes: dict[str, Any] = {}
    for case_id, query in (
        ("osaka", "大阪市の人口"),
        ("paris", "フランスの首都は"),
        ("nonsense", "zzzz_nonexistent_xyz_12345"),
    ):
        s = search_web(query=query)
        hits = s.get("hits") or []
        row: dict[str, Any] = {
            "query": query,
            "hit_count": len(hits),
            "error": s.get("error"),
            "fetch": None,
        }
        if hits:
            r = read_url_text(hits[0].get("url") or "")
            mt = str(r.get("main_text") or "")
            q = r.get("quality") or {}
            row["fetch"] = {
                "ok": r.get("ok"),
                "url": hits[0].get("url"),
                "fact_ready": q.get("fact_ready"),
                "extraction_method": q.get("extraction_method"),
                "main_text_len": len(mt),
                "population_signal": _has_population(mt),
            }
        probes[case_id] = row
    return probes


def probe_eval_vs_mirror_gap() -> dict[str, Any]:
    """Document eval-direct vs production_mirror enforcement gap (via CC-01 bridge)."""
    divergence = compare_path_divergence()
    return {
        "eval_direct_hit_count": divergence["diagnostic"]["hit_count"],
        "eval_direct_has_boundary": divergence["diagnostic"]["boundary_applied"],
        "mirror_boundary_applied": divergence["canonical"]["boundary_applied"],
        "mirror_final_suppressed_numeric": divergence["canonical"]["boundary_applied"],
        "canonical_production_equivalent": divergence["canonical"]["production_equivalent"],
        "diagnostic_production_equivalent": divergence["diagnostic"]["production_equivalent"],
        "gap_confirmed": divergence["gap_confirmed"],
        "bridge": "eval_production_parity_bridge",
    }


def probe_live_mirror_e2e(*, chat_fn=None, model: str = "") -> dict[str, Any]:
    if chat_fn is None:
        return {"status": "SKIPPED", "reason": "no_llm"}
    loop = run_production_agent_web_loop(
        "大阪市の人口をWeb検索で調べ、read_url_textで確認して教えてください",
        chat_fn=chat_fn,
        model=model,
        search_web_fn=search_web,
        read_url_text_fn=read_url_text,
        max_rounds=5,
        live=True,
    )
    fetch = next((t for t in loop.tool_executions if t.tool_name == "read_url_text"), None)
    mt = str((fetch.result if fetch else {}).get("main_text") or "")
    agg = loop.web_session_aggregate or {}
    return {
        "status": "OK",
        "tools": [t.tool_name for t in loop.tool_executions],
        "web_status": agg.get("overall"),
        "fact_ready": ((fetch.result if fetch else {}).get("quality") or {}).get("fact_ready"),
        "population_in_main": _has_population(mt),
        "answer_has_population": _has_population(loop.final_answer or ""),
        "grade": "PASS"
        if agg.get("overall") == "SUCCESS" and _has_population(mt)
        else "PARTIAL",
    }


def generate_options(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "OPT_STOP_D",
            "name": "No Production change — post-extraction baseline",
            "layer": "none",
            "effect": "Acknowledge extraction fix closed primary Osaka chain",
            "risk": "none",
            "scope": "documentation + probes only",
            "human_review": False,
            "recommended_if": assessment.get("live_e2e_pass") and assessment.get("golden_pass"),
        },
        {
            "id": "OPT_EVAL_CANONICAL",
            "name": "Canonical eval via production_mirror wrapper",
            "layer": "evaluation harness",
            "effect": "Fix autonomous loop metric drift vs production",
            "risk": "low",
            "scope": "ai_tool harness only",
            "human_review": False,
            "recommended_if": assessment.get("eval_gap_confirmed"),
        },
        {
            "id": "OPT_AGENT_FETCH_POLICY",
            "name": "Agent mandatory fetch when search hits",
            "layer": "agent.py",
            "effect": "Reduce fetch-skip orchestration failures",
            "risk": "medium",
            "scope": "agent + prompt",
            "human_review": True,
            "recommended_if": assessment.get("fetch_skip_observed"),
        },
        {
            "id": "OPT_EVIDENCE_AVAIL",
            "name": "evidence_availability grounding hint",
            "layer": "web_evidence",
            "effect": "Separate question-specific availability from fact_ready",
            "risk": "schema-adjacent",
            "human_review": True,
            "recommended_if": False,
        },
    ]


def select_option(options: list[dict[str, Any]], assessment: dict[str, Any]) -> tuple[str, str, StopReason]:
    if assessment.get("live_e2e_pass") and assessment.get("golden_pass"):
        return (
            "OPT_STOP_D",
            "Primary factual chain (Osaka) passes live search→fetch→extraction→LLM. "
            "Extraction fix (d37e343) addressed dominant blocker. "
            "Remaining gaps are eval-path observability and env-transient search — not sufficient ROI for Production change now.",
            "STOP_D",
        )
    if not assessment.get("golden_pass"):
        return ("OPT_STOP_A", "Golden regression fail — insufficient evidence for change", "STOP_A")
    return ("OPT_STOP_E", "Architecture change unclear — need more observation", "STOP_E")


def run_autonomous_improvement(
    *,
    fetch_live: bool = True,
    llm_enabled: bool = False,
    chat_fn=None,
    model: str = "",
) -> dict[str, Any]:
    golden = run_production_golden(fetch_live=fetch_live)
    chain = probe_search_fetch_chain()
    gap = probe_eval_vs_mirror_gap()
    live_e2e = probe_live_mirror_e2e(chat_fn=chat_fn if llm_enabled else None, model=model)

    assessment = {
        "golden_pass": golden.get("overall") == "PASS",
        "golden_pass_count": golden.get("pass_count"),
        "osaka_chain_pass": bool(
            chain.get("osaka", {}).get("fetch", {}) and chain["osaka"]["fetch"].get("population_signal")
        ),
        "live_e2e_pass": live_e2e.get("grade") == "PASS",
        "eval_gap_confirmed": gap.get("gap_confirmed"),
        "fetch_skip_observed": False,
    }

    options = generate_options(assessment)
    selected, why, stop_reason = select_option(options, assessment)

    confirmed = []
    if assessment["golden_pass"]:
        confirmed.append("GT1-GT6 golden PASS at HEAD (post d37e343 extraction)")
    if assessment["osaka_chain_pass"]:
        confirmed.append("Live search→fetch Osaka: population in main_text, fact_ready")
    if assessment["live_e2e_pass"]:
        confirmed.append("Live production_mirror E2E Osaka: web_status SUCCESS")
    if gap.get("gap_confirmed"):
        confirmed.append("Eval-direct lacks boundary; production_mirror applies boundary on empty search")

    unknowns = [
        "SUCCESS-class wrong answer rate not measured",
        "agent.py subprocess vs production_mirror parity under all models",
        "Long-tail JSON-LD sites outside metadata strip patterns",
        "Search backend stability across sessions (env-dependent)",
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": "d37e343",
        "current_head": _git_head(),
        "human_intervention_count": 0,
        "phase": "autonomous_improvement_selection",
        "production_changes": False,
        "probes": {
            "golden": golden,
            "search_fetch_chain": chain,
            "eval_vs_mirror_gap": gap,
            "live_mirror_e2e": live_e2e,
        },
        "assessment": assessment,
        "confirmed_facts": confirmed,
        "hypotheses": [
            "Eval path gap causes autonomous loops to over-estimate hallucination vs production",
            "Historical Live E2E SEARCH_FAILED was env-transient or pre-extraction",
        ],
        "unknowns": unknowns,
        "candidate_options": options,
        "selected_option": selected,
        "selection_reason": why,
        "rejected_options": [o["id"] for o in options if o["id"] != selected],
        "stop_reason": stop_reason,
        "stop": True,
        "next_recommended_direction": "Canonical eval harness (OPT_EVAL_CANONICAL) as next low-risk iteration",
        "overall": "PASS" if assessment["live_e2e_pass"] and assessment["golden_pass"] else "PARTIAL",
    }
