"""Normal Development with Defensive Core Discovery — phase harness.

Track A: assess current Production problems (minimal fix if measured).
Track B: observe future Core candidates without mandating implementation.

Does NOT modify Production, Agent, Registry, or Prompt.
"""
from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.defensive_core_discovery_policy import (
    CoreCandidate,
    CostBenefitMatrix,
    evaluate_llm_capability_role,
    existing_core_registry,
    normal_development_operating_model,
    phase_forbidden_actions,
    phase_success_criteria,
    policy_summary_for_harnesses,
    track_b_defer_priorities,
    track_b_extend_priorities,
)
from ai_tool.web_tool_autonomous_improvement import run_autonomous_improvement
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[1]

PhaseDecision = Literal[
    "CONTINUE",
    "IMPLEMENT",
    "INVESTIGATE",
    "EXPERIMENTAL",
    "RECORD",
    "HUMAN_REVIEW_REQUIRED",
    "STOP_NO_CHANGE",
]


@dataclass
class TrackBCandidate:
    id: str
    name: str
    current_use: str
    future_uses: list[str]
    reuse_potential: str
    defensive_value: str
    implementation_cost: str
    regression_risk: str
    production_coupling: str
    existing_core_overlap: str
    reversibility: str
    sunset_conditions: list[str]
    classification: Literal["C0", "C1", "C2", "C3", "C4"]
    llm_relationship: str
    decision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_report_row(self) -> dict[str, str]:
        return {
            "ID": self.id,
            "Capability": self.name,
            "C0-C4": self.classification,
            "Cost": self.implementation_cost,
            "Benefit": self.defensive_value,
            "Reuse": self.reuse_potential,
            "LLMとの関係": self.llm_relationship,
            "Decision": self.decision,
        }


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def assess_track_a(*, fetch_live: bool = True, llm_enabled: bool = False, chat_fn=None, model: str = "") -> dict[str, Any]:
    golden = run_production_golden(fetch_live=fetch_live)
    improvement = run_autonomous_improvement(
        fetch_live=fetch_live,
        llm_enabled=llm_enabled,
        chat_fn=chat_fn,
        model=model,
    )
    assessment = improvement.get("assessment") or {}
    probes = improvement.get("probes") or {}

    measured_production_defect = False
    if fetch_live:
        if not assessment.get("golden_pass"):
            measured_production_defect = True
        elif not assessment.get("osaka_chain_pass"):
            measured_production_defect = True

    current_problem = None
    root_cause = None
    if fetch_live and not assessment.get("golden_pass"):
        current_problem = "Golden GT regression"
        root_cause = "extraction/fetch path failure"
    elif fetch_live and not assessment.get("osaka_chain_pass"):
        current_problem = "Osaka search→fetch chain failure"
        root_cause = "search or fetch quality"
    else:
        current_problem = "NONE — no measured Production defect"

    return {
        "current_problem": current_problem,
        "observation": {
            "golden": f"{golden.get('pass_count')}/{golden.get('total')} {golden.get('overall')}",
            "osaka_chain": assessment.get("osaka_chain_pass"),
            "live_e2e": assessment.get("live_e2e_pass"),
            "eval_gap_documented": assessment.get("eval_gap_confirmed"),
            "fetch_skip": assessment.get("fetch_skip_observed"),
        },
        "root_cause": root_cause or "N/A",
        "implementation": "NONE — no Production change warranted",
        "regression": golden,
        "production_impact": "NONE",
        "measured_production_defect": measured_production_defect,
        "autonomous_improvement": {
            "selected_option": improvement.get("selected_option"),
            "stop_reason": improvement.get("stop_reason"),
            "confirmed_facts": improvement.get("confirmed_facts"),
            "unknowns": improvement.get("unknowns"),
        },
        "probes_summary": {
            "osaka_hit_count": (probes.get("search_fetch_chain") or {}).get("osaka", {}).get("hit_count"),
            "osaka_population_signal": ((probes.get("search_fetch_chain") or {}).get("osaka", {}).get("fetch") or {}).get(
                "population_signal"
            ),
            "eval_gap": probes.get("eval_vs_mirror_gap"),
        },
    }


