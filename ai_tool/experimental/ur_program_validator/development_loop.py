"""Phase I — TDA Tool Development Loop (Validator + URSim + LLM explanation)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec, tda_evaluation_cases
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import assess_reuse, extract_requirement_facets
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.ur_program_validator.compare import compare_results
from ai_tool.experimental.ur_program_validator.llm_explanation import explain_validation, format_for_llm_context
from ai_tool.experimental.ur_program_validator.live_ursim_manager import (
    docker_daemon_ok,
    execute_urscript_live,
)
from ai_tool.experimental.ur_program_validator.spec_catalog import build_catalog
from ai_tool.experimental.ur_program_validator.static_validator import suggest_fixes, validate_script
from ai_tool.experimental.ur_program_validator.ur_sim_adapter import run_ursim_stub
from ai_tool.experimental.ur_program_validator.version_context import VersionContext

LoopDecision = Literal["LOOP_COMPLETED", "LOOP_PARTIAL", "LOOP_BLOCKED"]

PHASE_I_REQUIREMENT = (
    "URScriptで簡単なロボットプログラムを作りたい。"
    "必要な仕様を調べて、実際にシミュレータで確認できるところまでやってほしい。"
)

PHASE_I_REUSE_REQUIREMENT = (
    "前回調べたURScriptについて、PolyScope 5.15向けの別Version観点だけ追加調査したい。"
)


@dataclass
class ScriptAttempt:
    attempt: int
    script: str
    validator_status: str
    ursim_status: str
    compare_interpretation: str
    revision_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "script": self.script,
            "validator_status": self.validator_status,
            "ursim_status": self.ursim_status,
            "compare_interpretation": self.compare_interpretation,
            "revision_reason": self.revision_reason,
            "note": "Records observation only — not LLM understood correctness",
        }


@dataclass
class DevelopmentLoopResult:
    requirement: str
    workflow: dict[str, Any]
    reuse_assessment: dict[str, Any] | None
    attempts: list[ScriptAttempt]
    final_explanation: str
    llm_context: dict[str, Any]
    decision: LoopDecision
    capability_ideas: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "workflow": self.workflow,
            "reuse_assessment": self.reuse_assessment,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_explanation": self.final_explanation,
            "llm_context": self.llm_context,
            "decision": self.decision,
            "capability_ideas": self.capability_ideas,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _catalog_script_v1() -> str:
    """First candidate from official catalog — not LLM memory."""
    return """
def simple_move():
    movej(get_actual_joint_positions(), 0.4, 0.4)
end
"""


def _catalog_script_v2() -> str:
    """Revision after simulated failure — still catalog-backed."""
    return """
def simple_move():
    movej(get_actual_joint_positions(), 0.4, 0.4)
    sleep(0.05)
end
"""


def _run_ursim_for_loop(script: str, *, polyscope_version: str = "5.15") -> Any:
    if docker_daemon_ok():
        live = execute_urscript_live(script)
        return live.to_ursim_result(automation_level=2)
    return run_ursim_stub(script, polyscope_version=polyscope_version)


def run_development_loop(
    requirement: str = PHASE_I_REQUIREMENT,
    *,
    max_attempts: int = 3,
    seed_store: ResearchStore | None = None,
) -> DevelopmentLoopResult:
    """
    Minimal TDA → URScript → Validator → URSim → LLM explanation loop.
    Does not claim LLM correctness — only observations.
    """
    store = seed_store or ResearchStore()
    ur_case = next((c for c in tda_evaluation_cases() if c.case_id == "TDA-G"), None)
    tda = ur_case or TDACaseSpec(
        case_id="PhaseI-UR",
        label="URScript development loop",
        requirement=requirement,
        fixture_html_key="urscript",
    )

    workflow = run_standard_workflow(requirement, tda=tda, store=store, llm_enabled=False)
    wf_dict = workflow.to_dict()

    reuse = None
    facets = extract_requirement_facets(PHASE_I_REUSE_REQUIREMENT)
    if store.records:
        reuse = assess_reuse(facets, store).to_dict()

    catalog = build_catalog(polyscope_version="5.15")
    ctx = VersionContext(
        robot=catalog.robot,
        polyscope_version="5.15",
        urscript_version=catalog.urscript_version,
    )

    scripts = [_catalog_script_v1(), _catalog_script_v2()]
    attempts: list[ScriptAttempt] = []
    revision_reasons = ["initial catalog-backed candidate", "added sleep() after observation review"]

    for i in range(min(max_attempts, len(scripts))):
        script = scripts[i]
        v = validate_script(script, catalog, version_ctx=ctx)
        u = _run_ursim_for_loop(script)
        cmp = compare_results(v, u, test_id=f"loop-{i+1}")
        attempts.append(
            ScriptAttempt(
                attempt=i + 1,
                script=script.strip(),
                validator_status=v.status,
                ursim_status=u.status,
                compare_interpretation=cmp.interpretation,
                revision_reason=revision_reasons[i] if i < len(revision_reasons) else "retry",
            )
        )
        if v.status == "PASS" and u.status == "PASS":
            break

    last_v = validate_script(attempts[-1].script, catalog, version_ctx=ctx)
    last_u = _run_ursim_for_loop(attempts[-1].script)
    last_cmp = compare_results(last_v, last_u, test_id="loop-final")
    suggestions = suggest_fixes(last_v, catalog)
    explanation = explain_validation(last_v, last_u, last_cmp, test_id="development-loop")
    llm_ctx = format_for_llm_context(last_v, last_u, last_cmp, suggestions)

    decision: LoopDecision
    if wf_dict.get("stop_reason") and attempts and attempts[-1].validator_status == "PASS":
        decision = "LOOP_COMPLETED" if attempts[-1].ursim_status == "PASS" else "LOOP_PARTIAL"
    else:
        decision = "LOOP_PARTIAL"

    ideas = [
        {
            "idea": "Simulation-backed Development Assistant",
            "stage": "Phase I loop",
            "higher_level_goal": wf_dict.get("goals", {}).get("level_2", ""),
            "existing_capability": "standard_workflow + ur_program_validator",
            "potential_generalization": "Other DSL validators + simulators",
            "cost": "HIGH",
            "risk": "Over-automation of safety-critical domains",
            "decision": "RECORD",
        },
        {
            "idea": "Research Transaction Core",
            "stage": "Research resume",
            "higher_level_goal": "Cross-session evidence reuse",
            "existing_capability": "research_reuse.py",
            "cost": "HIGH",
            "risk": "Scope creep",
            "decision": "REJECT",
        },
    ]

    return DevelopmentLoopResult(
        requirement=requirement,
        workflow=wf_dict,
        reuse_assessment=reuse,
        attempts=attempts,
        final_explanation=explanation,
        llm_context=llm_ctx,
        decision=decision,
        capability_ideas=ideas,
    )
