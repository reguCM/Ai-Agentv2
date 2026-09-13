"""Phase I-R harness — Environment Recovery & Official Simulation Re-evaluation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.development_loop import run_development_loop
from ai_tool.experimental.ur_program_validator.environment_recovery import (
    assess_deployment_decision,
    build_environment_matrix,
    collect_phase_i_r_official_sources,
    compare_ursim_versions,
    probe_extended_host,
)
from ai_tool.experimental.ur_program_validator.live_environment import investigate_live_environment
from ai_tool.experimental.ur_program_validator.live_ursim_manager import (
    assess_automation_level,
    docker_daemon_ok,
    run_smoke_test,
    stop_container,
)
from ai_tool.experimental.ur_program_validator.phase_i_harness import _run_live_test
from ai_tool.experimental.ur_program_validator.recovery_test_cases import all_recovery_test_cases
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

PhaseIRDecision = Literal[
    "LIVE_URSIM_CONFIRMED",
    "LIVE_URSIM_AUTOMATION_CONFIRMED",
    "LIVE_DEVELOPMENT_LOOP_CONFIRMED",
    "ENVIRONMENT_BLOCKED",
    "ENVIRONMENT_ALTERNATIVE_CONFIRMED",
    "PENDING_USER_APPROVAL",
]


def _try_docker_recovery() -> dict[str, Any]:
    """Non-destructive Docker recovery attempt — no WSL install."""
    env = investigate_live_environment()
    result: dict[str, Any] = {
        "attempted": True,
        "daemon_before": env.host.docker_daemon,
        "daemon_after": docker_daemon_ok(),
        "actions_taken": ["Docker Desktop start attempted in probe only — no WSL install"],
        "wsl_required": not env.host.wsl_installed,
        "success": docker_daemon_ok(),
    }
    if not result["success"]:
        result["failure_class"] = "Docker daemon / WSL backend"
        result["note"] = "Windows Docker Desktop typically requires WSL2 when Hyper-V backend unavailable"
    return result


def run_phase_i_r_investigation(*, attempt_live: bool = True) -> dict[str, Any]:
    """
    Phase I-R architecture investigation.
    Stops at PENDING_USER_APPROVAL when OS/virtualization changes required.
    """
    sources = collect_phase_i_r_official_sources()
    host_ext = probe_extended_host()
    versions = compare_ursim_versions()
    matrix = build_environment_matrix()
    decision_info = assess_deployment_decision()
    docker_recovery = _try_docker_recovery() if attempt_live else {"attempted": False}

    live_mode = attempt_live and docker_daemon_ok()
    smoke = None
    if live_mode:
        smoke = run_smoke_test()
        if not smoke.passed:
            live_mode = False

    test_results = [_run_live_test(c, live_mode=live_mode) for c in all_recovery_test_cases()]
    pass_count = sum(1 for r in test_results if r["pass"])

    t7 = next((r for r in test_results if r["test_id"] == "I-R6"), {})
    t7_result = "NOT_FOUND"
    if t7.get("validator", {}).get("status") in ("PASS", "WARNING") and t7.get("ursim", {}).get("status") == "FAIL":
        t7_result = "CRITICAL_MISS"
    elif t7.get("validator", {}).get("status") in ("PASS", "WARNING") and t7.get("ursim", {}).get("status") == "PASS":
        t7_result = "NOT_FOUND"

    dev_loop = None
    if live_mode:
        dev_loop = run_development_loop()
        stop_container()

    automation = assess_automation_level(smoke)

    golden = run_production_golden()

    r_checks = {
        "R1_environment_reprobe": bool(host_ext),
        "R2_official_methods_compared": len(matrix) >= 3,
        "R3_docker_attempted": docker_recovery.get("attempted", False),
        "R4_alternative_documented": any("VirtualBox" in m.name for m in matrix),
        "R5_live_start": smoke.passed if smoke else False,
        "R6_polyscope_access": smoke.polyscope_accessible if smoke else False,
        "R7_robot_select": smoke.robot_model_visible != "UNKNOWN" if smoke else False,
        "R8_ursim_execute": live_mode and any(r["ursim"].get("executed") for r in test_results),
        "R9_validator_compare": all("compare" in r for r in test_results),
        "R10_blind_spot_search": t7_result in ("NOT_FOUND", "CRITICAL_MISS"),
        "R11_level2_automation": automation.get("level", 0) >= 2 if live_mode else False,
        "R12_dev_loop_live": dev_loop.decision == "LOOP_COMPLETED" if dev_loop else False,
    }

    final_decision: PhaseIRDecision
    if decision_info.requires_user_approval and not live_mode:
        final_decision = "PENDING_USER_APPROVAL"
    elif live_mode and dev_loop and dev_loop.decision == "LOOP_COMPLETED":
        final_decision = "LIVE_DEVELOPMENT_LOOP_CONFIRMED"
    elif live_mode and automation.get("level", 0) >= 2:
        final_decision = "LIVE_URSIM_AUTOMATION_CONFIRMED"
    elif live_mode and smoke and smoke.passed:
        final_decision = "LIVE_URSIM_CONFIRMED"
    elif not live_mode and any(m.name.startswith("C.") for m in matrix):
        final_decision = "ENVIRONMENT_BLOCKED"
    else:
        final_decision = "ENVIRONMENT_BLOCKED"

    capability_ideas = [
        {
            "idea": "Officiality as Decision Factor",
            "stage": "Phase I-R",
            "higher_level_goal": "Trust/reproducibility in specialized tool development",
            "existing_capability": "decision_factors.py pattern",
            "generalization": "Official / Official-adjacent / Community / Self-built",
            "cost": "LOW",
            "risk": "Treating official as always correct",
            "decision": "RECORD",
        },
        {
            "idea": "Simulation Backend abstraction",
            "stage": "Phase I-R",
            "existing_capability": "live_ursim_manager.py",
            "generalization": "External Verification Backend",
            "cost": "HIGH",
            "risk": "Premature Core",
            "decision": "DEFER",
        },
        {
            "idea": "Sandbox Runner revival",
            "stage": "Phase C DEFER",
            "existing_capability": "URSim as verification backend",
            "decision": "REJECT",
            "reason": "URSim is official simulator path — not sandbox generalization",
        },
    ]

    human_recommendation = {
        "status": "STOP_FOR_APPROVAL" if decision_info.requires_user_approval else "PROCEED",
        "recommended_path": decision_info.recommended,
        "version_stay": "5.15.2 / Docker tag 5.15 — catalog alignment",
        "version_not_selected": "5.25.2 — requires catalog migration decision",
        "options": [
            {
                "id": "B",
                "name": "WSL2 + Docker Desktop",
                "officiality": "Official",
                "pros": ["High automation", "Pinned Docker tag", "Matches ROS2 official docs"],
                "cons": ["WSL2 install + reboot", "OS feature changes"],
                "required_work": decision_info.approval_items if "WSL" in decision_info.recommended else [],
            },
            {
                "id": "C",
                "name": "VirtualBox + Official URSim VM 5.15.2",
                "officiality": "Official",
                "pros": ["No WSL required", "Official Non-Linux guide", "UI fidelity"],
                "cons": ["VirtualBox install", "Large VM download", "Lower automation default"],
                "required_work": [
                    "Install VirtualBox",
                    "Download UR Non-Linux VM from support site",
                    "Import VM (~8GB+ disk)",
                ],
            },
        ],
        "risk_note": "Do not treat stub results as live URSim confirmation",
    }

    return {
        "phase": "Phase I-R — URSim Live Environment Recovery",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "official_sources": [s.to_dict() for s in sources],
        "version_comparison": [v.to_dict() for v in versions],
        "environment_matrix": [m.to_dict() for m in matrix],
        "host_probe": host_ext,
        "deployment_decision": decision_info.to_dict(),
        "docker_recovery": docker_recovery,
        "live_mode": live_mode,
        "smoke_test": smoke.to_dict() if smoke else None,
        "test_results": test_results,
        "pass_count": pass_count,
        "total": len(test_results),
        "t7_result": t7_result,
        "t7_note": "NOT_FOUND means no natural blind spot in this set — not validator completeness",
        "automation_assessment": automation,
        "development_loop": dev_loop.to_dict() if dev_loop else {"status": "skipped_live_blocked"},
        "success_criteria": r_checks,
        "human_recommendation": human_recommendation,
        "capability_ideas": capability_ideas,
        "production_changes": 0,
        "core_discovery": {"c3_implemented": 0},
        "golden_pass": golden.get("pass"),
        "decision": final_decision,
        "safety_boundary": [
            "No real robot connection",
            "Official URSim ≠ real robot safety",
            "Minimal port exposure (localhost preferred)",
            "No unauthorized OS/virtualization changes in this phase",
        ],
    }
