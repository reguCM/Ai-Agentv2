"""Tests for Phase I-R-B preflight and harness."""
from __future__ import annotations

from ai_tool.experimental.ur_program_validator.phase_i_r_b_harness import run_phase_i_r_b
from ai_tool.experimental.ur_program_validator.wsl_docker_backend import run_preflight


def test_preflight_records_client_server_separately():
    pf = run_preflight()
    assert "client_server" in pf["docker"]
    cs = pf["docker"]["client_server"]
    assert cs.get("client") or cs.get("client", {}).get("raw")
    assert "wsl" in pf
    assert "preflight_ok_for_wsl_install" in pf


def test_preflight_diagnosis_not_service_only():
    pf = run_preflight()
    diag = pf["docker"].get("diagnosis", "")
    assert "WSL" in diag or "wslEngine" in diag.lower() or "wsl" in diag.lower()


def test_harness_pending_approval_without_wsl():
    result = run_phase_i_r_b(wsl_install_approved=False)
    assert result["decision"] in ("PENDING_USER_APPROVAL", "CHECKPOINT_0_COMPLETE", "ENVIRONMENT_BLOCKED")
    assert result["production_changes"] == 0
    cps = {c["checkpoint"]: c for c in result["checkpoints"]}
    assert "CHECKPOINT 0" in cps


def test_harness_has_checkpoint_chain():
    result = run_phase_i_r_b(wsl_install_approved=False)
    names = [c["checkpoint"] for c in result["checkpoints"]]
    assert "CHECKPOINT 0" in names
    assert "CHECKPOINT 1" in names
