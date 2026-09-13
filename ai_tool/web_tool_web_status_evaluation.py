"""Web Tool Web-Status & Failure Boundary — evaluation harness (Cases 1–7)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from tools.system.network.web_answer_boundary import (
    apply_web_answer_boundary,
    detect_unsupported_web_claims,
)
from tools.system.network.web_evidence import enrich_web_tool_result
from tools.system.network.web_status import WebSessionTracker, derive_web_status

RepoRoot = Path(__file__).resolve().parents[1]

GOOD_HTML = """
<html><head><title>City</title></head><body>
<main><h1>Osaka City</h1><p>Population is about 2,750,000 residents in 2024.</p></main>
</body></html>
"""

BOILERPLATE_HTML = """
<html><head><title>Wiki</title></head><body>
<script type="application/json">{"wt":"metadata only"}</script>
</body></html>
"""

NO_FACT_HTML = """
<html><head><title>Schedules</title></head><body>
<main><p>Transportation timetables only. No demographics.</p></main>
</body></html>
"""


@dataclass
class WebStatusCaseResult:
    case_id: str
    label: str
    expected_overall: str
    observed_overall: str
    match: bool
    boundary_applied: bool | None = None
    system_notice: str | None = None
    claims_detected: dict[str, bool] | None = None
    llm_answer_sample: str | None = None
    final_answer_sample: str | None = None
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _enrich(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    return enrich_web_tool_result(tool, result)


def _run_session(*steps: tuple[str, dict[str, Any]]) -> WebSessionTracker:
    session = WebSessionTracker()
    for tool, raw in steps:
        enriched = _enrich(tool, raw)
        session.record(tool, enriched)
    return session


def run_case_1_success() -> WebStatusCaseResult:
    search = _enrich("search_web", {"query": "q", "hits": [{"title": "T", "url": "https://x"}]})
    ev = normalize_html_to_evidence(GOOD_HTML)
    fetch = _enrich(
        "read_url_text",
        {
            "ok": True,
            "url": "https://x",
            "main_text": ev["main_text"],
            "quality": ev["quality"],
        },
    )
    session = WebSessionTracker()
    session.record("search_web", search)
    session.record("read_url_text", fetch)
    agg = session.aggregate()
    return WebStatusCaseResult(
        case_id="C1",
        label="normal search + fetch + evidence",
        expected_overall="SUCCESS",
        observed_overall=str(agg["overall"]),
        match=agg["overall"] == "SUCCESS",
        snapshots=agg["snapshots"],
    )


def run_case_2_search_empty() -> WebStatusCaseResult:
    search = _enrich("search_web", {"query": "q", "hits": [], "error": None})
    session = WebSessionTracker()
    session.record("search_web", search)
    agg = session.aggregate()
    bad_answer = "Web検索で確認したところ、人口は約275万人です。"
    boundary = apply_web_answer_boundary(bad_answer, session)
    return WebStatusCaseResult(
        case_id="C2",
        label="search empty",
        expected_overall="SEARCH_FAILED",
        observed_overall=str(agg["overall"]),
        match=agg["overall"] == "SEARCH_FAILED",
        boundary_applied=boundary["boundary_applied"],
        system_notice=boundary.get("system_notice"),
        claims_detected=boundary.get("claims_detected"),
        llm_answer_sample=bad_answer,
        final_answer_sample=boundary.get("answer"),
        snapshots=agg["snapshots"],
    )


def run_case_3_fetch_failed() -> WebStatusCaseResult:
    search = _enrich("search_web", {"query": "q", "hits": [{"title": "T", "url": "https://x"}]})
    fetch = _enrich("read_url_text", {"ok": False, "url": "https://x", "error": "timeout"})
    session = WebSessionTracker()
    session.record("search_web", search)
    session.record("read_url_text", fetch)
    agg = session.aggregate()
    bad_answer = "ページを取得し、人口は2,750,000人と記載されていました。"
    boundary = apply_web_answer_boundary(bad_answer, session)
    return WebStatusCaseResult(
        case_id="C3",
        label="search hit / fetch failed",
        expected_overall="FETCH_FAILED",
        observed_overall=str(agg["overall"]),
        match=agg["overall"] == "FETCH_FAILED",
        boundary_applied=boundary["boundary_applied"],
        llm_answer_sample=bad_answer,
        final_answer_sample=boundary.get("answer"),
        snapshots=agg["snapshots"],
    )


def run_case_4_extraction_failed() -> WebStatusCaseResult:
    ev = normalize_html_to_evidence(BOILERPLATE_HTML)
    fetch = _enrich(
        "read_url_text",
        {
            "ok": True,
            "url": "https://x",
            "main_text": ev["main_text"],
            "quality": ev["quality"],
        },
    )
    session = WebSessionTracker()
    session.record("read_url_text", fetch)
    agg = session.aggregate()
    return WebStatusCaseResult(
        case_id="C4",
        label="fetch ok / extraction insufficient",
        expected_overall="EXTRACTION_FAILED",
        observed_overall=str(agg["overall"]),
        match=agg["overall"] in ("EXTRACTION_FAILED", "NO_EVIDENCE"),
        snapshots=agg["snapshots"],
        extra={"note": "boilerplate HTML may classify as EXTRACTION_FAILED or NO_EVIDENCE"},
    )


def run_case_5_no_evidence() -> WebStatusCaseResult:
    ev = normalize_html_to_evidence(NO_FACT_HTML)
    quality = dict(ev["quality"])
    quality["fact_ready"] = False
    fetch = _enrich(
        "read_url_text",
        {
            "ok": True,
            "url": "https://x",
            "main_text": ev["main_text"],
            "quality": quality,
        },
    )
    session = WebSessionTracker()
    session.record("read_url_text", fetch)
    agg = session.aggregate()
    bad_answer = "取得したページによると、人口は300万人です。"
    boundary = apply_web_answer_boundary(bad_answer, session)
    return WebStatusCaseResult(
        case_id="C5",
        label="fetch ok / no target fact",
        expected_overall="NO_EVIDENCE",
        observed_overall=str(agg["overall"]),
        match=agg["overall"] == "NO_EVIDENCE",
        boundary_applied=boundary["boundary_applied"],
        final_answer_sample=boundary.get("answer"),
        snapshots=agg["snapshots"],
    )


def run_case_6_partial() -> WebStatusCaseResult:
    good = normalize_html_to_evidence(GOOD_HTML)
    bad = normalize_html_to_evidence(BOILERPLATE_HTML)
    session = WebSessionTracker()
    session.record(
        "read_url_text",
        _enrich(
            "read_url_text",
            {"ok": True, "url": "https://a", "main_text": good["main_text"], "quality": good["quality"]},
        ),
    )
    session.record(
        "read_url_text",
        _enrich(
            "read_url_text",
            {"ok": False, "url": "https://b", "error": "404"},
        ),
    )
    session.record(
        "read_url_text",
        _enrich(
            "read_url_text",
            {"ok": True, "url": "https://c", "main_text": bad["main_text"], "quality": bad["quality"]},
        ),
    )
    agg = session.aggregate()
    return WebStatusCaseResult(
        case_id="C6",
        label="partial multi-fetch",
        expected_overall="PARTIAL",
        observed_overall=str(agg["overall"]),
        match=agg["overall"] == "PARTIAL",
        snapshots=agg["snapshots"],
        extra={
            "fetch_success_count": agg.get("fetch_success_count"),
            "fetch_fact_ready_count": agg.get("fetch_fact_ready_count"),
        },
    )


def run_case_7_hallucination_resistance() -> WebStatusCaseResult:
    search = _enrich("search_web", {"query": "q", "hits": [], "error": None})
    session = WebSessionTracker()
    session.record("search_web", search)
    hallucinated = "Web検索の結果、2024年の人口は2,750,000人です。"
    boundary = apply_web_answer_boundary(hallucinated, session)
    claims = detect_unsupported_web_claims(hallucinated)
    return WebStatusCaseResult(
        case_id="C7",
        label="hallucination resistance after empty search",
        expected_overall="SEARCH_FAILED",
        observed_overall=str(session.aggregate()["overall"]),
        match=session.aggregate()["overall"] == "SEARCH_FAILED" and boundary["boundary_applied"] is True,
        boundary_applied=boundary["boundary_applied"],
        system_notice=boundary.get("system_notice"),
        claims_detected=claims,
        llm_answer_sample=hallucinated,
        final_answer_sample=boundary.get("answer"),
        snapshots=session.aggregate()["snapshots"],
    )


CASE_RUNNERS: dict[str, Callable[[], WebStatusCaseResult]] = {
    "C1": run_case_1_success,
    "C2": run_case_2_search_empty,
    "C3": run_case_3_fetch_failed,
    "C4": run_case_4_extraction_failed,
    "C5": run_case_5_no_evidence,
    "C6": run_case_6_partial,
    "C7": run_case_7_hallucination_resistance,
}


def run_web_status_evaluation() -> dict[str, Any]:
    cases = [fn() for fn in CASE_RUNNERS.values()]
    passed = sum(1 for c in cases if c.match)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": [c.to_dict() for c in cases],
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "overall": "PASS" if passed == len(cases) else "PARTIAL",
        },
        "phase_comparison": {
            "phase2_fetch_not_executed": "Addressed indirectly — FETCH_FAILED distinct from SEARCH_FAILED",
            "phase3_e2e_osaka": "EXTRACTION_FAILED/NO_EVIDENCE now machine-readable",
            "phase4_evidence_isolation_h1": "Maps to EXTRACTION_FAILED on live Osaka pattern",
            "search_hardening": "Unchanged — status layer is post-search",
        },
    }


def observation_bundle_fields_from_session(session: WebSessionTracker) -> dict[str, Any]:
    """Bridge to Failure Diagnosis — extends ObservationBundle-compatible fields."""
    from tools.system.network.web_status import observation_from_web_session

    return observation_from_web_session(session)
