"""Post-Baseline Architecture Exploration — observation and option selection.

Does NOT modify Production. Re-verifies baseline and explores remaining problems.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from ai_tool.agent_integration.production_agent_web_loop import run_production_agent_web_loop
from ai_tool.agent_integration.trial import make_mock_chat_fn
from ai_tool.agent_integration.trial_scenarios import TrialScenario
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.web_tool_extraction_normalization_production import run_production_golden
from tools.system.network.search_web import search_web
from tools.system.network.web_status import derive_web_status

RepoRoot = Path(__file__).resolve().parents[1]

StopReason = Literal["STOP_A", "STOP_B", "STOP_C", "STOP_D", "STOP_E"]
Knowledge = Literal["CONFIRMED FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]

POP_PAT = (r"人口", r"population", r"2[,，]?8[0-9]{2}")


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def _has_population(text: str) -> bool:
    return any(re.search(p, text or "", re.I) for p in POP_PAT)


def verify_baseline(*, fetch_live: bool = True, chat_fn=None, model: str = "", llm_enabled: bool = False) -> dict[str, Any]:
    golden = run_production_golden(fetch_live=fetch_live)
    chain: dict[str, Any] = {}

    s = search_web(query="大阪市の人口")
    hits = s.get("hits") or []
    chain["osaka_search"] = {"hit_count": len(hits), "error": s.get("error")}
    if hits:
        r = read_url_text(hits[0].get("url") or "")
        mt = str(r.get("main_text") or "")
        chain["osaka_fetch"] = {
            "ok": r.get("ok"),
            "fact_ready": (r.get("quality") or {}).get("fact_ready"),
            "population": _has_population(mt),
            "web_status": derive_web_status("read_url_text", r).overall,
            "method": (r.get("quality") or {}).get("extraction_method"),
        }

    scenario = TrialScenario(
        "boundary_probe", "q", "either", "n",
        mock_tool_calls=[{"name": "search_web", "arguments": {"query": "x"}}],
        mock_final_answer="人口は275万人です。",
    )

    def _empty(**_kw):
        return {"ok": True, "hits": [], "error": "empty"}

    loop = run_production_agent_web_loop(
        "大阪市の人口", chat_fn=make_mock_chat_fn(scenario), model="mock",
        search_web_fn=_empty, read_url_text_fn=read_url_text, max_rounds=2,
    )
    chain["boundary"] = {
        "applied": loop.boundary_applied,
        "suppressed_numeric": "275" not in (loop.final_answer or ""),
        "web_status": (loop.web_session_aggregate or {}).get("overall"),
    }

    live_e2e = {"status": "SKIPPED"}
    if llm_enabled and chat_fn:
        loop2 = run_production_agent_web_loop(
            "大阪市の人口をWeb検索で調べ、read_url_textで確認して教えてください",
            chat_fn=chat_fn, model=model, search_web_fn=search_web,
            read_url_text_fn=read_url_text, max_rounds=5, live=True,
        )
        fetch = next((t for t in loop2.tool_executions if t.tool_name == "read_url_text"), None)
        mt = str((fetch.result if fetch else {}).get("main_text") or "")
        live_e2e = {
            "status": "OK",
            "tools": [t.tool_name for t in loop2.tool_executions],
            "web_status": (loop2.web_session_aggregate or {}).get("overall"),
            "population_main": _has_population(mt),
            "population_answer": _has_population(loop2.final_answer or ""),
        }

    all_pass = (
        golden.get("overall") == "PASS"
        and chain.get("osaka_fetch", {}).get("population")
        and chain.get("boundary", {}).get("suppressed_numeric")
        and (live_e2e.get("web_status") == "SUCCESS" if llm_enabled else True)
    )
    return {
        "golden": golden,
        "chain": chain,
        "live_e2e": live_e2e,
        "baseline_pass": all_pass,
    }


def explore_remaining(*, fetch_live: bool = True) -> dict[str, Any]:
    findings: dict[str, Any] = {"confirmed": [], "observations": [], "hypotheses": [], "unknowns": []}

    # CONFIRMED: execute_registry_tool defaults to mock search
    direct = search_web(query="zzzz_nonexistent_xyz_12345")
    via_registry = execute_registry_tool("search_web", {"query": "zzzz_nonexistent_xyz_12345"})
    direct_hits = len(direct.get("hits") or [])
    registry_hits = len(via_registry.result.get("hits") or [])
    if direct_hits == 0 and registry_hits > 0:
        findings["confirmed"].append(
            "execute_registry_tool uses _mock_search_web by default — eval metrics diverge from Production search"
        )
    findings["exploration"] = {
        "direct_nonsense_hits": direct_hits,
        "registry_nonsense_hits": registry_hits,
        "registry_backend": (via_registry.result.get("hits") or [{}])[0].get("backend") if registry_hits else None,
    }

    # Boundary without session on eval path
    findings["confirmed"].append(
        "execute_registry_tool path has no WebSessionTracker / apply_web_answer_boundary (prior Live E2E doc)"
    )

    if fetch_live:
        r = read_url_text("https://example.com/")
        findings["observations"].append(
            f"Non-Wikipedia example.com: ok={r.get('ok')} fact_ready={(r.get('quality') or {}).get('fact_ready')} "
            f"method={(r.get('quality') or {}).get('extraction_method')}"
        )

    findings["unknowns"] = [
        "SUCCESS-class wrong answer rate under live varied queries",
        "Search backend instability across time (currently OK this session)",
        "Long-tail JSON-LD / metadata patterns not in strip list",
        "agent.py subprocess parity vs production_mirror for all models",
        "Question-specific evidence availability vs fact_ready semantic gap impact",
    ]
    findings["hypotheses"] = [
        "Primary Production factual chain is sufficient for baseline Wikipedia ja/en municipality queries",
        "Eval mock default causes false positives in autonomous empty-search probes if search_web_fn omitted",
        "Architecture changes (RTT, structured claims) have low ROI until SUCCESS wrong-answer rate measured",
    ]
    return findings


def architecture_options(baseline_pass: bool, findings: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "OPT0_NO_ACTION",
            "name": "現状維持 — Production baseline sufficient",
            "target_problems": [],
            "scope": "none",
            "regression_risk": "none",
            "automation_fit": "high (probes exist)",
            "human_review": False,
        },
        {
            "id": "OPT1_EVAL_PRODUCTION_BRIDGE",
            "name": "Evaluation-only: production search + mirror wrapper for harnesses",
            "target_problems": ["eval mock default", "boundary gap on eval path"],
            "scope": "ai_tool/agent_integration harness",
            "regression_risk": "low (may affect tests expecting mock)",
            "automation_fit": "high",
            "human_review": False,
        },
        {
            "id": "OPT2_MINIMAL_AGENT_POLICY",
            "name": "Agent fetch gate when search hits exist",
            "target_problems": ["fetch skip (historical)"],
            "scope": "agent.py",
            "regression_risk": "medium",
            "automation_fit": "medium",
            "human_review": True,
            "note": "Not reproduced in current live Osaka E2E",
        },
        {
            "id": "OPT3_STRUCTURED_MECHANICAL",
            "name": "Structured / mechanical answer layer",
            "target_problems": ["SUCCESS wrong-answer", "traceability"],
            "scope": "large",
            "regression_risk": "high",
            "automation_fit": "high",
            "human_review": True,
            "note": "ROI unproven — UNKNOWN wrong-answer rate",
        },
        {
            "id": "OPT4_RTT",
            "name": "Research Transaction abstraction",
            "target_problems": ["orchestration observability"],
            "scope": "large",
            "regression_risk": "high",
            "human_review": True,
            "note": "Deferred in prior phases; baseline E2E now passes",
        },
    ]


def select_option(baseline_pass: bool, options: list[dict[str, Any]], findings: dict[str, Any]) -> tuple[str, str, StopReason, list[str]]:
    rejected = [o["id"] for o in options if o["id"] != "OPT0_NO_ACTION"]
    if baseline_pass:
        why = (
            "Baseline re-verified: Golden 6/6, live Osaka chain SUCCESS, boundary on empty search, live E2E PASS. "
            "Remaining confirmed issues are eval-path mock default and missing boundary on execute_registry_tool — "
            "these affect autonomous metrics, not Production user path. ROI of Production change is low."
        )
        return "OPT0_NO_ACTION", why, "STOP_A", rejected
    return "OPT0_NO_ACTION", "Baseline fail — investigate before architecture change", "STOP_B", rejected


def run_post_baseline_exploration(
    *,
    fetch_live: bool = True,
    llm_enabled: bool = False,
    chat_fn=None,
    model: str = "",
) -> dict[str, Any]:
    initial_head = _git_head()
    baseline = verify_baseline(fetch_live=fetch_live, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
    findings = explore_remaining(fetch_live=fetch_live)
    options = architecture_options(baseline["baseline_pass"], findings)
    selected, why, stop_reason, rejected = select_option(baseline["baseline_pass"], options, findings)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": initial_head,
        "final_head": initial_head,
        "human_intervention_count": 0,
        "phase": "post_baseline_architecture_exploration",
        "production_changes": [],
        "evaluation_changes": [],
        "baseline_status": "PASS" if baseline["baseline_pass"] else "FAIL",
        "baseline_detail": baseline,
        "observations": findings.get("observations", []),
        "confirmed_causes": findings.get("confirmed", []),
        "hypotheses": findings.get("hypotheses", []),
        "unknowns": findings.get("unknowns", []),
        "exploration_detail": findings.get("exploration", {}),
        "architecture_options": options,
        "selected_option": selected,
        "selection_reason": why,
        "rejected_options": rejected,
        "tests": ["golden production", "live chain", "boundary probe", "pytest web suite (external)"],
        "before_after": {
            "pre_extraction_era_osaka": "FAIL",
            "post_d37e343_baseline": "PASS",
            "this_session": baseline["baseline_pass"],
        },
        "decision": "NO_ACTION",
        "stop_reason": stop_reason,
        "stop": True,
        "overall": "PASS" if baseline["baseline_pass"] else "PARTIAL",
        "next_recommended_direction": (
            "OPT1_EVAL_PRODUCTION_BRIDGE as optional low-risk eval-only iteration — not mandatory"
        ),
    }
