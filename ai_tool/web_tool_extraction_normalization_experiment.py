"""Web Tool Extraction Normalization — Experimental Prototype & Golden Regression.

Does NOT modify Production extraction, Agent, Registry, Prompt, Search, web_status, or boundary.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.experimental.read_url.config import DEFAULT_LIMITS
from ai_tool.experimental.read_url.extraction_prototype import (
    ExtractionPrototypeResult,
    STRATEGIES,
    run_all_strategies,
    run_strategy,
)
from ai_tool.experimental.read_url.http_client import default_http_get
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.experimental.read_url.ssrf import validate_url
from ai_tool.web_tool_evidence_extraction_isolation_phase4 import run_llm_extraction
from tools.system.network.web_status import derive_web_status

RepoRoot = Path(__file__).resolve().parents[1]

Knowledge = Literal["CONFIRMED FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]
MechanicalGrade = Literal["PASS", "FAIL", "PARTIAL", "SKIP"]

URL_GT1_OSAKA = "https://ja.wikipedia.org/wiki/%E5%A4%A7%E9%98%AA%E5%B8%82"
URL_GT2_CAPITAL = "https://ja.wikipedia.org/wiki/%E6%97%A5%E6%9C%AC%E3%81%AE%E9%A6%96%E9%83%BD"
URL_GT4_YOKOHAMA = "https://ja.wikipedia.org/wiki/%E6%A8%AA%E6%B5%9C%E5%B8%82"
URL_GT5_OSAKA_EN = "https://en.wikipedia.org/wiki/Osaka"

GT3_NAV_FIXTURE = """
<html><head><title>Search Portal</title></head><body>
<nav>メインメニュー sidebar jump to content</nav>
<div class="sidebar">No article content here.</div>
</body></html>
"""

GT6_SIMPLE_HTML = """
<html><head><title>City Stats</title></head><body>
<main><h1>Demo City</h1><p>The population is 450,000 as of 2024.</p></main>
</body></html>
"""


@dataclass
class GoldenCaseSpec:
    case_id: str
    label: str
    url: str | None
    fixture_html: str | None
    expect: str
    pass_criteria: dict[str, Any]
    regression_criteria: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyGoldenResult:
    case_id: str
    strategy_id: str
    mechanical_grade: MechanicalGrade
    extraction_status: str
    evidence_presence: dict[str, bool]
    fact_ready: bool
    fact_ready_reason: str
    warnings: list[str]
    removed_regions: list[str]
    main_text_length: int
    main_text_excerpt: str
    diagnosis: dict[str, Any]
    trace: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def fetch_raw_html(url: str, *, max_bytes: int = 524288) -> tuple[str, dict[str, Any]]:
    normalized, err = validate_url(url)
    meta: dict[str, Any] = {"url": url, "ok": False, "error": err}
    if err or not normalized:
        return "", meta
    try:
        status, headers, body, final = default_http_get(
            normalized,
            timeout_seconds=DEFAULT_LIMITS.timeout_seconds,
            max_bytes=max_bytes,
            max_redirects=DEFAULT_LIMITS.max_redirects,
        )
        text = body.decode("utf-8", errors="replace")
        meta.update({"ok": status < 400, "status_code": status, "bytes": len(body), "final_url": final})
        return text, meta
    except Exception as exc:  # noqa: BLE001
        meta["error"] = str(exc)
        return "", meta


def _derive_extraction_status(result: ExtractionPrototypeResult, *, expect: str) -> str:
    ep = result.evidence_presence
    if ep.get("wikidata_boilerplate") and not ep.get(expect if expect != "any" else "population", False):
        return "EXTRACTION_FAILED"
    if expect == "population" and ep.get("population") and not ep.get("wikidata_boilerplate"):
        return "SUCCESS"
    if expect == "capital" and ep.get("capital"):
        return "SUCCESS"
    if expect == "none" and not ep.get("population") and not ep.get("capital"):
        return "SUCCESS"
    if not ep.get("non_empty"):
        return "EXTRACTION_FAILED"
    if result.fact_ready:
        return "SUCCESS"
    return "EXTRACTION_FAILED"


def _mechanical_grade(
    result: ExtractionPrototypeResult,
    spec: GoldenCaseSpec,
) -> tuple[MechanicalGrade, list[str]]:
    reasons: list[str] = []
    ep = result.evidence_presence
    criteria = spec.pass_criteria

    if criteria.get("require_population"):
        if not ep.get("population"):
            reasons.append("population_evidence_missing")
        if ep.get("wikidata_boilerplate"):
            reasons.append("wikidata_boilerplate_center")
        if ep.get("navigation_only"):
            reasons.append("navigation_only")

    if criteria.get("require_capital"):
        if not ep.get("capital"):
            reasons.append("capital_evidence_missing")

    if criteria.get("forbid_false_population") and ep.get("population"):
        reasons.append("false_population_detected")

    if criteria.get("forbid_false_capital") and ep.get("capital"):
        reasons.append("false_capital_detected")

    if criteria.get("min_main_text_length") and len(result.main_text) < int(criteria["min_main_text_length"]):
        reasons.append("main_text_too_short")

    if spec.regression_criteria:
        reg = spec.regression_criteria
        if reg.get("production_capital_present") and not ep.get("capital"):
            reasons.append("regression_capital_lost")

    if not reasons:
        return "PASS", reasons
    if criteria.get("allow_partial") and len(reasons) == 1 and "main_text_too_short" in reasons:
        return "PARTIAL", reasons
    return "FAIL", reasons


def _build_diagnosis(result: ExtractionPrototypeResult, grade: MechanicalGrade, reasons: list[str]) -> dict[str, Any]:
    ep = result.evidence_presence
    classification: Knowledge = "OBSERVATION"
    if grade == "PASS":
        classification = "CONFIRMED FACT"
    elif ep.get("wikidata_boilerplate"):
        classification = "CONFIRMED FACT"
    hypothesis = ""
    if ep.get("population") and not result.fact_ready:
        hypothesis = "case3_heuristic_vs_evidence_mismatch"
    elif not ep.get("population") and result.fact_ready:
        hypothesis = "fact_ready_true_without_target_evidence"
    elif ep.get("wikidata_boilerplate"):
        hypothesis = "infobox_json_selected_as_body"
    return {
        "classification": classification,
        "mechanical_reasons": reasons,
        "hypothesis": hypothesis,
        "fact_ready_semantics_unchanged": True,
        "evidence_availability_vs_fact_ready": {
            "evidence_presence": ep,
            "fact_ready": result.fact_ready,
            "note": "evidence_presence is question-specific; fact_ready is production quality heuristic",
        },
    }


def _web_status_bridge(result: ExtractionPrototypeResult) -> dict[str, Any]:
    synthetic = {
        "ok": True,
        "main_text": result.main_text,
        "quality": {
            "fact_ready": result.fact_ready,
            "body_reached": result.body_reached,
            "extraction_success": bool(result.main_text.strip()),
            "warnings": result.warnings,
        },
    }
    return derive_web_status("read_url_text", synthetic).to_dict()


def evaluate_golden_case(
    spec: GoldenCaseSpec,
    *,
    html: str,
    fetch_meta: dict[str, Any],
) -> list[StrategyGoldenResult]:
    rows: list[StrategyGoldenResult] = []
    for sid in STRATEGIES:
        proto = run_strategy(sid, html, url=spec.url, expect=spec.expect)
        grade, reasons = _mechanical_grade(proto, spec)
        status = _derive_extraction_status(proto, expect=spec.expect)
        trace = [
            {"step": "fetch", **fetch_meta},
            {"step": "strategy", "strategy_id": sid},
            {"step": "extract", "method": proto.extraction_method, "removed": proto.removed_regions},
            {"step": "web_status", **(_web_status_bridge(proto))},
        ]
        rows.append(
            StrategyGoldenResult(
                case_id=spec.case_id,
                strategy_id=sid,
                mechanical_grade=grade,
                extraction_status=status,
                evidence_presence=dict(proto.evidence_presence),
                fact_ready=proto.fact_ready,
                fact_ready_reason=proto.fact_ready_reason,
                warnings=list(proto.warnings),
                removed_regions=list(proto.removed_regions),
                main_text_length=len(proto.main_text or ""),
                main_text_excerpt=proto.main_text[:400],
                diagnosis=_build_diagnosis(proto, grade, reasons),
                trace=trace,
            )
        )
    return rows


def golden_case_specs() -> list[GoldenCaseSpec]:
    return [
        GoldenCaseSpec(
            case_id="GT1",
            label="大阪市 — population evidence",
            url=URL_GT1_OSAKA,
            fixture_html=None,
            expect="population",
            pass_criteria={
                "require_population": True,
                "forbid_false_capital_only_center": False,
            },
        ),
        GoldenCaseSpec(
            case_id="GT2",
            label="日本の首都 — regression",
            url=URL_GT2_CAPITAL,
            fixture_html=None,
            expect="capital",
            pass_criteria={"require_capital": True, "min_main_text_length": 200},
            regression_criteria={"production_capital_present": True},
        ),
        GoldenCaseSpec(
            case_id="GT3",
            label="Navigation-only fixture — no false evidence",
            url=None,
            fixture_html=GT3_NAV_FIXTURE,
            expect="none",
            pass_criteria={
                "forbid_false_population": True,
                "forbid_false_capital": True,
            },
        ),
        GoldenCaseSpec(
            case_id="GT4",
            label="横浜市 — additional ja municipality",
            url=URL_GT4_YOKOHAMA,
            fixture_html=None,
            expect="population",
            pass_criteria={"require_population": True},
        ),
        GoldenCaseSpec(
            case_id="GT5",
            label="Osaka en.wikipedia — cross-language",
            url=URL_GT5_OSAKA_EN,
            fixture_html=None,
            expect="population",
            pass_criteria={"require_population": True},
        ),
        GoldenCaseSpec(
            case_id="GT6",
            label="Simple HTML main — non-wiki",
            url="fixture://simple",
            fixture_html=GT6_SIMPLE_HTML,
            expect="population",
            pass_criteria={"require_population": True},
        ),
    ]


def score_strategies(all_rows: list[StrategyGoldenResult]) -> dict[str, Any]:
    scores: dict[str, dict[str, int]] = {sid: {"pass": 0, "fail": 0, "partial": 0} for sid in STRATEGIES}
    for row in all_rows:
        bucket = scores[row.strategy_id]
        if row.mechanical_grade == "PASS":
            bucket["pass"] += 1
        elif row.mechanical_grade == "PARTIAL":
            bucket["partial"] += 1
        else:
            bucket["fail"] += 1

    gt1 = [r for r in all_rows if r.case_id == "GT1"]
    gt2 = [r for r in all_rows if r.case_id == "GT2"]
    gt3 = [r for r in all_rows if r.case_id == "GT3"]

    def _rank(candidates: list[StrategyGoldenResult]) -> list[str]:
        ordered = sorted(
            candidates,
            key=lambda r: (
                0 if r.mechanical_grade == "PASS" else 1,
                0 if r.fact_ready else 1,
                -r.main_text_length,
            ),
        )
        return [r.strategy_id for r in ordered]

    best_gt1 = _rank(gt1)[0] if gt1 else None
    passing_gt2 = {r.strategy_id for r in gt2 if r.mechanical_grade == "PASS"}
    passing_gt3 = {r.strategy_id for r in gt3 if r.mechanical_grade == "PASS"}

    safe_candidates = passing_gt2 & passing_gt3
    tie_preference = ("S4_PARAGRAPH_DENSITY", "S7_LARGEST_BLOCK", "S3_METADATA_STRIP", "S5_SEMANTIC", "S8_PRESTRIP_PRODUCTION", "S6_WIKI_MERGED")
    best_overall = None
    best_score = -1
    for sid, bucket in scores.items():
        if sid not in safe_candidates:
            continue
        score = bucket["pass"] * 2 + bucket["partial"] - bucket["fail"]
        if score > best_score:
            best_score = score
            best_overall = sid
    tied = [sid for sid, bucket in scores.items() if sid in safe_candidates and bucket["pass"] * 2 + bucket["partial"] - bucket["fail"] == best_score]
    if len(tied) > 1:
        for pref in tie_preference:
            if pref in tied:
                best_overall = pref
                break

    return {
        "per_strategy": scores,
        "best_gt1": best_gt1,
        "safe_candidates_gt2_gt3": sorted(safe_candidates),
        "best_overall_balanced": best_overall,
        "tied_candidates": tied if len(tied) > 1 else [],
        "production_gt1_grade": next((r.mechanical_grade for r in gt1 if r.strategy_id == "S0_PRODUCTION"), "UNKNOWN"),
    }


def run_llm_utilization_cases(
    *,
    chat_fn: Callable[..., Any] | None,
    model: str,
    llm_enabled: bool,
    osaka_results: list[ExtractionPrototypeResult],
) -> dict[str, Any]:
    """LLM Cases A/B/C separated from extraction scoring."""
    if not llm_enabled or not chat_fn:
        return {"status": "SKIPPED", "reason": "ollama_unavailable"}

    prod = next((r for r in osaka_results if r.strategy_id == "S0_PRODUCTION"), None)
    passing = [r for r in osaka_results if r.evidence_presence.get("population") and not r.evidence_presence.get("wikidata_boilerplate")]
    best = max(passing, key=lambda r: len(r.main_text), default=None)

    cases: list[dict[str, Any]] = []

    if best:
        llm_a = run_llm_extraction(
            "LLM-A",
            "evidence with population",
            best.main_text[:8000],
            chat_fn=chat_fn,
            model=model,
            quality={"fact_ready": best.fact_ready, "warnings": best.warnings},
        )
        cases.append(
            {
                "case": "A_evidence_present",
                "strategy": best.strategy_id,
                "answer_has_population": llm_a.answer_contains_target_fact,
                "state_class": llm_a.state_class,
                "grade": "PASS" if llm_a.answer_contains_target_fact else "FAIL",
            }
        )

    if prod:
        llm_b = run_llm_extraction(
            "LLM-B",
            "evidence without population (production)",
            prod.main_text[:8000],
            chat_fn=chat_fn,
            model=model,
            quality={"fact_ready": prod.fact_ready, "warnings": prod.warnings},
        )
        refused = llm_b.answer_contains_target_fact is False or "記載なし" in (llm_b.llm_answer or "")
        cases.append(
            {
                "case": "B_evidence_absent",
                "strategy": "S0_PRODUCTION",
                "refused_or_no_claim": refused,
                "invented_numeric": llm_b.numeric_claim_supported_by_evidence is False and bool(re.search(r"[0-9]{4,}", llm_b.llm_answer or "")),
                "state_class": llm_b.state_class,
                "grade": "PASS" if refused and not llm_b.answer_contains_target_fact else "PARTIAL",
            }
        )

    llm_c = run_llm_extraction(
        "LLM-C",
        "empty evidence",
        "This page discusses transportation schedules only.",
        chat_fn=chat_fn,
        model=model,
        quality={"fact_ready": False, "warnings": ["no_fact"]},
    )
    cases.append(
        {
            "case": "C_unsupported",
            "refused": "記載なし" in (llm_c.llm_answer or "") or not llm_c.answer_contains_target_fact,
            "invented": llm_c.state_class == "D",
            "state_class": llm_c.state_class,
            "grade": "PASS" if llm_c.state_class in ("C", "UNKNOWN") else "FAIL",
        }
    )

    return {"status": "OK", "cases": cases, "model": model}


def build_proposed_changes(scoring: dict[str, Any], best: str | None) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    if best and best != "S0_PRODUCTION":
        proposals.append(
            {
                "id": "PROPOSED_CHANGE_1",
                "layer": "html_normalize (Production)",
                "description": f"Merge experimental strategy {best} principles into normalize_html_to_evidence",
                "expected_effect": "GT1 population evidence; preserve GT2/GT3",
                "risk": "Regression on non-Wikipedia HTML if metadata patterns too aggressive",
                "scope": "ai_tool/experimental/read_url/html_normalize.py",
                "automation_suitability": "high — golden GT1-GT6 pytest",
                "human_review_required": True,
                "implement_in_this_phase": False,
            }
        )
    if best in ("S6_WIKI_MERGED",):
        proposals.append(
            {
                "id": "PROPOSED_CHANGE_2",
                "layer": "Wikipedia-specific branch",
                "description": "Host-based Wikipedia merge path",
                "expected_effect": "Strong wiki accuracy",
                "risk": "Site-specific maintenance",
                "human_review_required": True,
                "implement_in_this_phase": False,
                "note": "Only if generic strategies insufficient",
            }
        )
    proposals.append(
        {
            "id": "PROPOSED_CHANGE_EVIDENCE_AVAIL",
            "layer": "web_evidence / diagnosis (future)",
            "description": "Separate evidence_availability from fact_ready in grounding hints",
            "expected_effect": "Case3 visibility without changing fact_ready semantics",
            "risk": "Schema drift",
            "human_review_required": True,
            "implement_in_this_phase": False,
        }
    )
    return proposals


def build_decision_log(
    *,
    scoring: dict[str, Any],
    best: str | None,
    all_rows: list[StrategyGoldenResult],
    llm: dict[str, Any],
) -> dict[str, Any]:
    prod_gt1 = next((r for r in all_rows if r.case_id == "GT1" and r.strategy_id == "S0_PRODUCTION"), None)
    s3_gt1 = next((r for r in all_rows if r.case_id == "GT1" and r.strategy_id == "S3_METADATA_STRIP"), None)
    s4_gt1 = next((r for r in all_rows if r.case_id == "GT1" and r.strategy_id == "S4_PARAGRAPH_DENSITY"), None)

    confirmed: list[str] = []
    rejected: list[str] = []
    unknown: list[str] = []
    hypothesis: list[str] = []

    if prod_gt1 and prod_gt1.mechanical_grade == "FAIL":
        confirmed.append("S0_PRODUCTION fails GT1 — infobox/wikidata center (CONFIRMED)")
    if s3_gt1 and s3_gt1.mechanical_grade == "PASS":
        confirmed.append("S3_METADATA_STRIP passes GT1 — metadata strip is sufficient without wiki-only merge")
    if s4_gt1 and s4_gt1.mechanical_grade == "PASS":
        confirmed.append("S4_PARAGRAPH_DENSITY passes GT1 — generic paragraph path works")

    if best == "S6_WIKI_MERGED":
        hypothesis.append("Wikipedia-specific merge may beat generic on some pages")
    else:
        rejected.append("S6_WIKI_MERGED as default — generic strategies match or beat wiki-specific")

    if best == "S3_METADATA_STRIP":
        rejected.append("A4 adopted blindly — S3 chosen by balanced score across GT1-GT6 not Osaka alone")
    elif best == "S4_PARAGRAPH_DENSITY":
        rejected.append("A4 alone — S4 paragraph-density wins balanced scoring")

    unknown.append("Long-tail non-Wikipedia sites with embedded JSON-LD")
    unknown.append("Live Agent E2E after proposed normalize change")

    return {
        "initial_hypothesis": "Metadata strip + content region fixes Osaka without Wikipedia hardcode",
        "alternative_hypotheses": [
            "Wikipedia-only merge required (S6)",
            "Production prestrip sufficient (S8)",
            "Semantic HTML alone sufficient (S5)",
        ],
        "confirmed_facts": confirmed,
        "rejected_hypotheses": rejected,
        "hypotheses": hypothesis,
        "unknowns": unknown,
        "why_best_selected": (
            f"{best} selected by pass count across GT1-GT6 with GT2/GT3 safety filter"
            if best
            else "No candidate passed all safety filters"
        ),
        "why_a4_not_auto_adopted": "S3 is A4-class but compared against S4-S8; best chosen by regression balance",
        "llm_results": llm,
        "regression_summary": scoring,
    }


def run_extraction_normalization_experiment(
    *,
    fetch_live: bool = True,
    llm_enabled: bool = False,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "",
) -> dict[str, Any]:
    specs = golden_case_specs()
    all_rows: list[StrategyGoldenResult] = []
    case_artifacts: dict[str, Any] = {}

    for spec in specs:
        if spec.fixture_html is not None:
            html = spec.fixture_html
            fetch_meta = {"ok": True, "fixture": True}
        elif fetch_live and spec.url:
            html, fetch_meta = fetch_raw_html(spec.url)
        else:
            html, fetch_meta = "", {"ok": False, "skipped": True}

        if not html.strip():
            case_artifacts[spec.case_id] = {"error": "no_html", "fetch_meta": fetch_meta}
            continue

        rows = evaluate_golden_case(spec, html=html, fetch_meta=fetch_meta)
        all_rows.extend(rows)
        case_artifacts[spec.case_id] = {
            "spec": spec.to_dict(),
            "fetch_meta": fetch_meta,
            "strategies": [r.to_dict() for r in rows],
            "before_after": {
                "S0_PRODUCTION": next((r.to_dict() for r in rows if r.strategy_id == "S0_PRODUCTION"), None),
                "best_passing": next(
                    (r.to_dict() for r in rows if r.mechanical_grade == "PASS"),
                    None,
                ),
            },
        }

    scoring = score_strategies(all_rows)
    best = scoring.get("best_overall_balanced") or scoring.get("best_gt1")

    osaka_html, _ = fetch_raw_html(URL_GT1_OSAKA) if fetch_live else ("", {})
    osaka_protos = run_all_strategies(osaka_html, url=URL_GT1_OSAKA, expect="population") if osaka_html else []
    llm = run_llm_utilization_cases(
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
        osaka_results=osaka_protos,
    )

    proposals = build_proposed_changes(scoring, best)
    decision = build_decision_log(scoring=scoring, best=best, all_rows=all_rows, llm=llm)

    gt1_pass = any(r.case_id == "GT1" and r.strategy_id == best and r.mechanical_grade == "PASS" for r in all_rows)
    gt2_pass = any(r.case_id == "GT2" and r.strategy_id == best and r.mechanical_grade == "PASS" for r in all_rows)
    gt3_pass = any(r.case_id == "GT3" and r.strategy_id == best and r.mechanical_grade == "PASS" for r in all_rows)

    if gt1_pass and gt2_pass and gt3_pass:
        overall = "PASS"
    elif gt1_pass and gt2_pass:
        overall = "PARTIAL"
    else:
        overall = "FAIL"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "phase": "extraction_normalization_experiment",
        "production_changes": False,
        "overall": overall,
        "best_candidate": best,
        "confidence": "high" if gt1_pass and gt2_pass and gt3_pass else ("medium" if gt1_pass else "low"),
        "strategy_scoring": scoring,
        "golden_cases": case_artifacts,
        "golden_transactions": [
            {
                "case_id": spec.case_id,
                "url": spec.url,
                "results_summary": {
                    sid: next(
                        (
                            {
                                "grade": r.mechanical_grade,
                                "extraction_status": r.extraction_status,
                                "fact_ready": r.fact_ready,
                                "evidence_presence": r.evidence_presence,
                            }
                            for r in all_rows
                            if r.case_id == spec.case_id and r.strategy_id == sid
                        ),
                        {},
                    )
                    for sid in STRATEGIES
                },
            }
            for spec in specs
        ],
        "llm_utilization": llm,
        "fact_ready_semantics": {
            "changed": False,
            "confirmed": "fact_ready remains text-quality heuristic; evidence_presence is separate experimental field",
            "case3_observed": any(
                r.evidence_presence.get("population") and not r.fact_ready
                for r in all_rows
                if r.case_id == "GT1"
            ),
        },
        "automation": {
            "observable": ["evidence_presence.population", "wikidata_boilerplate", "mechanical_grade"],
            "diagnosable": "EXTRACTION_FAILED when grade FAIL and wikidata_boilerplate",
            "regression_testable": True,
            "auto_repair_candidate": best,
            "loop": "observation -> golden GT1-GT6 -> strategy score -> PROPOSED_CHANGE",
        },
        "proposed_production_changes": proposals,
        "human_review_packet": [p for p in proposals if p.get("human_review_required")],
        "decision_log": decision,
        "stop": True,
    }
