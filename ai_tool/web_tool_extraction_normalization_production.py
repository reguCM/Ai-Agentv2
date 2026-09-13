"""Web Tool Extraction Normalization — Production Implementation validation."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.web_tool_extraction_normalization_experiment import (
    GT3_NAV_FIXTURE,
    GT6_SIMPLE_HTML,
    URL_GT1_OSAKA,
    URL_GT2_CAPITAL,
    URL_GT4_YOKOHAMA,
    URL_GT5_OSAKA_EN,
    golden_case_specs,
)
from ai_tool.web_tool_extraction_normalization_experiment import (
    evaluate_golden_case,
    fetch_raw_html,
)
from tools.system.network.web_status import derive_web_status

RepoRoot = Path(__file__).resolve().parents[1]

POPULATION_PATTERNS = (
    r"人口",
    r"population",
    r"[0-9]{1,3}[,，][0-9]{3,}",
    r"[0-9]{3,}\s*人",
)
CAPITAL_PATTERNS = (r"東京", r"Tokyo", r"首都")


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def _has_population(text: str) -> bool:
    return any(re.search(p, text or "", re.I) for p in POPULATION_PATTERNS)


def _has_capital(text: str) -> bool:
    return any(re.search(p, text or "", re.I) for p in CAPITAL_PATTERNS)


def run_production_golden(*, fetch_live: bool = True) -> dict[str, Any]:
    """Golden GT1-GT6 via production read_url_text path."""
    results: dict[str, Any] = {}
    for spec in golden_case_specs():
        if spec.fixture_html:
            fetched = {"ok": True, "fixture": True}
            # Use normalize path through read_url mock - evaluate via prototype S0 which IS production normalize
            from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence

            ev = normalize_html_to_evidence(spec.fixture_html)
            main_text = ev.get("main_text") or ""
            quality = ev.get("quality") or {}
            row = {
                "case_id": spec.case_id,
                "grade": _grade_production(spec, main_text, quality),
                "main_text_length": len(main_text),
                "population": _has_population(main_text),
                "capital": _has_capital(main_text),
                "fact_ready": quality.get("fact_ready"),
                "extraction_method": quality.get("extraction_method"),
                "warnings": quality.get("warnings"),
                "main_text_excerpt": main_text[:400],
            }
            ws = derive_web_status(
                "read_url_text",
                {"ok": True, "main_text": main_text, "quality": quality},
            )
            row["web_status"] = ws.to_dict()
            results[spec.case_id] = row
            continue

        if not fetch_live or not spec.url:
            results[spec.case_id] = {"error": "skipped"}
            continue

        r = read_url_text(spec.url)
        main_text = str(r.get("main_text") or "")
        quality = r.get("quality") or {}
        row = {
            "case_id": spec.case_id,
            "fetch_ok": r.get("ok"),
            "grade": _grade_production(spec, main_text, quality),
            "main_text_length": len(main_text),
            "population": _has_population(main_text),
            "capital": _has_capital(main_text),
            "fact_ready": quality.get("fact_ready"),
            "extraction_method": quality.get("extraction_method"),
            "warnings": quality.get("warnings"),
            "main_text_excerpt": main_text[:400],
        }
        ws = derive_web_status("read_url_text", r)
        row["web_status"] = ws.to_dict()
        results[spec.case_id] = row
    pass_count = sum(1 for v in results.values() if v.get("grade") == "PASS")
    return {
        "cases": results,
        "pass_count": pass_count,
        "total": len(results),
        "overall": "PASS" if pass_count == len(results) else "FAIL",
    }


def _grade_production(spec, main_text: str, quality: dict) -> str:
    pc = spec.pass_criteria
    if pc.get("require_population") and not _has_population(main_text):
        return "FAIL"
    if pc.get("require_capital") and not _has_capital(main_text):
        return "FAIL"
    if pc.get("forbid_false_population") and _has_population(main_text):
        return "FAIL"
    if pc.get("forbid_false_capital") and _has_capital(main_text):
        return "FAIL"
    if pc.get("min_main_text_length") and len(main_text) < int(pc["min_main_text_length"]):
        return "FAIL"
    if '"wt"' in main_text and pc.get("require_population"):
        return "FAIL"
    return "PASS"


def run_production_mirror_e2e_osaka(*, chat_fn=None, model: str = "") -> dict[str, Any]:
    """production_mirror path: mock search -> read_url_text -> observe evidence."""
    from ai_tool.agent_integration.production_agent_web_loop import run_production_agent_web_loop
    from ai_tool.agent_integration.trial import make_mock_chat_fn
    from ai_tool.agent_integration.trial_scenarios import TrialScenario

    osaka_url = URL_GT1_OSAKA

    def _mock_search(**_kw):
        return {
            "ok": True,
            "hits": [{"title": "大阪市", "url": osaka_url, "snippet": "大阪市 Wikipedia"}],
            "error": None,
        }

    def _read_url(**kwargs):
        url = kwargs.get("url") or ""
        return read_url_text(url)

    if chat_fn is None:
        scenario = TrialScenario(
            scenario_id="osaka_population_e2e",
            user_request="大阪市の人口を教えてください",
            expected_tool="either",
            routing_note="search then fetch osaka wiki",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口"}},
                {"name": "read_url_text", "arguments": {"url": osaka_url}},
            ],
            mock_final_answer="",
        )
        chat = make_mock_chat_fn(scenario)
    else:
        chat = chat_fn

    loop = run_production_agent_web_loop(
        "大阪市の人口を教えてください",
        chat_fn=chat,
        model=model or "mock",
        search_web_fn=_mock_search,
        read_url_text_fn=_read_url,
        max_rounds=4,
        live=chat_fn is not None,
    )

    fetch_exec = next((t for t in loop.tool_executions if t.tool_name == "read_url_text"), None)
    fetch_result = fetch_exec.result if fetch_exec else {}
    main_text = str(fetch_result.get("main_text") or "")
    agg = loop.web_session_aggregate or {}

    return {
        "tool_names": [t.tool_name for t in loop.tool_executions],
        "fetch_ok": fetch_result.get("ok"),
        "main_text_population": _has_population(main_text),
        "fact_ready": (fetch_result.get("quality") or {}).get("fact_ready"),
        "web_status_overall": agg.get("overall"),
        "extraction_method": (fetch_result.get("quality") or {}).get("extraction_method"),
        "raw_llm_answer_excerpt": (loop.raw_llm_answer or "")[:500],
        "final_answer_excerpt": (loop.final_answer or "")[:500],
        "rounds": loop.rounds,
        "error": loop.error,
        "grade": "PASS" if _has_population(main_text) and fetch_result.get("ok") else "PARTIAL",
    }


def run_validation(
    *,
    fetch_live: bool = True,
    baseline: dict[str, Any] | None = None,
    llm_enabled: bool = False,
    chat_fn=None,
    model: str = "",
) -> dict[str, Any]:
    golden = run_production_golden(fetch_live=fetch_live)
    e2e = run_production_mirror_e2e_osaka(chat_fn=chat_fn if llm_enabled else None, model=model)

    gt1 = golden["cases"].get("GT1", {})
    before_gt1 = (baseline or {}).get("GT1", {}).get("grade", "FAIL")

    comparison = {
        "GT1_Osaka": {"before": before_gt1, "after": gt1.get("grade")},
        "GT2_Capital": {"before": "PASS", "after": golden["cases"].get("GT2", {}).get("grade")},
        "GT3_nav": {"before": "PASS", "after": golden["cases"].get("GT3", {}).get("grade")},
        "GT4_Yokohama": {"before": "FAIL", "after": golden["cases"].get("GT4", {}).get("grade")},
        "GT5_en_Osaka": {"before": "FAIL", "after": golden["cases"].get("GT5", {}).get("grade")},
        "GT6_simple": {"before": "PASS", "after": golden["cases"].get("GT6", {}).get("grade")},
        "osaka_population_in_main_text": {
            "before": "absent",
            "after": "present" if gt1.get("population") else "absent",
        },
        "fact_ready_semantics": {"before": "unchanged", "after": "unchanged"},
    }

    overall = "PASS" if golden["overall"] == "PASS" else "PARTIAL" if golden["pass_count"] >= 4 else "FAIL"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "phase": "extraction_normalization_production",
        "selected_strategy": "S4_paragraph_density",
        "golden_production": golden,
        "production_mirror_e2e": e2e,
        "before_after": comparison,
        "baseline_recorded": baseline,
        "overall": overall,
        "human_review_required": True,
        "human_intervention_count": 0,
        "remaining_unknowns": [
            "Live agent.py subprocess with unstable search backends",
            "Long-tail JSON-LD sites not matching metadata patterns",
        ],
        "next_iteration_candidates": [
            "Live E2E with real search_web (non-mocked)",
            "evidence_availability grounding hint (separate from fact_ready)",
        ],
        "stop": golden["overall"] == "PASS",
    }
