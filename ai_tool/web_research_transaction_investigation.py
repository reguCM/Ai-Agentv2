"""Web Research Transaction — Investigation & Wikipedia Extractor Spike.

Read-only investigation harness. Does NOT modify Production, Registry, Agent, or Prompt.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.web_tool_evidence_extraction_isolation_phase4 import (
    POPULATION_PATTERNS,
    URL_E1_KNOWN_GOOD,
    URL_E2_OSAKA,
    _contains_target_fact,
    _fact_ready_reason,
)

RepoRoot = Path(__file__).resolve().parents[1]

Knowledge = Literal["CONFIRMED FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]
ExtractionCase = Literal[
    "case1_extraction_failure",
    "case2_fact_absent_in_html",
    "case3_heuristic_false_negative",
    "case4_llm_utilization",
    "unknown",
]

# Fixed URLs — prior phases
URL_JAPAN_CAPITAL = URL_E1_KNOWN_GOOD
URL_OSAKA = URL_E2_OSAKA
URL_NONEXISTENT_QUERY = "https://ja.wikipedia.org/wiki/ThisPageDoesNotExist_XYZ_404"

CAPITAL_PATTERNS = (r"東京", r"とうきょう", r"Tokyo", r"capital", r"首都")
UNSEARCHABLE_QUERY = "zzzz_nonexistent_entity_12345_population_9999"

_STRIP_TAGS = frozenset(
    {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg"}
)
_METADATA_STRIP_PATTERNS = (
    r"(?is)<table\b[^>]*class=[^>]*infobox[^>]*>.*?</table>",
    r"(?is)<div\b[^>]*class=[^>]*navbox[^>]*>.*?</div>",
    r"(?is)<div\b[^>]*class=[^>]*metadata[^>]*>.*?</div>",
    r"(?is)<div\b[^>]*class=[^>]*mw-wiki-editor[^>]*>.*?</div>",
    r"(?is)<span\b[^>]*typeof=[^>]*>.*?</span>",
)


@dataclass
class ExtractionProbeResult:
    probe_id: str
    label: str
    selector_strategy: str
    main_text_length: int
    body_reached: bool
    fact_ready: bool
    fact_ready_reason: str
    warnings: list[str]
    extraction_method: str
    boilerplate_flag: bool
    population_present: bool
    capital_present: bool
    raw_html_population_present: bool | None
    extraction_case: ExtractionCase
    main_text_excerpt: str
    quality_notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoldenTransaction:
    case_id: str
    intent: str
    query: str
    search_status: str
    selected_source: str | None
    fetch_status: str
    extraction_status: str
    evidence_summary: dict[str, Any]
    failure_state: str | None
    trace: list[dict[str, Any]]
    final_answer_policy: str
    research_result_minimal: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def _strip_noise(html: str) -> str:
    work = html or ""
    for tag in _STRIP_TAGS:
        work = re.sub(rf"(?is)<{tag}\b[^>]*>.*?</{tag}>", " ", work)
    work = re.sub(r"(?is)<!--.*?-->", " ", work)
    return work


def _html_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<br\s*/?>", "\n", fragment)
    text = re.sub(r"(?is)<(?:p|div|li|h[1-6]|tr|td|th|section|blockquote)\b[^>]*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_boilerplate(text: str) -> bool:
    from ai_tool.experimental.read_url.html_normalize import _looks_like_boilerplate_or_metadata

    return _looks_like_boilerplate_or_metadata(text)


def _quality_from_text(main_text: str, *, method: str, body_reached: bool) -> dict[str, Any]:
    warnings: list[str] = []
    extraction_success = bool(main_text.strip())
    truncated = False
    fact_ready = (
        extraction_success
        and len(main_text.strip()) >= 40
        and body_reached
        and not _looks_boilerplate(main_text)
    )
    if not fact_ready and extraction_success and _looks_boilerplate(main_text):
        warnings.append("main_text_looks_like_boilerplate_or_metadata")
    if not fact_ready and extraction_success and not body_reached:
        warnings.append("main_text_present_but_body_region_uncertain")
    return {
        "extraction_success": extraction_success,
        "body_reached": body_reached,
        "truncated": truncated,
        "fact_ready": fact_ready,
        "extraction_method": method,
        "warnings": warnings,
    }


def _extract_region(html: str, pattern: str, *, method: str) -> tuple[str, str, bool]:
    cleaned = _strip_noise(html)
    match = re.search(pattern, cleaned)
    if match:
        segment = match.group(1)
        text = _html_to_text(segment)
        return text, method, True
    body = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", cleaned)
    if body:
        return _html_to_text(body.group(1)), "body_fallback", True
    return _html_to_text(cleaned), "full_document", False


def extract_a1_production(url: str, *, raw_html: str | None = None) -> ExtractionProbeResult:
    """A1 — current read_url_text."""
    if raw_html is None:
        fetched = read_url_text(url)
        main_text = str(fetched.get("main_text") or "")
        quality = fetched.get("quality") or {}
        raw_present = None
    else:
        evidence = normalize_html_to_evidence(raw_html)
        main_text = str(evidence.get("main_text") or "")
        quality = evidence.get("quality") or {}
        raw_present = any(re.search(p, raw_html, re.I) for p in POPULATION_PATTERNS)
    return _probe_from_parts(
        "A1",
        "production read_url_text / normalize_html_to_evidence",
        "production_default_selectors",
        main_text,
        quality,
        raw_html_population_present=raw_present,
    )


def extract_a2_mw_content_text(html: str) -> ExtractionProbeResult:
    """A2 — #mw-content-text centered."""
    text, method, reached = _extract_region(
        html,
        r'(?is)<div\b[^>]*id=["\']mw-content-text["\'][^>]*>(.*?)</div>\s*(?:<div|$)',
        method="mw-content-text",
    )
    quality = _quality_from_text(text, method=method, body_reached=reached)
    return _probe_from_parts(
        "A2",
        "mw-content-text region",
        "#mw-content-text",
        text,
        quality,
        raw_html_population_present=_raw_has_population(html),
    )


