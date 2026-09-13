"""Defensive Core Discovery Policy — autonomous development rule (Model B).

Integrates Track A (current problem) and Track B (future core discovery).
Does NOT modify Production, Agent, Registry, or Prompt.

Policy version is mutable — not a fixed architecture rule.
"""
from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[1]

POLICY_VERSION = "1.1-llm-centered"
CapabilityClass = Literal["C0", "C1", "C2", "C3", "C4"]
CostLevel = Literal["LOW", "MEDIUM", "HIGH"]
PhaseDecision = Literal[
    "NO_CORE_ACTION",
    "RECORD",
    "INVESTIGATE",
    "EXPERIMENTAL_CAPABILITY",
    "HUMAN_REVIEW_REQUIRED",
    "SUNSET",
    "CONTINUE",
]
PolicyAdoption = Literal["ADOPT", "ADOPT_WITH_LIMITS", "DEFER", "REJECT"]


@dataclass
class CostBenefitMatrix:
    implementation_cost: CostLevel
    maintenance_cost: CostLevel
    reuse_value: CostLevel
    defensive_value: CostLevel
    future_value: CostLevel
    coupling_risk: CostLevel
    production_risk: CostLevel
    reversibility: CostLevel

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def favors_prebuild(self) -> bool:
        """Future Value × Reuse vs Cost × Coupling — heuristic."""
        value_score = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        fv = value_score[self.future_value] + value_score[self.reuse_value]
        cost_score = value_score[self.implementation_cost] + value_score[self.coupling_risk]
        return fv >= cost_score + 1


@dataclass
class CoreCapabilityRecord:
    id: str
    name: str
    classification: CapabilityClass
    location: str
    reuse_count: int
    consumers: list[str]
    consuming_phases: list[str]
    actual_benefit: str
    maintenance_cost: CostLevel
    last_used_phase: str
    sunset_status: Literal["KEEP", "SIMPLIFY", "SUNSET", "N/A"] = "KEEP"
    production_connected: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CoreCandidate:
    id: str
    name: str
    problem: str
    classification: CapabilityClass
    future_uses: list[str]
    matrix: CostBenefitMatrix
    current_evidence: str
    production_impact: str
    experimental_value: str
    recommendation: str
    rejected_reason: str | None = None

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
    reason: str
    expected_benefit: list[str]
    risk: list[str]
    migration_cost: list[str]
    backward_compatibility: str
    human_review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MandatoryPhaseReport:
    phase_id: str
    current_problem_track: dict[str, Any]
    future_core_track: dict[str, Any]
    existing_core_usage: dict[str, Any]
    specification_requests: list[dict[str, Any]]
    complexity_check: dict[str, Any]
    decisions: list[PhaseDecision]
    policy_adoption: PolicyAdoption
    policy_adoption_rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def policy_tracks() -> dict[str, Any]:
    return {
        "track_a_current_problem": {
            "flow": "Observation → Reproduction → Diagnosis → Minimal Fix → Regression",
            "production_change_rule": "Measured problem required",
        },
        "track_b_future_core": {
            "flow": "Discovery Q1–Q7 → Classify C0–C4 → Cost/Benefit → Experimental or Record",
            "production_change_rule": "Forbidden unless C4 + Human Review",
        },
        "separation": "Tracks evaluated independently every phase",
    }


def discovery_questions() -> list[dict[str, str]]:
    return [
        {"id": "Q1", "question": "複数箇所から利用できそうな処理・判断が発生したか？"},
        {"id": "Q2", "question": "今は不要だが将来 Agent/LLM/Eval/Safety/Diagnosis で再利用できそうか？"},
        {"id": "Q3", "question": "後から作るより今独立 module 保有の方が安いか？"},
        {"id": "Q4", "question": "先行実装が Production Architecture を拘束するか？"},
        {"id": "Q5", "question": "Production 接続なしでも価値を持つか？"},
        {"id": "Q6", "question": "独立して削除・交換できるか？"},
        {"id": "Q7", "question": "既存 Capability との重複はないか？"},
        {
            "id": "Q8",
            "question": "LLMの能力を置き換えるものか、拡張するものか？",
            "reference": "WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md §10",
        },
    ]


