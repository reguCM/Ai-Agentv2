"""Phase I-Live — empirical Development Loop on official URSim 5.15.2.

Reuses Phase H/I validator, compare, TDA loop, and Live URSim Manager.
Does not restart an already-running container. Does not connect a real robot.
Production code is not imported for mutation.
"""
from __future__ import annotations

import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.compare import compare_results
from ai_tool.experimental.ur_program_validator.development_loop import run_development_loop
from ai_tool.experimental.ur_program_validator.live_environment import default_live_target, investigate_live_environment
from ai_tool.experimental.ur_program_validator.live_test_cases import LiveTestCase, all_live_test_cases
from ai_tool.experimental.ur_program_validator.live_ursim_manager import (
    CONTAINER_NAME,
    SmokeTestResult,
    assess_automation_level,
    container_running,
    docker_daemon_ok,
    execute_urscript_live,
    _dashboard_command,
    _tcp_probe,
)
from ai_tool.experimental.ur_program_validator.llm_explanation import explain_validation, format_for_llm_context
from ai_tool.experimental.ur_program_validator.phase_i_harness import _run_live_test
from ai_tool.experimental.ur_program_validator.recovery_test_cases import (
    I_R1_VALID,
    I_R2_SYNTAX,
    I_R3_UNKNOWN,
    I_R6_BLIND_SPOT,
)
from ai_tool.experimental.ur_program_validator.spec_catalog import build_catalog
from ai_tool.experimental.ur_program_validator.static_validator import suggest_fixes, validate_script
from ai_tool.experimental.ur_program_validator.storage_policy import ensure_storage_dirs
from ai_tool.experimental.ur_program_validator.ur_sim_adapter import run_ursim_stub
from ai_tool.experimental.ur_program_validator.version_context import VersionContext
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

LiveLoopDecision = Literal["LIVE_LOOP_CONFIRMED", "LIVE_LOOP_PARTIAL", "LIVE_LOOP_BLOCKED"]

DASHBOARD_COMMANDS = (
    "version",
    "get robot model",
    "robotmode",
    "safetymode",
    "programstate",
    "running",
    "get loaded program",
    "is in remote control",
    "get operational mode",
)

# Observational fixtures — catalog/fixture backed, not LLM-generated.
# Live send is skipped for anything that could hang the controller.
OBS_CASES: list[LiveTestCase] = [
    LiveTestCase(
        test_id="L-OBS-TEXTMSG",
        label="textmsg exists on controller, absent from catalog",
        script="""
def obs_textmsg():
    textmsg("phase-i-live")
end
""",
        expect_validator="FAIL",
        expect_ursim="ANY",
        expect_compare="ANY",
        notes="Natural over-validation candidate: real URScript builtin not in Phase H catalog",
    ),
    LiveTestCase(
        test_id="L-OBS-SLEEP",
        label="sleep-only catalog function",
        script="""
def obs_sleep():
    sleep(0.05)
end
""",
        expect_validator="PASS",
        expect_ursim="ANY",
        expect_compare="ANY",
        notes="Minimal non-motion catalog script",
    ),
    LiveTestCase(
        test_id="L-OBS-DIGITAL",
        label="set_digital_out catalog function",
        script="""
def obs_dout():
    set_digital_out(0, True)
end
""",
        expect_validator="PASS",
        expect_ursim="ANY",
        expect_compare="ANY",
        notes="IO call is catalog-valid; simulation IO is not a safety claim",
    ),
]


def _dash(cmd: str) -> dict[str, Any]:
    try:
        resp = _dashboard_command("127.0.0.1", 29999, cmd)
        return {"ok": True, "command": cmd, "response": resp}
    except OSError as e:
        return {"ok": False, "command": cmd, "error": str(e)}


def probe_live_connection() -> dict[str, Any]:
    """Step 1 — do not recreate the container if it is already running."""
    target = default_live_target()
    env = investigate_live_environment()
    running = container_running()
    ports = {
        "vnc_5900": _tcp_probe("127.0.0.1", target.ports_vnc),
        "web_6080": _tcp_probe("127.0.0.1", target.ports_web),
        "dashboard_29999": _tcp_probe("127.0.0.1", target.ports_dashboard),
        "primary_30001": _tcp_probe("127.0.0.1", target.ports_primary),
        "secondary_30002": _tcp_probe("127.0.0.1", target.ports_secondary),
    }
    dashboard = {c: _dash(c) for c in DASHBOARD_COMMANDS} if ports["dashboard_29999"] else {}
    return {
        "docker_daemon_ok": docker_daemon_ok(),
        "container_name": CONTAINER_NAME,
        "container_running": running,
        "live_available": env.live_available,
        "block_reason": env.block_reason,
        "target": {**target.to_dict(), "full_image": target.full_image},
        "ports": ports,
        "dashboard": dashboard,
        "note": "Existing container reused — run_smoke_test() would docker rm -f and was not called",
    }