def extract_a3_mw_parser_output(html: str) -> ExtractionProbeResult:
    """A3 — mw-parser-output centered."""
    text, method, reached = _extract_region(
        html,
        r'(?is)<div\b[^>]*class=["\'][^"\']*mw-parser-output[^"\']*["\'][^>]*>(.*?)</div>',
        method="mw-parser-output",
    )
    quality = _quality_from_text(text, method=method, body_reached=reached)
    return _probe_from_parts(
        "A3",
        "mw-parser-output region",
        "div.mw-parser-output",
        text,
        quality,
        raw_html_population_present=_raw_has_population(html),
    )


def extract_a4_metadata_stripped(html: str) -> ExtractionProbeResult:
    """A4 — strip infobox/navbox/metadata then mw-content-text."""
    work = html or ""
    for pat in _METADATA_STRIP_PATTERNS:
        work = re.sub(pat, " ", work)
    work = re.sub(r"(?is)\{" + r'"@context"[^}]+\}', " ", work)
    text, method, reached = _extract_region(
        work,
        r'(?is)<div\b[^>]*id=["\']mw-content-text["\'][^>]*>(.*?)</div>\s*(?:<div|$)',
        method="mw-content-text_metadata_stripped",
    )
    quality = _quality_from_text(text, method=method, body_reached=reached)
    return _probe_from_parts(
        "A4",
        "metadata stripped + mw-content-text",
        "mw-content-text minus infobox/navbox/wikidata spans",
        text,
        quality,
        raw_html_population_present=_raw_has_population(html),
    )


def extract_a5_article_density(html: str) -> ExtractionProbeResult:
    """A5 — generic article/main + paragraph density (no Wikipedia id)."""
    cleaned = _strip_noise(html)
    for pat in _METADATA_STRIP_PATTERNS:
        cleaned = re.sub(pat, " ", cleaned)
    candidates: list[tuple[str, str]] = []
    for pat, name in (
        (r"(?is)<article\b[^>]*>(.*?)</article>", "article"),
        (r"(?is)<main\b[^>]*>(.*?)</main>", "main"),
        (r"(?is)<div\b[^>]*role=[\"']main[\"'][^>]*>(.*?)</div>", "role_main"),
    ):
        m = re.search(pat, cleaned)
        if m:
            candidates.append((m.group(1), name))
    if not candidates:
        body = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", cleaned)
        candidates = [(body.group(1), "body")] if body else [(cleaned, "full_document")]

    best_text = ""
    best_method = "none"
    best_score = -1
    for fragment, name in candidates:
        paras = re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", fragment)
        para_text = "\n\n".join(_html_to_text(p) for p in paras if _html_to_text(p))
        score = len(para_text) + 50 * len(paras)
        if score > best_score:
            best_score = score
            best_text = para_text if para_text else _html_to_text(fragment)
            best_method = f"paragraph_density_{name}"
    quality = _quality_from_text(best_text, method=best_method, body_reached=bool(best_text))
    return _probe_from_parts(
        "A5",
        "generic article/main paragraph density",
        "article|main|role=main + <p> aggregation",
        best_text,
        quality,
        raw_html_population_present=_raw_has_population(html),
    )