def llm_capability_role_criteria() -> dict[str, Any]:
    """WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC §10 — Core evaluation extension."""
    return {
        "spec_version": "1.0",
        "spec_document": "docs/ai_tool/project_audit/WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md",
        "principle": "LLM-centric conversation; Web and Mechanical capabilities extend LLM",
        "extends_llm_priorities": [
            "Increase LLM judgment materials (Evidence, Source metadata)",
            "Source selection assistance",
            "Evidence retention and provenance",
            "Answer traceability for users",
            "LLM anomaly detection (defensive)",
            "Multiple interpretations when appropriate",
            "Preserve future answer-mode flexibility",
        ],
        "replaces_llm_defer_until": [
            "Mechanical Answer replacing conversational LLM output",
            "Pre-LLM truth gate blocking all uncertain Evidence",
            "Always-on dual-answer presentation",
            "Context packaging without measured Production benefit",
        ],
        "mechanical_verification_not_mechanical_answer": True,
    }


def evaluate_llm_capability_role(
    *,
    extends_llm: bool,
    replaces_llm: bool,
    measured_production_need: bool = False,
) -> str:
    """Heuristic guidance for Core candidates under SCR-02."""
    if replaces_llm and not measured_production_need:
        return "DEFER_PRODUCTION — LLM replacement without measured need"
    if extends_llm and not replaces_llm:
        return "FAVOR_RECORD_OR_EXPERIMENTAL"
    if extends_llm and replaces_llm:
        return "INVESTIGATE — mixed role; split verification from answer replacement"
    return "NEUTRAL"


def normal_development_operating_model() -> dict[str, Any]:
    """Formal Model B — Production minimal + Defensive Core Discovery lane."""
    return {
        "spec_reference": "WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md",
        "production_chain": (
            "Search → Fetch → Extraction → Evidence → web_status → Boundary → LLM → User Conversation"
        ),
        "track_a": {
            "name": "Current Development",
            "flow": "Observation → Reproduction → Diagnosis → Minimal Fix → Regression → Decision Log",
            "production_change_rule": "Measured problem only",
        },
        "track_b": {
            "name": "Defensive Core Discovery",
            "flow": "Observe → Q1–Q8 → C0–C4 → Record / Investigate / Experimental",
            "production_change_rule": "Forbidden unless C4 + Human Review",
        },
        "principle": (
            "Production stays minimal; low-cost LLM-extending cores discovered in a separate lane"
        ),
    }


def phase_forbidden_actions() -> list[str]:
    """Actions forbidden without measured need (LLM-centered adoption phase)."""
    return [
        "Full Web Research Architecture redesign",
        "Mechanical Answer replacing LLM conversational output",
        "Structured answer for all responses",
        "Large Research Transaction infrastructure",
        "Generic Retry/Fallback infrastructure",
        "Full migration to new Context Format (post-shootout)",
        "Purposeless Search backend swap",
        "Multiple Experimental Cores in one phase (max 1 C3)",
        "Treating harness creation alone as phase success",
    ]


def phase_success_criteria() -> list[str]:
    return [
        "Normal development can continue",
        "Production Web Tool chain remains stable",
        "LLM-centered design philosophy maintained",
        "New Core candidates recorded without being missed",
        "Only valuable candidates advance to Investigate/Experimental",
        "Unnecessary Cores are not forced",
        "Production changes require sufficient evidence as before",
        "Mechanical Verification retained as future-capable capability",
        "Record what was NOT built each phase",
    ]


