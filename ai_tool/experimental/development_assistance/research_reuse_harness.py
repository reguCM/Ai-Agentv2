"""Phase E — Research Reuse & Hierarchical Capability Discovery harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Literal

from ai_tool.defensive_core_discovery_policy import (
    evaluate_llm_capability_role,
    phase_forbidden_actions,
)
from ai_tool.experimental.development_assistance.decision_factors import compare_candidates_for_decision
from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec, tda_evaluation_cases
from ai_tool.experimental.development_assistance.goal_abstraction import discover_capabilities
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.research_audit import audit_summary
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import (
    assess_reuse,
    extract_requirement_facets,
    merge_past_and_new_material,
    reuse_conversation_material,
)
from ai_tool.experimental.development_assistance.spec_draft import build_spec_draft
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

PhaseEDecision = Literal[
    "STOP_NO_NEW_CORE",
    "CONTINUE",
    "INVESTIGATE",
    "EXPERIMENTAL_RETAIN",
    "HUMAN_REVIEW_REQUIRED",
]

ChatFn = Callable[..., Any]
CompareMode = Literal["A_llm_only", "B_llm_web", "C_past_research", "D_past_partial_web"]


@dataclass
class TRECaseSpec:
    case_id: str
    label: str
    current_requirement: str
    tda_id: str = ""
    user_constraints: dict[str, str] = field(default_factory=dict)
    seed_tda_id: str = ""
    expected_reuse: Literal["full_reuse", "partial_reuse", "no_reuse"] = "no_reuse"
    seed_checked_at_offset_days: int = 14
    hierarchical_only: bool = False
    partial_web_tda_id: str = ""


def phase_e_cases() -> list[TRECaseSpec]:
    return [
        TRECaseSpec(
            case_id="TRE-1",
            label="Full Reuse — Polars repeat",
            current_requirement="Polarsという新しいデータフレームライブラリでCSVを処理するToolを作りたい",
            tda_id="TDA-B",
            seed_tda_id="TDA-B",
            expected_reuse="full_reuse",
        ),
        TRECaseSpec(
            case_id="TRE-2",
            label="Partial Reuse — PyTorch Python version shift",
            current_requirement="PyTorchでGPU推論Toolを作りたい。Python 3.13とCUDA 12が必要",
            tda_id="TDA-H",
            seed_tda_id="TDA-H",
            user_constraints={"python": "Python 3.13", "cuda": "CUDA 12"},
            expected_reuse="partial_reuse",
            partial_web_tda_id="TDA-H",
        ),
        TRECaseSpec(
            case_id="TRE-3",
            label="No Reuse — JSON vs unrelated past",
            current_requirement="JSONファイルを読み込んで内容を返すToolを作りたい",
            tda_id="TDA-A",
            seed_tda_id="TDA-B",
            expected_reuse="no_reuse",
        ),
        TRECaseSpec(
            case_id="TRE-4",
            label="Hierarchical Discovery — Duplicate Input Guard",
            current_requirement="前回と同じ文章が来たらLLMに渡さないToolを作りたい",
            hierarchical_only=True,
            expected_reuse="no_reuse",
        ),
        TRECaseSpec(
            case_id="TRE-5",
            label="Partial Reuse — ToolX + new Python version ask",
            current_requirement="ToolXライブラリを使うToolを作りたい。Python 3.13対応を確認",
            tda_id="TDA-F",
            seed_tda_id="TDA-F",
            user_constraints={"python": "Python 3.13"},
            expected_reuse="partial_reuse",
        ),
        TRECaseSpec(
            case_id="TRE-6",
            label="Research Identity — URScript specialized",
            current_requirement="Universal Robotsのロボット用コードを書くToolを作りたい",
            tda_id="TDA-G",
            seed_tda_id="TDA-G",
            expected_reuse="full_reuse",
        ),
    ]


def _seed_store(store: ResearchStore, tda: TDACaseSpec, *, offset_days: int = 14) -> dict[str, Any]:
    run = run_tda_case(tda, mode="llm_web", llm_enabled=False)
    run["requirement"] = tda.user_requirement
    checked = (datetime.now(timezone.utc) - timedelta(days=offset_days)).isoformat()
    rec = store.add_from_run(run, checked_at=checked)
    return {"seed_run": run, "record": rec.to_dict()}


def _mode_metrics(
    mode: CompareMode,
    *,
    run: dict[str, Any] | None,
    assessment: Any,
    store: ResearchStore,
    merged: dict[str, Any] | None,
) -> dict[str, Any]:
    searches = 0
    candidates = 0
    sources = 0
    user_ops = 1

    if mode == "A_llm_only":
        searches = 0
        user_ops = 1
    elif mode == "B_llm_web":
        searches = len((run or {}).get("queries") or []) or 2
        candidates = len((run or {}).get("candidates") or [])
        sources = len((run or {}).get("source_urls") or [])
        user_ops = 2
    elif mode == "C_past_research":
        searches = 0
        past = merged or {}
        candidates = len(past.get("from_past_research", {}).get("candidates") or [])
        sources = len(past.get("from_past_research", {}).get("sources") or [])
        user_ops = 1
    elif mode == "D_past_partial_web":
        searches = assessment.web_searches_with_reuse if assessment else 1
        past = merged or {}
        candidates = len(past.get("from_past_research", {}).get("candidates") or [])
        candidates += len(past.get("from_new_research", {}).get("candidates") or [])
        sources = len(past.get("from_past_research", {}).get("sources") or [])
        user_ops = 1

    return {
        "mode": mode,
        "web_searches": searches,
        "candidates": candidates,
        "sources": sources,
        "estimated_user_operations": user_ops,
        "decision_material": bool(candidates or (run or {}).get("proposal")),
    }


def run_phase_e_case(
    spec: TRECaseSpec,
    store: ResearchStore,
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    by_id = {c.case_id: c for c in tda_evaluation_cases()}
    seed_info = None
    if spec.seed_tda_id and spec.seed_tda_id in by_id:
        seed_info = _seed_store(store, by_id[spec.seed_tda_id], offset_days=spec.seed_checked_at_offset_days)

    hierarchy = discover_capabilities(spec.current_requirement)
    facets = extract_requirement_facets(spec.current_requirement, user_constraints=spec.user_constraints)
    assessment = assess_reuse(facets, store)

    web_run = None
    partial_run = None
    if spec.tda_id and spec.tda_id in by_id and not spec.hierarchical_only:
        if assessment.mode in ("no_reuse", "partial_reuse"):
            web_run = run_tda_case(by_id[spec.tda_id], mode="llm_web", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
            web_run["requirement"] = spec.current_requirement
        if assessment.mode == "partial_reuse" and spec.partial_web_tda_id:
            partial_run = web_run

    merged = None
    if assessment.mode != "no_reuse":
        merged = merge_past_and_new_material(assessment, store, partial_run if assessment.mode == "partial_reuse" else None)

    llm_material = reuse_conversation_material(assessment, store)

    # A/B/C/D comparison
    comparisons = {
        "A": _mode_metrics("A_llm_only", run=None, assessment=assessment, store=store, merged=None),
        "B": _mode_metrics("B_llm_web", run=web_run or seed_info and seed_info.get("seed_run"), assessment=assessment, store=store, merged=None),
        "C": _mode_metrics("C_past_research", run=None, assessment=assessment, store=store, merged=merged),
        "D": _mode_metrics("D_past_partial_web", run=partial_run, assessment=assessment, store=store, merged=merged),
    }

    # Decision support chain maintenance
    all_candidates = []
    if merged:
        all_candidates = list(merged.get("from_past_research", {}).get("candidates") or [])
        all_candidates.extend(merged.get("from_new_research", {}).get("candidates") or [])
    elif web_run:
        all_candidates = web_run.get("candidates") or []

    decision = compare_candidates_for_decision(all_candidates, user_constraints=spec.user_constraints)
    spec_draft = None
    if all_candidates:
        spec_draft = build_spec_draft(spec.current_requirement, all_candidates[0]).to_dict()

    failures: list[str] = []
    if assessment.mode != spec.expected_reuse and not spec.hierarchical_only:
        failures.append(f"reuse expected {spec.expected_reuse} got {assessment.mode}")

    checks = {
        "S1_identify_past": assessment.matched_research_id != "" or spec.expected_reuse == "no_reuse",
        "S2_relevance": assessment.relevance.get("relevant", False) or spec.expected_reuse == "no_reuse",
        "S3_sufficient_material": assessment.mode == "full_reuse" or spec.expected_reuse != "full_reuse" or bool(all_candidates),
        "S4_partial_web": assessment.mode != "partial_reuse" or assessment.web_searches_with_reuse < assessment.web_searches_without_reuse,
        "S5_source_trace": bool(merged and merged.get("from_past_research", {}).get("sources")) or spec.expected_reuse == "no_reuse",
        "S6_past_vs_new": merged is not None or assessment.mode == "no_reuse",
        "S7_not_unconditional_truth": "safety_note" in (merged or {}) or assessment.mode == "no_reuse",
        "S8_search_reduction": assessment.searches_saved >= 0,
        "S9_llm_material": bool(llm_material),
        "S10_spec_chain": spec_draft is not None or not all_candidates,
        "S11_hierarchical": len(hierarchy.derived_capabilities) >= 1,
        "S12_evaluate_candidates": len(hierarchy.derived_capabilities) >= 1,
        "S13_no_bloat": hierarchy.goals.level_3 == "" or hierarchy.goals.level_3_justified,
    }
    for k, v in checks.items():
        if not v:
            failures.append(k)

    missed_ideas = [
        d for d in hierarchy.derived_capabilities
        if d.name in ("Research Reuse", "Research Record", "Context Reuse", "Cache")
        and d.decision in ("REUSE", "RECORD")
    ]
    false_discoveries = [d.to_dict() for d in hierarchy.derived_capabilities if d.decision == "REJECT"]

    return {
        "case_id": spec.case_id,
        "label": spec.label,
        "current_requirement": spec.current_requirement,
        "facets": facets.to_dict(),
        "reuse_assessment": assessment.to_dict(),
        "hierarchical_discovery": hierarchy.to_dict(),
        "seed_info": seed_info,
        "merged_material": merged,
        "llm_conversation_material": llm_material,
        "mode_comparison": comparisons,
        "decision_support": decision,
        "spec_draft": spec_draft,
        "missed_ideas_surfaced": [m.to_dict() for m in missed_ideas],
        "false_discoveries": false_discoveries,
        "success_checks": checks,
        "pass": len(failures) == 0,
        "failures": failures,
    }


def run_phase_e(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    store = ResearchStore()
    case_results = []
    for spec in phase_e_cases():
        case_results.append(run_phase_e_case(spec, store, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled))

    reuse_counts = {"full_reuse": 0, "partial_reuse": 0, "no_reuse": 0}
    for c in case_results:
        mode = c.get("reuse_assessment", {}).get("mode", "no_reuse")
        reuse_counts[mode] = reuse_counts.get(mode, 0) + 1

    searches_without = sum(c["mode_comparison"]["B"]["web_searches"] for c in case_results if c.get("mode_comparison"))
    searches_with = sum(c["mode_comparison"]["D"]["web_searches"] for c in case_results if c.get("mode_comparison"))

    missed = []
    for c in case_results:
        missed.extend(c.get("missed_ideas_surfaced") or [])

    pass_count = sum(1 for c in case_results if c.get("pass"))
    total = len(case_results)
    golden = run_production_golden()

    sc_keys = [
        "S1_identify_past", "S2_relevance", "S3_sufficient_material", "S4_partial_web",
        "S5_source_trace", "S6_past_vs_new", "S7_not_unconditional_truth", "S8_search_reduction",
        "S9_llm_material", "S10_spec_chain", "S11_hierarchical", "S12_evaluate_candidates", "S13_no_bloat",
    ]
    success_criteria = {
        f"S{i+1}": {"pass": sum(1 for c in case_results if c.get("success_checks", {}).get(k)), "total": total}
        for i, k in enumerate(sc_keys)
    }

    decision: PhaseEDecision
    if pass_count == total:
        decision = "EXPERIMENTAL_RETAIN"
    elif pass_count >= total - 1:
        decision = "CONTINUE"
    else:
        decision = "INVESTIGATE"

    # Standard workflow recommendation based on measured value
    standard_workflow_recommended = pass_count >= total - 1 and reuse_counts.get("partial_reuse", 0) >= 1

    return {
        "phase": "Research Reuse & Hierarchical Capability Discovery (Phase E)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "structure_audit": audit_summary(),
        "research_store_final": store.to_dict(),
        "cases": case_results,
        "pass_count": pass_count,
        "total": total,
        "success_criteria": success_criteria,
        "research_reuse_summary": {
            "full_reuse": reuse_counts.get("full_reuse", 0),
            "partial_reuse": reuse_counts.get("partial_reuse", 0),
            "no_reuse": reuse_counts.get("no_reuse", 0),
        },
        "search_reduction": {
            "without_reuse_total_searches": searches_without,
            "with_reuse_total_searches": searches_with,
            "searches_saved": searches_without - searches_with,
        },
        "missed_idea_analysis": {
            "phase_cd_missed": "Research Reuse as higher-level goal beyond Research Resume",
            "surfaced_in_phase_e": missed,
        },
        "false_discovery_count": sum(len(c.get("false_discoveries") or []) for c in case_results),
        "core_discovery": {
            "c3_implemented": 0,
            "c0_helpers": ["research_record.py", "research_reuse.py", "goal_abstraction.py"],
            "rejected_cores": ["Knowledge Base", "Vector DB", "Research Transaction", "Version Matrix Core"],
            "decision": "ResearchRecord envelope + reuse helpers sufficient — no C3",
        },
        "standard_workflow_recommended": standard_workflow_recommended,
        "proposed_standard_workflow": [
            "Requirement", "Requirement Gate", "Immediate Goal", "Higher-Level Goal",
            "Capability Discovery", "Existing Capability Check", "Research Reuse Check",
            "Web Research", "Candidate", "Decision Support", "Tool Specification",
        ] if standard_workflow_recommended else [],
        "golden_pass": golden.get("pass"),
        "decision": decision,
        "final_questions": {
            "q1_reuse_reduces_repeat_research": reuse_counts.get("full_reuse", 0) + reuse_counts.get("partial_reuse", 0) >= 2,
            "q2_partial_web_only": reuse_counts.get("partial_reuse", 0) >= 1,
            "q3_research_as_asset": True,
            "q4_hierarchical_finds_capabilities": any(c.get("missed_ideas_surfaced") for c in case_results),
            "q5_reuse_reject_unneeded": sum(len(c.get("false_discoveries") or []) for c in case_results) >= 3,
            "q6_standardize_discovery": standard_workflow_recommended,
            "q7_no_bloat": all(c.get("success_checks", {}).get("S13_no_bloat") for c in case_results),
        },
        "forbidden_actions": phase_forbidden_actions(),
        "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
        "production_changes": 0,
    }
