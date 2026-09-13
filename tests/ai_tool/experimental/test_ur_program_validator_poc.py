"""Tests for Phase H UR Program Validator PoC."""
from __future__ import annotations

from ai_tool.experimental.ur_program_validator.harness import run_phase_h_poc, run_test_case
from ai_tool.experimental.ur_program_validator.static_validator import validate_script
from ai_tool.experimental.ur_program_validator.spec_catalog import build_catalog
from ai_tool.experimental.ur_program_validator.test_cases import (
    T1_VALID_BASIC,
    T2_UNKNOWN_FUNCTION,
    T7_BLIND_SPOT,
    all_test_cases,
)
from ai_tool.experimental.ur_program_validator.compare import compare_results
from ai_tool.experimental.ur_program_validator.ur_sim_adapter import run_ursim


def test_unknown_function_detected():
    cat = build_catalog()
    r = validate_script(T2_UNKNOWN_FUNCTION.script, cat)
    assert r.status == "FAIL"
    assert any(i.kind.value == "unknown_function" for i in r.issues)


def test_valid_script_passes():
    cat = build_catalog()
    r = validate_script(T1_VALID_BASIC.script, cat)
    assert r.status == "PASS"


def test_critical_miss_t7():
    result = run_test_case(T7_BLIND_SPOT)
    assert result["compare"]["interpretation"] == "critical_miss"
    assert result["validator"]["status"] == "PASS"
    assert result["ursim"]["status"] == "FAIL"


def test_all_cases_count():
    assert len(all_test_cases()) >= 10


def test_run_phase_h_poc():
    result = run_phase_h_poc()
    assert result["pass_count"] == result["total"]
    assert result["production_changes"] == 0
    assert result["core_discovery"]["c3_implemented"] == 0
    assert result["decision"] == "POC_BOUNDARY_CONFIRMED"
    assert len(result["critical_misses"]) >= 1