def track_b_extend_priorities() -> list[str]:
    return [
        "Extends LLM (materials, provenance, anomaly detection) — not replacement",
        "Multiple plausible future uses",
        "Independent of Production path",
        "Low implementation and maintenance cost",
        "Reusable if Production connection is later justified",
        "Combines with existing Core (CC-01, CC-02, web_status, boundary)",
        "Failure does not break Production",
    ]


def track_b_defer_priorities() -> list[str]:
    return [
        "Convenience without current problem",
        "Full LLM replacement via mechanical answer layer",
        "Generic Retry/Fallback without observed need",
        "Duplicate of existing Core",
        "High maintenance cost",
        "Built only because 'AI Agent should have it'",
    ]


def classification_rules() -> dict[str, str]:
    return {
        "C0": "No candidate — build nothing for future core",
        "C1": "Record — future value, weak build rationale now",
        "C2": "Investigate — spike/prototype only, no Production",
        "C3": "Experimental — isolated prebuild, Production connection forbidden",
        "C4": "Production candidate — measured need + HR required",
    }


def c3_creation_requirements() -> list[str]:
    return [
        "Requirement A — Reuse Potential: ≥2 concrete future uses",
        "Requirement B — Independent Boundary: separate from Production",
        "Requirement C — Low Coupling: minimal intrusion into existing modules",
        "Requirement D — Observation First: observe results, do not replace answers",
        "Requirement E — Reversible: removal does not break Production",
    ]


def anti_overengineering_rules() -> list[str]:
    return [
        "Max 1 new C3+ Core Capability per phase",
        "No Core mass production",
        "Abstraction for abstraction's sake forbidden",
        "Harness creation alone is not success",
        "Capability count is not a success metric",
        "Future convenience alone cannot justify Production change",
        "'Not used now' is not a rejection reason — use C1/C2/C3 instead",
    ]


def human_review_boundary() -> list[str]:
    return [
        "Production Architecture change",
        "Agent policy change",
        "SYSTEM_PROMPT change",
        "Registry change",
        "Warning / Retry / Fallback Production connection",
        "Mechanical Verification Production connection",
        "Core Capability answer replacement",
        "Capability strongly constrains existing Architecture",
    ]


def sunset_policy() -> dict[str, Any]:
    return {
        "triggers": [
            "2 consecutive phases unused",
            "No new use cases discovered",
            "No measured benefit",
            "Maintenance cost increasing",
        ],
        "actions": ["KEEP", "SIMPLIFY", "SUNSET"],
        "exception": "Important defensive capabilities — do not delete on frequency alone",
    }


