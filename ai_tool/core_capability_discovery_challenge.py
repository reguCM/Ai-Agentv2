"""Core Capability Discovery & Specification Challenge — evaluation harness.

Discovers future Core Capabilities, classifies them, and recommends policy.
Does NOT modify Production, Agent, Registry, or Prompt.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[1]

CapabilityClass = Literal["C0", "C1", "C2", "C3", "C4", "C5"]
Decision = Literal[
    "STOP_NO_CHANGE",
    "RECORD_FUTURE_CAPABILITIES",
    "INVESTIGATE",
    "EXPERIMENTAL_CAPABILITY",
    "HUMAN_REVIEW_REQUIRED",
    "SPECIFICATION_CHANGE_REQUEST",
]


@dataclass
class CapabilityMatrix:
    current_need: str
    future_value: str
    reuse: str
    defensive_value: str
    cost: str
    risk: str
    reversibility: str
    integration_cost: str
    specification_impact: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class CoreCapabilityCandidate:
    id: str
    name: str
    summary: str
    future_uses: list[str]
    classification: CapabilityClass
    matrix: CapabilityMatrix
    rationale: str
    sunset_conditions: list[str] = field(default_factory=list)
    combines_with: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["matrix"] = self.matrix.to_dict()
        return d


@dataclass
class SpecificationChangeRequest:
    id: str
    current_specification: str
    observed_problem: str
    proposed_specification: str
    why_limiting: str
    benefits: list[str]
    costs: list[str]
    risks: list[str]
    alternative_keep_current: str
    recommendation: str
    human_decision_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def current_architecture_inventory() -> dict[str, Any]:
    return {
        "production_integrated": [
            "search_web + search hardening",
            "read_url_text + extraction normalization (S4)",
            "web_evidence.enrich_web_tool_result",
            "web_status + WebSessionTracker",
            "web_answer_boundary",
            "agent_tool_gate",
            "Agent tool loop (gate → enrich → session → boundary)",
        ],
        "eval_observation": [
            "production_mirror (production_agent_web_loop)",
            "failure_diagnosis_phase4",
            "success_class / broader success_class evaluation",
            "autonomous improvement probes",
            "mechanical_verification (experimental)",
        ],
        "deferred_or_absent": [
            "Research Transaction",
            "Structured Claim (Production)",
            "Mechanical Answer (Production)",
            "Fallback framework",
            "Retry/Recovery orchestration",
            "Eval canonical bridge (unified)",
            "Capability sunset registry",
        ],
        "confirmed_gaps": [
            "execute_registry_tool mock default vs production search",
            "eval-direct path lacks WebSessionTracker/boundary",
            "Open-domain verification requires ExpectedFact",
            "Live search intermittency (Web layer, not Core Capability)",
        ],
    }


def discover_future_capabilities() -> list[CoreCapabilityCandidate]:
    """Max 3 candidates — derived from multi-phase observations, not convenience."""
    return [
        CoreCapabilityCandidate(
            id="CC-01",
            name="Eval Production Parity Bridge",
            summary=(
                "Unified eval wrapper forcing production_mirror + injectable fixtures "
                "for all autonomous harness PASS/FAIL metrics."
            ),
            future_uses=[
                "Autonomous improvement loop metric parity",
                "Regression without false positives from mock search",
                "Agent policy experiments with same boundary path",
                "LLM/model comparison on canonical path",
            ],
            classification="C2",
            matrix=CapabilityMatrix(
                current_need="LOW — Production user path OK; eval metrics diverge",
                future_value="HIGH",
                reuse="HIGH — all web_tool_* harnesses",
                defensive_value="MEDIUM — prevents wrong autonomous decisions",
                cost="LOW — harness-only module",
                risk="LOW — no Production connection",
                reversibility="HIGH",
                integration_cost="MEDIUM if deferred — each harness keeps custom path",
                specification_impact="YES — eval canonical path policy",
                evidence="CONFIRMED: post-baseline, broader eval, transaction investigation",
            ),
            rationale=(
                "Observed across 3+ phases. Not needed for Production users but blocks "
                "reliable Cursor self-evaluation. Investigate/prototype before Production touch."
            ),
            sunset_conditions=[
                "All harnesses migrated to bridge OR policy rejects unified eval path",
                "2 phases after migration with zero eval-gap observations",
            ],
            combines_with=["production_mirror", "failure_diagnosis", "WebSessionTracker"],
        ),
        CoreCapabilityCandidate(
            id="CC-02",
            name="Verification Metadata Envelope",
            summary=(
                "Post-LLM deterministic verification results as structured metadata "
                "(MATCH/MISMATCH/UNSUPPORTED/UNKNOWN) — observation-only, no answer replacement."
            ),
            future_uses=[
                "Success-class eval enrichment",
                "Future Warning layer (OPT7)",
                "Autonomous loop: verify before declaring STOP_D",
                "Human review packets with claim-level evidence",
                "Combine with web_status SUCCESS to detect LLM-layer failures",
            ],
            classification="C3",
            matrix=CapabilityMatrix(
                current_need="LOW — numeric_error 7.7%, no Production ROI",
                future_value="HIGH",
                reuse="HIGH — any Evidence+LLM path",
                defensive_value="MEDIUM–HIGH when connected; HIGH as eval",
                cost="LOW — built on mechanical_verification",
                risk="LOW while experimental",
                reversibility="HIGH",
                integration_cost="HIGH if bolted onto boundary without design",
                specification_impact="MEDIUM — LLM/boundary responsibility split",
                evidence="mechanical_verification 92.6% pass, FP=0, FN=0",
            ),
            rationale=(
                "Mechanical Verification experimental module validates viability. "
                "Retain as Core Capability; do NOT connect to Production until live failure rate warrants."
            ),
            sunset_conditions=[
                "No harness references for 2 consecutive phases",
                "OR live numeric_error_rate < 5% sustained AND no HR request for Warning layer",
                "OR superseded by Structured Claim architecture (explicit HR decision)",
            ],
            combines_with=["mechanical_verification", "web_answer_boundary", "success_class eval"],
        ),
        CoreCapabilityCandidate(
            id="CC-03",
            name="Capability Lifecycle Registry",
            summary=(
                "Machine-readable registry of Experimental Core Capabilities with "
                "classification, sunset date, last-used phase, and connect/disconnect status."
            ),
            future_uses=[
                "Prevent Cursor harness/Capability proliferation",
                "Sunset enforcement for Model B policy",
                "Autonomous loop knows what exists vs deferred",
                "Human audit of experimental surface area",
            ],
            classification="C1",
            matrix=CapabilityMatrix(
                current_need="NONE — policy exists in docs only",
                future_value="MEDIUM–HIGH as capability count grows",
                reuse="HIGH — all future phases",
                defensive_value="MEDIUM — anti-bloat, anti-runaway",
                cost="LOW — JSON/markdown registry",
                risk="LOW",
                reversibility="HIGH",
                integration_cost="LOW now; HIGH if added after 10+ orphan harnesses",
                specification_impact="LOW",
                evidence="HYPOTHESIS — 15+ web_tool harness files, deferred RTT/mechanical answer docs",
            ),
            rationale=(
                "Record now; build when experimental capability count exceeds manageable "
                "manual tracking (~5 active). Prevents Legacy accumulation."
            ),
            sunset_conditions=[
                "Never needed if experimental count stays ≤3 active",
            ],
            combines_with=["autonomous improvement loop", "Decision Log format"],
        ),
    ]


def assess_mechanical_verification() -> dict[str, Any]:
    return {
        "location": "ai_tool/experimental/mechanical_verification/",
        "classification": "C3 — Experimental Capability (retain)",
        "generic_enough": True,
        "genericity_limits": [
            "Requires ExpectedFact or question-specific patterns for entity/scope",
            "Heuristic-only mode limited to numerics/years",
            "English million requires fact_id naming convention",
        ],
        "future_uses": [
            "Success-class / broader eval replay",
            "Pre-Production Warning metadata (OPT7)",
            "Autonomous STOP validation (did LLM answer match evidence?)",
            "Human review claim packets",
            "Combine with failure_diagnosis ObservationBundle",
        ],
        "mechanical_answer_separation": "CLEAR — verify_answer does not replace LLM output",
        "evolution_path": {
            "observation_only": "CURRENT",
            "warning_metadata": "FUTURE — if numeric_error > 15%",
            "retry": "DEFERRED — HR required",
            "fallback": "REJECTED for this project scope",
        },
        "combines_with": [
            "web_status (SUCCESS-class gate)",
            "web_answer_boundary (failure vs success-class split)",
            "success_class ExpectedFact",
            "failure_diagnosis",
        ],
        "retain_without_production": True,
        "retain_reason": (
            "92.6% scenario pass, FP=0, FN=0; low cost; enables future OPT7 without "
            "Production commit; separates 'verify' from 'replace'."
        ),
        "sunset_conditions": [
            "No harness invocation for 2 consecutive scheduled eval phases",
            "Live numeric_error_rate < 5% for 3 consecutive broader eval runs AND no Warning HR",
            "Superseded by Structured Claim (explicit HR + migration plan)",
        ],
        "production_connection": "NOT RECOMMENDED at current measured failure rates",
        "metrics_reference": "runs/ai_tool/20260829_144008_web_tool_mechanical_verification/",
    }


def specification_change_requests() -> list[SpecificationChangeRequest]:
    return [
        SpecificationChangeRequest(
            id="SCR-01",
            current_specification=(
                "Web tool evaluation harnesses may use execute_registry_tool directly "
                "or production_mirror interchangeably; no project-wide canonical eval path."
            ),
            observed_problem=(
                "CONFIRMED across phases: execute_registry_tool defaults to mock search (3 hits "
                "on nonsense query); no WebSessionTracker/boundary on eval-direct path. "
                "Autonomous metrics can diverge from Production without indicating failure."
            ),
            proposed_specification=(
                "Project policy: PASS/FAIL metrics for Web Research autonomous evaluation "
                "MUST use production_mirror (or Eval Production Parity Bridge wrapper). "
                "execute_registry_tool direct path is diagnostic-only and MUST NOT drive "
                "STOP/Architecture decisions."
            ),
            why_limiting=(
                "Without canonical eval spec, Cursor can pass autonomous phases while "
                "Production and eval paths diverge — undermines self-improvement loop integrity."
            ),
            benefits=[
                "Autonomous STOP decisions align with Production behavior",
                "Reduces false Architecture conclusions",
                "Single wrapper (CC-01) implementable without Production change",
            ],
            costs=[
                "Harness migration effort",
                "Tests expecting mock-default behavior may need update",
                "Slightly longer eval runs (live search when not fixture-injected)",
            ],
            risks=[
                "Over-constraining quick diagnostic probes",
                "Live search flakiness affects eval PASS rate",
            ],
            alternative_keep_current=(
                "Keep dual paths but require explicit path_label in Decision Log and "
                "forbid STOP_D based on eval-direct metrics alone."
            ),
            recommendation=(
                "Adopt proposed specification OR alternative with path_label mandate. "
                "Does not require Production code change — policy + harness only."
            ),
            human_decision_required=True,
        ),
    ]


def autonomous_policy_recommendation() -> dict[str, Any]:
    return {
        "auto_implement_production": [
            "Measured Failure on Production user path",
            "Golden + live E2E regression protection",
            "Minimal diff scope",
        ],
        "experimental_prebuild_allowed": [
            "Core system capability (not End Tool)",
            "≥2 concrete future use cases documented",
            "Independent module under ai_tool/experimental/",
            "Observation-only first; no Production import from Production side",
            "Automatic tests; reversible; max 1 new Core per phase",
        ],
        "ask_user": [
            "Specification changes (SCR-*)",
            "Agent policy / Prompt / Registry changes",
            "Production Warning/Retry/Fallback connection",
            "Architecture with Human Review flag",
        ],
        "stop_without_implement": [
            "No measured Production defect",
            "ROI unproven for Production connection",
            "Capability count would exceed 3 active without sunset",
            "Duplicate of existing capability",
        ],
        "decision_model": [
            "Observation",
            "Diagnosis",
            "Current Fix Candidate",
            "Core Capability Discovery (max 3)",
            "Future Scenario Analysis",
            "Cost/Risk/Reuse Evaluation",
            "Capability/Production Separation",
            "Options",
            "Select → Implement / Experimental / Defer / Reject / Ask User",
            "Regression",
            "STOP",
        ],
        "anti_runaway_rules": [
            "Max 3 Core candidates recorded per phase",
            "Max 1 new Experimental Core implementation per phase",
            "Sunset after 2 unused phases",
            "Production connection requires measured failure + HR matrix",
            "Harness creation alone is not success",
        ],
    }


def select_decisions(
    candidates: list[CoreCapabilityCandidate],
    scrs: list[SpecificationChangeRequest],
    mech: dict[str, Any],
) -> list[Decision]:
    decisions: list[Decision] = ["RECORD_FUTURE_CAPABILITIES"]
    if any(c.classification == "C2" for c in candidates):
        decisions.append("INVESTIGATE")
    if mech.get("retain_without_production"):
        decisions.append("EXPERIMENTAL_CAPABILITY")
    if scrs:
        decisions.append("SPECIFICATION_CHANGE_REQUEST")
        decisions.append("HUMAN_REVIEW_REQUIRED")
    if not any(c.classification == "C4" for c in candidates):
        decisions.append("STOP_NO_CHANGE")  # no Production work
    return sorted(set(decisions), key=lambda d: [
        "STOP_NO_CHANGE", "RECORD_FUTURE_CAPABILITIES", "INVESTIGATE",
        "EXPERIMENTAL_CAPABILITY", "HUMAN_REVIEW_REQUIRED", "SPECIFICATION_CHANGE_REQUEST",
    ].index(d))


def run_core_capability_discovery_challenge(*, fetch_live_baseline: bool = True) -> dict[str, Any]:
    initial_head = _git_head()
    baseline = run_production_golden(fetch_live=fetch_live_baseline)
    inventory = current_architecture_inventory()
    candidates = discover_future_capabilities()
    mech = assess_mechanical_verification()
    scrs = specification_change_requests()
    policy = autonomous_policy_recommendation()
    decisions = select_decisions(candidates, scrs, mech)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": initial_head,
        "final_head": initial_head,
        "overall": "PASS" if baseline.get("overall") == "PASS" else "PARTIAL",
        "baseline_golden": f"{baseline.get('pass_count')}/{baseline.get('total')}",
        "current_architecture": inventory,
        "discovered_capabilities": [c.to_dict() for c in candidates],
        "mechanical_verification_assessment": mech,
        "specification_change_requests": [s.to_dict() for s in scrs] if scrs else "NONE",
        "autonomous_policy": policy,
        "decisions": decisions,
        "production_changes": [],
        "experimental_changes": [],
        "independent_challenges": {
            "need_now_vs_need_future": (
                "Validated separation: CC-02 has low current need, high future value — "
                "not same as 'future unnecessary'."
            ),
            "low_roi_vs_core_value": (
                "Production ROI low for verify Warning; Core experimental value HIGH — "
                "not contradictory."
            ),
            "prebuild_reduces_future_cost": (
                "YES for CC-01 (eval gap) and CC-02 (verify module exists); "
                "NO for RTT/mechanical answer (deferred correctly)."
            ),
            "legacy_risk": (
                "MEDIUM — harness proliferation; CC-03 lifecycle registry mitigates."
            ),
            "cursor_runaway_risk": (
                "HIGH without max-1-per-phase and sunset rules; policy addresses."
            ),
            "user_unanticipated_spec_issue": (
                "SCR-01 eval canonical path — discovered from observations, not user prompt."
            ),
        },
        "rejected_as_core": [
            "Research Transaction — integration cost too high, deferred 3+ phases",
            "Mechanical Answer Production — ROI insufficient",
            "Generic Retry/Fallback framework — no confirmed Production symptom",
        ],
        "stop": True,
    }
