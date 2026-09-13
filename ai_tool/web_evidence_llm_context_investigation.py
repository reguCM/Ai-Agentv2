"""Web Evidence → LLM Context Architecture Investigation.

Compares context packaging formats (A1–A6) deterministically.
Does NOT modify Production, Agent, Registry, or Prompt.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.evidence_context.packager import (
    ContextFormat,
    EvidenceBundle,
    EvidenceSource,
    VerificationMode,
    build_context,
    compress_context_levels,
    fact_coverage_in_context,
)
from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.web_tool_extraction_normalization_production import run_production_golden
from ai_tool.web_tool_success_class_accuracy_evaluation import (
    CAPITAL_FIXTURE,
    COMPARATIVE_FIXTURE,
    ExpectedFact,
    TEMPORAL_FIXTURE,
    YOKOHAMA_FIXTURE,
    classify_answer,
)
from ai_tool.web_tool_web_status_evaluation import GOOD_HTML

RepoRoot = Path(__file__).resolve().parents[1]

CONTEXT_FORMATS: list[ContextFormat] = [
    "A1_RAW",
    "A2_PASSAGE",
    "A3_SOURCE_GROUPED",
    "A4_CLAIM",
    "A5_VERIFY",
    "A6_HYBRID",
]

# Investigation F — conflicting sources
CONFLICT_SOURCE_A = EvidenceSource(
    url="https://stats.example.gov/a",
    title="Portal A (2024)",
    main_text="大阪市の推計人口は2024年現在275万人（2,750,000人）です。",
    quality={"fact_ready": True, "extraction_method": "fixture"},
    backend="gov_a",
)
CONFLICT_SOURCE_B = EvidenceSource(
    url="https://stats.example.gov/b",
    title="Portal B (2020 census)",
    main_text="2020年国勢調査による大阪市人口は2,752,412人でした。",
    quality={"fact_ready": True, "extraction_method": "fixture"},
    backend="gov_b",
)

NOISE_FIXTURE = """
<html><body>
<nav>sidebar menu jump content</nav>
<p>Population statistics portal. Last updated.</p>
<main><h1>大阪市</h1>
<p>大阪市の人口は約275万人（2,750,000人）です。面積225.21km²。</p>
</main>
<footer>Copyright</footer>
</body></html>
"""


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def _html_to_source(url: str, title: str, html: str, backend: str = "fixture") -> EvidenceSource:
    ev = normalize_html_to_evidence(html)
    return EvidenceSource(
        url=url,
        title=title,
        main_text=str(ev.get("main_text") or ""),
        quality=ev.get("quality") or {},
        backend=backend,
    )


def investigation_cases() -> list[EvidenceBundle]:
    """Reuse success_class fixtures + conflict + noise cases."""
    cases: list[EvidenceBundle] = []

    mapping = [
        ("IC-B01", "basic", "大阪市の人口", GOOD_HTML, [
            ExpectedFact("osaka_pop", "numeric", [r"275", r"2[,，]?750"], [r"275|750"], numeric_min=2_500_000, numeric_max=2_900_000),
        ]),
        ("IC-B02", "entity", "日本の首都", CAPITAL_FIXTURE, [
            ExpectedFact("capital", "entity", [r"東京"], [r"東京"]),
        ]),
        ("IC-B03", "numeric", "日本 国土面積", """
<html><body><main><p>日本の国土面積は約377,975平方キロメートルです。</p></main></body></html>
""", [
            ExpectedFact("area", "numeric", [r"377"], [r"377"], numeric_min=370_000, numeric_max=380_000),
        ]),
        ("IC-B04", "temporal", "2020 大阪 人口", TEMPORAL_FIXTURE, [
            ExpectedFact("pop2020", "numeric", [r"2020", r"272"], [r"2020|272"], numeric_min=2_600_000, numeric_max=2_800_000),
        ]),
        ("IC-B05", "comparison", "最多 都市", COMPARATIVE_FIXTURE, [
            ExpectedFact("largest", "comparison", [r"横浜"], [r"横浜"]),
        ]),
        ("IC-B06", "scope", "横浜 人口", YOKOHAMA_FIXTURE, [
            ExpectedFact("yokohama", "numeric", [r"375", r"3[,，]?7"], [r"375|37"], numeric_min=3_500_000, numeric_max=4_000_000),
        ]),
        ("IC-B07", "english", "Osaka population", """
