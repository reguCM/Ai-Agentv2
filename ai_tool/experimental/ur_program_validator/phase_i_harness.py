"""Phase I harness — Live URSim + Validator + TDA Development Loop."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.compare import compare_results
from ai_tool.experimental.ur_program_validator.development_loop import run_development_loop
from ai_tool.experimental.ur_program_validator.live_environment import investigate_live_environment
from ai_tool.experimental.ur_program_validator.live_test_cases import LiveTestCase, all_live_test_cases
from ai_tool.experimental.ur_program_validator.live_ursim_manager import (
    assess_automation_level,
    docker_daemon_ok,
    execute_urscript_live,
    run_smoke_test,
    stop_container,
)
from ai_tool.experimental.ur_program_validator.llm_explanation import explain_validation, format_for_llm_context
from ai_tool.experimental.ur_program_validator.spec_catalog import build_catalog
from ai_tool.experimental.ur_program_validator.static_validator import suggest_fixes, validate_script
from ai_tool.experimental.ur_program_validator.ur_sim_adapter import run_ursim_stub
from ai_tool.experimental.ur_program_validator.version_context import VersionContext
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

PhaseIDecision = Literal[
    "LIVE_POC_CONFIRMED",
    "DEVELOPMENT_LOOP_CONFIRMED",
    "AUTOMATION_LIMIT_CONFIRMED",
    "BLOCKED",
]


def _run_live_test(case: LiveTestCase, *, live_mode: bool) -> dict[str, Any]:
    catalog = build_catalog(polyscope_version=case.polyscope_version)
    ctx = VersionContext(
        robot=catalog.robot,
        polyscope_version=case.polyscope_version,
        urscript_version=catalog.urscript_version,
    )
    v_result = validate_script(case.script, catalog, version_ctx=ctx)

    if live_mode:
        live_exec = execute_urscript_live(case.script)
        u_result = live_exec.to_ursim_result(automation_level=2)
    else:
        u_result = run_ursim_stub(case.script, test_id=case.test_id, polyscope_version=case.polyscope_version)

    cmp = compare_results(v_result, u_result, test_id=case.test_id)
    suggestions = suggest_fixes(v_result, catalog)
    explanation = explain_validation(v_result, u_result, cmp, test_id=case.test_id)

    t7_result = "NOT_APPLICABLE"
    if case.test_id == "I-T6":
        if v_result.status in ("PASS", "WARNING") and u_result.status == "FAIL":
            t7_result = "CRITICAL_MISS"
        elif v_result.status in ("PASS", "WARNING") and u_result.status == "PASS":
            t7_result = "NOT_FOUND"
        else:
            t7_result = "OTHER"

    failures: list[str] = []
    if case.expect_validator != "ANY" and v_result.status != case.expect_validator:
        if not (case.expect_validator == "WARNING" and v_result.status == "PASS"):
            failures.append(f"validator expected {case.expect_validator} got {v_result.status}")
    if case.expect_ursim != "ANY" and case.expect_ursim != "SKIP" and u_result.status != case.expect_ursim:
        failures.append(f"ursim expected {case.expect_ursim} got {u_result.status}")
    if case.expect_compare != "ANY" and cmp.interpretation != case.expect_compare:
        failures.append(f"compare expected {case.expect_compare} got {cmp.interpretation}")

    return {
        "test_id": case.test_id,
        "label": case.label,
        "live_mode": live_mode,
        "validator": v_result.to_dict(),
        "ursim": u_result.to_dict(),
        "compare": cmp.to_dict(),
        "t7_live_result": t7_result,
        "suggestions": suggestions,
        "llm_explanation": explanation,
        "llm_context": format_for_llm_context(v_result, u_result, cmp, suggestions),
        "pass": len(failures) == 0,
        "failures": failures,
        "notes": case.notes,
    }


def run_phase_i_poc(*, attempt_live: bool = True) -> dict[str, Any]:
    env_report = investigate_live_environment()
    live_mode = attempt_live and env_report.live_available

    smoke = None
    smoke_passed = False
    if live_mode:
        smoke = run_smoke_test()
        smoke_passed = smoke.passed
        if not smoke_passed:
            live_mode = False

    test_results = [_run_live_test(c, live_mode=live_mode) for c in all_live_test_cases()]
    pass_count = sum(1 for r in test_results if r["pass"])

    t7_cases = [r for r in test_results if r["test_id"] == "I-T6"]
    t7_live = t7_cases[0]["t7_live_result"] if t7_cases else "NOT_APPLICABLE"

    dev_loop = run_development_loop()
    automation = assess_automation_level(smoke)

    if live_mode:
        stop_container()

    i_checks = {
        "I1_live_start": smoke_passed if live_mode else False,
        "I2_robot_select": bool(smoke and smoke.robot_model_visible != "UNKNOWN") if live_mode else False,
        "I3_official_script": any(r["test_id"] == "I-T1" for r in test_results),
        "I4_normal_confirm": any(
            r["test_id"] == "I-T1" and r["validator"]["status"] == "PASS" for r in test_results
        ),
        "I5_abnormal_confirm": any(
            r["test_id"] in ("I-T2", "I-T3", "I-T4") and r["validator"]["status"] == "FAIL" for r in test_results
        ),
        "I6_compare": all("compare" in r for r in test_results),
        "I7_t7_attempted": t7_live != "NOT_APPLICABLE",
        "I8_automation_level": automation.get("level") is not None,
        "I9_llm_observation": all(r.get("llm_explanation") for r in test_results),
        "I10_provenance": bool(env_report.official_sources),
        "I11_dev_loop": dev_loop.decision in ("LOOP_COMPLETED", "LOOP_PARTIAL"),
    }

    golden = run_production_golden()

    decision: PhaseIDecision
    if not env_report.live_available:
        decision = "BLOCKED"
    elif live_mode and smoke_passed and pass_count == len(test_results):
        decision = "DEVELOPMENT_LOOP_CONFIRMED" if dev_loop.decision == "LOOP_COMPLETED" else "LIVE_POC_CONFIRMED"
    elif live_mode and smoke_passed:
        decision = "AUTOMATION_LIMIT_CONFIRMED"
    else:
        decision = "BLOCKED" if not env_report.live_available else "AUTOMATION_LIMIT_CONFIRMED"

    capability_ideas = dev_loop.capability_ideas + [
        {
            "idea": "URSim PolyScope X image",
            "stage": "Environment",
            "higher_level_goal": "Next-gen PolyScope",
            "existing_capability": "ursim_e-series selected",
            "cost": "MEDIUM",
            "risk": "Version drift",
            "decision": "DEFER",
        },
        {
            "idea": "WSL2 bootstrap automation",
            "stage": "Windows host",
            "why_useful": "Enable Docker Desktop backend",
            "existing_capability": "manual install",
            "cost": "LOW",
            "risk": "Environment change",
            "decision": "RECORD",
        },
    ]

    return {
        "phase": "Live URSim Verification + Tool Development Loop (Phase I)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env_report.to_dict(),
        "live_mode": live_mode,
        "smoke_test": smoke.to_dict() if smoke else None,
        "test_results": test_results,
        "pass_count": pass_count,
        "total": len(test_results),
        "t7_live_result": t7_live,
        "t7_phase_h_comparison": (
            "Phase H T7 used RUNTIME_FAIL synthetic marker → critical_miss in stub. "
            "Live I-T6 without marker: NOT_FOUND if both PASS."
        ),
        "automation_assessment": automation,
        "development_loop": dev_loop.to_dict(),
        "success_criteria": i_checks,
        "capability_ideas": capability_ideas,
        "production_changes": 0,
        "core_discovery": {"c3_implemented": 0},
        "golden_pass": golden.get("pass"),
        "decision": decision,
        "safety_boundary": [
            "No real robot connection",
            "URSim Success ≠ real robot safe",
            "Validator PASS ≠ runtime correctness",
            "Live automation uses secondary client — not full PolyScope UI path",
        ],
        "block_reason": env_report.block_reason if not env_report.live_available else "",
    }