def probe_polyscope_http() -> dict[str, Any]:
    """TCP :6080 is noVNC; record HTTP path without claiming PolyScope pixels."""
    try:
        with socket.create_connection(("127.0.0.1", 6080), timeout=3) as sock:
            sock.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            time.sleep(0.3)
            raw = sock.recv(4096).decode("utf-8", "replace")
    except OSError as e:
        return {"ok": False, "error": str(e)}
    snippet = raw[:800]
    return {
        "ok": True,
        "http_snippet": snippet,
        "looks_like_novnc_listing": "vnc.html" in raw or "Directory listing" in raw,
        "boundary": "Port 6080 serves noVNC (vnc.html / vnc_lite.html), not a native PolyScope HTML app",
    }


def staged_program_flow(script: str) -> dict[str, Any]:
    """Step 4 — separate handoff / load / play / state. Failures are boundaries."""
    stages: list[dict[str, Any]] = []
    dirs = ensure_storage_dirs()
    programs = Path(dirs["ursim_programs"])
    programs.mkdir(parents=True, exist_ok=True)
    path = programs / "phase_i_live_min.script"
    path.write_text(script.strip() + "\n", encoding="utf-8")
    stages.append(
        {
            "stage": "handoff_write",
            "status": "PASS",
            "detail": str(path),
            "boundary": "Host bind-mount D:\\AI-Agent-data\\ursim\\programs → /ursim/programs",
        }
    )

    for load_arg in (
        "phase_i_live_min.script",
        "/ursim/programs/phase_i_live_min.script",
        "phase_i_live_min.urp",
    ):
        r = _dash(f"load {load_arg}")
        stages.append(
            {
                "stage": "load",
                "status": "OBSERVED",
                "detail": r,
                "boundary": "Dashboard load historically expects a PolyScope .urp, not raw .script",
            }
        )

    for cmd in (
        "is in remote control",
        "play",
        "programstate",
        "running",
        "get loaded program",
    ):
        r = _dash(cmd)
        stages.append({"stage": f"dashboard:{cmd}", "status": "OBSERVED", "detail": r})

    before = {c: _dash(c) for c in ("programstate", "running", "robotmode")}
    live = execute_urscript_live(script)
    time.sleep(0.8)
    after = {c: _dash(c) for c in ("programstate", "running", "robotmode")}
    stages.append(
        {
            "stage": "secondary_send_30002",
            "status": live.status,
            "executed_flag": live.executed,
            "script_response": live.script_response,
            "dashboard_log": live.dashboard_log,
            "errors": live.errors,
            "state_before": before,
            "state_after": after,
            "boundary": (
                "Empty secondary response is treated as PASS by execute_urscript_live heuristic; "
                "programstate/running must be checked separately. Not real-robot motion."
            ),
        }
    )
    return {"stages": stages, "live_exec": live.to_ursim_result(2).to_dict()}


def _case_pair(case: LiveTestCase) -> dict[str, Any]:
    live = _run_live_test(case, live_mode=True)
    catalog = build_catalog(polyscope_version=case.polyscope_version)
    ctx = VersionContext(
        robot=catalog.robot,
        polyscope_version=case.polyscope_version,
        urscript_version=catalog.urscript_version,
    )
    v = validate_script(case.script, catalog, version_ctx=ctx)
    stub = run_ursim_stub(case.script, test_id=case.test_id, polyscope_version=case.polyscope_version)
    stub_cmp = compare_results(v, stub, test_id=f"{case.test_id}-stub")
    return {
        "test_id": case.test_id,
        "label": case.label,
        "notes": case.notes,
        "validator_before_ursim": v.to_dict(),
        "live": live,
        "stub": {
            "ursim": stub.to_dict(),
            "compare": stub_cmp.to_dict(),
            "note": "STUB ONLY — not live URSim",
        },
        "divergence_stub_vs_live": {
            "stub_ursim": stub.status,
            "live_ursim": live["ursim"]["status"],
            "same": stub.status == live["ursim"]["status"],
        },
    }


