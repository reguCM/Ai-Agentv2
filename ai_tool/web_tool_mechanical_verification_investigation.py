"""Web Tool Mechanical Verification Investigation — eval-only harness.

Evaluates experimental Mechanical Verification capability against
built-in scenarios and success_class mock dataset. No Production changes.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.mechanical_verification.verifier import (
    MechanicalVerificationReport,
    VerificationVerdict,
    verify_answer,
)
from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.web_tool_broader_success_class_evaluation import broader_dataset_v2
from ai_tool.web_tool_success_class_accuracy_evaluation import (
    CAPITAL_FIXTURE,
    GOOD_HTML,
    ExpectedFact,
    classify_answer,
    success_class_dataset,
)
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[1]

Conclusion = Literal["A_NO_BUILD", "B_DESIGN_ONLY", "C_EXPERIMENTAL", "D_WARNING", "E_OTHER"]


@dataclass
class VerificationScenario:
    scenario_id: str
    label: str
    evidence: str
    answer: str
    expected_facts: list[ExpectedFact]
    expected_verdict: VerificationVerdict
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["expected_facts"] = [f.to_dict() for f in self.expected_facts]
        return d


@dataclass
class ScenarioResult:
    scenario_id: str
    expected_verdict: VerificationVerdict
    observed_verdict: VerificationVerdict
    match: bool
    answer_class: str
    report: dict[str, Any]
    false_positive: bool
    false_negative: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def built_in_scenarios() -> list[VerificationScenario]:
    pop_fact = ExpectedFact(
        "osaka_population",
        "numeric",
        [r"2[,，]?817[,，]?627", r"275", r"272"],
        [r"275|272|2[,，]?8"],
        numeric_min=2_500_000,
        numeric_max=2_900_000,
    )
    capital_fact = ExpectedFact(
        "capital",
        "entity",
        [r"東京"],
        [r"東京"],
        forbidden_patterns=[r"大阪.*首都"],
    )
    year_fact = ExpectedFact(
        "founded",
        "temporal",
        [r"1889"],
        [r"1889"],
    )
    ev_osaka = normalize_html_to_evidence(GOOD_HTML)["main_text"]
    ev_capital = normalize_html_to_evidence(CAPITAL_FIXTURE)["main_text"]

    return [
        VerificationScenario(
            "V01", "numeric match with 約 tolerance",
            ev_osaka,
            "大阪市の人口は約275万人（2,750,000人）です。",
            [pop_fact], "MATCH",
        ),
        VerificationScenario(
            "V02", "numeric mismatch",
            ev_osaka,
            "大阪市の人口は約1,900万人です。",
            [pop_fact], "MISMATCH",
        ),
        VerificationScenario(
            "V03", "unsupported — no population in evidence",
            "Transportation timetables only. No demographics.",
            "大阪市の人口は約282万人です。",
            [pop_fact], "MISMATCH",
            notes="Evidence lacks population; claim should not MATCH",
        ),
        VerificationScenario(
            "V04", "entity match",
            ev_capital,
            "日本の首都は東京（東京都）です。",
            [capital_fact], "MATCH",
        ),
        VerificationScenario(
            "V05", "entity mismatch",
            ev_capital,
            "日本の首都は大阪市です。",
            [capital_fact], "MISMATCH",
        ),
        VerificationScenario(
            "V06", "year match",
            "1889年（明治22年）に市制が施行された。",
            "1889年に市制が施行されました。",
            [year_fact], "MATCH",
        ),
        VerificationScenario(
            "V07", "year mismatch",
            "1889年に市制が施行された。",
            "1950年に市制が施行されました。",
            [year_fact], "MISMATCH",
        ),
        VerificationScenario(
            "V08", "million unit english",
            "Osaka has a population of approximately 2.75 million people.",
            "Osaka has a population of approximately 2.75 million.",
            [ExpectedFact(
                "osaka_population_en", "numeric",
                [r"2\.75\s*million", r"275"],
                [r"2\.75|million"],
                numeric_min=2_500_000, numeric_max=2_900_000,
            )], "MATCH",
        ),
        VerificationScenario(
            "V09", "multiple claims — one unsupported numeric extra",
            ev_capital,
            "首都は東京です。人口は1,400万人です。",
            [capital_fact], "UNSUPPORTED",
            notes="Entity MATCH but extra unsupported numeric",
        ),
        VerificationScenario(
            "V10", "long answer with embedded correct numeric",
            ev_osaka + "\n" + ("追加の説明文。" * 20),
            "以上より、大阪市の人口は約272万人と考えられます。" + ("詳細分析。" * 15),
            [pop_fact], "MATCH",
        ),
    ]


def _verdict_matches_expected(observed: VerificationVerdict, expected: VerificationVerdict) -> bool:
    if expected == "UNSUPPORTED":
        return observed in ("UNSUPPORTED", "MISMATCH")
    return observed == expected


def run_scenario(spec: VerificationScenario) -> ScenarioResult:
    report = verify_answer(spec.evidence, spec.answer, spec.expected_facts)
    ans_class, _, _, _ = classify_answer(spec.answer, spec.evidence, spec.expected_facts)
    obs = report.overall
    exp = spec.expected_verdict
    matched = _verdict_matches_expected(obs, exp)
    fp = exp == "MATCH" and obs in ("MISMATCH", "UNSUPPORTED")
    fn = exp in ("MISMATCH", "UNSUPPORTED") and obs == "MATCH"
    return ScenarioResult(
        scenario_id=spec.scenario_id,
        expected_verdict=exp,
        observed_verdict=obs,
        match=matched,
        answer_class=ans_class,
        report=report.to_dict(),
        false_positive=fp,
        false_negative=fn,
    )


def replay_success_class_mock_cases() -> list[ScenarioResult]:
    """Replay mock cases from success_class + broader datasets."""
    results: list[ScenarioResult] = []
    seen: set[str] = set()
    for ds_fn in (success_class_dataset, broader_dataset_v2):
        for case in ds_fn(include_live=False):
            if case.case_id in seen or not case.mock_scenario or not case.expected_facts:
                continue
            seen.add(case.case_id)
            # Resolve evidence from fixture via read_url_text_fn path
            evidence = ""
            if case.read_url_text_fn:
                r = case.read_url_text_fn(url="fixture://local")
                evidence = str(r.get("main_text") or "")
            if not evidence:
                continue
            answer = case.mock_scenario.mock_final_answer
            report = verify_answer(evidence, answer, case.expected_facts)
            exp_verdict: VerificationVerdict = "MATCH" if case.expect_correct else "MISMATCH"
            if case.taxonomy_control and "unsupported" in case.label.lower():
                exp_verdict = "UNSUPPORTED"
            ans_class, _, _, _ = classify_answer(answer, evidence, case.expected_facts)
            obs = report.overall
            matched = _verdict_matches_expected(obs, exp_verdict) if case.expect_correct else obs != "MATCH"
            if case.taxonomy_control:
                matched = obs in ("MISMATCH", "UNSUPPORTED")
            results.append(
                ScenarioResult(
                    scenario_id=case.case_id,
                    expected_verdict=exp_verdict,
                    observed_verdict=obs,
                    match=matched,
                    answer_class=ans_class,
                    report=report.to_dict(),
                    false_positive=case.expect_correct and obs in ("MISMATCH", "UNSUPPORTED"),
                    false_negative=case.taxonomy_control and obs == "MATCH",
                )
            )
    return results


def aggregate_metrics(builtin: list[ScenarioResult], replay: list[ScenarioResult]) -> dict[str, Any]:
    all_r = builtin + replay
    n = len(all_r) or 1
    tp = sum(1 for r in all_r if r.match)
    fp = sum(1 for r in all_r if r.false_positive)
    fn = sum(1 for r in all_r if r.false_negative)
    builtin_ok = sum(1 for r in builtin if r.match)
    replay_ok = sum(1 for r in replay if r.match)
    tax = [r for r in replay if r.scenario_id.startswith(("SC-M0", "BC-CTL"))]
    tax_detect = sum(1 for r in tax if r.observed_verdict in ("MISMATCH", "UNSUPPORTED"))
    return {
        "total_scenarios": len(all_r),
        "builtin_count": len(builtin),
        "replay_count": len(replay),
        "scenario_pass_rate": round(tp / n, 4),
        "builtin_pass_rate": round(builtin_ok / max(len(builtin), 1), 4),
        "replay_pass_rate": round(replay_ok / max(len(replay), 1), 4),
        "false_positive_count": fp,
        "false_negative_count": fn,
        "taxonomy_detection_rate": round(tax_detect / max(len(tax), 1), 4) if tax else None,
    }


def architecture_options(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    fp = metrics.get("false_positive_count", 0)
    fn = metrics.get("false_negative_count", 0)
    return [
        {"id": "OPT0", "name": "現状維持", "stage": "none", "production_risk": "none"},
        {"id": "OPT1", "name": "Experimental Capability", "stage": "observation-only", "production_risk": "none"},
        {"id": "OPT2", "name": "Production Warning", "stage": "warning", "production_risk": "medium", "note": f"fp={fp} blocks safe deploy"},
        {"id": "OPT3", "name": "Retry on MISMATCH", "stage": "retry", "production_risk": "medium-high"},
        {"id": "OPT4", "name": "Mechanical Answer Fallback", "stage": "fallback", "production_risk": "high"},
        {"id": "OPT5", "name": "Structured Claim Architecture", "stage": "structured", "production_risk": "high"},
        {"id": "OPT6", "name": "Hybrid verify + LLM", "stage": "hybrid", "production_risk": "medium-high"},
        {"id": "OPT7", "name": "Post-LLM verify-only metadata (Cursor)", "stage": "observation→warning", "production_risk": "low-medium",
         "note": "Extend boundary with verification metadata without answer replacement"},
    ]


def select_conclusion(metrics: dict[str, Any]) -> tuple[Conclusion, str, str, list[str]]:
    rate = metrics.get("scenario_pass_rate", 0)
    fp = metrics.get("false_positive_count", 0)
    fn = metrics.get("false_negative_count", 0)
    if rate >= 0.85 and fp <= 1:
        why = (
            f"Verification pass rate {rate:.0%} on built-in + replay scenarios. "
            f"FP={fp}, FN={fn}. Experimental module viable; Production connection not justified."
        )
        return "C_EXPERIMENTAL", "OPT1", why, ["OPT2", "OPT3", "OPT4", "OPT5"]
    if rate >= 0.7:
        why = f"Partial viability ({rate:.0%}) — experimental exists but needs refinement before expansion."
        return "C_EXPERIMENTAL", "OPT1", why, ["OPT2", "OPT3", "OPT4"]
    if rate >= 0.5:
        return "B_DESIGN_ONLY", "OPT0", f"Pass rate {rate:.0%} — design documented, defer implementation expansion", ["OPT1"]
    return "A_NO_BUILD", "OPT0", f"Pass rate {rate:.0%} — deterministic verification insufficient", ["OPT1", "OPT2"]


def run_mechanical_verification_investigation(*, fetch_live_baseline: bool = True) -> dict[str, Any]:
    initial_head = _git_head()
    baseline = run_production_golden(fetch_live=fetch_live_baseline)

    builtin_specs = built_in_scenarios()
    builtin_results = [run_scenario(s) for s in builtin_specs]
    replay_results = replay_success_class_mock_cases()
    metrics = aggregate_metrics(builtin_results, replay_results)
    options = architecture_options(metrics)
    conclusion, selected, why, rejected = select_conclusion(metrics)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": initial_head,
        "final_head": initial_head,
        "overall": "PASS" if baseline.get("overall") == "PASS" else "PARTIAL",
        "baseline_golden": baseline.get("pass_count"),
        "baseline_total": baseline.get("total"),
        "builtin_scenarios": [s.to_dict() for s in builtin_specs],
        "builtin_results": [r.to_dict() for r in builtin_results],
        "replay_results": [r.to_dict() for r in replay_results],
        "metrics": metrics,
        "architecture_options": options,
        "conclusion": conclusion,
        "selected_option": selected,
        "selection_reason": why,
        "rejected_options": rejected,
        "production_changes": [],
        "experimental_changes": [
            "ai_tool/experimental/mechanical_verification/verifier.py",
            "ai_tool/web_tool_mechanical_verification_investigation.py",
        ],
        "registry_changes": [],
        "prompt_changes": [],
        "cost_estimate": "LOW",
        "risk_estimate": "LOW",
        "reuse_potential": "HIGH",
        "production_risk": "NONE",
        "development_philosophy_assessment": {
            "model_b_support": True,
            "note": "Experimental verify-only aligns with Model B; Production ROI still insufficient for OPT2+",
        },
        "mechanical_answer_production": "NOT_RECOMMENDED",
        "mechanical_verification_experimental": "RECOMMENDED" if conclusion == "C_EXPERIMENTAL" else "DEFERRED",
        "human_review_required_for": ["OPT2 Production Warning", "OPT3 Retry", "OPT4 Mechanical Fallback"],
        "remaining_unknowns": [
            "Verification without ExpectedFact (open-domain)",
            "Verbose LLM answers with buried claims",
            "Non-Wikipedia evidence patterns",
            "Live BC-L02 style numeric miss detection",
        ],
        "recommended_next_step": (
            "Maintain experimental module; periodic replay on broader dataset; "
            "re-evaluate OPT7 warning metadata if live numeric_error_rate > 15%"
        ),
        "stop": True,
    }