def _raw_has_population(html: str) -> bool:
    return any(re.search(p, html, re.I) for p in POPULATION_PATTERNS)


def _raw_has_capital(html: str) -> bool:
    return any(re.search(p, html, re.I) for p in CAPITAL_PATTERNS)


def _classify_extraction_case(
    *,
    population_in_main: bool,
    raw_population: bool | None,
    fact_ready: bool,
) -> ExtractionCase:
    if raw_population is False and not population_in_main:
        return "case2_fact_absent_in_html"
    if raw_population and not population_in_main:
        return "case1_extraction_failure"
    if population_in_main and not fact_ready:
        return "case3_heuristic_false_negative"
    return "unknown"


def _probe_from_parts(
    probe_id: str,
    label: str,
    selector: str,
    main_text: str,
    quality: dict[str, Any],
    *,
    raw_html_population_present: bool | None,
) -> ExtractionProbeResult:
    pop = _contains_target_fact(main_text, target="population")
    cap = any(re.search(p, main_text, re.I) for p in CAPITAL_PATTERNS)
    reason = _fact_ready_reason(quality, main_text)
    ext_case = _classify_extraction_case(
        population_in_main=pop,
        raw_population=raw_html_population_present,
        fact_ready=bool(quality.get("fact_ready")),
    )
    notes = []
    if ext_case == "case1_extraction_failure":
        notes.append("HTML contains fact but extractor missed it")
    elif ext_case == "case2_fact_absent_in_html":
        notes.append("Fact not found in raw HTML either")
    elif ext_case == "case3_heuristic_false_negative":
        notes.append("Text has fact but fact_ready=false")
    return ExtractionProbeResult(
        probe_id=probe_id,
        label=label,
        selector_strategy=selector,
        main_text_length=len(main_text),
        body_reached=bool(quality.get("body_reached")),
        fact_ready=bool(quality.get("fact_ready")),
        fact_ready_reason=reason,
        warnings=list(quality.get("warnings") or []),
        extraction_method=str(quality.get("extraction_method") or ""),
        boilerplate_flag=_looks_boilerplate(main_text),
        population_present=pop,
        capital_present=cap,
        raw_html_population_present=raw_html_population_present,
        extraction_case=ext_case,
        main_text_excerpt=main_text[:500],
        quality_notes="; ".join(notes) if notes else "ok_or_mixed",
    )


def run_extraction_spike(*, fetch_live: bool = True) -> dict[str, Any]:
    """Investigation A — compare extraction strategies on fixed Wikipedia ja URLs."""
    results: dict[str, Any] = {"osaka": {}, "capital": {}, "raw_analysis": {}}

    osaka_html = ""
    capital_html = ""
    if fetch_live:
        osaka_fetch = read_url_text(URL_OSAKA)
        capital_fetch = read_url_text(URL_JAPAN_CAPITAL)
        osaka_html = _get_raw_html(URL_OSAKA, osaka_fetch)
        capital_html = _get_raw_html(URL_JAPAN_CAPITAL, capital_fetch)
        results["fetch_meta"] = {
            "osaka_ok": osaka_fetch.get("ok"),
            "capital_ok": capital_fetch.get("ok"),
            "osaka_bytes": osaka_fetch.get("size_bytes"),
            "capital_bytes": capital_fetch.get("size_bytes"),
        }

    if osaka_html:
        results["raw_analysis"]["osaka"] = {
            "html_length": len(osaka_html),
            "raw_population_patterns": _raw_has_population(osaka_html),
            "raw_人口_count": osaka_html.count("人口"),
            "raw_infobox_present": bool(re.search(r"infobox", osaka_html, re.I)),
            "raw_mw_content_text_present": "mw-content-text" in osaka_html,
        }
        results["osaka"]["probes"] = [
            extract_a1_production(URL_OSAKA, raw_html=osaka_html).to_dict(),
            extract_a2_mw_content_text(osaka_html).to_dict(),
            extract_a3_mw_parser_output(osaka_html).to_dict(),
            extract_a4_metadata_stripped(osaka_html).to_dict(),
            extract_a5_article_density(osaka_html).to_dict(),
        ]
        results["osaka"]["a1_live_tool"] = extract_a1_production(URL_OSAKA).to_dict()

    if capital_html:
        results["raw_analysis"]["capital"] = {
            "html_length": len(capital_html),
            "raw_capital_patterns": _raw_has_capital(capital_html),
            "raw_東京_count": capital_html.count("東京"),
        }
        cap_probes = [
            extract_a1_production(URL_JAPAN_CAPITAL, raw_html=capital_html),
            extract_a2_mw_content_text(capital_html),
            extract_a3_mw_parser_output(capital_html),
            extract_a4_metadata_stripped(capital_html),
            extract_a5_article_density(capital_html),
        ]
        results["capital"]["probes"] = [p.to_dict() for p in cap_probes]

    results["general_principle"] = _derive_extraction_principles(results)
    return results