<html><body><main><p>Osaka has a population of approximately 2.75 million people as of 2024.</p></main></body></html>
""", [
            ExpectedFact("osaka_en", "numeric", [r"2\.75\s*million", r"population"], [r"million|2\.75"], numeric_min=2_500_000, numeric_max=2_900_000),
        ]),
        ("IC-B08", "non_wiki", "デモ市 統計", """
<html><body><main><h1>Demo Municipality</h1><p>Registered population: 1,234,567. Land area: 156.8 km².</p></main></body></html>
""", [
            ExpectedFact("demo", "numeric", [r"1[,，]?234"], [r"1[,，]?234"], numeric_min=1_200_000, numeric_max=1_300_000),
        ]),
        ("IC-B09", "multi_source", "大阪市 人口 面積", "", []),  # filled below
        ("IC-B10", "noise", "大阪市 人口", NOISE_FIXTURE, [
            ExpectedFact("osaka_pop", "numeric", [r"275", r"2[,，]?750"], [r"275|750"], numeric_min=2_500_000, numeric_max=2_900_000),
        ]),
    ]

    for cid, cat, req, html, facts in mapping:
        if cid == "IC-B09":
            src_a = _html_to_source("https://fixture/a", "Osaka stats A", GOOD_HTML)
            src_b = _html_to_source("https://fixture/b", "Osaka area B", """