def existing_core_registry() -> list[CoreCapabilityRecord]:
    """Known Core Capabilities with reuse tracking from observed phases."""
    return [
        CoreCapabilityRecord(
            id="PROD-web_status",
            name="web_status + WebSessionTracker",
            classification="C4",
            location="tools/system/network/web_status.py",
            reuse_count=12,
            consumers=[
                "agent.py",
                "production_agent_web_loop",
                "web_tool_success_class_*",
                "eval_production_parity_bridge",
            ],
            consuming_phases=["extraction", "status_boundary", "success_class", "canonical_migration"],
            actual_benefit="Layer-level SUCCESS/FAILURE gate for Web chain",
            maintenance_cost="LOW",
            last_used_phase="canonical_migration",
            production_connected=True,
        ),
        CoreCapabilityRecord(
            id="PROD-boundary",
            name="web_answer_boundary",
            classification="C4",
            location="tools/system/network/web_answer_boundary.py",
            reuse_count=10,
            consumers=["agent.py", "production_agent_web_loop", "eval_production_parity_bridge"],
            consuming_phases=["status_boundary", "success_class", "canonical_migration"],
            actual_benefit="Suppress numeric claims on Web failure",
            maintenance_cost="LOW",
            last_used_phase="canonical_migration",
            production_connected=True,
        ),
        CoreCapabilityRecord(
            id="CC-01",
            name="Eval Production Parity Bridge",
            classification="C3",
            location="ai_tool/agent_integration/eval_production_parity_bridge.py",
            reuse_count=8,
            consumers=[
                "web_tool_practical_evaluation*",
                "web_tool_end_to_end_evaluation_phase3",
                "web_tool_success_class_*",
                "web_tool_autonomous_improvement",
                "web_tool_evaluation_canonical_migration",
            ],
            consuming_phases=["parity_bridge", "canonical_migration"],
            actual_benefit="Eval/Production parity; mock false-PASS prevention",
            maintenance_cost="LOW",
            last_used_phase="canonical_migration",
            production_connected=False,
            notes=["RETAIN_CORE — validated by migration"],
        ),
        CoreCapabilityRecord(
            id="CC-02",
            name="Mechanical Verification",
            classification="C3",
            location="ai_tool/experimental/mechanical_verification/",
            reuse_count=3,
            consumers=["web_tool_mechanical_verification_investigation", "success_class eval"],
            consuming_phases=["mechanical_verification_investigation"],
            actual_benefit="Claim verification observation-only; FP=0 FN=0 on scenarios",
            maintenance_cost="LOW",
            last_used_phase="mechanical_verification_investigation",
            production_connected=False,
            notes=[
                "No Warning/Retry/Fallback Production connection",
                "Mechanical Verification ≠ Mechanical Answer (SCR-02)",
                "Observation-oriented; extends LLM anomaly detection, does not replace conversation",
            ],
        ),
        CoreCapabilityRecord(
            id="EVAL-production_mirror",
            name="production_mirror",
            classification="C3",
            location="ai_tool/agent_integration/production_agent_web_loop.py",
            reuse_count=15,
            consumers=["success_class", "broader eval", "golden e2e", "CC-01 bridge delegate"],
            consuming_phases=["multiple web_tool eval phases"],
            actual_benefit="Agent loop mirror without agent.py import",
            maintenance_cost="LOW",
            last_used_phase="canonical_migration",
            production_connected=False,
        ),
        CoreCapabilityRecord(
            id="EVAL-failure_diagnosis",
            name="failure_diagnosis_phase4",
            classification="C3",
            location="ai_tool/web_tool_failure_diagnosis_phase4.py",
            reuse_count=4,
            consumers=["e2e phase3", "failure isolation"],
            consuming_phases=["failure_diagnosis", "e2e phase3"],
            actual_benefit="Observation bundle for Web failures",
            maintenance_cost="LOW",
            last_used_phase="failure_diagnosis_phase4",
            production_connected=False,
        ),
        CoreCapabilityRecord(
            id="C1-CC-03",
            name="Capability Lifecycle Registry",
            classification="C1",
            location="(not implemented)",
            reuse_count=0,
            consumers=[],
            consuming_phases=["core_capability_discovery"],
            actual_benefit="None yet — hypothesized anti-bloat",
            maintenance_cost="LOW",
            last_used_phase="core_capability_discovery",
            production_connected=False,
            sunset_status="N/A",
        ),
    ]


def phase_core_candidates() -> list[CoreCandidate]:
    """This phase: policy integration — no new C3; CC-03 remains C1."""
    return [
        CoreCandidate(
            id="CC-03",
            name="Capability Lifecycle Registry",
            problem="6+ experimental touchpoints; manual tracking of reuse/sunset",
            classification="C1",
            future_uses=[
                "Sunset enforcement for Model B",
                "Autonomous loop inventory of experimental surface",
            ],
            matrix=CostBenefitMatrix(
                implementation_cost="LOW",
                maintenance_cost="LOW",
                reuse_value="HIGH",
                defensive_value="MEDIUM",
                future_value="MEDIUM",
                coupling_risk="LOW",
                production_risk="LOW",
                reversibility="HIGH",
            ),
            current_evidence="HYPOTHESIS — 8 CC-01 consumers documented in migration",
            production_impact="NONE",
            experimental_value="MEDIUM — record until active experimental > 5",
            recommendation="C1 Record — do not build registry until manual tracking fails",
        ),
    ]


