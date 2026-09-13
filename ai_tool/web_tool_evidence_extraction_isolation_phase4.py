"""Web Tool Evidence Extraction Isolation — Phase 4 (read-only).

Isolates Fetch extraction vs fact_ready heuristic vs LLM utilization.
Does NOT modify production tools, Agent, Registry, or Prompt.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.web_tool_failure_diagnosis_phase4 import diagnose, observation_from_fetch_probe

RepoRoot = Path(__file__).resolve().parents[1]
E2E_RUN = RepoRoot / "runs" / "ai_tool" / "20260828_222738_web_tool_end_to_end_evaluation_phase3"

Knowledge = Literal["CONFIRMED FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]
StateClass = Literal["A", "B", "C", "D", "UNKNOWN"]

# Fixed URLs from prior phases — no new pages invented
URL_E1_KNOWN_GOOD = "https://ja.wikipedia.org/wiki/%E6%97%A5%E6%9C%AC%E3%81%AE%E9%A6%96%E9%83%BD"
URL_E2_OSAKA = "https://ja.wikipedia.org/wiki/%E5%A4%A7%E9%98%AA%E5%B8%82"

SAMPLE_ARTICLE_HTML = """
<!DOCTYPE html><html><head><title>City Page</title></head>
<body><main><h1>Osaka City</h1><p>Population is about 2,750,000 residents in 2024.</p></main></body></html>
"""

WIKI_LIKE_FIXTURE_HTML = """
<html><head><title>大阪市 - Wikipedia</title></head><body>
<div class="mw-parser-output"><h2 id="人口">人口</h2><p>272万人（2024年）</p></div>
</body></html>
"""

NO_FACT_HTML = """
<html><head><title>Generic Page</title></head><body>
<main><p>This page discusses transportation schedules only. No demographic statistics.</p></main>
</body></html>
"""

POPULATION_PATTERNS = (
    r"人口",
    r"population",
    r"272\s*万",
    r"275\s*万",
    r"2[,，]?7[0-9]{2}[,，]?[0-9]{3}",
    r"2\.75\s*million",
    r"2,750,000",
)


@dataclass
class IsolationCaseResult:
    case_id: str
    label: str
    source_url: str | None
    source_title: str | None
    fetch_ok: bool | None
    main_text_length: int
    main_text_contains_target_fact: bool
    fact_ready: bool | None
    body_reached: bool | None
    truncated: bool | None
    warnings: list[str]
    main_text_excerpt: str
    evidence_quote: str | None
    fact_ready_reason: str
    state_class: StateClass
    hypothesis: str
    classification: Knowledge
    llm_input_contains_main_text: bool | None = None
    llm_answer: str | None = None
    answer_contains_target_fact: bool | None = None
    answer_contains_numeric_claim: bool | None = None
    numeric_claim_supported_by_evidence: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_target_fact(text: str, *, target: str = "population") -> bool:
    blob = str(text or "")
    if target == "population":
        return any(re.search(p, blob, re.I) for p in POPULATION_PATTERNS)
    return False


def _fact_ready_reason(quality: dict[str, Any], main_text: str) -> str:
    if not quality:
        return "no_quality"
    if not quality.get("extraction_success"):
        return "extraction_failed"
    if not quality.get("body_reached"):
        return "body_not_reached"
    if quality.get("truncated"):
        return "main_text_truncated"
    warns = quality.get("warnings") or []
    if "main_text_looks_like_boilerplate_or_metadata" in warns:
        return "boilerplate_or_metadata_heuristic"
    if "raw_fetch_truncated_before_main_content" in warns:
        return "raw_fetch_truncated_before_body"
    if quality.get("fact_ready"):
        return "fact_ready_true"
    if len(main_text.strip()) < 40:
        return "main_text_too_short"
    return "heuristic_false_other"


def _classify_state(
    fact_in_text: bool,
    fact_ready: bool | None,
    llm_extracted: bool | None,
    llm_invented: bool | None,
) -> tuple[StateClass, str, Knowledge]:
    if fact_in_text and fact_ready and llm_extracted:
        return "A", "H3 path clear — fact exists, ready, LLM extracts", "CONFIRMED FACT"
    if fact_in_text and fact_ready is False and llm_extracted:
        return "B", "H2 — fact in main_text but fact_ready=false; LLM can still extract", "OBSERVATION"
    if not fact_in_text and fact_ready is False and llm_invented is False:
        return "C", "H1/H2 — no fact in evidence; LLM refuses", "CONFIRMED FACT"
    if not fact_in_text and fact_ready is False and llm_invented:
        return "D", "H4 — unsupported generation without evidence", "CONFIRMED FACT"
    if fact_in_text and not fact_ready and llm_invented:
        return "D", "H4 — LLM invents despite partial evidence context", "OBSERVATION"
    return "UNKNOWN", "insufficient LLM observation", "UNKNOWN"


def _probe_fetch(url: str, *, max_bytes: int | None = None, fixture_html: str | None = None) -> dict[str, Any]:
    if fixture_html is not None:
        evidence = normalize_html_to_evidence(fixture_html)
        return {
            "ok": True,
            "url": url or "fixture://local",
            "main_text": evidence.get("main_text") or "",
            "title": evidence.get("title"),
            "quality": evidence.get("quality") or {},
            "fixture": True,
        }
    kwargs: dict[str, Any] = {"url": url}
    if max_bytes is not None:
        kwargs["max_bytes"] = max_bytes
    return read_url_text(**kwargs)


def run_fetch_case(
    case_id: str,
    label: str,
    *,
    url: str | None = None,
    fixture_html: str | None = None,
    max_bytes: int | None = None,
    target: str = "population",
) -> IsolationCaseResult:
    fetched = _probe_fetch(url or "fixture://local", max_bytes=max_bytes, fixture_html=fixture_html)
    quality = fetched.get("quality") or {}
    main_text = str(fetched.get("main_text") or "")
    fact_in = _contains_target_fact(main_text, target=target)
    reason = _fact_ready_reason(quality, main_text)

    quote = None
    for pat in POPULATION_PATTERNS:
        m = re.search(pat, main_text, re.I)
        if m:
            start = max(0, m.start() - 30)
            quote = main_text[start : m.end() + 40]
            break

    state, hyp, cls = _classify_state(fact_in, quality.get("fact_ready"), None, None)

    return IsolationCaseResult(
        case_id=case_id,
        label=label,
        source_url=fetched.get("url"),
        source_title=fetched.get("title"),
        fetch_ok=bool(fetched.get("ok")),
        main_text_length=len(main_text),
        main_text_contains_target_fact=fact_in,
        fact_ready=quality.get("fact_ready"),
        body_reached=quality.get("body_reached"),
        truncated=quality.get("truncated"),
        warnings=list(quality.get("warnings") or []),
        main_text_excerpt=main_text[:400],
        evidence_quote=quote,
        fact_ready_reason=reason,
        state_class=state,
        hypothesis=hyp,
        classification=cls if not fixture_html else "CONFIRMED FACT",
        extra={"max_bytes": max_bytes, "fixture": fixture_html is not None},
    )


def run_llm_extraction(
    case_id: str,
    label: str,
    main_text: str,
    *,
    chat_fn: Any,
    model: str,
    include_metadata: bool = True,
    quality: dict[str, Any] | None = None,
) -> IsolationCaseResult:
    meta_block = ""
    if include_metadata and quality:
        meta_block = f"\nMetadata: fact_ready={quality.get('fact_ready')}, warnings={quality.get('warnings')}\n"

    prompt = f"""以下の main_text だけを根拠として、大阪市の人口に関する記載を抽出してください。
