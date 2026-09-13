"""Broader Success-Class Evaluation — extended dataset + architecture decision.

Extends success_class_v1 with broader failure modes and layer separation.
Does NOT modify Production. Uses production_mirror as canonical eval path.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.agent_integration.eval_production_parity_bridge import run_canonical_web_eval
from ai_tool.agent_integration.production_agent_web_loop import make_e2e_trust_file
from ai_tool.agent_integration.trial import make_mock_chat_fn
from ai_tool.agent_integration.trial_scenarios import TrialScenario
from ai_tool.web_tool_extraction_normalization_experiment import (
    URL_GT1_OSAKA,
    URL_GT2_CAPITAL,
    URL_GT4_YOKOHAMA,
    URL_GT5_OSAKA_EN,
)
from ai_tool.web_tool_extraction_normalization_production import run_production_golden
from ai_tool.web_tool_success_class_accuracy_evaluation import (
    CAPITAL_FIXTURE,
    COMPARATIVE_FIXTURE,
    ExpectedFact,
    SuccessClassCaseResult,
    SuccessClassCaseSpec,
    TEMPORAL_FIXTURE,
    YOKOHAMA_FIXTURE,
    _fixture_fetch,
    _fixture_search,
    aggregate_accuracy,
    classify_answer,
    is_success_class,
    run_success_class_case,
    success_class_dataset,
)

RepoRoot = Path(__file__).resolve().parents[1]

Decision = Literal["STOP_NO_CHANGE", "PROPOSE_CHANGE", "INVESTIGATE_MORE", "IMPLEMENT_CHANGE"]
FailureLayer = Literal[
    "NONE",
    "SEARCH",
    "FETCH",
    "EXTRACTION",
    "EVIDENCE",
    "LLM",
    "AGENT",
    "BOUNDARY",
    "UNKNOWN",
]


@dataclass
class LayerStatus:
    search: str
    fetch: str
    extraction: str
    evidence: str
    web_overall: str
    llm_answer_present: bool
    boundary_applied: bool
    failure_layer: FailureLayer
    llm_failure: bool
    web_failure: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BroaderCaseResult:
    case_result: SuccessClassCaseResult
    layers: LayerStatus
    scope_category: str
    source_type: str  # mock_fixture | live_wikipedia | live_other

    def to_dict(self) -> dict[str, Any]:
        d = self.case_result.to_dict()
        d["layers"] = self.layers.to_dict()
        d["scope_category"] = self.scope_category
        d["source_type"] = self.source_type
        return d


# --- v2 fixture HTML ---

PREFECTURE_FIXTURE = """
<html><head><title>大阪府</title></head><body>
<main><h1>大阪府</h1>
<p>大阪府（おおさかふ）は、日本の近畿地方に位置する府。府庁所在地は大阪市北区。
面積は1,905.14平方キロメートル。人口は約880万人（2024年時点）。</p>
<p>近畿地方の中核として経済・文化が集積する。</p>
</main></body></html>
"""

AREA_JAPAN_FIXTURE = """
<html><head><title>日本の地理</title></head><body>
<main><h1>日本の地理</h1>
<p>日本の総面積は、約377,975平方キロメートル（377,975 km²）である。
この数値は国土交通省のデータに基づく。</p>
</main></body></html>
"""

POPULATION_2020_FIXTURE = """
<html><head><title>大阪市 2020年人口</title></head><body>
<main><h1>大阪市の人口（2020年）</h1>
<p>2020年（令和2年）国勢調査による大阪市の人口は2,752,412人であった。
2015年比で増加し、政令指定都市の中でも注目された。</p>
</main></body></html>
"""

ORG_FIXTURE = """
<html><head><title>国立天文台</title></head><body>
<main><h1>国立天文台</h1>
<p>国立天文台（こくりつてんもんだい）は、国立研究開発法人情報通信研究機構（NICT）の
研究機関。本部は東京都三鷹市。1888年に東京測候台として創設された。</p>
</main></body></html>
"""

EN_OSAKA_FIXTURE = """
<html><head><title>Osaka</title></head><body>
<main><h1>Osaka</h1>
<p>Osaka is a designated city in the Kansai region of Japan. It is the capital of Osaka Prefecture.
As of 2024, the city has a population of approximately 2.75 million people.</p>
</main></body></html>
"""

NON_WIKI_FIXTURE = """
<html><head><title>City Data Portal</title></head><body>
<main><h1>Demo Municipality Statistics</h1>
<p>Official statistics portal (non-Wikipedia source). Registered population: 1,234,567 as of March 2024.
Land area: 156.8 km². This page is maintained by the municipal statistics bureau.</p>
</main></body></html>
"""

LARGEST_CITY_FIXTURE = """
<html><head><title>日本の市区町村人口</title></head><body>
<main><h1>市区町村別人口</h1>
<p>日本で人口が最も多い市区町村は横浜市（神奈川県）で、約375.9万人。
2位は大阪市（約272万人）、3位は名古屋市（約232万人）である。</p>
</main></body></html>
"""


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def verify_baseline(*, fetch_live: bool = True) -> dict[str, Any]:
    golden = run_production_golden(fetch_live=fetch_live)
    return {
        "golden": golden,
        "golden_pass": golden.get("overall") == "PASS",
        "pass_count": golden.get("pass_count"),
        "total": golden.get("total"),
    }


def broader_dataset_v2(*, include_live: bool = True) -> list[SuccessClassCaseSpec]:
    """Extend v1 with broader entity/numeric/temporal/scope/english/non-wiki cases."""
    v1 = success_class_dataset(include_live=False)
    extra: list[SuccessClassCaseSpec] = [
        # Entity — prefecture
        SuccessClassCaseSpec(
            "BC-E01",
            "entity",
            "prefecture capital",
            "大阪府の府庁所在地をWeb検索しread_url_textで確認してください。",
            [ExpectedFact("pref_capital", "entity", [r"大阪市", r"北区"], [r"大阪市|北区"])],
            search_web_fn=_fixture_search("https://fixture.local/osaka-pref"),
            read_url_text_fn=_fixture_fetch(PREFECTURE_FIXTURE),
            mock_scenario=_mock("BC-E01", "大阪府 府庁所在地", "https://fixture.local/osaka-pref",
                                "府庁所在地は大阪市北区です。"),
        ),
        # Entity — organization
        SuccessClassCaseSpec(
            "BC-E02",
            "entity",
            "organization HQ",
            "国立天文台の本部所在地をWeb検索しread_url_textで確認してください。",
            [ExpectedFact("nao_hq", "entity", [r"三鷹"], [r"三鷹"])],
            search_web_fn=_fixture_search("https://fixture.local/nao"),
            read_url_text_fn=_fixture_fetch(ORG_FIXTURE),
            mock_scenario=_mock("BC-E02", "国立天文台 本部", "https://fixture.local/nao",
                                "本部は東京都三鷹市にあります。"),
        ),
        # Numeric — area
        SuccessClassCaseSpec(
            "BC-N01",
            "numeric",
            "country area km2",
            "日本の国土面積をWeb検索しread_url_textで確認してください。",
            [ExpectedFact("japan_area", "numeric", [r"377[,，]?975", r"377975"],
                          [r"377"], numeric_min=370_000, numeric_max=380_000)],
            search_web_fn=_fixture_search("https://fixture.local/japan-geo"),
            read_url_text_fn=_fixture_fetch(AREA_JAPAN_FIXTURE),
            mock_scenario=_mock("BC-N01", "日本 国土面積", "https://fixture.local/japan-geo",
                                "国土面積は約377,975平方キロメートルです。"),
        ),
        # Temporal / scope — year-specific population
        SuccessClassCaseSpec(
            "BC-T01",
            "temporal",
            "2020 osaka population",
            "2020年の大阪市の人口をWeb検索しread_url_textで確認してください。",
            [ExpectedFact("pop_2020", "numeric", [r"2[,，]?752[,，]?412", r"275"],
                          [r"275|2[,，]?752"], numeric_min=2_700_000, numeric_max=2_800_000)],
            search_web_fn=_fixture_search("https://fixture.local/osaka-2020"),
            read_url_text_fn=_fixture_fetch(POPULATION_2020_FIXTURE),
            mock_scenario=_mock("BC-T01", "大阪市 2020 人口", "https://fixture.local/osaka-2020",
                                "2020年国勢調査では2,752,412人でした。"),
        ),
        # Scope — largest city in Japan
        SuccessClassCaseSpec(
            "BC-S01",
            "scope",
            "largest city by population",
            "日本で最も人口が多い都市はどこですか。Web検索しread_url_textで確認してください。",
            [ExpectedFact("largest_city", "comparison", [r"横浜", r"375"],
                          [r"横浜"])],
            search_web_fn=_fixture_search("https://fixture.local/city-rank"),
            read_url_text_fn=_fixture_fetch(LARGEST_CITY_FIXTURE),
            mock_scenario=_mock("BC-S01", "日本 人口最多 都市", "https://fixture.local/city-rank",
                                "最も人口が多いのは横浜市（約375.9万人）です。"),
        ),
        # English non-ja page
        SuccessClassCaseSpec(
            "BC-EN01",
            "english",
            "english osaka population",
            "What is the population of Osaka city? Search the web and use read_url_text.",
            [ExpectedFact("osaka_pop_en", "numeric", [r"2\.75\s*million", r"275"],
                          [r"2\.75|275|million"], numeric_min=2_500_000, numeric_max=2_900_000)],
            search_web_fn=_fixture_search("https://fixture.local/osaka-en", "Osaka"),
            read_url_text_fn=_fixture_fetch(EN_OSAKA_FIXTURE, "https://fixture.local/osaka-en"),
            mock_scenario=_mock("BC-EN01", "Osaka population", "https://fixture.local/osaka-en",
                                "Osaka has a population of approximately 2.75 million."),
        ),
        # Non-Wikipedia source
        SuccessClassCaseSpec(
            "BC-EXT01",
            "non_wikipedia",
            "non-wiki statistics portal",
            "次の統計ページの登録人口をWeb検索しread_url_textで確認してください。",
            [ExpectedFact("demo_pop", "numeric", [r"1[,，]?234[,，]?567"],
                          [r"1[,，]?234"], numeric_min=1_200_000, numeric_max=1_250_000)],
            search_web_fn=_fixture_search("https://fixture.local/stats-portal"),
            read_url_text_fn=_fixture_fetch(NON_WIKI_FIXTURE),
            mock_scenario=_mock("BC-EXT01", "municipality statistics", "https://fixture.local/stats-portal",
                                "登録人口は1,234,567人です。"),
        ),
        # Taxonomy control — scope error (wrong city as largest)
        SuccessClassCaseSpec(
            "BC-CTL01",
            "scope",
            "injected scope error",
            "日本で最も人口が多い都市はどこですか。Web検索しread_url_textで確認してください。",
            [ExpectedFact("largest_city", "comparison", [r"横浜"], [r"横浜"],
                          forbidden_patterns=[r"大阪.*最多|大阪.*最も人口"])],
            search_web_fn=_fixture_search("https://fixture.local/city-rank"),
            read_url_text_fn=_fixture_fetch(LARGEST_CITY_FIXTURE),
            mock_scenario=_mock("BC-CTL01", "日本 人口最多", "https://fixture.local/city-rank",
                                "最も人口が多いのは大阪市です。"),
            expect_correct=False,
            taxonomy_control=True,
        ),
        # Taxonomy control — temporal numeric error
        SuccessClassCaseSpec(
            "BC-CTL02",
            "temporal",
            "injected temporal numeric error",
            "2020年の大阪市の人口をWeb検索しread_url_textで確認してください。",
            [ExpectedFact("pop_2020", "numeric", [r"2[,，]?752"],
                          [r"275|2[,，]?752"], numeric_min=2_700_000, numeric_max=2_800_000)],
            search_web_fn=_fixture_search("https://fixture.local/osaka-2020"),
            read_url_text_fn=_fixture_fetch(POPULATION_2020_FIXTURE),
            mock_scenario=_mock("BC-CTL02", "大阪 2020 人口", "https://fixture.local/osaka-2020",
                                "2020年の人口は190万人でした。"),
            expect_correct=False,
            taxonomy_control=True,
        ),
    ]

    live_extra: list[SuccessClassCaseSpec] = []
    if include_live:
        live_extra = [
            SuccessClassCaseSpec(
                "BC-L01",
                "scope",
                "live largest city",
                "日本で最も人口が多い市区町村はどこですか。Web検索しread_url_textで確認してください。",
                [ExpectedFact("largest", "comparison", [r"横浜", r"375", r"人口"],
                              [r"横浜|375"])],
                notes="Live: Yokohama expected",
            ),
            SuccessClassCaseSpec(
                "BC-L02",
                "numeric",
                "live japan area",
                "日本の国土面積をWeb検索しread_url_textで確認してください。",
                [ExpectedFact("area", "numeric", [r"377", r"km", r"平方"],
                              [r"377"], numeric_min=370_000, numeric_max=380_000)],
                notes="Live: Japan area",
            ),
            SuccessClassCaseSpec(
                "BC-L03",
                "english",
                "live english osaka",
                "What is the population of Osaka? Use search_web and read_url_text.",
                [ExpectedFact("osaka_en", "numeric", [r"population", r"272", r"275"],
                              [r"272|275|million|population"], numeric_min=2_500_000, numeric_max=2_900_000)],
                notes=f"Live EN: {URL_GT5_OSAKA_EN}",
            ),
            SuccessClassCaseSpec(
                "BC-L04",
                "temporal",
                "live 2020 osaka population",
                "2020年国勢調査における大阪市の人口をWeb検索しread_url_textで教えてください。",
                [ExpectedFact("pop2020", "numeric", [r"2020", r"275", r"272", r"人口"],
                              [r"275|272|2[,，]?7"], numeric_min=2_600_000, numeric_max=2_850_000)],
                notes=f"Live temporal: {URL_GT1_OSAKA}",
            ),
        ]

    # v1 mock cases (exclude v1 live to avoid duplication — v1 live covered by BC-L* and SC-L in v1 if needed)
    v1_mock = [c for c in v1 if not c.case_id.startswith("SC-L")]
    return v1_mock + extra + live_extra


def _mock(sid: str, query: str, url: str, answer: str) -> TrialScenario:
    return TrialScenario(
        sid, "", "either", "",
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": query}},
            {"name": "read_url_text", "arguments": {"url": url}},
        ],
        mock_final_answer=answer,
    )


def classify_layers(
    case: SuccessClassCaseResult,
    *,
    loop_agg: dict[str, Any] | None = None,
    boundary_applied: bool = False,
) -> LayerStatus:
    agg = loop_agg or {}
    layers = agg.get("layers") or {}
    search_s = str(layers.get("search") or "UNKNOWN")
    fetch_s = str(layers.get("fetch") or "UNKNOWN")
    ext_s = str(layers.get("extraction") or "UNKNOWN")
    ev_s = str(layers.get("evidence") or "UNKNOWN")
    overall = str(agg.get("overall") or case.web_status_overall or "UNKNOWN")

    web_failure = not case.web_success
    llm_failure = (
        case.web_success
        and case.expect_correct
        and not case.taxonomy_control
        and case.answer_class not in ("Correct", "SKIPPED", "Ambiguous")
    )

    failure_layer: FailureLayer = "NONE"
    if search_s in ("FAILED", "SEARCH_FAILED") or overall == "SEARCH_FAILED":
        failure_layer = "SEARCH"
    elif fetch_s in ("FAILED", "FETCH_FAILED") or overall == "FETCH_FAILED":
        failure_layer = "FETCH"
    elif ext_s in ("FAILED", "INSUFFICIENT", "EXTRACTION_FAILED") or overall == "EXTRACTION_FAILED":
        failure_layer = "EXTRACTION"
    elif ev_s in ("UNAVAILABLE", "INSUFFICIENT") or overall == "NO_EVIDENCE":
        failure_layer = "EVIDENCE"
    elif web_failure:
        failure_layer = "UNKNOWN"
    elif llm_failure:
        failure_layer = "LLM"

    return LayerStatus(
        search=search_s,
        fetch=fetch_s,
        extraction=ext_s,
        evidence=ev_s,
        web_overall=overall,
        llm_answer_present=bool(case.llm_answer and str(case.llm_answer).strip()),
        boundary_applied=boundary_applied,
        failure_layer=failure_layer,
        llm_failure=llm_failure,
        web_failure=web_failure,
    )


def compute_failure_rates(results: list[BroaderCaseResult]) -> dict[str, Any]:
    ec = [r for r in results if r.case_result.web_success and r.case_result.expect_correct
          and not r.case_result.taxonomy_control and r.case_result.answer_class != "SKIPPED"]
    n = len(ec) or 1

    def rate(cls: str) -> float:
        return round(sum(1 for r in ec if r.case_result.answer_class == cls) / n, 4)

    claim_unsupported = sum(
        1 for r in ec for c in r.case_result.claims if c.support == "unsupported"
    )
    claim_contradicted = sum(
        1 for r in ec for c in r.case_result.claims if c.support == "contradicted"
    )
    claim_total = sum(len(r.case_result.claims) for r in ec) or 1

    web_fail = [r for r in results if r.layers.web_failure]
    llm_fail = [r for r in results if r.layers.llm_failure]

    return {
        "expected_correct_success_class_count": len(ec),
        "numeric_error_rate": rate("Numeric Error"),
        "entity_error_rate": rate("Entity Error"),
        "temporal_error_rate": rate("Temporal Error"),
        "scope_error_rate": rate("Scope Error"),
        "unsupported_addition_rate": rate("Unsupported Addition"),
        "contradiction_rate": rate("Contradiction"),
        "evidence_mismatch_rate": round(claim_contradicted / claim_total, 4),
        "claim_unsupported_rate": round(claim_unsupported / claim_total, 4),
        "accuracy_rate": round(sum(1 for r in ec if r.case_result.answer_class == "Correct") / n, 4),
        "web_failure_count": len(web_fail),
        "llm_failure_count": len(llm_fail),
        "web_failure_cases": [r.case_result.case_id for r in web_fail],
        "llm_failure_cases": [r.case_result.case_id for r in llm_fail],
    }


def architecture_options_broader(rates: dict[str, Any], agg: dict[str, Any]) -> list[dict[str, Any]]:
    acc = rates.get("accuracy_rate", 0)
    num_rate = rates.get("numeric_error_rate", 0)
    uns_rate = rates.get("unsupported_addition_rate", 0)
    web_fail = rates.get("web_failure_count", 0)

    opts = [
        {
            "id": "OPT0_NO_CHANGE",
            "name": "現状維持",
            "solves": [],
            "does_not_solve": ["sustained high LLM failure if rate rises"],
            "production_scope": "none",
            "regression_risk": "none",
            "human_review": False,
            "roi": "high" if acc >= 0.85 and num_rate < 0.15 else "medium",
        },
        {
            "id": "OPT1_PROMPT_AGENT",
            "name": "Prompt / Agent policy",
            "solves": ["entity_error", "scope_error"],
            "does_not_solve": ["search instability", "fetch failures"],
            "production_scope": "agent.py prompt",
            "regression_risk": "medium",
            "human_review": True,
            "roi": "low" if acc >= 0.85 else "medium",
        },
        {
            "id": "OPT2_EVIDENCE_GROUNDING",
            "name": "Evidence grounding強化",
            "solves": ["unsupported_addition", "verbose hallucination"],
            "does_not_solve": ["search empty", "wrong entity when evidence ambiguous"],
            "production_scope": "web_evidence / LLM input",
            "regression_risk": "low-medium",
            "human_review": False,
            "roi": "low" if uns_rate < 0.1 else "medium",
        },
        {
            "id": "OPT3_STRUCTURED_CLAIM",
            "name": "Structured Claim",
            "solves": ["claim-level traceability", "partial unsupported"],
            "does_not_solve": ["web layer failures"],
            "production_scope": "large new layer",
            "regression_risk": "high",
            "human_review": True,
            "roi": "low" if num_rate < 0.2 else "medium-high",
        },
        {
            "id": "OPT4_MECHANICAL",
            "name": "Mechanical / deterministic verification",
            "solves": ["numeric_error", "temporal year match"],
            "does_not_solve": ["narrative synthesis", "comparison reasoning"],
            "production_scope": "post-LLM verification or answer gating",
            "regression_risk": "medium",
            "human_review": True,
            "roi": "high" if num_rate >= 0.25 else "low",
        },
        {
            "id": "OPT5_HYBRID",
            "name": "Hybrid mechanical + LLM",
            "solves": ["verifiable claims + LLM fallback"],
            "does_not_solve": ["search instability"],
            "production_scope": "verification layer + LLM",
            "regression_risk": "medium-high",
            "human_review": True,
            "roi": "medium" if num_rate >= 0.15 else "low",
        },
        {
            "id": "OPT6_POST_LLM_VERIFY",
            "name": "Post-LLM claim verification (verify, not replace)",
            "solves": ["SUCCESS-class wrong numeric/entity without replacing LLM synthesis"],
            "does_not_solve": ["web search empty", "extraction noise"],
            "production_scope": "optional boundary extension — eval prototype first",
            "regression_risk": "low-medium",
            "human_review": True,
            "roi": "medium" if num_rate >= 0.1 and num_rate < 0.25 else "low",
            "note": "Cursor-discovered: verify LLM claims against evidence main_text; differs from full mechanical answer",
        },
        {
            "id": "OPT7_EVAL_CANONICAL_BRIDGE",
            "name": "Eval-only production_mirror canonical wrapper",
            "solves": ["eval vs production path divergence", "mock search false positives"],
            "does_not_solve": ["live LLM accuracy"],
            "production_scope": "ai_tool harness only — no Production",
            "regression_risk": "low",
            "human_review": False,
            "roi": "high" if web_fail > 0 else "medium",
            "note": "Cursor-discovered from prior phases; improves observability not user path",
        },
    ]
    for o in opts:
        o["automation_fit"] = "high"
        o["observability"] = "high" if "eval" in o.get("production_scope", "") else "medium"
    return opts


def decide_production_change(
    rates: dict[str, Any],
    baseline: dict[str, Any],
    options: list[dict[str, Any]],
) -> tuple[Decision, str, str, list[str], str]:
    if not baseline.get("golden_pass"):
        return (
            "INVESTIGATE_MORE",
            "OPT0_NO_CHANGE",
            "Baseline golden regression FAIL — do not change Production until diagnosed",
            [o["id"] for o in options if o["id"] != "OPT0_NO_CHANGE"],
            "UNKNOWN",
        )

    acc = rates.get("accuracy_rate", 0)
    num_rate = rates.get("numeric_error_rate", 0)
    llm_fail = rates.get("llm_failure_count", 0)
    ec = rates.get("expected_correct_success_class_count", 0)

    if ec == 0:
        return (
            "INVESTIGATE_MORE",
            "OPT0_NO_CHANGE",
            "No SUCCESS-class expected-correct cases scored",
            [o["id"] for o in options if o["id"] != "OPT0_NO_CHANGE"],
            "UNKNOWN",
        )

    if acc >= 0.85 and num_rate < 0.15 and llm_fail <= max(1, ec * 0.15):
        why = (
            f"Broader SUCCESS-class accuracy {acc:.0%} ({ec} cases). "
            f"numeric_error_rate={num_rate:.0%}, llm_failures={llm_fail}. "
            "No Production change warranted."
        )
        mech = "NOT_RECOMMENDED" if num_rate < 0.25 else "DEFERRED"
        return "STOP_NO_CHANGE", "OPT0_NO_CHANGE", why, [
            o["id"] for o in options if o["id"] != "OPT0_NO_CHANGE"
        ], mech

    if num_rate >= 0.25:
        why = (
            f"numeric_error_rate={num_rate:.0%} on SUCCESS-class — "
            "OPT4/OPT6 may have ROI but require Human Review before Production."
        )
        return "PROPOSE_CHANGE", "OPT6_POST_LLM_VERIFY", why, [
            o["id"] for o in options if o["id"] not in ("OPT6_POST_LLM_VERIFY", "OPT4_MECHANICAL")
        ], "DEFERRED"

    why = (
        f"Mixed signals: accuracy={acc:.0%}, llm_failures={llm_fail}. "
        "Continue measurement; no safe minimal Production delta identified."
    )
    return "STOP_NO_CHANGE", "OPT0_NO_CHANGE", why, [
        o["id"] for o in options if o["id"] != "OPT0_NO_CHANGE"
    ], "DEFERRED"


def run_broader_success_class_evaluation(
    *,
    include_live: bool = True,
    llm_enabled: bool = False,
    chat_fn=None,
    model: str = "",
    trust_path: Path | None = None,
    fetch_live_baseline: bool = True,
) -> dict[str, Any]:
    initial_head = _git_head()
    baseline = verify_baseline(fetch_live=fetch_live_baseline)

    if not baseline.get("golden_pass"):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "initial_head": initial_head,
            "final_head": initial_head,
            "overall": "FAIL",
            "baseline": baseline,
            "decision": "INVESTIGATE_MORE",
            "production_changes": [],
            "human_intervention_count": 0,
            "stop": True,
        }

    trust = trust_path or (RepoRoot / "runs" / "ai_tool" / "_broader_success_class_trust.json")
    make_e2e_trust_file(trust)

    dataset = broader_dataset_v2(include_live=include_live)
    broader_results: list[BroaderCaseResult] = []

    for spec in dataset:
        is_live = spec.case_id.startswith(("BC-L", "SC-L"))
        if is_live and not llm_enabled:
            continue
        if is_live and not chat_fn:
            continue

        from ai_tool.web_tool_success_class_accuracy_evaluation import _evidence_from_loop, _live_fetch_fn

        # Mock cases always use mock LLM — never live chat_fn (preserves taxonomy controls)
        if is_live and chat_fn:
            chat = chat_fn
        elif spec.mock_scenario:
            chat = make_mock_chat_fn(spec.mock_scenario)
        else:
            chat = make_mock_chat_fn(TrialScenario("fallback", "", "either", ""))
        loop, path_meta = run_canonical_web_eval(
            spec.user_request,
            chat_fn=chat,
            model=model or "mock",
            search_web_fn=spec.search_web_fn,
            read_url_text_fn=spec.read_url_text_fn or (_live_fetch_fn if is_live else None),
            trust_path=trust,
            live=is_live and llm_enabled,
            scored=True,
        )
        _path_kw = {
            "path": path_meta.path_label,
            "production_equivalent": path_meta.production_equivalent,
            "boundary_applied": loop.boundary_applied,
            "web_session_tracked": path_meta.web_session_tracker,
        }

        agg = loop.web_session_aggregate or {}
        evidence, quality = _evidence_from_loop(loop)
        web_ok = is_success_class(agg, fetch_quality=quality)

        if not spec.success_class_candidate:
            cr = SuccessClassCaseResult(
                spec.case_id, spec.category, spec.label, web_ok, agg.get("overall"),
                (quality or {}).get("fact_ready"), len(evidence), loop.final_answer,
                loop.raw_llm_answer, "SKIPPED", [], [], {}, path_meta.path_label, is_live,
                spec.expect_correct, spec.taxonomy_control,
                ["negative — excluded"], "CONFIRMED",
                **_path_kw,
            )
        elif not web_ok:
            cr = SuccessClassCaseResult(
                spec.case_id, spec.category, spec.label, False, agg.get("overall"),
                (quality or {}).get("fact_ready"), len(evidence), loop.final_answer,
                loop.raw_llm_answer, "SKIPPED", [], [], {}, path_meta.path_label, is_live,
                spec.expect_correct, spec.taxonomy_control,
                [f"web not SUCCESS: {agg.get('overall')}"], "OBSERVATION",
                **_path_kw,
            )
        else:
            ans_class, claims, fact_met, det_ver = classify_answer(
                loop.final_answer, evidence, spec.expected_facts,
            )
            cr = SuccessClassCaseResult(
                spec.case_id, spec.category, spec.label, True, agg.get("overall"),
                (quality or {}).get("fact_ready"), len(evidence), loop.final_answer,
                loop.raw_llm_answer, ans_class, claims, det_ver, fact_met, path_meta.path_label,
                is_live, spec.expect_correct, spec.taxonomy_control, [],
                "CONFIRMED" if ans_class == "Correct" else "OBSERVATION",
                **_path_kw,
            )

        scope_cat = spec.category
        src = "live_wikipedia" if is_live and "wiki" in (spec.notes or "").lower() else (
            "live_other" if is_live else "mock_fixture"
        )
        layers = classify_layers(cr, loop_agg=agg, boundary_applied=loop.boundary_applied)
        broader_results.append(BroaderCaseResult(cr, layers, scope_cat, src))

    case_results = [b.case_result for b in broader_results]
    agg = aggregate_accuracy(case_results)
    rates = compute_failure_rates(broader_results)
    options = architecture_options_broader(rates, agg)
    decision, selected, why, rejected, mechanical = decide_production_change(rates, baseline, options)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": initial_head,
        "final_head": initial_head,
        "overall": "PASS" if baseline.get("golden_pass") else "FAIL",
        "baseline": baseline,
        "dataset": "success_class_v2_broader",
        "dataset_size": len(dataset),
        "cases_run": len(broader_results),
        "cases": [b.to_dict() for b in broader_results],
        "aggregation": agg,
        "failure_rates": rates,
        "architecture_options": options,
        "selected_option": selected,
        "selection_reason": why,
        "rejected_options": rejected,
        "mechanical_answer": mechanical,
        "decision": decision,
        "production_changes": [],
        "human_intervention_count": 0,
        "confirmed_causes": _confirmed(broader_results, rates),
        "hypotheses": _hypotheses(rates),
        "unknowns": _unknowns(llm_enabled, include_live),
        "next_iteration": _next_iter(decision, selected, mechanical),
        "stop": True,
    }


def _confirmed(results: list[BroaderCaseResult], rates: dict[str, Any]) -> list[str]:
    out = [
        f"Broader dataset: {len(results)} cases, expected-correct SUCCESS-class accuracy {rates.get('accuracy_rate', 0):.0%}",
        f"Web failures separated: {rates.get('web_failure_count')} cases",
        f"LLM failures (SUCCESS-class): {rates.get('llm_failure_count')} cases",
    ]
    tax = [r for r in results if r.case_result.taxonomy_control and r.case_result.answer_class != "Correct"]
    if tax:
        out.append(f"Taxonomy controls detected: {len(tax)}/{sum(1 for r in results if r.case_result.taxonomy_control)}")
    return out


def _hypotheses(rates: dict[str, Any]) -> list[str]:
    return [
        f"SUCCESS-class numeric_error_rate ~{rates.get('numeric_error_rate', 0):.0%} on broader dataset",
        "Web search intermittency causes SKIPPED cases — not LLM failures",
        "Post-LLM verification (OPT6) may suffice before full mechanical answer if numeric errors rise",
    ]


def _unknowns(llm_enabled: bool, include_live: bool) -> list[str]:
    u = [
        "Non-Wikipedia live fetch reliability",
        "Scope error detection on verbose LLM answers",
        "English-only query search ranking",
    ]
    if include_live and not llm_enabled:
        u.append("Live BC-L* cases skipped — ollama unavailable")
    return u


def _next_iter(decision: str, selected: str, mechanical: str) -> str:
    if decision == "STOP_NO_CHANGE":
        return "Periodic re-run of broader harness; OPT7 eval bridge if autonomous metrics diverge"
    if decision == "PROPOSE_CHANGE":
        return f"{selected} — Human Review before Production"
    return "Fix baseline first"
