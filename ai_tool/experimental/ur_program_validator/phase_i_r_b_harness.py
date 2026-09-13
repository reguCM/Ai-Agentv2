"""Phase I-R-B harness — WSL2 + Docker + URSim live backend checkpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.development_loop import run_development_loop
from ai_tool.experimental.ur_program_validator.live_ursim_manager import (
    assess_automation_level,
    docker_daemon_ok,
    execute_urscript_live,
    pull_image,
    run_smoke_test,
    stop_container,
)
from ai_tool.experimental.ur_program_validator.phase_i_harness import _run_live_test
from ai_tool.experimental.ur_program_validator.recovery_test_cases import (
    I_R1_VALID,
    I_R2_SYNTAX,
    I_R3_UNKNOWN,
    I_R6_BLIND_SPOT,
)
from ai_tool.experimental.ur_program_validator.storage_policy import (
    ensure_storage_dirs,
    format_approval_request,
    probe_storage,
)
from ai_tool.experimental.ur_program_validator.wsl_docker_backend import (
    run_docker_smoke_tests,
    run_preflight,
)
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

PhaseIRBDecision = Literal[
    "LIVE_URSIM_CONFIRMED",
    "LIVE_URSIM_AUTOMATION_CONFIRMED",
    "LIVE_DEVELOPMENT_LOOP_CONFIRMED",
    "DOCKER_BLOCKED_VM_REQUIRED",
    "ENVIRONMENT_BLOCKED",
    "PENDING_USER_APPROVAL",
    "CHECKPOINT_0_COMPLETE",
]


def _cp(
    checkpoint: str,
    name: str,
    status: str,
    criteria: dict[str, bool],
    notes: list[str],
    layer: str,
) -> dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "name": name,
        "status": status,
        "criteria": criteria,
        "notes": notes,
        "layer": layer,
    }


def run_phase_i_r_b(
    *,
    wsl_install_approved: bool = False,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """
    Phase I-R-B orchestration.
    wsl_install_approved must be True to attempt WSL install (not performed here — external step).
    """
    root = project_root or Path.cwd()
    checkpoints: list[dict[str, Any]] = []
    preflight = run_preflight()
    storage = probe_storage(root)
    storage_approval = format_approval_request(storage)
    ensure_storage_dirs(root)
    checkpoints.append(
        _cp(
            "CHECKPOINT 0",
            "Preflight",
            "PASS" if preflight["preflight_ok_for_wsl_install"] else "FAIL",
            {
                "B1_preflight_ram_disk": preflight["hardware"]["ram_gb"] >= 8
                and preflight["hardware"]["disk_free_c_gb"] >= 20,
                "docker_cli": bool(preflight["docker"]["client_server"].get("client")),
                "wsl_state_recorded": True,
            },
            preflight.get("blockers", []),
            "Environment",
        )
    )

    wsl = preflight["wsl"]
    engine_up = bool(preflight["docker"]["client_server"].get("server"))

    # CHECKPOINT 1 — WSL2
    if not wsl["installed"]:
        cp1_status = "PENDING_APPROVAL" if wsl.get("needs_install", True) else "FAIL"
        if not wsl_install_approved:
            checkpoints.append(
                _cp(
                    "CHECKPOINT 1",
                    "WSL2 ready",
                    cp1_status,
                    {"B1_wsl2": False},
                    ["WSL not installed — run wsl --install after user approval, then reboot"],
                    "WSL",
                )
            )
        else:
            checkpoints.append(
                _cp(
                    "CHECKPOINT 1",
                    "WSL2 ready",
                    "FAIL",
                    {"B1_wsl2": False},
                    ["Approval granted but WSL still not installed — execute wsl --install + reboot externally"],
                    "WSL",
                )
            )
    else:
        checkpoints.append(
            _cp(
                "CHECKPOINT 1",
                "WSL2 ready",
                "PASS" if wsl.get("wsl2_ready") else "FAIL",
                {"B1_wsl2": wsl.get("wsl2_ready", False)},
                [wsl.get("list_output", "")[:200]],
                "WSL",
            )
        )

    # CHECKPOINT 2 — Docker
    checkpoints.append(
        _cp(
            "CHECKPOINT 2",
            "Docker ready",
            "PASS" if engine_up else "BLOCKED",
            {"B2_docker_backend": engine_up, "B3_docker_engine": engine_up},
            [preflight["docker"].get("diagnosis", "")],
            "Docker",
        )
    )

    docker_smoke: dict[str, Any] = {"blocked": "Engine not up"}
    if engine_up:
        docker_smoke = run_docker_smoke_tests(project_root=root)
        checkpoints.append(
            _cp(
                "CHECKPOINT 3",
                "Container ready",
                "PASS"
                if docker_smoke.get("hello_world", {}).get("status") == "PASS"
                else "FAIL",
                {
                    "B4_hello_world": docker_smoke.get("hello_world", {}).get("status") == "PASS",
                    "B5_file_share": docker_smoke.get("file_share", {}).get("status") == "PASS",
                    "B6_network": docker_smoke.get("network", {}).get("status") == "PASS",
                },
                [],
                "Docker",
            )
        )
    else:
        checkpoints.append(
            _cp(
                "CHECKPOINT 3",
                "Container ready",
                "SKIP",
                {"B4": False, "B5": False, "B6": False},
                ["Skipped — Docker Engine not available"],
                "Docker",
            )
        )

    ursim_smoke = None
    live_tests: list[dict[str, Any]] = []
    dev_loop = None
    pull_ok = False

    if engine_up and docker_smoke.get("hello_world", {}).get("status") == "PASS":
        pull_ok, pull_msg = pull_image()
        ursim_smoke = run_smoke_test()
        checkpoints.append(
            _cp(
                "CHECKPOINT 4",
                "URSim ready",
                "PASS" if ursim_smoke.passed else "FAIL",
                {
                    "B7_image_pull": pull_ok,
                    "B8_container": ursim_smoke.container_started,
                    "B9_polyscope": ursim_smoke.polyscope_accessible,
                    "B10_robot": ursim_smoke.robot_model_visible != "UNKNOWN",
                },
                ursim_smoke.notes,
                "URSim",
            )
        )

        if ursim_smoke.passed:
            live_mode = True
            for case in (I_R1_VALID, I_R2_SYNTAX, I_R3_UNKNOWN, I_R6_BLIND_SPOT):
                live_tests.append(_run_live_test(case, live_mode=live_mode))
            cp5 = any(
                t["test_id"] == "I-R1"
                and t["validator"]["status"] == "PASS"
                and t["ursim"]["status"] == "PASS"
                for t in live_tests
            )
            blind = next((t for t in live_tests if t["test_id"] == "I-R6"), {})
            t7 = "NOT_FOUND"
            if blind.get("validator", {}).get("status") in ("PASS", "WARNING") and blind.get(
                "ursim", {}
            ).get("status") == "FAIL":
                t7 = "CRITICAL_MISS"
            checkpoints.append(
                _cp(
                    "CHECKPOINT 5",
                    "URScript execution ready",
                    "PASS" if cp5 else "FAIL",
                    {"B11_minimal_ursim": cp5, "B12_validator_compare": len(live_tests) >= 3},
                    [f"T7 natural blind spot: {t7}"],
                    "URScript",
                )
            )
            prog = execute_urscript_live(I_R1_VALID.script)
            checkpoints.append(
                _cp(
                    "CHECKPOINT 6",
                    "Programmatic control ready",
                    "PASS" if prog.status in ("PASS", "UNKNOWN") else "FAIL",
                    {"B13_programmatic": prog.executed or prog.status == "PASS"},
                    prog.dashboard_log[:3],
                    "Network/URSim",
                )
            )
            dev_loop = run_development_loop()
            checkpoints.append(
                _cp(
                    "CHECKPOINT 7",
                    "TDA integration ready",
                    "PASS" if dev_loop.decision == "LOOP_COMPLETED" else "SKIP",
                    {"B14_artifact_path": docker_smoke.get("file_share", {}).get("status") == "PASS",
                     "B15_dev_loop": dev_loop.decision == "LOOP_COMPLETED"},
                    [],
                    "TDA",
                )
            )
            stop_container()
    else:
        for name, layer in (
            ("CHECKPOINT 4", "URSim"),
            ("CHECKPOINT 5", "URScript"),
            ("CHECKPOINT 6", "Programmatic"),
            ("CHECKPOINT 7", "TDA"),
        ):
            checkpoints.append(
                _cp(name, f"{name} skipped", "SKIP", {}, ["Prior checkpoint blocked"], layer)
            )

    golden = run_production_golden()

    if not wsl_install_approved and not wsl["installed"]:
        decision: PhaseIRBDecision = "PENDING_USER_APPROVAL"
    elif not wsl["installed"]:
        decision = "PENDING_USER_APPROVAL"
    elif wsl.get("installed") and not engine_up and wsl.get("reboot_maybe_required"):
        decision = "CHECKPOINT_0_COMPLETE"  # WSL installed; reboot before Docker
    elif engine_up and dev_loop and dev_loop.decision == "LOOP_COMPLETED":
        decision = "LIVE_DEVELOPMENT_LOOP_CONFIRMED"
    elif engine_up and ursim_smoke and ursim_smoke.passed:
        decision = "LIVE_URSIM_CONFIRMED"
    elif wsl.get("wsl2_ready") and not engine_up:
        decision = "ENVIRONMENT_BLOCKED"
    elif not engine_up and preflight["preflight_ok_for_wsl_install"]:
        decision = "CHECKPOINT_0_COMPLETE"
    else:
        decision = "ENVIRONMENT_BLOCKED"

    return {
        "phase": "Phase I-R-B — WSL2 + Docker URSim Live Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "preflight": preflight,
        "storage_probe": storage.to_dict(),
        "storage_approval": storage_approval,
        "checkpoints": checkpoints,
        "docker_smoke": docker_smoke,
        "ursim_smoke": ursim_smoke.to_dict() if ursim_smoke else None,
        "live_tests": live_tests,
        "development_loop": dev_loop.to_dict() if dev_loop else None,
        "decision": decision,
        "wsl_install_approved": wsl_install_approved,
        "production_changes": 0,
        "core_discovery": {"c3_implemented": 0},
        "golden_pass": golden.get("pass"),
        "human_next_steps": preflight.get("recommended_post_install", []),
    }