def active_specification_requests() -> list[SpecificationChangeRequest]:
    return [
        SpecificationChangeRequest(
            id="SCR-01",
            current_specification="Web eval harnesses may use eval-direct or production_mirror interchangeably",
            observed_problem="Mock default diverges from Production; autonomous STOP can false-pass",
            proposed_specification="Scored metrics MUST use run_canonical_web_eval; eval-direct diagnostic-only",
            reason="Self-improvement loop integrity",
            expected_benefit=[
                "Autonomous STOP aligns with Production",
                "CC-01 reuse validated",
            ],
            risk=["Over-constraining quick diagnostic probes"],
            migration_cost=["Harness migration — largely complete in canonical_migration phase"],
            backward_compatibility="Diagnostic path retained with explicit path_label",
            human_review_required=True,
        ),
        SpecificationChangeRequest(
            id="SCR-02",
            current_specification="Implicit mix of LLM-centric conversation and mechanical answer patterns",
            observed_problem="Context/Verification phases risked conflating packaging gains with Production answer replacement",
            proposed_specification=(
                "LLM-centric conversational Agent; Web extends LLM; "
                "Mechanical Verification ≠ Mechanical Answer; Q8 LLM extend vs replace"
            ),
            reason="Align Core Discovery and autonomous development with architecture intent",
            expected_benefit=[
                "Clear Production connection bar for mechanical answer replacement",
                "Context packaging evaluated as LLM extension only",
                "Conflict/multi-source handled conversationally when LLM succeeds",
            ],
            risk=["Over-deferring useful defensive capabilities"],
            migration_cost=["Documentation and policy module only — no Production migration"],
            backward_compatibility="Production chain unchanged; experimental modules retained",
            human_review_required=False,
        ),
    ]


def evaluate_policy_adoption(*, golden_pass: bool, integration_cost: str) -> tuple[PolicyAdoption, str]:
    if not golden_pass:
        return "DEFER", "Golden regression failed — defer policy until stable"
    if integration_cost == "HIGH":
        return "DEFER", "Integration cost too high — design only (C2)"
    return (
        "ADOPT_WITH_LIMITS",
        "Policy module integrates without Production/Agent/Registry changes; "
        "max 1 C3/phase, sunset rules, HR boundary preserved; policy version mutable",
    )


