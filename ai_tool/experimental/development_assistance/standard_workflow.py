"""TDA Standard Workflow — orchestration over existing modules (not a new Core)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from ai_tool.experimental.development_assistance.api_observation import observe_apis_from_sources
from ai_tool.experimental.development_assistance.decision_factors import compare_candidates_for_decision
from ai_tool.experimental.development_assistance.decision_presentation import format_decision_comparison
from ai_tool.experimental.development_assistance.discovery_skip_policy import classify_discovery
from ai_tool.experimental.development_assistance.facet_coverage import (
    asserts_coverage_not_a_decision,
    discover_coverage,
)
from ai_tool.experimental.development_assistance.facet_discovery import (
    asserts_not_a_decision,
    discover_facets,
    plan_follow_up,
)
from ai_tool.experimental.development_assistance.goal_abstraction import discover_capabilities
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog
from ai_tool.experimental.development_assistance.relevant_facet_router import (
    RelevantSlice,
    RoutingMode,
    format_slice_material,
    items_from_dicts,
    route_relevant_facets,
    slice_to_decision_factors,
)
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import (
    assess_reuse,
    extract_requirement_facets,
    merge_past_and_new_material,
    reuse_conversation_material,
)
from ai_tool.experimental.development_assistance.spec_draft import build_spec_draft

ChatFn = Callable[..., Any]
WorkflowStop = Literal[
    "COMPLETE",
    "EARLY_EXIT_GATE",
    "EARLY_EXIT_FULL_REUSE",
    "PARTIAL_REUSE_WEB",
    "FULL_WEB_RESEARCH",
]
FacetDiscoveryFlag = Literal["off", "conditional"]


@dataclass
class WorkflowStageRecord:
    stage: str
    outcome: str
    skipped: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StandardWorkflowResult:
    requirement: str
    stages: list[WorkflowStageRecord]
    stop_reason: WorkflowStop
    gate: dict[str, Any]
    goals: dict[str, Any]
    capability_discovery: dict[str, Any]
    reuse_assessment: dict[str, Any]
    web_searches: int
    candidates: list[dict[str, Any]]
    decision_support: dict[str, Any]
    spec_draft: dict[str, Any] | None
    llm_material: str
    preserved_ideas: list[dict[str, Any]]
    complexity_steps: int
    early_exit_at: str = ""
    facet_routing: str = "off"
    relevant_slice: dict[str, Any] = field(default_factory=dict)
    facet_discovery: str = "off"
    coverage_overlay: bool = False
    discovery_decision: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _legacy_workflow(
    requirement: str,
    tda: Any | None,
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    """Phase B style: Gate → Web Research (no goal abstraction, no reuse)."""
    gate = assess_research_requirement(
        requirement,
        force_research=getattr(tda, "force_research", None) if tda else None,
        case_hint=getattr(tda, "case_id", None) if tda else None,
    )
    searches = 0
    candidates: list[dict[str, Any]] = []
    if gate.decision == "RESEARCH_REQUIRED" and tda is not None:
        run = run_tda_case(tda, mode="llm_web", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
        searches = len(run.get("queries") or []) or (2 if run.get("candidates") else 0)
        candidates = run.get("candidates") or []
    elif gate.decision == "RESEARCH_NOT_REQUIRED":
        run = run_tda_case(tda, mode="llm_only", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled) if tda else {}
        candidates = run.get("candidates") or []
    stages = ["Requirement Gate", "Web Research"]
    return {
        "workflow": "legacy_phase_b",
        "stages_executed": stages,
        "stage_count": len(stages),
        "gate": gate.to_dict(),
        "web_searches": searches,
        "candidates": candidates,
        "goal_abstraction": None,
        "reuse_check": None,
        "capability_discovery": None,
        "early_exit": gate.decision == "RESEARCH_NOT_REQUIRED",
    }


def run_standard_workflow(
    requirement: str,
    *,
    tda: Any | None = None,
    store: ResearchStore | None = None,
    idea_catalog: IdeaCatalog | None = None,
    user_constraints: dict[str, str] | None = None,
    api_names: list[str] | None = None,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
    facet_routing: RoutingMode = "off",
    facet_discovery: FacetDiscoveryFlag = "off",
    coverage_overlay: bool = True,
    session: dict[str, Any] | None = None,
) -> StandardWorkflowResult:
    """Standard TDA workflow — skips stages when existing capability suffices.

    facet_discovery default is off (Phase F unchanged). Experimental
    facet_discovery='conditional' uses Policy D + optional coverage overlay.
    """
    stages: list[WorkflowStageRecord] = []
    research_store = store or ResearchStore()
    ideas = idea_catalog or IdeaCatalog()
    session = session or {}

    # 1. Requirement Gate
    gate = assess_research_requirement(requirement, force_research=getattr(tda, "force_research", None) if tda else None)
    stages.append(WorkflowStageRecord("Requirement Gate", gate.decision, detail=gate.to_dict()))

    # 2–4. Goal abstraction L0–L3
    hierarchy = discover_capabilities(requirement)
    goals = hierarchy.goals.to_dict()
    stages.append(WorkflowStageRecord("L0-L2 Goal Abstraction", "done", detail=goals))
    if goals.get("level_3") and goals.get("level_3_justified"):
        stages.append(WorkflowStageRecord("L3 System Goal", "justified", detail={"level_3": goals["level_3"]}))

    # 5. Capability Discovery + Existing Check
    derived = [d.to_dict() for d in hierarchy.derived_capabilities]
    reuse_existing = [d for d in hierarchy.derived_capabilities if d.decision == "REUSE"]
    rejected = [d for d in hierarchy.derived_capabilities if d.decision == "REJECT"]
    for d in hierarchy.derived_capabilities:
        if d.decision in ("REJECT", "DEFER", "RECORD"):
            ideas.add_from_discovery(
                name=d.name,
                higher_goal=goals.get("level_2", ""),
                decision=d.decision,
                alternative=d.existing_alternative,
                reason=d.reason,
            )
    stages.append(
        WorkflowStageRecord(
            "Capability Discovery",
            f"{len(derived)} derived, {len(reuse_existing)} REUSE, {len(rejected)} REJECT",
            detail={"derived": derived},
        )
    )

    re_eval = ideas.re_evaluate_for_requirement(requirement)
    if re_eval:
        stages.append(
            WorkflowStageRecord(
                "Idea Re-evaluation",
                f"{len(re_eval)} prior ideas noted",
                detail={"ideas": [i.to_dict() for i in re_eval]},
            )
        )

    discovery_decision: dict[str, Any] = {}
    coverage_dict: dict[str, Any] = {}
    needed_ids: list[str] = []
    discovery_invoked = False
    follow_plan = None
    if facet_discovery == "conditional":
        policy = classify_discovery(requirement, policy="D", store=research_store)
        discovery_decision = policy.to_dict()
        discovery_invoked = bool(policy.invoked)
        if not discovery_invoked:
            stages.append(
                WorkflowStageRecord(
                    "Facet Discovery",
                    policy.mode,
                    skipped=True,
                    detail={"reason": "policy skip", "policy": discovery_decision},
                )
            )
        elif coverage_overlay:
            cov = discover_coverage(requirement, research_store, mode="GCR", session=session)
            coverage_dict = cov.to_dict()
            if policy.mode == "DISCOVERY_OPTIONAL":
                needed_ids = list(cov.candidate_ids())
            else:
                needed_ids = list(dict.fromkeys(cov.required_ids() + cov.candidate_ids()))
            stages.append(
                WorkflowStageRecord(
                    "Facet Discovery",
                    policy.mode,
                    detail={
                        "policy": discovery_decision,
                        "required": cov.required_ids(),
                        "candidates": cov.candidate_ids(),
                        "unknown": cov.unknown_ids(),
                        "unresolved": cov.unresolved,
                        "not_a_decision": asserts_coverage_not_a_decision(cov),
                    },
                )
            )
            follow_plan = plan_follow_up(requirement, research_store, session=session)
        else:
            disc = discover_facets(requirement, research_store, session=session)
            needed_ids = list(disc.catalog_ids())
            coverage_dict = {"mode": "K", "catalog_ids": needed_ids, "concepts": disc.concepts}
            stages.append(
                WorkflowStageRecord(
                    "Facet Discovery",
                    policy.mode,
                    detail={
                        "policy": discovery_decision,
                        "catalog_ids": needed_ids,
                        "not_a_decision": asserts_not_a_decision(disc),
                    },
                )
            )
            follow_plan = plan_follow_up(requirement, research_store, session=session)

    web_searches = 0
    candidates: list[dict[str, Any]] = []
    reuse_dict: dict[str, Any] = {}
    stop: WorkflowStop = "FULL_WEB_RESEARCH"
    early_exit = ""

    gate_only_exit = gate.decision == "RESEARCH_NOT_REQUIRED" and not (
        facet_discovery == "conditional" and discovery_invoked
    )

    # Early exit: gate says no research (and experimental discovery did not override)
    if gate_only_exit:
        stop = "EARLY_EXIT_GATE"
        early_exit = "Requirement Gate"
        stages.append(WorkflowStageRecord("Research Reuse Check", "skipped", skipped=True, detail={"reason": "gate"}))
        stages.append(WorkflowStageRecord("Web Research", "skipped", skipped=True, detail={"reason": "gate"}))
        if tda:
            run = run_tda_case(tda, mode="llm_only", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
            candidates = run.get("candidates") or []
    else:
        # 6. Research Reuse Check
        facets = extract_requirement_facets(requirement, user_constraints=user_constraints)
        assessment = assess_reuse(facets, research_store)
        reuse_dict = assessment.to_dict()
        stages.append(WorkflowStageRecord("Research Reuse Check", assessment.mode, detail=reuse_dict))

        merged = None
        skip_web_from_discovery = bool(
            follow_plan is not None and not follow_plan.missing and research_store.records
        )
        if skip_web_from_discovery:
            stop = "EARLY_EXIT_FULL_REUSE"
            early_exit = "Research Reuse (discovery missing=0)"
            web_searches = 0
            merged = merge_past_and_new_material(assessment, research_store, None)
            candidates = list(merged.get("from_past_research", {}).get("candidates") or [])
            stages.append(
                WorkflowStageRecord(
                    "Web Research",
                    "skipped",
                    skipped=True,
                    detail={"reason": "existing evidence covers requested facets", "searches": 0},
                )
            )
        elif follow_plan is not None and follow_plan.missing:
            stop = "PARTIAL_REUSE_WEB"
            web_searches = follow_plan.searches_estimate
            if tda:
                run = run_tda_case(tda, mode="llm_web", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
                web_searches = min(len(run.get("queries") or []) or web_searches, web_searches or 1)
                merged = merge_past_and_new_material(assessment, research_store, run)
                candidates = list(merged.get("from_past_research", {}).get("candidates") or [])
                candidates.extend(merged.get("from_new_research", {}).get("candidates") or [])
            stages.append(
                WorkflowStageRecord(
                    "Web Research",
                    "partial",
                    detail={"missing": follow_plan.missing, "searches": web_searches},
                )
            )
        elif assessment.mode == "full_reuse":
            stop = "EARLY_EXIT_FULL_REUSE"
            early_exit = "Research Reuse (full)"
            web_searches = 0
            merged = merge_past_and_new_material(assessment, research_store, None)
            candidates = list(merged.get("from_past_research", {}).get("candidates") or [])
            stages.append(WorkflowStageRecord("Web Research", "skipped", skipped=True, detail={"reason": "full_reuse"}))
        elif assessment.mode == "partial_reuse":
            stop = "PARTIAL_REUSE_WEB"
            web_searches = assessment.web_searches_with_reuse
            if tda:
                run = run_tda_case(tda, mode="llm_web", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
                web_searches = len(run.get("queries") or []) or assessment.web_searches_with_reuse
                merged = merge_past_and_new_material(assessment, research_store, run)
                candidates = list(merged.get("from_past_research", {}).get("candidates") or [])
                candidates.extend(merged.get("from_new_research", {}).get("candidates") or [])
            stages.append(
                WorkflowStageRecord(
                    "Web Research",
                    "partial",
                    detail={"missing": assessment.missing_fields, "searches": web_searches},
                )
            )
        else:
            stop = "FULL_WEB_RESEARCH"
            if tda:
                run = run_tda_case(tda, mode="llm_web", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
                web_searches = len(run.get("queries") or []) or 2
                candidates = run.get("candidates") or []
                research_store.add_from_run({**run, "requirement": requirement})
            stages.append(WorkflowStageRecord("Web Research", "full", detail={"searches": web_searches}))

    # Relevant Facet Routing. Default off adds no stage (Phase F unchanged).
    # Gate early-exit never runs the router so JSON tools stay simple.
    # Conditional discovery: empty needed must not dump the catalog.
    relevant_slice_dict: dict[str, Any] = {}
    run_router = facet_routing != "off"
    if run_router and facet_discovery == "off" and gate.decision == "RESEARCH_NOT_REQUIRED":
        run_router = False
    if run_router and facet_discovery == "conditional" and not discovery_invoked:
        run_router = False
    if run_router and facet_discovery == "conditional" and discovery_invoked and not needed_ids:
        stages.append(
            WorkflowStageRecord(
                "Relevant Facet Routing",
                "skipped",
                skipped=True,
                detail={"reason": "no needed facet ids; refuse catalog dump"},
            )
        )
        run_router = False
    if run_router:
        route_kw: dict[str, Any] = {"mode": facet_routing}
        if facet_discovery == "conditional" and needed_ids:
            route_kw["needed_facet_ids"] = needed_ids
        slice_ = route_relevant_facets(requirement, list(research_store.records), **route_kw)
        relevant_slice_dict = slice_.to_dict()
        stages.append(
            WorkflowStageRecord(
                "Relevant Facet Routing",
                f"{slice_.mode}:{len(slice_.facet_ids)} facets",
                skipped=slice_.skipped,
                detail={"facet_ids": slice_.facet_ids, "skipped": slice_.skipped, "needed": needed_ids},
            )
        )

    # API observation (when requested)
    if api_names and candidates:
        sources = [{"url": c.get("url"), "main_text": c.get("description", ""), "title": c.get("source_title")} for c in candidates]
        api_obs = observe_apis_from_sources(api_names, sources)
        stages.append(
            WorkflowStageRecord(
                "API Observation",
                "done",
                detail={"observations": [a.to_dict() for a in api_obs]},
            )
        )

    # Decision Support
    decision = compare_candidates_for_decision(candidates, user_constraints=user_constraints or {})
    if coverage_dict:
        decision["coverage"] = {
            "required": list(coverage_dict.get("required") or []),
            "candidates": list(coverage_dict.get("candidates") or []),
            "unknown": list(coverage_dict.get("unknown") or []),
            "unresolved": list(coverage_dict.get("unresolved") or []),
            "keep": list(coverage_dict.get("keep_facets") or []),
        }
        decision["discovery_policy"] = discovery_decision
    if relevant_slice_dict.get("items"):
        items = items_from_dicts(list(relevant_slice_dict["items"]))
        slice_factors = slice_to_decision_factors(items)
        decision["relevant_slice"] = relevant_slice_dict
        decision["slice_factors"] = [f.to_dict() for f in slice_factors]
        syn = {
            "candidate_id": "relevant_slice",
            "name": "Relevant Research Slice",
            "type": "Vendor controller",
            "version": next(
                (i.get("version") for i in relevant_slice_dict["items"] if i.get("version")),
                "UNKNOWN",
            ),
            "license": "UNKNOWN",
            "source_category": "Official Documentation",
            "source_title": "Routed facet_records",
            "url": "",
            "unknowns": [
                u
                for i in relevant_slice_dict["items"]
                for u in (i.get("unknown") or [])
            ],
            "conflicts": [
                {"note": c}
                for i in relevant_slice_dict["items"]
                for c in (i.get("conflicts") or [])
            ],
        }
        decision["slice_presentation"] = format_decision_comparison(
            [syn],
            {"relevant_slice": [f.to_dict() for f in slice_factors]},
        )
    stages.append(
        WorkflowStageRecord(
            "Decision Support",
            "done",
            detail={
                "hints": decision.get("comparison_hints"),
                "slice_ids": relevant_slice_dict.get("facet_ids") or [],
            },
        )
    )

    # Tool Spec Draft
    spec = build_spec_draft(requirement, candidates[0]).to_dict() if candidates else None
    if spec and relevant_slice_dict.get("items"):
        extra_unknown = [
            u for i in relevant_slice_dict["items"] for u in (i.get("unknown") or [])
        ]
        extra_conflict = [
            c for i in relevant_slice_dict["items"] for c in (i.get("conflicts") or [])
        ]
        spec["unknowns"] = list(spec.get("unknowns") or []) + extra_unknown
        spec["constraints"] = list(spec.get("constraints") or []) + [
            f"slice_conflict: {c}" for c in extra_conflict
        ]
    if spec:
        stages.append(WorkflowStageRecord("Tool Specification Draft", "done", detail={"tool_name": spec.get("tool_name")}))

    llm_material = reuse_conversation_material(
        assess_reuse(extract_requirement_facets(requirement, user_constraints=user_constraints), research_store),
        research_store,
    )
    if relevant_slice_dict.get("items"):
        items = items_from_dicts(list(relevant_slice_dict["items"]))
        llm_material = (
            llm_material
            + "\n\n"
            + format_slice_material(
                RelevantSlice(
                    mode=facet_routing,
                    requirement=requirement,
                    facet_ids=list(relevant_slice_dict.get("facet_ids") or []),
                    items=items,
                )
            )
        )

    return StandardWorkflowResult(
        requirement=requirement,
        stages=[s.to_dict() for s in stages],
        stop_reason=stop,
        gate=gate.to_dict(),
        goals=goals,
        capability_discovery=hierarchy.to_dict(),
        reuse_assessment=reuse_dict,
        web_searches=web_searches,
        candidates=candidates,
        decision_support=decision,
        spec_draft=spec,
        llm_material=llm_material,
        preserved_ideas=[i.to_dict() for i in ideas.ideas],
        complexity_steps=len(stages),
        early_exit_at=early_exit,
        facet_routing=facet_routing,
        relevant_slice=relevant_slice_dict,
        facet_discovery=facet_discovery,
        coverage_overlay=bool(coverage_overlay and facet_discovery == "conditional"),
        discovery_decision=discovery_decision,
        coverage=coverage_dict,
    )


def compare_workflows(
    requirement: str,
    *,
    tda: Any | None = None,
    store: ResearchStore | None = None,
    user_constraints: dict[str, str] | None = None,
    api_names: list[str] | None = None,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    """Before (legacy) vs After (standard) workflow comparison."""
    before = _legacy_workflow(requirement, tda, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
    after = run_standard_workflow(
        requirement,
        tda=tda,
        store=store,
        user_constraints=user_constraints,
        api_names=api_names,
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )
    return {
        "requirement": requirement,
        "before": before,
        "after": after.to_dict(),
        "search_reduction": before["web_searches"] - after.web_searches,
        "complexity_delta": after.complexity_steps - before["stage_count"],
        "early_exit": after.early_exit_at or None,
        "capability_discovery_added": after.capability_discovery is not None,
    }
