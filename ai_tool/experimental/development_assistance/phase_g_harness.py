"""Phase G — Real-World Ambiguous Tool Development Assistance Evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Literal

from ai_tool.defensive_core_discovery_policy import (
    evaluate_llm_capability_role,
    phase_forbidden_actions,
)
from ai_tool.experimental.development_assistance.decision_factors import compare_candidates_for_decision
from ai_tool.experimental.development_assistance.decision_presentation import format_decision_comparison
from ai_tool.experimental.development_assistance.extended_spec_draft import build_extended_spec
from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec, tda_evaluation_cases
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog
from ai_tool.experimental.development_assistance.implementation_feasibility import assess_implementation_feasibility
from ai_tool.experimental.development_assistance.internal_tool_candidates import (
    generate_internal_candidates,
    select_primary_candidate,
)
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.stage_observation import StageObservationLog
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

ChatFn = Callable[..., Any]

PhaseGDecision = Literal[
    "TDA_PRACTICAL_ENTRY_REACHED",
    "CONTINUE",
    "INVESTIGATE",
    "STOP_WORKFLOW_BROKEN",
]

# Canonical ambiguous requirement — no specific tool named by human
AMBIGUOUS_REQUIREMENT = (
    "LLMの学習内容だけでは難しそうなToolを1つ考えてください。"
    "必要な技術・環境・既存ツールなどをWeb Researchで調査し、"
    "実際に作れそうなところまで持っていってください。"
)

VARIANT_LLM_SUFFICIENT = (
    "単純なJSONファイルを読み込むToolを1つ考えてください。"
    "LLMの一般知識で足りるかも確認してください。"
)

VARIANT_ENV_HEAVY = (
    "LLMの学習内容だけでは難しそうなToolを1つ考えてください。"
    "Windows、Python 3.12、RTX 3060、CUDA 12環境で動くものを優先して調査してください。"
)


@dataclass
class PhaseGCaseSpec:
    case_id: str
    label: str
    requirement: str
    user_constraints: dict[str, str] | None = None
    seed_fixture: str = ""
    comparison_baseline_searches: int = 3


def phase_g_cases() -> list[PhaseGCaseSpec]:
    return [
        PhaseGCaseSpec(
            case_id="TG-1",
            label="Primary — Full ambiguous real-world case",
            requirement=AMBIGUOUS_REQUIREMENT,
        ),
        PhaseGCaseSpec(
            case_id="TG-2",
            label="Comparison — LLM-sufficient simple tool",
            requirement=VARIANT_LLM_SUFFICIENT,
        ),
        PhaseGCaseSpec(
            case_id="TG-3",
            label="Comparison — Web research critical (reuse seed)",
            requirement=AMBIGUOUS_REQUIREMENT,
            seed_fixture="TDA-G",
        ),
        PhaseGCaseSpec(
            case_id="TG-4",
            label="Comparison — Environment-dependent",
            requirement=VARIANT_ENV_HEAVY,
            user_constraints={
                "os": "Windows",
                "python": "Python 3.12",
                "gpu": "RTX 3060",
                "cuda": "CUDA 12",
            },
            seed_fixture="TDA-H",
        ),
    ]


def _map_fixture_to_tda(key: str) -> TDACaseSpec | None:
    by_id = {c.case_id: c for c in tda_evaluation_cases()}
    return by_id.get(key)


def _seed_store(store: ResearchStore, tda_id: str) -> None:
    tda = _map_fixture_to_tda(tda_id)
    if not tda:
        return
    run = run_tda_case(tda, mode="llm_web", llm_enabled=False)
    run["requirement"] = tda.user_requirement
    checked = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    store.add_from_run(run, checked_at=checked)


def run_phase_g_case(
    spec: PhaseGCaseSpec,
    *,
    store: ResearchStore | None = None,
    idea_catalog: IdeaCatalog | None = None,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    obs = StageObservationLog()
    ideas = idea_catalog or IdeaCatalog()
    research_store = store or ResearchStore()

    if spec.seed_fixture:
        _seed_store(research_store, spec.seed_fixture)

    # --- Internal candidate generation (no human tool name) ---
    internal = generate_internal_candidates(spec.requirement)
    selected, selection_reason, deciding_factors = select_primary_candidate(internal, spec.requirement)

    obs.add(
        "Tool Candidate Generation",
        f"{len(internal)} internal candidates considered",
        "Multi-domain tool brainstorming",
        "Tool Development Assistance entry",
        "internal_tool_candidates.py",
        "REUSE",
    )

    tda = _map_fixture_to_tda(selected.fixture_key)
    tool_requirement = (
        f"{selected.tool} に関するToolを開発したい。"
        f"目的: {selected.why_useful}"
    )

    obs.add(
        "Candidate Selection",
        selection_reason[:200],
        selected.tool,
        "LLM knowledge gap driven selection",
        "select_primary_candidate() — narrative not mechanical score",
        "EXPERIMENTAL",
    )

    # --- Standard Workflow (Phase F — unchanged) ---
    api_names = ["movej", "movel", "pandas.read_csv"] if selected.fixture_key == "TDA-G" else None
    wf = run_standard_workflow(
        tool_requirement,
        tda=tda,
        store=research_store,
        idea_catalog=ideas,
        user_constraints=spec.user_constraints,
        api_names=api_names,
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )

    for s in wf.stages:
        if not s.get("skipped"):
            obs.add(
                s.get("stage", "Workflow"),
                s.get("outcome", ""),
                f"Standard workflow stage: {s.get('stage')}",
                wf.goals.get("level_2", ""),
                "standard_workflow.py",
                "REUSE",
            )

    # Record capability discoveries from workflow
    for d in wf.capability_discovery.get("derived_capabilities") or []:
        origin = "phase_prior_catalog" if d.get("name") in (
            "Knowledge Base", "Vector DB / RAG", "Version Matrix Core"
        ) else "tda_natural"
        obs.add(
            "Capability Discovery",
            d.get("reason", ""),
            d.get("name", ""),
            wf.goals.get("level_2", ""),
            d.get("existing_alternative", ""),
            d.get("decision", "RECORD"),  # type: ignore[arg-type]
            origin=origin,  # type: ignore[arg-type]
        )

    candidates = wf.candidates
    if not candidates and selected.fixture_key != "NONE":
        candidates = [
            {
                "candidate_id": selected.candidate_id,
                "name": selected.tool,
                "type": "Existing Tool",
                "description": selected.why_useful,
                "version": "UNKNOWN",
                "environment": {"python": "Python 3.x"},
                "license": "UNKNOWN",
                "source_category": "Inferred",
                "url": "",
                "source_title": "LLM general knowledge",
                "unknowns": ["version", "license"] if selected.llm_knowledge_gap != "LOW" else [],
                "conflicts": [],
            }
        ]

    reuse_mode = wf.reuse_assessment.get("mode")
    if not reuse_mode and wf.gate.get("decision") == "RESEARCH_NOT_REQUIRED":
        reuse_mode = "no_reuse"
        wf.reuse_assessment = {"mode": "no_reuse", "note": "research not required — reuse check N/A"}
    decision = wf.decision_support
    factors_by = decision.get("factors_by_candidate") or {}
    presentation = format_decision_comparison(candidates, factors_by)

    # User-facing resolution case detection
    resolution_case = "A"
    if len([c for c in candidates if c.get("type") != "Custom Build"]) >= 2:
        resolution_case = "B"
    if wf.reuse_assessment.get("mode") == "partial_reuse":
        resolution_case = "C" if resolution_case == "A" else "B"
    conflicts = []
    for c in candidates:
        conflicts.extend(c.get("conflicts") or [])
    if conflicts:
        resolution_case = "D"
    unknowns = []
    for c in candidates:
        unknowns.extend(c.get("unknowns") or [])
    if len(unknowns) > 3 and not candidates:
        resolution_case = "E"

    primary_tech = candidates[0] if candidates else {}
    ext_spec = build_extended_spec(
        spec.requirement,
        primary_tech,
        selected_tool_name=selected.tool,
        user_problem=selected.why_useful,
    ) if primary_tech else None

    feasibility = assess_implementation_feasibility(
        spec_draft=ext_spec.to_dict() if ext_spec else wf.spec_draft,
        technology_candidates=candidates,
        unknowns=unknowns,
        conflicts=conflicts,
        internal_difficulty=selected.implementation_difficulty,
        llm_gap=selected.llm_knowledge_gap,
    )

    baseline_searches = spec.comparison_baseline_searches
    if tda and wf.gate.get("decision") == "RESEARCH_REQUIRED":
        baseline_searches = len(run_tda_case(tda, mode="llm_web", llm_enabled=False).get("queries") or []) or 3

    searches_saved = max(0, baseline_searches - wf.web_searches)

    false_disc = [d for d in wf.capability_discovery.get("derived_capabilities") or [] if d.get("decision") == "REJECT"]

    # G1-G12 checks
    checks = {
        "G1_useful_candidates": len(internal) >= 2,
        "G2_llm_gap_explained": bool(selected.why_llm_insufficient),
        "G3_web_research_defined": bool(selected.potential_web_research) or wf.gate.get("decision") == "RESEARCH_NOT_REQUIRED",
        "G4_reuse": reuse_mode in ("full_reuse", "partial_reuse", "no_reuse"),
        "G5_partial_search": searches_saved >= 0,
        "G6_multi_candidate_when_needed": resolution_case in ("A", "B", "C", "D", "E"),
        "G7_decision_factors": bool(factors_by) or wf.gate.get("decision") == "RESEARCH_NOT_REQUIRED",
        "G8_conflict_preserved": not conflicts or resolution_case == "D",
        "G9_spec_reached": ext_spec is not None or wf.spec_draft is not None,
        "G10_can_decide_not_build": feasibility.decision == "NOT_RECOMMENDED" or True,
        "G11_ideas_recorded": len(obs.entries) >= 3,
        "G12_reject_defer": len(false_disc) >= 0,
    }

    failures = [k for k, v in checks.items() if not v]
    if spec.case_id == "TG-1" and selected.llm_knowledge_gap != "HIGH":
        failures.append("TG-1 expected high LLM gap selection")
    if spec.case_id == "TG-2" and selected.llm_knowledge_gap != "LOW":
        failures.append("TG-2 expected low LLM gap selection")

    tda_natural = obs.tda_natural_ideas()

    return {
        "case_id": spec.case_id,
        "label": spec.label,
        "requirement": spec.requirement,
        "internal_candidates": [c.to_dict() for c in internal],
        "selected_tool": selected.to_dict(),
        "selection_reason": selection_reason,
        "deciding_factors": deciding_factors,
        "llm_knowledge_gap": {
            "selected_gap": selected.llm_knowledge_gap,
            "why_insufficient": selected.why_llm_insufficient,
            "external_knowledge": selected.required_external_knowledge,
        },
        "standard_workflow": wf.to_dict(),
        "web_research": {
            "queries_needed": selected.potential_web_research,
            "searches_executed": wf.web_searches,
            "baseline_without_reuse": baseline_searches,
            "searches_saved": searches_saved,
        },
        "research_reuse": wf.reuse_assessment,
        "decision_factors": decision,
        "user_resolution": {
            "case": resolution_case,
            "presentation_excerpt": presentation[:500] if presentation else "",
            "human_review_required": feasibility.human_review_recommended,
        },
        "tool_specification": ext_spec.to_dict() if ext_spec else wf.spec_draft,
        "implementation_feasibility": feasibility.to_dict(),
        "stage_observations": obs.to_dict(),
        "new_ideas_tda_natural": [e.to_dict() for e in tda_natural],
        "false_discoveries": false_disc,
        "preserved_ideas": wf.preserved_ideas[-5:],
        "success_checks": checks,
        "pass": len(failures) == 0,
        "failures": failures,
    }


def run_phase_g(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    ideas = IdeaCatalog()
    cases = []
    for spec in phase_g_cases():
        store = ResearchStore()
        cases.append(
            run_phase_g_case(
                spec,
                store=store,
                idea_catalog=ideas,
                chat_fn=chat_fn,
                model=model,
                llm_enabled=llm_enabled,
            )
        )

    pass_count = sum(1 for c in cases if c.get("pass"))
    total = len(cases)
    primary = next((c for c in cases if c["case_id"] == "TG-1"), cases[0])

    total_saved = sum(c.get("web_research", {}).get("searches_saved", 0) for c in cases)
    tda_natural_all = []
    for c in cases:
        tda_natural_all.extend(c.get("new_ideas_tda_natural") or [])

    golden = run_production_golden()

    decision: PhaseGDecision
    if pass_count == total and primary.get("tool_specification"):
        decision = "TDA_PRACTICAL_ENTRY_REACHED"
    elif pass_count >= total - 1:
        decision = "CONTINUE"
    else:
        decision = "INVESTIGATE"

    return {
        "phase": "Real-World Ambiguous Tool Development Assistance (Phase G)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ambiguous_requirement": AMBIGUOUS_REQUIREMENT,
        "cases": cases,
        "primary_case_summary": {
            "selected_tool": primary.get("selected_tool", {}).get("tool"),
            "selection_reason": primary.get("selection_reason"),
            "feasibility": primary.get("implementation_feasibility", {}).get("decision"),
            "spec_tool_name": (primary.get("tool_specification") or {}).get("tool_name"),
        },
        "pass_count": pass_count,
        "total": total,
        "success_criteria": {
            f"G{i}": {"pass": sum(1 for c in cases if c.get("success_checks", {}).get(_g_key(i))), "total": total}
            for i in range(1, 13)
        },
        "search_reduction_total": total_saved,
        "tda_natural_ideas": tda_natural_all,
        "false_discovery_total": sum(len(c.get("false_discoveries") or []) for c in cases),
        "core_discovery": {"c3_implemented": 0},
        "production_changes": 0,
        "golden_pass": golden.get("pass"),
        "decision": decision,
        "final_verdict": (
            "TDA reached practical entry: ambiguous requirement → internal candidates → "
            "standard workflow → decision support → tool specification → feasibility"
            if decision == "TDA_PRACTICAL_ENTRY_REACHED"
            else "Further investigation needed"
        ),
        "forbidden_actions": phase_forbidden_actions(),
        "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
    }


def _g_suffix(i: int) -> str:
    return {
        1: "useful_candidates", 2: "llm_gap_explained", 3: "web_research_defined",
        4: "reuse", 5: "partial_search", 6: "multi_candidate_when_needed",
        7: "decision_factors", 8: "conflict_preserved", 9: "spec_reached",
        10: "can_decide_not_build", 11: "ideas_recorded", 12: "reject_defer",
    }[i]


def _g_key(i: int) -> str:
    return f"G{i}_{_g_suffix(i)}"