def discover_track_b_candidates(*, track_a: dict[str, Any]) -> list[TrackBCandidate]:
    """Observe candidates from current development context — no forced creation."""
    candidates: list[TrackBCandidate] = []

    def _cand(
        *,
        id: str,
        name: str,
        current_use: str,
        future_uses: list[str],
        reuse_potential: str,
        defensive_value: str,
        implementation_cost: str,
        regression_risk: str,
        production_coupling: str,
        existing_core_overlap: str,
        reversibility: str,
        sunset_conditions: list[str],
        classification: Literal["C0", "C1", "C2", "C3", "C4"],
        extends_llm: bool,
        replaces_llm: bool = False,
        decision: str | None = None,
    ) -> TrackBCandidate:
        llm_rel = evaluate_llm_capability_role(extends_llm=extends_llm, replaces_llm=replaces_llm)
        return TrackBCandidate(
            id=id,
            name=name,
            current_use=current_use,
            future_uses=future_uses,
            reuse_potential=reuse_potential,
            defensive_value=defensive_value,
            implementation_cost=implementation_cost,
            regression_risk=regression_risk,
            production_coupling=production_coupling,
            existing_core_overlap=existing_core_overlap,
            reversibility=reversibility,
            sunset_conditions=sunset_conditions,
            classification=classification,
            llm_relationship="拡張" if extends_llm and not replaces_llm else ("置換" if replaces_llm else "中立"),
            decision=decision or ("RECORD" if classification == "C1" else classification),
        )

    candidates.append(
        _cand(
            id="CC-03",
            name="Capability Lifecycle Registry",
            current_use="Documented in defensive_core_discovery_policy registry",
            future_uses=["Sunset enforcement when experimental count > 5", "Autonomous loop inventory"],
            reuse_potential="HIGH",
            defensive_value="MEDIUM — anti-bloat",
            implementation_cost="LOW",
            regression_risk="LOW",
            production_coupling="NONE",
            existing_core_overlap="Extends policy module; no duplicate of CC-01/CC-02",
            reversibility="HIGH",
            sunset_conditions=["Never needed if active experimental ≤ 3"],
            classification="C1",
            extends_llm=True,
        )
    )

    candidates.append(
        _cand(
            id="OPT7",
            name="Post-LLM Verify Metadata (observation)",
            current_use="CC-02 Mechanical Verification — observation only",
            future_uses=["Anomaly detection metadata", "Future Warning layer if numeric_error > 15%"],
            reuse_potential="MEDIUM",
            defensive_value="MEDIUM–HIGH when connected",
            implementation_cost="LOW (extends CC-02)",
            regression_risk="MEDIUM if Production connected",
            production_coupling="HIGH if connected — HR required",
            existing_core_overlap="CC-02 — extend, do not duplicate",
            reversibility="HIGH while experimental",
            sunset_conditions=["numeric_error < 5% sustained", "2 unused phases"],
            classification="C1",
            extends_llm=True,
            decision="RECORD — Warning/Retry/Fallback deferred",
        )
    )

    candidates.append(
        _cand(
            id="CTX-PASSAGE",
            name="Evidence Passage Selector (experimental packager)",
            current_use="ai_tool/experimental/evidence_context/ — shootout C0",
            future_uses=["Token budget for long evidence", "Eval-only context experiments"],
            reuse_potential="MEDIUM",
            defensive_value="LOW",
            implementation_cost="LOW",
            regression_risk="LOW",
            production_coupling="NONE",
            existing_core_overlap="Does not replace enrich_web_tool_result",
            reversibility="HIGH",
            sunset_conditions=["2 unused phases", "No live benefit vs RAW sustained"],
            classification="C0",
            extends_llm=True,
            decision="RECORD — no Production context change",
        )
    )

    candidates.append(
        _cand(
            id="CTX-HYBRID",
            name="Hybrid Context Packaging",
            current_use="Shootout +1 case vs RAW; not category-consistent",
            future_uses=["Eval format experiments", "Dataset expansion re-validation"],
            reuse_potential="MEDIUM",
            defensive_value="LOW–MEDIUM",
            implementation_cost="MEDIUM",
            regression_risk="MEDIUM if Production connected",
            production_coupling="NONE",
            existing_core_overlap="Experimental packager only",
            reversibility="HIGH",
            sunset_conditions=["No reproducible multi-category gain", "2 unused phases"],
            classification="C1",
            extends_llm=True,
            decision="RECORD — not Production candidate",
        )
    )

    candidates.append(
        _cand(
            id="CTX-CONFLICT-OBS",
            name="Conflict Observation (not resolver)",
            current_use="IC-F01 live shootout — all formats Correct",
            future_uses=["Multi-source eval fixtures", "LLM uncertainty observation"],
            reuse_potential="LOW",
            defensive_value="LOW — LLM handled conflict conversationally",
            implementation_cost="MEDIUM if built as Core",
            regression_risk="LOW",
            production_coupling="NONE",
            existing_core_overlap="Source metadata in enrich + LLM conversation",
            reversibility="HIGH",
            sunset_conditions=["Conflict failures absent on live LLM", "2 unused phases"],
            classification="C1",
            extends_llm=True,
            decision="RECORD — no Conflict Resolver Production build",
        )
    )

    candidates.append(
        _cand(
            id="REJ-RTT",
            name="Research Transaction",
            current_use="Deferred 3+ phases",
            future_uses=["Multi-step web research orchestration"],
            reuse_potential="MEDIUM",
            defensive_value="MEDIUM",
            implementation_cost="HIGH",
            regression_risk="HIGH",
            production_coupling="HIGH",
            existing_core_overlap="production_mirror + failure_diagnosis cover partial need",
            reversibility="LOW",
            sunset_conditions=["N/A — not building"],
            classification="C0",
            extends_llm=True,
            decision="REJECTED",
        )
    )

    candidates.append(
        _cand(
            id="REJ-MECH-ANSWER",
            name="Mechanical Answer Layer",
            current_use="Explicitly forbidden by SCR-02",
            future_uses=[],
            reuse_potential="LOW",
            defensive_value="N/A",
            implementation_cost="HIGH",
            regression_risk="HIGH",
            production_coupling="HIGH",
            existing_core_overlap="Conflicts with LLM-centered conversation",
            reversibility="LOW",
            sunset_conditions=["N/A — not building"],
            classification="C0",
            extends_llm=False,
            replaces_llm=True,
            decision="REJECTED — Q8 defer",
        )
    )

    if track_a.get("observation", {}).get("eval_gap_documented"):
        candidates.append(
            _cand(
                id="CC-01-followup",
                name="Eval Parity Bridge adoption completion",
                current_use="CC-01 implemented; M1–M4 migrated",
                future_uses=["Remaining diagnostic-only harnesses stay labeled"],
                reuse_potential="HIGH — already reused 8×",
                defensive_value="HIGH",
                implementation_cost="LOW",
                regression_risk="LOW",
                production_coupling="NONE",
                existing_core_overlap="IS CC-01 — not new Core",
                reversibility="HIGH",
                sunset_conditions=["All harnesses on canonical path"],
                classification="C0",
                extends_llm=True,
                decision="REUSE existing CC-01",
            )
        )

    return candidates