def _get_raw_html(url: str, fetched: dict[str, Any]) -> str:
    """Re-fetch raw HTML for offline probe comparison (same URL, read-only)."""
    from ai_tool.experimental.read_url.config import DEFAULT_LIMITS
    from ai_tool.experimental.read_url.http_client import default_http_get
    from ai_tool.experimental.read_url.ssrf import validate_url

    normalized, err = validate_url(url)
    if err or not normalized:
        return ""
    try:
        _status, _headers, body, _final = default_http_get(
            normalized,
            timeout_seconds=DEFAULT_LIMITS.timeout_seconds,
            max_bytes=524288,
            max_redirects=DEFAULT_LIMITS.max_redirects,
        )
        return body.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _derive_extraction_principles(results: dict[str, Any]) -> dict[str, Any]:
    osaka_probes = (results.get("osaka") or {}).get("probes") or []
    if not osaka_probes:
        return {"status": "no_data"}
    best_pop = max(osaka_probes, key=lambda p: (p.get("population_present"), p.get("main_text_length")))
    prod = next((p for p in osaka_probes if p.get("probe_id") == "A1"), {})
    principles: list[str] = []
    if best_pop.get("probe_id") != "A1" and best_pop.get("population_present"):
        principles.append(
            f"Production A1 misses population; {best_pop.get('probe_id')} succeeds — region/metadata selection not ranking"
        )
    if prod.get("boilerplate_flag") and not prod.get("population_present"):
        principles.append("Boilerplate/metadata heuristic triggers without article body — general sites with JSON-LD risk same")
    if any(p.get("probe_id") == "A4" and p.get("population_present") for p in osaka_probes):
        principles.append("Metadata stripping before content region is a general principle (not Wikipedia-only hardcode)")
    if any(p.get("probe_id") == "A5" and p.get("population_present") for p in osaka_probes):
        principles.append("Paragraph-density article extraction works without Wikipedia ids")
    raw = (results.get("raw_analysis") or {}).get("osaka") or {}
    if raw.get("raw_population_patterns") and not prod.get("population_present"):
        principles.append("CONFIRMED case1: fact exists in HTML, production extraction fails")
    elif not raw.get("raw_population_patterns"):
        principles.append("Case2 candidate: population not in raw HTML — extraction failure misdiagnosed")
    return {
        "best_probe_for_population": best_pop.get("probe_id"),
        "production_probe": prod.get("probe_id"),
        "principles": principles,
    }


