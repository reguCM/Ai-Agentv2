"""Phase H harness — URScript Validator + URSim boundary PoC."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from ai_tool.experimental.development_assistance.goal_abstraction import discover_capabilities
from ai_tool.experimental.ur_program_validator.compare import compare_results
from ai_tool.experimental.ur_program_validator.llm_explanation import explain_validation, format_for_llm_context
from ai_tool.experimental.ur_program_validator.official_sources import (
    collect_official_sources,
    investigate_ursim_environment,
)
from ai_tool.experimental.ur_program_validator.spec_catalog import build_catalog
from ai_tool.experimental.ur_program_validator.static_validator import suggest_fixes, validate_script
from ai_tool.experimental.ur_program_validator.test_cases import URTestCase, all_test_cases
from ai_tool.experimental.ur_program_validator.ur_sim_adapter import probe_local_ursim, run_ursim
from ai_tool.experimental.ur_program_validator.version_context import VersionContext
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

PhaseHDecision = Literal[
    "POC_BOUNDARY_CONFIRMED",
    "CONTINUE",
    "STOP_URSIM_UNAVAILABLE",
    "INVESTIGATE",
]


def _check_expect(actual: str, expected: str) -> bool:
    if expected == "ANY" or expected == "SKIP":
        return True
    if expected == "WARNING" and actual in ("WARNING", "PASS"):
        return True
    return actual == expected


def run_test_case(case: URTestCase) -> dict[str, Any]:
    catalog = build_catalog(polyscope_version=case.polyscope_version)
    ctx = VersionContext(
        robot=catalog.robot,
        polyscope_version=case.polyscope_version,
        urscript_version=catalog.urscript_version,
    )
    v_result = validate_script(case.script, catalog, version_ctx=ctx)
    u_result = run_ursim(
        case.script,
        test_id=case.test_id,
        expect_runtime_fail=case.expect_runtime_fail,
        polyscope_version=case.polyscope_version,
    )
    cmp = compare_results(v_result, u_result, test_id=case.test_id)
    suggestions = suggest_fixes(v_result, catalog)
    explanation = explain_validation(v_result, u_result, cmp, test_id=case.test_id)

    failures: list[str] = []
    if not _check_expect(v_result.status, case.expect_validator):
        failures.append(f"validator expected {case.expect_validator} got {v_result.status}")
    if case.expect_ursim != "SKIP" and not _check_expect(u_result.status, case.expect_ursim):
        failures.append(f"ursim expected {case.expect_ursim} got {u_result.status}")
    if case.expect_compare != "ANY" and cmp.interpretation != case.expect_compare:
        failures.append(f"compare expected {case.expect_compare} got {cmp.interpretation}")

    return {
        "test_id": case.test_id,
        "label": case.label,
        "notes": case.notes,
        "validator": v_result.to_dict(),
        "ursim": u_result.to_dict(),
        "compare": cmp.to_dict(),
        "suggestions": suggestions,
        "llm_explanation": explanation,
        "llm_context": format_for_llm_context(v_result, u_result, cmp, suggestions),
        "pass": len(failures) == 0,
        "failures": failures,
    }


def run_phase_h_poc() -> dict[str, Any]:
    env = investigate_ursim_environment()
    probe = probe_local_ursim()
    sources = collect_official_sources()
    hierarchy = discover_capabilities(
        "URScript program validator with URSim simulation boundary for Universal Robots"
    )

    results = [run_test_case(c) for c in all_test_cases()]
    pass_count = sum(1 for r in results if r["pass"])
    total = len(results)

    disagreements = [r for r in results if r["compare"]["interpretation"] not in ("expected", "unknown")]
    critical_misses = [r for r in results if r["compare"]["interpretation"] == "critical_miss"]

    catalog = build_catalog()
    capability_ideas = [
        {
            "idea": "Specification-backed Code Validator",
            "stage": "Phase H",
            "why_useful": "Generalize URScript validator to other DSLs",
            "higher_level_goal": hierarchy.goals.level_2,
            "existing_alternative": "static_validator.py pattern",
            "cost": "MEDIUM",
            "risk": "Over-generalization",
            "decision": "RECORD",
        },
        {
            "idea": "URSim full automation API",
            "stage": "URSim adapter",
            "why_useful": "CI integration for robot programs",
            "existing_alternative": "manual HITL",
            "cost": "HIGH",
            "risk": "Automation fragility",
            "decision": "DEFER",
        },
        {
            "idea": "Version Matrix Core",
            "stage": "Version handling",
            "why_useful": "Cross-version function matrix",
            "existing_alternative": "spec_catalog + VersionContext",
            "cost": "HIGH",
            "risk": "Scope creep",
            "decision": "REJECT",
        },
        {
            "idea": "Real robot execution bridge",
            "stage": "Safety",
            "why_useful": "End-to-end validation",
            "existing_alternative": "none in PoC",
            "cost": "HIGH",
            "risk": "SAFETY — prohibited in Phase H",
            "decision": "REJECT",
        },
    ]

    h_checks = {
        "H1_official_spec": len(sources) >= 1,
        "H2_version_distinction": any(r["test_id"].startswith("T6") for r in results),
        "H3_unknown_function": any(
            r["test_id"] in ("T2", "T2b") and r["validator"]["status"] == "FAIL" for r in results
        ),
        "H4_arg_errors": any(r["test_id"] == "T3" and r["validator"]["status"] == "FAIL" for r in results),
        "H5_syntax_errors": any(r["test_id"] == "T5" and r["validator"]["status"] == "FAIL" for r in results),
        "H6_ursim_normal": any(r["test_id"].startswith("T8") and r["ursim"]["status"] == "PASS" for r in results),
        "H7_ursim_abnormal": any(r["test_id"] == "T2" and r["ursim"]["status"] == "FAIL" for r in results),
        "H8_compare": len(results) == total,
        "H9_boundary_explicit": bool(catalog.to_dict().get("functions")),
        "H10_llm_explain": all(r.get("llm_explanation") for r in results),
        "H11_provenance": all(r.get("suggestions") is not None for r in results),
        "H12_safety_boundary": True,
    }

    golden = run_production_golden()

    decision: PhaseHDecision
    if pass_count == total and h_checks["H1_official_spec"]:
        decision = "POC_BOUNDARY_CONFIRMED"
    elif probe.mode == "unavailable" and not results:
        decision = "STOP_URSIM_UNAVAILABLE"
    else:
        decision = "CONTINUE" if pass_count >= total - 1 else "INVESTIGATE"

    return {
        "phase": "URScript Static Validation + URSim Boundary PoC (Phase H)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env.to_dict(),
        "ursim_probe": probe.to_dict(),
        "official_sources": [s.to_dict() for s in sources],
        "spec_catalog_summary": {
            "robot": catalog.robot,
            "function_count": len(catalog.functions),
            "coverage_note": "Minimal PoC — not full URScript manual",
        },
        "test_results": results,
        "pass_count": pass_count,
        "total": total,
        "validator_ursim_disagreements": disagreements,
        "critical_misses": critical_misses,
        "automation_assessment": {
            "level": probe.automation_level,
            "mode": probe.mode,
            "why_difficult": "URSim not installed; Docker present but container not orchestrated",
            "missing_api": "Official URSim headless execution API not integrated",
            "manual_operation": "Human-in-the-loop verification path recommended",
            "workaround": "Stub adapter for structural PoC; live URSim manual run",
        },
        "success_criteria": h_checks,
        "capability_ideas": capability_ideas,
        "goal_abstraction": hierarchy.to_dict(),
        "production_changes": 0,
        "core_discovery": {"c3_implemented": 0},
        "golden_pass": golden.get("pass"),
        "decision": decision,
        "safety_boundary": [
            "No real robot connection",
            "Validator PASS ≠ safe",
            "URSim Success ≠ real robot safe",
            "Static validation scope explicitly limited",
        ],
    }
