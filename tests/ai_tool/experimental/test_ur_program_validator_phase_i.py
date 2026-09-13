"""Tests for Phase I — Live URSim + Development Loop."""
from __future__ import annotations

from unittest.mock import patch

from ai_tool.experimental.ur_program_validator.development_loop import run_development_loop
from ai_tool.experimental.ur_program_validator.live_environment import investigate_live_environment
from ai_tool.experimental.ur_program_validator.live_test_cases import all_live_test_cases, I_T2_UNKNOWN
from ai_tool.experimental.ur_program_validator.phase_i_harness import run_phase_i_poc, _run_live_test
from ai_tool.experimental.ur_program_validator.static_validator import validate_script
from ai_tool.experimental.ur_program_validator.spec_catalog import build_catalog


def test_live_environment_probe():
    env = investigate_live_environment()
    assert env.host.os_name
    assert len(env.official_sources) >= 3
    assert env.target.image == "universalrobots/ursim_e-series"


def test_unknown_function_validator():
    cat = build_catalog()
    r = validate_script(I_T2_UNKNOWN.script, cat)
    assert r.status == "FAIL"


def test_live_test_stub_mode():
    case = all_live_test_cases()[0]
    result = _run_live_test(case, live_mode=False)
    assert result["validator"]["status"] == "PASS"
    assert result["ursim"]["mode"] == "stub"


def test_development_loop_runs():
    loop = run_development_loop()
    assert loop.attempts
    assert loop.workflow.get("stop_reason")
    assert loop.decision in ("LOOP_COMPLETED", "LOOP_PARTIAL")


def test_phase_i_harness_blocked_or_live():
    result = run_phase_i_poc(attempt_live=False)
    assert result["decision"] in (
        "BLOCKED",
        "AUTOMATION_LIMIT_CONFIRMED",
        "LIVE_POC_CONFIRMED",
        "DEVELOPMENT_LOOP_CONFIRMED",
    )
    assert result["production_changes"] == 0
    assert result["total"] == len(all_live_test_cases())
    assert result["development_loop"]["attempts"]


def test_phase_i_success_criteria_keys():
    result = run_phase_i_poc(attempt_live=False)
    checks = result["success_criteria"]
    for key in ("I3_official_script", "I6_compare", "I11_dev_loop"):
        assert key in checks