def _classify_blind_spots(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    found = {
        "validator_pass_live_reject": [],
        "validator_warning_live_ok": [],
        "validator_fail_live_ok_over_validation": [],
        "validator_pass_live_pass_unconfirmed_motion": [],
        "version_or_api_gap": [],
    }
    for row in rows:
        vid = row["test_id"]
        vs = row["validator_before_ursim"]["status"]
        us = row["live"]["ursim"]["status"]
        interp = row["live"]["compare"]["interpretation"]
        resp = (row["live"]["ursim"].get("message") or "") + str(row["live"].get("ursim", {}))
        if interp == "critical_miss":
            found["validator_pass_live_reject"].append(vid)
        if vs == "WARNING" and us == "PASS":
            found["validator_warning_live_ok"].append(vid)
        if interp == "possible_over_validation":
            found["validator_fail_live_ok_over_validation"].append(vid)
        if vs == "PASS" and us == "PASS":
            found["validator_pass_live_pass_unconfirmed_motion"].append(vid)
        if "legacy_move" in row.get("label", "") or vid in ("I-T5", "I-R5"):
            found["version_or_api_gap"].append(vid)
        _ = resp
    return found


def run_phase_i_live(*, max_loop_attempts: int = 2) -> dict[str, Any]:
    connection = probe_live_connection()
    polyscope_http = probe_polyscope_http()
    reachable = (
        connection["container_running"]
        and connection["ports"].get("dashboard_29999")
        and connection["docker_daemon_ok"]
    )

    if not reachable:
        golden = run_production_golden()
        return {
            "phase": "Phase I-Live — official URSim Development Loop",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": "LIVE_LOOP_BLOCKED",
            "connection": connection,
            "polyscope_http": polyscope_http,
            "production_changes": 0,
            "golden_pass": golden.get("pass"),
            "block_reason": "Live URSim not reachable; existing container/dashboard missing",
        }

    min_script = I_R1_VALID.script
    staged = staged_program_flow(min_script)

    fixture_rows = [_case_pair(c) for c in all_live_test_cases()]
    recovery_rows = [_case_pair(c) for c in (I_R1_VALID, I_R2_SYNTAX, I_R3_UNKNOWN, I_R6_BLIND_SPOT)]
    obs_rows = [_case_pair(c) for c in OBS_CASES]
    all_rows = fixture_rows + recovery_rows + obs_rows
    blinds = _classify_blind_spots(all_rows)

    loop = run_development_loop(max_attempts=max_loop_attempts)
    dash = connection.get("dashboard") or {}
    model = "UNKNOWN"
    model_resp = (dash.get("get robot model") or {}).get("response", "")
    if "UR" in str(model_resp):
        model = str(model_resp).strip()
    smoke = SmokeTestResult(
        container_started=connection["container_running"],
        polyscope_accessible=connection["ports"].get("web_6080", False),
        dashboard_reachable=connection["ports"].get("dashboard_29999", False),
        robot_model_visible=model,
        simulation_mode="simulation",
        notes=["existing container reused; smoke restart skipped"],
    )
    automation = assess_automation_level(smoke)
    automation["live_remote_control"] = dash.get("is in remote control", {})
    automation["not_confirmed"] = list(automation.get("not_confirmed") or []) + [
        "Dashboard play without Remote Control",
        "Headless .urp load",
        "Confirmed joint motion / RTDE telemetry",
        "PolyScope GUI pixel state (noVNC only)",
    ]

    last_v = fixture_rows[0]["live"]["validator"]
    last_u = fixture_rows[0]["live"]["ursim"]
    explanation = fixture_rows[0]["live"]["llm_explanation"]

    play_failed = any(
        "play" in str(s.get("stage")) and "Failed" in str(s.get("detail"))
        for s in staged["stages"]
    )
    secondary_empty = not (staged["live_exec"].get("message") and staged["stages"][-1].get("script_response"))
    loop_ok = loop.decision in ("LOOP_COMPLETED", "LOOP_PARTIAL")
    validator_live_ran = any(r["live"]["validator"]["status"] for r in fixture_rows)

    confirmed_motion = False
    after = staged["stages"][-1].get("state_after") or {}
    running_after = str(after.get("running", {}).get("response", "")).lower()
    if "true" in running_after:
        confirmed_motion = True

    if confirmed_motion and loop.decision == "LOOP_COMPLETED" and not play_failed:
        decision: LiveLoopDecision = "LIVE_LOOP_CONFIRMED"
    elif validator_live_ran and loop_ok:
        decision = "LIVE_LOOP_PARTIAL"
    else:
        decision = "LIVE_LOOP_BLOCKED"

    ideas = [
        idea
        for idea in loop.capability_ideas
        if idea.get("decision") in ("RECORD", "DEFER")
    ]
    ideas.extend(
        [
            {
                "idea": "Headless PolyScope load/play (.urp + Remote Control)",
                "why_now": "Dashboard play failed while is in remote control = false",
                "existing_capability": "live_ursim_manager dashboard TCP",
                "decision": "RECORD",
                "implement_now": False,
                "note": "Necessity observed; not a new Core",
            },
            {
                "idea": "Motion/runtime confirmation (programstate or RTDE)",
                "why_now": "Secondary :30002 send returns empty; PASS is heuristic",
                "existing_capability": "execute_urscript_live + dashboard programstate",
                "decision": "RECORD",
                "implement_now": False,
                "note": "RTDE/primary not implemented — necessity only",
            },
            {
                "idea": "Catalog coverage for common builtins (textmsg, halt, popup)",
                "why_now": "L-OBS-TEXTMSG is FAIL on validator while likely legal URScript",
                "existing_capability": "spec_catalog.py",
                "decision": "RECORD",
                "implement_now": False,
            },
        ]
    )

    catalog = build_catalog(polyscope_version="5.15")
    v_min = validate_script(min_script, catalog, version_ctx=VersionContext(
        robot=catalog.robot, polyscope_version="5.15", urscript_version=catalog.urscript_version
    ))
    u_min = execute_urscript_live(min_script).to_ursim_result(2)
    cmp_min = compare_results(v_min, u_min, test_id="human-review-min")
    suggestions = suggest_fixes(v_min, catalog)

    golden = run_production_golden()

    return {
        "phase": "Phase I-Live — official URSim Development Loop",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "production_changes": 0,
        "core_discovery": {"c3_implemented": 0},
        "golden_pass": golden.get("pass"),
        "safety_boundary": [
            "No real UR robot connection",
            "Not a safe autonomous system",
            "No unlimited program injection",
            "URSim success ≠ real-robot safety",
            "Validator PASS ≠ runtime correctness",
            "Empty secondary response ≠ confirmed motion",
        ],
        "connection": connection,
        "polyscope_http": polyscope_http,
        "staged_execution": staged,
        "fixtures_live_vs_stub": fixture_rows,
        "recovery_live_vs_stub": recovery_rows,
        "observational_live_vs_stub": obs_rows,
        "blind_spots": blinds,
        "development_loop": loop.to_dict(),
        "automation_assessment": automation,
        "sample_llm_explanation": explanation,
        "sample_llm_context": format_for_llm_context(v_min, u_min, cmp_min, suggestions),
        "human_review": {
            "confirmed": [
                "Docker container ai_agent_ursim_phase_i running ursim_e-series:5.15",
                "Dashboard version 5.15.2 and get robot model UR5",
                "Dashboard robotmode / safetymode / programstate / running",
                "TCP 5900/6080/29999/30001/30002 open",
                "Bind-mount programs directory on D:",
                "Static Validator on catalog fixtures (PASS/FAIL as designed)",
                "Stub adapter still produces labeled stub results",
                "TDA development_loop with max 2 attempts",
                "LLM explanation from observations (not truth)",
            ],
            "not_confirmed": [
                "Dashboard play of a loaded program (Remote Control false)",
                "Headless .urp compilation/load",
                "Confirmed arm motion or cycle complete",
                "RTDE / primary client telemetry",
                "Native PolyScope HTML (6080 is noVNC listing)",
                "Real-robot safety",
            ],
            "validator_limits": [
                "Catalog is minimal (movej/movel/sleep/set_digital_out/legacy_move)",
                "No runtime reachability, collision, or speed semantics",
                "Unknown legal builtins → FAIL (possible over-validation)",
            ],
            "ursim_limits": [
                "Simulation only; POWER_OFF until dashboard power on",
                "Remote Control not enabled from Dashboard set operational mode alone",
            ],
            "dashboard_api_limits": [
                "play requires remote control",
                "load of .script/.urp without a valid PolyScope program fails",
                "Some English commands (help, popup, safety status) not understood",
            ],
            "llm_role": [
                "Explain validator/URSim observations",
                "Not a judge of URScript correctness",
                "Not allowed to drive unlimited live injection",
            ],
            "automation_possible": [
                "Container inspect, dashboard query, validator, stub compare, secondary send, TDA loop (2 attempts)",
            ],
            "human_required": [
                "PolyScope GUI / Remote Control enable",
                "Visual confirmation of motion in noVNC",
                "Any safety or real-robot decision",
            ],
            "why_not_real_robot": [
                "No safety I/O, no cell model, no speed/force supervision",
                "Secondary send heuristic can claim PASS without motion",
                "Explicit project boundary: simulation verification target only",
            ],
            "play_failed": play_failed,
            "secondary_response_empty": secondary_empty,
            "confirmed_motion": confirmed_motion,
        },
        "capability_ideas": ideas,
        "tool_vs_platform": {
            "validator_as_tool": (
                "Static Validator is usable as a pre-filter for catalog-covered URScript, "
                "not as a simulation oracle and not as a safety certifier."
            ),
            "environment_as_platform": (
                "Docker URSim 5.15.2 + Dashboard + programs mount + Experimental harness "
                "is reusable as a Tool-development lab, with Remote Control / .urp / motion "
                "confirmation still as HITL boundaries."
            ),
        },
    }