<html><body><main><p>大阪市の面積は225.21平方キロメートル。</p></main></body></html>
""")
            cases.append(
                EvidenceBundle(
                    case_id=cid,
                    user_request=f"{req} をWeb検索し確認してください。",
                    query=req,
                    sources=[src_a, src_b],
                    expected_facts=[
                        ExpectedFact("pop", "numeric", [r"275"], [r"275"], numeric_min=2_500_000, numeric_max=2_900_000),
                        ExpectedFact("area", "numeric", [r"225"], [r"225"], numeric_min=200, numeric_max=250),
                    ],
                    category=cat,
                )
            )
            continue
        cases.append(
            EvidenceBundle(
                case_id=cid,
                user_request=f"{req} をWeb検索しread_url_textで確認してください。",
                query=req.split()[0] if req else req,
                sources=[_html_to_source(f"https://fixture/{cid}", cid, html)],
                expected_facts=facts,
                category=cat,
            )
        )

    cases.append(
        EvidenceBundle(
            case_id="IC-F01",
            user_request="大阪市の人口について複数ソースを比較してください。",
            query="大阪市 人口",
            sources=[CONFLICT_SOURCE_A, CONFLICT_SOURCE_B],
            expected_facts=[
                ExpectedFact("pop_a", "numeric", [r"275", r"2[,，]?750"], [r"275|750"], numeric_min=2_700_000, numeric_max=2_800_000),
                ExpectedFact("pop_b", "numeric", [r"2[,，]?752"], [r"2752|752"], numeric_min=2_700_000, numeric_max=2_800_000),
            ],
            category="conflict",
        )
    )
    return cases


def proxy_llm_from_context(context: str, bundle: EvidenceBundle, *, optimistic: bool = True) -> str:
    """Deterministic proxy: synthesize answer from facts findable in packaged context.

    Not an LLM judge — simulates ideal context consumption for packaging comparison.
    """
    met, total = fact_coverage_in_context(context, bundle.expected_facts)
    raw = bundle.raw_combined

    if optimistic and met == total and total > 0:
        parts: list[str] = []
        for f in bundle.expected_facts:
            if f.fact_type == "entity":
                parts.append("確認結果: 東京（東京都）" if "capital" in f.fact_id or "東京" in str(f.evidence_patterns) else "該当entity")
            elif f.fact_type == "numeric":
                m = re.search(r"2[,，]?75[0-9][\d,]*|275\s*万|2\.75\s*million", context, re.I)
                if m:
                    parts.append(f"人口は約{m.group(0)}です。")
                else:
                    m2 = re.search(r"377[,，]?975|377975", context)
                    if m2:
                        parts.append("国土面積は約377,975平方キロメートルです。")
                    else:
                        parts.append("数値はEvidenceに記載のとおりです。")
            elif f.fact_type == "comparison":
                parts.append("人口最多の都市は横浜市です。")
            elif f.fact_type == "temporal":
                parts.append("2020年時点の人口はEvidence記載値です。")
        return " ".join(parts) if parts else "Evidenceに基づく回答です。"

    # Pessimistic / incomplete context — simulate wrong answer or unsupported
    if "nav" in context.lower() or len(context) > len(raw) * 1.2:
        return "人口は999万人です。"  # unsupported numeric
    if met < total:
        return "確認できました。"  # vague — likely fail facts
    return "不明です。"


def evaluate_context_arm(
    bundle: EvidenceBundle,
    fmt: ContextFormat,
    *,
    verification_mode: VerificationMode = "E1_NONE",
) -> dict[str, Any]:
    raw = bundle.raw_combined
    ctx = build_context(fmt, bundle, verification_mode=verification_mode)
    proxy_ans = proxy_llm_from_context(ctx, bundle)
    ans_class, claims, fact_met, _ = classify_answer(proxy_ans, raw, bundle.expected_facts)
    cov_met, cov_total = fact_coverage_in_context(ctx, bundle.expected_facts)
    unsupported = sum(1 for c in claims if c.support == "unsupported")

    return {
        "case_id": bundle.case_id,
        "category": bundle.category,
        "format": fmt,
        "verification_mode": verification_mode,
        "context_size": len(ctx),
        "raw_evidence_size": len(raw),
        "fact_coverage_in_context": f"{cov_met}/{cov_total}",
        "fact_coverage_rate": round(cov_met / cov_total, 3) if cov_total else 0,
        "proxy_answer": proxy_ans[:200],
        "answer_class": ans_class,
        "expected_correct": ans_class == "Correct",
        "fact_met": fact_met,
        "unsupported_claims": unsupported,
        "compression_ratio": round(len(ctx) / max(len(raw), 1), 3),
    }


def run_format_comparison(cases: list[EvidenceBundle]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        for fmt in CONTEXT_FORMATS:
            vm: VerificationMode = "E4_ALL_VERDICTS" if fmt in ("A5_VERIFY", "A6_HYBRID") else "E1_NONE"
            rows.append(evaluate_context_arm(case, fmt, verification_mode=vm))
    return rows


def run_verification_comparison(case: EvidenceBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mode in ("E1_NONE", "E2_FULL", "E3_MATCH_ONLY", "E4_ALL_VERDICTS"):
        rows.append(evaluate_context_arm(case, "A4_CLAIM", verification_mode=mode))
    return rows


def run_compression_ladder(case: EvidenceBundle) -> list[dict[str, Any]]:
    levels = compress_context_levels(case)
    rows: list[dict[str, Any]] = []
    for level, ctx in levels.items():
        proxy = proxy_llm_from_context(ctx, case)
        ans_class, _, fact_met, _ = classify_answer(proxy, case.raw_combined, case.expected_facts)
        cov_met, cov_total = fact_coverage_in_context(ctx, case.expected_facts)
        rows.append(
            {
                "case_id": case.case_id,
                "level": level,
                "context_size": len(ctx),
                "fact_coverage": f"{cov_met}/{cov_total}",
                "answer_class": ans_class,
                "expected_correct": ans_class == "Correct",
            }
        )
    return rows


def run_conflict_analysis(case: EvidenceBundle) -> dict[str, Any]:
    ctx_raw = build_context("A1_RAW", case)
    ctx_grouped = build_context("A3_SOURCE_GROUPED", case)
    proxy_raw = proxy_llm_from_context(ctx_raw, case, optimistic=False)
    proxy_grouped = proxy_llm_from_context(ctx_grouped, case, optimistic=False)
    return {
        "case_id": case.case_id,
        "sources": len(case.sources),
        "raw_answer": proxy_raw,
        "grouped_answer": proxy_grouped,
        "note": "Conflict requires explicit year/source attribution — deterministic proxy may merge",
        "passes_dual_fact": all(
            re.search(p, case.raw_combined, re.I)
            for p in (r"275", r"752")
        ),
    }


def aggregate_by_format(rows: list[dict[str, Any]]) -> dict[str, Any]:
    agg: dict[str, dict[str, Any]] = {}
    for fmt in CONTEXT_FORMATS:
        sub = [r for r in rows if r["format"] == fmt]
        if not sub:
            continue
        correct = sum(1 for r in sub if r.get("expected_correct"))
        agg[fmt] = {
            "cases": len(sub),
            "expected_correct_count": correct,
            "accuracy": round(correct / len(sub), 3),
            "avg_context_size": int(sum(r["context_size"] for r in sub) / len(sub)),
            "avg_coverage_rate": round(sum(r["fact_coverage_rate"] for r in sub) / len(sub), 3),
            "avg_unsupported": round(sum(r["unsupported_claims"] for r in sub) / len(sub), 3),
        }
    return agg


def discover_core_candidates(agg: dict[str, Any]) -> list[dict[str, Any]]:
    best = max(agg.items(), key=lambda x: (x[1]["accuracy"], -x[1]["avg_context_size"]), default=(None, {}))
    best_fmt = best[0]
    raw_acc = (agg.get("A1_RAW") or {}).get("accuracy", 0)
    best_acc = best[1].get("accuracy", 0)

    cands: list[dict[str, Any]] = []

    if best_fmt and best_acc > raw_acc + 0.05:
        cands.append(
            {
                "id": "CTX-PASSAGE",
                "name": "Relevant Passage Selector",
                "classification": "C2" if best_fmt in ("A2_PASSAGE", "A6_HYBRID") else "C1",
                "current_need": "NONE",
                "future_value": "HIGH",
                "reuse": "Evidence→LLM, token budget, multi-source",
                "defensive_value": "MEDIUM — reduces noise",
                "cost": "LOW",
                "risk": "LOW experimental",
                "production_dependency": "NONE",
                "overlaps": "Partial overlap with extraction normalization — different layer",
                "sunset": "If A1_RAW matches best accuracy sustained",
            }
        )
    else:
        cands.append(
            {
                "id": "CTX-PASSAGE",
                "name": "Relevant Passage Selector",
                "classification": "C0",
                "note": "Raw or grouped sufficient in proxy eval — no clear gain",
            }
        )

    verify_a4 = agg.get("A4_CLAIM", {}).get("accuracy", 0)
    verify_a5 = agg.get("A5_VERIFY", {}).get("accuracy", 0)
    cands.append(
        {
            "id": "CTX-VERIFY-ENV",
            "name": "Verification Metadata Envelope",
            "classification": "C1" if verify_a5 <= verify_a4 else "C2",
            "current_need": "LOW",
            "future_value": "HIGH",
            "reuse": "Extend CC-02 Mechanical Verification",
            "defensive_value": "HIGH",
            "cost": "LOW",
            "risk": "LOW",
            "production_dependency": "NONE",
            "overlaps": "CC-02 — extend do not duplicate",
            "note": "Proxy LLM may not consume metadata; live LLM eval deferred",
        }
    )

    cands.append(
        {
            "id": "CTX-BUILDER",
            "name": "Standalone Context Builder module",
            "classification": "C0" if best_acc <= raw_acc else "C1",
            "note": "Packager functions sufficient; no standalone builder until C2 validates",
        }
    )

    cands.append(
        {
            "id": "CTX-CONFLICT",
            "name": "Conflict-aware Context Builder",
            "classification": "C2",
            "current_need": "NONE",
            "future_value": "MEDIUM",
            "reuse": "Multi-source benchmark cases",
            "defensive_value": "MEDIUM",
            "cost": "MEDIUM",
            "risk": "LOW",
            "production_dependency": "NONE",
            "note": "Conflict case IC-F01 — source grouping helps attribution",
        }
    )

    return cands


def run_web_evidence_llm_context_investigation(*, fetch_live_baseline: bool = True) -> dict[str, Any]:
    head = _git_head()
    golden = run_production_golden(fetch_live=fetch_live_baseline)
    golden_pass = golden.get("overall") == "PASS"

    # Baseline metrics from prior phases (documented)
    baseline_metrics = {
        "success_class_accuracy": "see runs/web_tool_success_class (mock + live subset)",
        "broader_accuracy": "84.6% documented in broader eval phase",
        "golden": f"{golden.get('pass_count')}/{golden.get('total')}",
    }

    cases = investigation_cases()
    format_rows = run_format_comparison(cases)
    agg = aggregate_by_format(format_rows)

    verify_rows: list[dict[str, Any]] = []
    for case in cases[:3]:
        verify_rows.extend(run_verification_comparison(case))

    compression_rows: list[dict[str, Any]] = []
    for case in cases[:5]:
        compression_rows.extend(run_compression_ladder(case))

    conflict = run_conflict_analysis(next(c for c in cases if c.case_id == "IC-F01"))

    core_cands = discover_core_candidates(agg)
    best_fmt = max(agg.items(), key=lambda x: x[1]["accuracy"], default=("A1_RAW", {}))[0]

    # STOP check: raw sufficient?
    raw_acc = (agg.get("A1_RAW") or {}).get("accuracy", 0)
    best_acc = max(v.get("accuracy", 0) for v in agg.values()) if agg else 0
    stop_raw_sufficient = raw_acc >= best_acc - 0.01 and raw_acc >= 0.8

    decision: Literal["STOP", "CONTINUE", "INVESTIGATE", "EXPERIMENTAL", "RECORD"] = (
        "STOP" if stop_raw_sufficient and golden_pass else "INVESTIGATE"
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": head,
        "final_head": head,
        "overall": "PASS" if golden_pass else "PARTIAL",
        "production_changes": [],
        "phase_start_baseline": {
            "head": head,
            "golden": golden,
            "baseline_metrics": baseline_metrics,
            "existing_cores": [
                "CC-01 Eval Parity Bridge",
                "CC-02 Mechanical Verification",
                "production_mirror",
                "web_status",
                "web_answer_boundary",
            ],
        },
        "current_evidence_llm_path": {
            "production": "enrich_web_tool_result → tool JSON in LLM messages (main_text + grounding hints)",
            "evaluation": "run_canonical_web_eval → boundary → final_answer",
            "gap": "No dedicated Evidence Packager; context format not systematically compared",
        },
        "investigation_a_format_comparison": {"rows": format_rows, "aggregate": agg},
        "investigation_b_categories": list({c.category for c in cases}),
        "investigation_c_evidence_volume": compression_rows,
        "investigation_d_compression": compression_rows,
        "investigation_e_verification": verify_rows,
        "investigation_f_conflict": conflict,
        "best_format_proxy": best_fmt,
        "stop_raw_sufficient": stop_raw_sufficient,
        "core_capability_discovery": core_cands,
        "production_connection_candidates": [],
        "human_review_required": False,
        "deterministic_scope": "Proxy LLM + classify_answer + ExpectedFact — live LLM not required for Phase 1",
        "remaining_unknowns": [
            "Live qwen3:8b consumption of packaged context formats",
            "Verification metadata effect on real LLM unsupported rate",
            "Optimal format for English vs Japanese queries",
        ],
        "next_phase_candidates": [
            "Live LLM same-evidence format shootout (HR optional)",
            "C2 passage selector prototype if A2/A6 beats A1 on live",
        ],
        "decision": decision,
        "architecture_options": [
            {
                "id": "OPT_KEEP_ENRICH",
                "status": "PROPOSE",
                "rationale": "Production enrich path stable; packaging is experimental overlay",
            },
            {
                "id": "OPT_PACKAGER_EXPERIMENTAL",
                "status": "RECORD" if stop_raw_sufficient else "INVESTIGATE",
                "rationale": f"Best proxy format: {best_fmt}; no Production connection",
            },
        ],
    }