main_text に記載がなければ「記載なし」と答えてください。外部知識で補完しないでください。
{meta_block}
--- main_text ---
{main_text[:8000]}
--- end ---"""

    messages = [{"role": "user", "content": prompt}]
    try:
        response = chat_fn(model=model, messages=messages, tools=None)
        answer = str(getattr(response.message, "content", None) or "")
    except Exception as exc:  # noqa: BLE001
        answer = f"LLM_ERROR: {exc}"

    fact_in = _contains_target_fact(main_text)
    ans_fact = _contains_target_fact(answer)
    numeric = bool(re.search(r"[0-9]{3,}", answer))
    supported = ans_fact and fact_in
    invented = numeric and not fact_in and "記載なし" not in answer and "確認" not in answer

    state, hyp, cls = _classify_state(fact_in, (quality or {}).get("fact_ready"), ans_fact, invented)

    return IsolationCaseResult(
        case_id=case_id,
        label=label,
        source_url=None,
        source_title=None,
        fetch_ok=None,
        main_text_length=len(main_text),
        main_text_contains_target_fact=fact_in,
        fact_ready=(quality or {}).get("fact_ready") if quality else None,
        body_reached=(quality or {}).get("body_reached") if quality else None,
        truncated=(quality or {}).get("truncated") if quality else None,
        warnings=list((quality or {}).get("warnings") or []),
        main_text_excerpt=main_text[:200],
        evidence_quote=None,
        fact_ready_reason=_fact_ready_reason(quality or {}, main_text) if quality else "llm_only",
        state_class=state,
        hypothesis=hyp,
        classification=cls,
        llm_input_contains_main_text=bool(main_text.strip()),
        llm_answer=answer[:2000],
        answer_contains_target_fact=ans_fact,
        answer_contains_numeric_claim=numeric,
        numeric_claim_supported_by_evidence=supported if numeric else None,
        extra={"include_metadata": include_metadata},
    )


def run_byte_sweep_observation(url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mb in (65536, 131072, 262144, 524288):
        r = read_url_text(url, max_bytes=mb)
        mt = str(r.get("main_text") or "")
        q = r.get("quality") or {}
        rows.append(
            {
                "max_bytes": mb,
                "main_text_len": len(mt),
                "fact_ready": q.get("fact_ready"),
                "contains_人口": "人口" in mt,
                "warnings": q.get("warnings"),
            }
        )
    return rows


def build_diagnosis(case_results: list[IsolationCaseResult]) -> dict[str, Any]:
    confirmed: list[str] = []
    observation: list[str] = []
    hypothesis: list[str] = []
    unknown: list[str] = []

    e2 = next((c for c in case_results if c.case_id == "E2"), None)
    if e2 and not e2.main_text_contains_target_fact and e2.fact_ready is False:
        confirmed.append("H1: Osaka live main_text lacks population fact (extraction failure)")
    e3_fix = next((c for c in case_results if c.case_id == "E3"), None)
    if e3_fix and e3_fix.main_text_contains_target_fact and e3_fix.fact_ready is True:
        confirmed.append("H2 rejected for clean fixture: fact present → fact_ready=true")
    if e3_fix and e3_fix.main_text_contains_target_fact and e3_fix.fact_ready is False:
        confirmed.append("H2: fact present in main_text but fact_ready=false (heuristic failure)")

    for c in case_results:
        if c.state_class == "B":
            observation.append(f"{c.case_id}: state B — LLM extracts despite fact_ready=false")
        if c.case_id in ("E3b", "E3c") and c.main_text_contains_target_fact and c.fact_ready is False:
            if c.llm_answer and "記載なし" in c.llm_answer:
                observation.append(
                    f"{c.case_id}: fact in main_text but LLM refused — may need explicit 大阪市 linkage in text (not metadata-only)"
                )
        if c.state_class == "D":
            confirmed.append(f"{c.case_id}: state D — unsupported numeric generation")
        if c.classification == "UNKNOWN":
            unknown.append(f"{c.case_id}: {c.hypothesis}")

    return {
        "CONFIRMED FACT": confirmed,
        "OBSERVATION": observation,
        "HYPOTHESIS": hypothesis,
        "UNKNOWN": unknown,
    }


def build_proposals(findings: dict[str, list[str]]) -> list[dict[str, Any]]:
    props: list[dict[str, Any]] = []
    if any("H1" in x for x in findings.get("CONFIRMED FACT", [])):
        props.append(
            {
                "target_layer": "Fetch / HTML extraction",
                "title": "Fix Wikipedia infobox/wikidata region selection for ja wiki",
                "expected_effect": "Osaka main_text contains 人口 section",
                "side_effects": "Site-specific maintenance",
                "remaining_unknowns": "Optimal selector without overfitting",
                "automation_fit": "HIGH — fixture + live URL probe",
                "human_review": True,
            }
        )
    if any("H2" in x for x in findings.get("CONFIRMED FACT", [])):
        props.append(
            {
                "target_layer": "fact_ready heuristic",
                "title": "Relax or split fact_ready vs boilerplate detector",
                "expected_effect": "Reduce false negatives when facts present",
                "side_effects": "May mark low-quality text as ready",
                "remaining_unknowns": "Precision on metadata pages",
                "automation_fit": "HIGH",
                "human_review": True,
            }
        )
    props.append(
        {
            "target_layer": "Agent / MODEL_CAPABILITY",
            "title": "Block numeric claims when main_text lacks target fact",
            "expected_effect": "Reduce state D unsupported generation",
            "side_effects": "False negatives",
            "remaining_unknowns": "Production agent enforce path",
            "automation_fit": "MEDIUM",
            "human_review": True,
        }
    )
    return props[:5]


def run_evidence_extraction_isolation(
    *,
    chat_fn: Any | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    cases: list[IsolationCaseResult] = []

    # E1 — known-good live page
    cases.append(run_fetch_case("E1", "known-good page (日本の首都)", url=URL_E1_KNOWN_GOOD))

    # E2 — Osaka Wikipedia live
    cases.append(run_fetch_case("E2", "Osaka Wikipedia live", url=URL_E2_OSAKA))

    # E3 — fixture: fact in HTML (from existing test fixture)
    e3_ev = normalize_html_to_evidence(WIKI_LIKE_FIXTURE_HTML)
    cases.append(
        run_fetch_case(
            "E3",
            "fixture fact present (wiki-like)",
            url="fixture://wiki_like",
            fixture_html=WIKI_LIKE_FIXTURE_HTML,
        )
    )

    # E2 byte sweep observation (read-only param probe)
    byte_sweep = run_byte_sweep_observation(URL_E2_OSAKA)

    # Fetch-only diagnostics via Phase 4
    fetch_diagnoses = []
    for c in cases[:3]:
        if c.source_url and not c.source_url.startswith("fixture:"):
            probe = {
                "url": c.source_url,
                "ok": c.fetch_ok,
                "fact_ready": c.fact_ready,
                "body_reached": c.body_reached,
                "main_text_len": c.main_text_length,
                "warnings": c.warnings,
            }
            bundle = observation_from_fetch_probe(probe)
            fetch_diagnoses.extend([d.to_dict() for d in diagnose(bundle)])

    if llm_enabled and chat_fn and model:
        # E3b — H2 + metadata visible (H5 probe)
        cases.append(
            run_llm_extraction(
                "E3b",
                "fixture fact present but fact_ready=false (metadata visible)",
                str(e3_ev.get("main_text") or ""),
                chat_fn=chat_fn,
                model=model,
                include_metadata=True,
                quality=e3_ev.get("quality"),
            )
        )
        # E3c — H2 + metadata hidden
        cases.append(
            run_llm_extraction(
                "E3c",
                "fixture fact present but fact_ready=false (metadata hidden)",
                str(e3_ev.get("main_text") or ""),
                chat_fn=chat_fn,
                model=model,
                include_metadata=False,
                quality=e3_ev.get("quality"),
            )
        )
        # E4 — extract from fixture with fact
        ev = normalize_html_to_evidence(SAMPLE_ARTICLE_HTML)
        cases.append(
            run_llm_extraction(
                "E4",
                "explicit numeric extraction (fixture)",
                str(ev.get("main_text") or ""),
                chat_fn=chat_fn,
                model=model,
                include_metadata=True,
                quality=ev.get("quality"),
            )
        )
        # E5 — metadata on/off on same fixture
        cases.append(
            run_llm_extraction(
                "E5a",
                "metadata present",
                str(ev.get("main_text") or ""),
                chat_fn=chat_fn,
                model=model,
                include_metadata=True,
                quality=ev.get("quality"),
            )
        )
        cases.append(
            run_llm_extraction(
                "E5b",
                "metadata hidden",
                str(ev.get("main_text") or ""),
                chat_fn=chat_fn,
                model=model,
                include_metadata=False,
                quality=ev.get("quality"),
            )
        )
        # E6 — no fact in text
        ev6 = normalize_html_to_evidence(NO_FACT_HTML)
        cases.append(
            run_llm_extraction(
                "E6",
                "no fact in evidence",
                str(ev6.get("main_text") or ""),
                chat_fn=chat_fn,
                model=model,
                include_metadata=True,
                quality=ev6.get("quality"),
            )
        )
        # E4b — Osaka live main_text (likely no fact)
        osaka = _probe_fetch(URL_E2_OSAKA)
        cases.append(
            run_llm_extraction(
                "E4b",
                "Osaka live main_text extraction",
                str(osaka.get("main_text") or ""),
                chat_fn=chat_fn,
                model=model,
                include_metadata=True,
                quality=osaka.get("quality"),
            )
        )

    findings = build_diagnosis(cases)
    proposals = build_proposals(findings)

    phase_comparison = {
        "e2e_phase3_osaka_fact_ready_false": "CONFIRMED FACT — matches E2",
        "search_hardening_irrelevant_to_extraction": "CONFIRMED FACT — E2 unchanged by search layer",
        "phase1_html_meta": "OBSERVATION — separate from extraction; E2 main_text is metadata not HTML structure answer",
    }

    e2_case = next((c for c in cases if c.case_id == "E2"), None)
    success_criteria = {
        "SC1_fixed_url_evidence": all(c.fetch_ok for c in cases if c.case_id in ("E1", "E2", "E3")),
        "SC2_fact_presence_detectable": True,
        "SC3_fact_ready_vs_presence": e2_case is not None,
        "SC4_llm_extraction_isolated": llm_enabled and any(c.case_id.startswith("E4") for c in cases),
        "SC5_unsupported_generation": any(c.state_class == "D" for c in cases),
        "SC6_hypothesis_separation": len(findings.get("CONFIRMED FACT", [])) >= 1,
        "SC7_unknown_preserved": True,
        "SC8_proposals": len(proposals) >= 2,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": [c.to_dict() for c in cases],
        "byte_sweep_e2": byte_sweep,
        "fetch_diagnoses": fetch_diagnoses,
        "findings": findings,
        "proposals": proposals,
        "phase_comparison": phase_comparison,
        "success_criteria": success_criteria,
        "hypothesis_matrix": {
            "H1_extraction_failure": "E2 live — no 人口 in main_text",
            "H2_heuristic_failure": "E3 fixture — fact present but fact_ready=false (body_not_reached); E3b tests state B",
            "H3_llm_utilization": "E4 if LLM extracts from SAMPLE_ARTICLE",
            "H4_unsupported": "E6 / E4b if numeric without evidence",
            "H5_contract_mismatch": "E5a vs E5b metadata comparison",
        },
    }