def build_mandatory_phase_report(*, phase_id: str, golden: dict[str, Any]) -> MandatoryPhaseReport:
    candidates = phase_core_candidates()
    registry = existing_core_registry()
    by_class: dict[str, list[str]] = {"C0": [], "C1": [], "C2": [], "C3": [], "C4": []}
    for c in candidates:
        by_class[c.classification].append(c.id)
    for r in registry:
        if r.classification in by_class and r.id not in by_class[r.classification]:
            pass  # existing cores tracked separately

    golden_pass = golden.get("overall") == "PASS"
    adoption, adoption_reason = evaluate_policy_adoption(golden_pass=golden_pass, integration_cost="LOW")

    decisions: list[PhaseDecision] = ["CONTINUE", "RECORD"]
    if any(c.classification == "C3" for c in candidates):
        decisions.append("EXPERIMENTAL_CAPABILITY")
    if active_specification_requests():
        decisions.append("HUMAN_REVIEW_REQUIRED")
    if not any(c.classification in ("C2", "C3", "C4") for c in candidates):
        decisions.append("NO_CORE_ACTION")

    new_consumers = ["defensive_core_discovery_policy (this phase)"]
    total_reuse = sum(r.reuse_count for r in registry)

    return MandatoryPhaseReport(
        phase_id=phase_id,
        current_problem_track={
            "observed_problems": [],
            "fixed_problems": [],
            "remaining_problems": ["SCR-01 full project policy adoption (optional HR)"],
            "regression": f"Golden {golden.get('pass_count')}/{golden.get('total')} {golden.get('overall')}",
        },
        future_core_track={
            "candidate_count": len(candidates),
            "C1": [c.id for c in candidates if c.classification == "C1"],
            "C2": [c.id for c in candidates if c.classification == "C2"],
            "C3": [c.id for c in candidates if c.classification == "C3"],
            "C4": [c.id for c in candidates if c.classification == "C4"],
            "rejected_candidates": [],
            "discovery_questions": discovery_questions(),
        },
        existing_core_usage={
            "registry_count": len(registry),
            "total_reuse_count": total_reuse,
            "cores": [r.to_dict() for r in registry],
            "new_consumers_this_phase": new_consumers,
            "cc01_reuse_count": next(r.reuse_count for r in registry if r.id == "CC-01"),
            "mechanical_verification_status": "C3 retain — no Production connection",
        },
        specification_requests=[s.to_dict() for s in active_specification_requests()],
        complexity_check={
            "added_loc_estimate": "~350 (policy module + runner + tests)",
            "added_modules": ["defensive_core_discovery_policy.py"],
            "new_dependencies": "none on Production",
            "coupling_increase": "LOW — eval/harness imports only",
            "maintenance_burden": "LOW",
            "agent_changes": False,
            "registry_changes": False,
            "prompt_changes": False,
        },
        decisions=sorted(set(decisions)),
        policy_adoption=adoption,
        policy_adoption_rationale=adoption_reason,
    )


def policy_summary_for_harnesses() -> dict[str, Any]:
    """Compact policy blob for other harness decision logs."""
    return {
        "policy_version": POLICY_VERSION,
        "tracks": policy_tracks(),
        "classification": classification_rules(),
        "c3_requirements": c3_creation_requirements(),
        "anti_overengineering": anti_overengineering_rules(),
        "human_review_boundary": human_review_boundary(),
        "sunset_policy": sunset_policy(),
        "llm_capability_role": llm_capability_role_criteria(),
        "architecture_spec": "SCR-02 WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md",
        "operating_model": normal_development_operating_model(),
        "end_tool_rule": "YAGNI — build when needed",
        "core_rule": "Evaluate future value × reuse vs cost × coupling; Q8 extend vs replace LLM",
    }


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def run_defensive_core_discovery_policy_integration(*, fetch_live_baseline: bool = True) -> dict[str, Any]:
    head = _git_head()
    golden = run_production_golden(fetch_live=fetch_live_baseline)
    phase_id = "defensive_core_discovery_policy_integration"
    report = build_mandatory_phase_report(phase_id=phase_id, golden=golden)

    stop_triggered = any(
        report.complexity_check.get(k)
        for k in ("agent_changes", "registry_changes", "prompt_changes")
        if report.complexity_check.get(k)
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": head,
        "final_head": head,
        "policy_version": POLICY_VERSION,
        "overall": "PASS" if golden.get("overall") == "PASS" and not stop_triggered else "PARTIAL",
        "production_changes": [],
        "registry_changes": [],
        "agent_changes": [],
        "prompt_changes": [],
        "policy_module": "ai_tool/defensive_core_discovery_policy.py",
        "policy_summary": policy_summary_for_harnesses(),
        "mandatory_phase_report": report.to_dict(),
        "policy_adoption": report.policy_adoption,
        "policy_adoption_rationale": report.policy_adoption_rationale,
        "phase_decisions": report.decisions,
        "golden_baseline": {
            "overall": golden.get("overall"),
            "pass_count": golden.get("pass_count"),
            "total": golden.get("total"),
        },
        "stop_reason": None if not stop_triggered else "STOP condition: Production/Agent/Registry change required",
        "integration_status": "IMPLEMENTED" if not stop_triggered else "C2_INVESTIGATE_ONLY",
    }