def compare_orchestration_models() -> dict[str, Any]:
    """Investigation B — RTT necessity comparison."""
    models = {
        "B1_current": {
            "name": "Current — LLM drives Search/Fetch",
            "orchestration_guarantee": "low",
            "failure_detection": "partial_post_hoc_web_status",
            "evidence_traceability": "low",
            "llm_freedom": "high",
            "latency": "low_amortized",
            "implementation_complexity": "low",
            "testability": "low_fragmented_paths",
            "automation_compatibility": "medium",
            "self_repair": "low",
            "human_intervention_reduction": "low",
        },
        "B2_policy": {
            "name": "Agent policy — force Search then Fetch",
            "orchestration_guarantee": "medium",
            "failure_detection": "medium",
            "evidence_traceability": "medium",
            "llm_freedom": "medium",
            "latency": "medium",
            "implementation_complexity": "medium",
            "testability": "medium",
            "automation_compatibility": "medium",
            "self_repair": "medium",
            "human_intervention_reduction": "medium",
        },
        "B3_rtt": {
            "name": "RTT — single Research Transaction abstraction",
            "orchestration_guarantee": "high",
            "failure_detection": "high",
            "evidence_traceability": "high",
            "llm_freedom": "low_for_tools_high_for_synthesis",
            "latency": "medium_higher",
            "implementation_complexity": "high",
            "testability": "high",
            "automation_compatibility": "high",
            "self_repair": "high",
            "human_intervention_reduction": "high",
        },
        "B4_hybrid": {
            "name": "Hybrid — deterministic fetch+extract; LLM search/select only",
            "orchestration_guarantee": "medium_high",
            "failure_detection": "high_for_fetch_extract",
            "evidence_traceability": "medium_high",
            "llm_freedom": "medium",
            "latency": "medium",
            "implementation_complexity": "medium",
            "testability": "high",
            "automation_compatibility": "high",
            "self_repair": "medium",
            "human_intervention_reduction": "medium_high",
        },
        "B5_alternative": {
            "name": "Extraction-first — fix read_url_text; keep LLM orchestration",
            "orchestration_guarantee": "low",
            "failure_detection": "partial",
            "evidence_traceability": "medium_after_fix",
            "llm_freedom": "high",
            "latency": "low",
            "implementation_complexity": "low_medium",
            "testability": "medium",
            "automation_compatibility": "medium",
            "self_repair": "low",
            "human_intervention_reduction": "low_medium",
        },
    }
    return {
        "models": models,
        "independent_assessment": {
            "rtt_necessary_if": [
                "eval/production path gap persists without single transaction artifact",
                "orchestration failures (skip fetch, empty search answer) remain after extraction fix",
            ],
            "rtt_unnecessary_if": [
                "extraction fix alone achieves E2E SUCCESS with B2 policy in agent.py",
                "ResearchResult adds schema weight without closing failure classes",
            ],
            "cursor_revised_stance": (
                "RTT is valuable as observability/unification layer, not necessarily as first production change. "
                "Extraction fix (B5/B4 partial) may suffice for Osaka; RTT justified for eval parity."
            ),
        },
    }


def research_result_schema_spike() -> dict[str, Any]:
    """Investigation C — minimal ResearchResult validity."""
    minimal = {
        "query": "user intent string",
        "selected_source": "url or null",
        "status": "SUCCESS | SEARCH_FAILED | FETCH_FAILED | EXTRACTION_FAILED | NO_EVIDENCE",
        "evidence": [{"url": "", "main_text_excerpt": "", "fact_ready": False}],
        "trace": [{"step": "search", "ok": True, "detail": ""}],
    }
    extended = {
        **minimal,
        "sources": [],
        "claims": [],
        "confidence": 0.0,
        "timestamps": {},
        "failure_status": {},
    }
    return {
        "minimal_schema": minimal,
        "extended_schema": extended,
        "assessment": {
            "minimal_sufficient_for": [
                "golden transaction regression",
                "failure diagnosis input",
                "before/after extraction comparison",
            ],
            "extended_risk": "Over-design before extraction fix validated; claims/confidence need SCS layer",
            "verdict": "minimal_schema_sufficient_for_investigation_phase",
            "production_schema_decision": "deferred",
        },
    }


def _minimal_research_result(
    *,
    query: str,
    selected_source: str | None,
    status: str,
    main_text: str,
    fact_ready: bool,
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "query": query,
        "selected_source": selected_source,
        "status": status,
        "evidence": [
            {
                "url": selected_source,
                "main_text_length": len(main_text),
                "fact_ready": fact_ready,
                "population_present": _contains_target_fact(main_text),
            }
        ],
        "trace": trace,
    }