def what_we_did_not_build() -> list[dict[str, str]]:
    """Explicit record of deferred/rejected work — phase success includes NOT building."""
    return [
        {"item": "Production Context Format migration", "reason": "Shootout RECORD; 1-case gap insufficient"},
        {"item": "Mechanical Answer / LLM answer replacement", "reason": "SCR-02 — Verification ≠ Answer"},
        {"item": "Conflict Resolver Production module", "reason": "Live LLM distinguished years/sources without it"},
        {"item": "Generic Retry/Fallback infrastructure", "reason": "No measured Production need"},
        {"item": "Research Transaction Core", "reason": "High cost; partial overlap with mirror/diagnosis"},
        {"item": "New C3 Experimental Core this phase", "reason": "Max 1/phase; no candidate met C3 bar"},
        {"item": "Full Web Research Architecture redesign", "reason": "Production chain stable"},
        {"item": "Search backend swap", "reason": "No purposeless change rule"},
    ]


def existing_core_reuse_assessment() -> dict[str, Any]:
    registry = existing_core_registry()
    return {
        "cores": [r.to_dict() for r in registry],
        "reuse_total": sum(r.reuse_count for r in registry),
        "recommendation": "Prefer extending CC-01, CC-02, production_mirror before new Core",
        "extension_opportunities": [
            "OPT7 → extend CC-02 Mechanical Verification (C1, not new module)",
            "CC-03 → record until manual tracking fails (C1)",
        ],
    }


