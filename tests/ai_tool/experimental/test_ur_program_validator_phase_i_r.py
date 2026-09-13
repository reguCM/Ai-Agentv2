"""Tests for Phase I-R environment recovery investigation."""
from __future__ import annotations

from ai_tool.experimental.ur_program_validator.environment_recovery import (
    assess_deployment_decision,
    build_environment_matrix,
    compare_ursim_versions,
    probe_extended_host,
)
from ai_tool.experimental.ur_program_validator.phase_i_r_harness import run_phase_i_r_investigation
from ai_tool.experimental.ur_program_validator.recovery_test_cases import all_recovery_test_cases


def test_version_comparison_includes_515_and_525():
    versions = compare_ursim_versions()
    ids = {v.version for v in versions}
    assert "5.15.2" in ids
    assert "5.25.2" in ids
    v515 = next(v for v in versions if v.version == "5.15.2")
    assert "HIGH" in v515.catalog_alignment


def test_environment_matrix_has_four_options():
    matrix = build_environment_matrix()
    assert len(matrix) >= 4
    names = " ".join(m.name for m in matrix)
    assert "Docker" in names
    assert "VirtualBox" in names


def test_deployment_decision_requires_approval_when_blocked():
    decision = assess_deployment_decision()
    if not decision.requires_user_approval:
        assert decision.chosen != "PENDING_USER_APPROVAL"
    else:
        assert decision.approval_items


def test_extended_host_probe():
    host = probe_extended_host()
    assert "docker_cli" in host or "docker_daemon" in host
    assert "virtualbox_installed" in host


def test_phase_i_r_investigation_runs():
    result = run_phase_i_r_investigation(attempt_live=False)
    assert result["decision"] in (
        "ENVIRONMENT_BLOCKED",
        "PENDING_USER_APPROVAL",
        "LIVE_URSIM_CONFIRMED",
        "LIVE_DEVELOPMENT_LOOP_CONFIRMED",
    )
    assert result["total"] == len(all_recovery_test_cases())
    assert result["production_changes"] == 0
    assert result["human_recommendation"]["status"] in ("STOP_FOR_APPROVAL", "PROCEED")


def test_officiality_capability_recorded():
    result = run_phase_i_r_investigation(attempt_live=False)
    ideas = result.get("capability_ideas", [])
    assert any(i.get("idea") == "Officiality as Decision Factor" for i in ideas)