def build_golden_transactions(*, extraction_results: dict[str, Any]) -> list[dict[str, Any]]:
    """Investigation D — fixed representative cases."""
    transactions: list[GoldenTransaction] = []

    osaka_probes = (extraction_results.get("osaka") or {}).get("probes") or []
    best = max(osaka_probes, key=lambda p: (p.get("population_present"), p.get("fact_ready")), default={})
    prod = next((p for p in osaka_probes if p.get("probe_id") == "A1"), {})

    trace_osaka = [
        {"step": "search", "ok": True, "detail": "fixed URL skip search — isolation"},
        {"step": "fetch", "ok": True, "url": URL_OSAKA},
        {"step": "extract_A1", "ok": prod.get("population_present"), "fact_ready": prod.get("fact_ready")},
        {"step": "extract_best", "probe": best.get("probe_id"), "population": best.get("population_present")},
    ]
    status = "EXTRACTION_FAILED" if not prod.get("population_present") else "SUCCESS"
    transactions.append(
        GoldenTransaction(
            case_id="GT1",
            intent="大阪市の人口",
            query="大阪市の人口",
            search_status="SKIPPED_FIXED_URL",
            selected_source=URL_OSAKA,
            fetch_status="OK",
            extraction_status=status,
            evidence_summary={
                "A1_population": prod.get("population_present"),
                "best_probe": best.get("probe_id"),
                "best_population": best.get("population_present"),
            },
            failure_state="EXTRACTION_FAILED" if status != "SUCCESS" else None,
            trace=trace_osaka,
            final_answer_policy="block_numeric_if_extraction_failed",
            research_result_minimal=_minimal_research_result(
                query="大阪市の人口",
                selected_source=URL_OSAKA,
                status=status,
                main_text=prod.get("main_text_excerpt") or "",
                fact_ready=bool(prod.get("fact_ready")),
                trace=trace_osaka,
            ),
        )
    )

    cap_probes = (extraction_results.get("capital") or {}).get("probes") or []
    cap_a1 = next((p for p in cap_probes if p.get("probe_id") == "A1"), {})
    trace_cap = [
        {"step": "search", "ok": True, "detail": "fixed URL"},
        {"step": "fetch", "ok": True, "url": URL_JAPAN_CAPITAL},
        {"step": "extract", "capital_present": cap_a1.get("capital_present")},
    ]
    cap_status = "SUCCESS" if cap_a1.get("capital_present") else "EXTRACTION_FAILED"
    transactions.append(
        GoldenTransaction(
            case_id="GT2",
            intent="日本の首都",
            query="日本の首都はどこですか",
            search_status="SKIPPED_FIXED_URL",
            selected_source=URL_JAPAN_CAPITAL,
            fetch_status="OK",
            extraction_status=cap_status,
            evidence_summary={"capital_in_main_text": cap_a1.get("capital_present")},
            failure_state=None if cap_status == "SUCCESS" else "EXTRACTION_FAILED",
            trace=trace_cap,
            final_answer_policy="allow_if_capital_in_evidence",
            research_result_minimal=_minimal_research_result(
                query="日本の首都",
                selected_source=URL_JAPAN_CAPITAL,
                status=cap_status,
                main_text=cap_a1.get("main_text_excerpt") or "",
                fact_ready=bool(cap_a1.get("fact_ready")),
                trace=trace_cap,
            ),
        )
    )

    trace_unsearchable = [
        {"step": "search", "ok": False, "detail": "mock empty hits", "query": UNSEARCHABLE_QUERY},
    ]
    transactions.append(
        GoldenTransaction(
            case_id="GT3",
            intent="存在しない情報",
            query=UNSEARCHABLE_QUERY,
            search_status="SEARCH_FAILED",
            selected_source=None,
            fetch_status="SKIPPED",
            extraction_status="SKIPPED",
            evidence_summary={"hits": 0},
            failure_state="SEARCH_FAILED",
            trace=trace_unsearchable,
            final_answer_policy="no_numeric_claims",
            research_result_minimal=_minimal_research_result(
                query=UNSEARCHABLE_QUERY,
                selected_source=None,
                status="SEARCH_FAILED",
                main_text="",
                fact_ready=False,
                trace=trace_unsearchable,
            ),
        )
    )

    return [t.to_dict() for t in transactions]


def document_path_boundaries() -> dict[str, Any]:
    """Investigation — Production vs Evaluation paths."""
    return {
        "paths": {
            "production_agent_subprocess": {
                "entry": "agent.py",
                "web_session_tracker": True,
                "enrich_web_evidence": True,
                "apply_web_answer_boundary": True,
                "web_status_stdout": True,
                "llm_tool_loop": True,
            },
            "production_mirror": {
                "entry": "production_agent_web_loop.py",
                "web_session_tracker": True,
                "enrich_web_evidence": True,
                "apply_web_answer_boundary": True,
                "llm_tool_loop": True,
                "note": "Same policy as agent.py; injectable search/fetch fns",
            },
            "tool_only_eval": {
                "entry": "execute_registry_tool (gpu_process_e2e)",
                "web_session_tracker": False,
                "apply_web_answer_boundary": False,
                "enrich_partial": True,
                "note": "Overstates hallucination vs production",
            },
            "isolation_harness": {
                "entry": "web_tool_*_phase*.py",
                "web_session_tracker": False,
                "direct_read_url_text": True,
            },
        },
        "recommended_canonical_eval_path": "production_mirror with injectable fixtures for search/fetch",
        "rationale": [
            "Matches agent.py enforcement without subprocess env fragility",
            "Supports golden ResearchResult injection for regression",
            "Tool-only path remains as lower-bound diagnostic only",
        ],
    }