def specification_and_user_decisions(*, track_a: dict[str, Any]) -> dict[str, Any]:
    scrs = [
        {
            "id": "SCR-02",
            "status": "ADOPTED — design philosophy; Production unchanged",
            "human_review_required": False,
            "document": "WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md",
        },
    ]
    user_decisions = []

    if track_a.get("observation", {}).get("eval_gap_documented"):
        scrs.append(
            {
                "id": "SCR-01",
                "status": "harness-level adopted; full project policy optional",
                "human_review_required": True,
            }
        )

    if not track_a.get("measured_production_defect"):
        user_decisions.append(
            {
                "type": "Operating Model",
                "topic": "Model B adopted — Production minimal + Defensive Discovery lane",
                "required": False,
                "note": "No user action needed unless promoting OPT7 or SCR-01 full adoption",
            }
        )

    return {"scr_candidates": scrs, "user_decision_requests": user_decisions}


def select_phase_decisions(
    *,
    track_a: dict[str, Any],
    candidates: list[TrackBCandidate],
) -> list[PhaseDecision]:
    decisions: list[PhaseDecision] = []
    if track_a.get("measured_production_defect"):
        decisions.append("IMPLEMENT")
    else:
        decisions.append("STOP_NO_CHANGE")
    if any(c.classification == "C1" for c in candidates):
        decisions.append("RECORD")
    if any(c.classification == "C2" for c in candidates):
        decisions.append("INVESTIGATE")
    if any(c.classification == "C3" for c in candidates):
        decisions.append("EXPERIMENTAL")
    if any(c.classification == "C4" for c in candidates):
        decisions.append("HUMAN_REVIEW_REQUIRED")
    if not track_a.get("measured_production_defect"):
        decisions.append("CONTINUE")
    return sorted(set(decisions), key=lambda d: [
        "STOP_NO_CHANGE", "CONTINUE", "RECORD", "INVESTIGATE", "EXPERIMENTAL", "IMPLEMENT", "HUMAN_REVIEW_REQUIRED",
    ].index(d))


def run_normal_development_defensive_core(
    *,
    fetch_live: bool = True,
    llm_enabled: bool = False,
    chat_fn=None,
    model: str = "",
) -> dict[str, Any]:
    head = _git_head()
    track_a = assess_track_a(fetch_live=fetch_live, llm_enabled=llm_enabled, chat_fn=chat_fn, model=model)
    candidates = discover_track_b_candidates(track_a=track_a)
    reuse = existing_core_reuse_assessment()
    spec = specification_and_user_decisions(track_a=track_a)
    decisions = select_phase_decisions(track_a=track_a, candidates=candidates)

    by_class = {c: [x.id for x in candidates if x.classification == c] for c in ("C0", "C1", "C2", "C3", "C4")}

    golden = track_a.get("regression") or {}
    if fetch_live:
        overall = "PASS" if golden.get("overall") == "PASS" and not track_a.get("measured_production_defect") else "PARTIAL"
    else:
        overall = "PASS" if not track_a.get("measured_production_defect") else "PARTIAL"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": head,
        "final_head": head,
        "phase": "llm_centered_web_research_architecture_adoption",
        "operating_model": normal_development_operating_model(),
        "policy": policy_summary_for_harnesses(),
        "forbidden_actions": phase_forbidden_actions(),
        "success_criteria": phase_success_criteria(),
        "track_b_extend_priorities": track_b_extend_priorities(),
        "track_b_defer_priorities": track_b_defer_priorities(),
        "overall": overall,
        "production_changes": [],
        "production_chain_maintained": True,
        "track_a": track_a,
        "track_b": {
            "new_core_candidates": [c.to_dict() for c in candidates],
            "report_table": [c.to_report_row() for c in candidates],
            "classification": by_class,
            "existing_core_reuse": reuse,
            "new_c3_created": False,
            "candidate_count": len(candidates),
            "no_new_core_message": None
            if any(c.classification in ("C2", "C3", "C4") for c in candidates)
            else "No new Core Capability advanced to C2/C3/C4 — observation and C0/C1 record only.",
        },
        "what_we_did_not_build": what_we_did_not_build(),
        "mechanical_verification": {
            "location": "ai_tool/experimental/mechanical_verification/",
            "answer_replacement": "FORBIDDEN",
            "warning": "DEFERRED",
            "retry": "DEFERRED",
            "fallback": "DEFERRED",
            "verification_observation": "CONTINUE",
        },
        "specification": spec,
        "decisions": decisions,
        "final_decision": decisions[0] if decisions else "CONTINUE",
        "stop_reason": None if "STOP_NO_CHANGE" in decisions else "measured Production defect",
        "human_review_required": "HUMAN_REVIEW_REQUIRED" in decisions,
    }