def run_llm_architecture_boundary(
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "",
    llm_enabled: bool = False,
    extraction_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Investigation — LLM vs architecture split."""
    from ai_tool.web_tool_evidence_extraction_isolation_phase4 import run_llm_extraction

    rows: list[dict[str, Any]] = []
    osaka_probes = ((extraction_results or {}).get("osaka") or {}).get("probes") or []
    a1 = next((p for p in osaka_probes if p.get("probe_id") == "A1"), {})
    best = max(osaka_probes, key=lambda p: (p.get("population_present"), p.get("main_text_length")), default={})

    deterministic = {
        "path": "deterministic_extraction_only",
        "A1_population_extracted": a1.get("population_present"),
        "best_probe_population": best.get("population_present"),
        "layer": "architecture",
    }
    rows.append(deterministic)

    if llm_enabled and chat_fn and a1.get("main_text_excerpt"):
        quality = {
            "fact_ready": a1.get("fact_ready"),
            "warnings": a1.get("warnings"),
            "body_reached": a1.get("body_reached"),
        }
        llm_a1 = run_llm_extraction(
            "LLM-A1",
            "osaka A1 main_text",
            a1.get("main_text_excerpt") or "",
            chat_fn=chat_fn,
            model=model,
            quality=quality,
        )
        rows.append(
            {
                "path": "qwen3_8b_on_A1_evidence",
                "model": model,
                "answer_has_population": llm_a1.answer_contains_target_fact,
                "invented_numeric": llm_a1.numeric_claim_supported_by_evidence is False,
                "state_class": llm_a1.state_class,
                "layer": "llm_utilization" if a1.get("population_present") else "blocked_by_architecture",
            }
        )
        if best.get("main_text_excerpt") and best.get("probe_id") != "A1":
            llm_best = run_llm_extraction(
                "LLM-BEST",
                f"osaka {best.get('probe_id')} main_text",
                best.get("main_text_excerpt") or "",
                chat_fn=chat_fn,
                model=model,
                quality={"fact_ready": best.get("fact_ready"), "warnings": best.get("warnings")},
            )
            rows.append(
                {
                    "path": f"qwen3_8b_on_{best.get('probe_id')}_evidence",
                    "answer_has_population": llm_best.answer_contains_target_fact,
                    "state_class": llm_best.state_class,
                    "layer": "llm_utilization",
                }
            )
    else:
        rows.append({"path": "llm", "status": "SKIPPED", "reason": "ollama unavailable or disabled"})

    architecture_failures = sum(
        1 for r in rows if r.get("layer") == "architecture" and not r.get("A1_population_extracted")
    )
    return {
        "comparisons": rows,
        "quantification": {
            "architecture_blocks_before_llm": architecture_failures > 0,
            "note": "If A1 lacks population but BEST has it, failure is architecture not LLM",
        },
        "unknowns": [
            "Agent-path tool skip rate not measured this run",
            "Empty-search hallucination requires mirror E2E not re-run here",
        ],
    }


def compare_architecture_options(extraction_results: dict[str, Any]) -> dict[str, Any]:
    """≥3 architecture options with post-investigation assessment."""
    osaka = (extraction_results.get("osaka") or {}).get("probes") or []
    a4_wins = any(p.get("probe_id") == "A4" and p.get("population_present") for p in osaka)
    a2_wins = any(p.get("probe_id") == "A2" and p.get("population_present") for p in osaka)
    extraction_fixable = a4_wins or a2_wins

    options = {
        "OPT1_extraction_policy_hybrid": {
            "name": "Extraction fix + Agent policy (no RTT)",
            "description": "Improve normalize path (metadata strip + content region); B2 agent gates",
            "solve_if": extraction_fixable,
            "rejects_rtt": True,
            "cursor_independent": True,
        },
        "OPT2_rtt_unified": {
            "name": "Full RTT with ResearchResult",
            "description": "Single web_research tool; LLM synthesis only",
            "solve_if": "always_for_orchestration",
            "rejects_rtt": False,
            "cursor_independent": False,
            "note": "Prior phase proposal — re-evaluated",
        },
        "OPT3_scs_first": {
            "name": "SCS before RTT",
            "description": "Structured claims from fixed extraction; defer transaction wrapper",
            "solve_if": extraction_fixable,
            "rejects_rtt": True,
            "cursor_independent": True,
        },
        "OPT4_status_quo_incremental": {
            "name": "web_status/boundary only",
            "description": "Continue current architecture",
            "solve_if": False,
            "rejected": True,
        },
    }
    return {
        "options": options,
        "extraction_fixable_evidence": extraction_fixable,
        "best_extraction_probe": max(osaka, key=lambda p: p.get("population_present"), default={}).get("probe_id"),
    }


def build_recommendation(
    extraction: dict[str, Any],
    orchestration: dict[str, Any],
    arch_options: dict[str, Any],
) -> dict[str, Any]:
    """Independent recommendation — may contradict prior RTT+SEG."""
    principles = (extraction.get("general_principle") or {}).get("principles") or []
    fixable = arch_options.get("extraction_fixable_evidence", False)
    best_probe = arch_options.get("best_extraction_probe")

    if fixable:
        rec = {
            "selected": "OPT1_extraction_policy_hybrid",
            "not_selected": ["OPT2_rtt_unified_as_first_move", "OPT4_status_quo"],
            "why": (
                f"Investigation shows population extractable via {best_probe} without Wikipedia-only hardcode. "
                "First production change should be extraction normalization (metadata strip + content region), "
                "plus Agent policy (mandatory fetch when search hits). RTT remains valuable for eval unification "
                "but is not prerequisite for Osaka SUCCESS."
            ),
            "contradicts_prior_phase": True,
            "prior_phase_recommended": "RTT+SEG phased",
            "human_review_required": [
                "Production html_normalize change scope",
                "Whether Agent policy gates belong in agent.py vs prompt",
            ],
        }
    else:
        rec = {
            "selected": "defer_additional_investigation",
            "why": "Extraction spike did not demonstrate fixable population extraction — root cause unclear",
            "human_review_required": ["Raw HTML fact location analysis"],
        }
    rec["principles_observed"] = principles
    rec["orchestration_note"] = orchestration.get("independent_assessment", {}).get("cursor_revised_stance")
    return rec


def run_investigation(
    *,
    fetch_live: bool = True,
    llm_enabled: bool = False,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "",
) -> dict[str, Any]:
    """Run full investigation suite."""
    extraction = run_extraction_spike(fetch_live=fetch_live)
    orchestration = compare_orchestration_models()
    schema = research_result_schema_spike()
    golden = build_golden_transactions(extraction_results=extraction)
    paths = document_path_boundaries()
    llm_boundary = run_llm_architecture_boundary(
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
        extraction_results=extraction,
    )
    arch_options = compare_architecture_options(extraction)
    recommendation = build_recommendation(extraction, orchestration, arch_options)

    findings_independent = [
        "Extraction spike re-evaluates Osaka without assuming prior RTT+SEG",
        recommendation.get("why", ""),
        orchestration.get("independent_assessment", {}).get("cursor_revised_stance", ""),
    ]
    findings_inherited = [
        "Osaka URL and Phase4 isolation methodology",
        "Eval/production path gap from Live E2E",
        "fact_ready heuristic semantics",
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "phase": "web_research_transaction_investigation",
        "production_changes": False,
        "investigation_a_extraction": extraction,
        "investigation_b_orchestration": orchestration,
        "investigation_c_schema": schema,
        "investigation_d_golden_transactions": golden,
        "investigation_paths": paths,
        "investigation_llm_boundary": llm_boundary,
        "architecture_options": arch_options,
        "recommendation": recommendation,
        "cursor_independent_findings": findings_independent,
        "findings_inherited_from_prior_phases": findings_inherited,
        "unknowns": [
            "Live search backend stability for E2E",
            "Agent tool-skip rate on production subprocess",
            "SCS structured output reliability on qwen3_8b",
            "Generalization of A4 beyond Wikipedia ja",
        ],
        "human_review_packet": recommendation.get("human_review_required", []),
        "next_phase_proposal": (
            "Extraction Normalization Human Review — prototype A4 logic in experimental module only, "
            "golden transaction regression, then Agent policy spike (no RTT yet)"
            if arch_options.get("extraction_fixable_evidence")
            else "Extended HTML forensics on Osaka page"
        ),
        "stop": True,
    }
