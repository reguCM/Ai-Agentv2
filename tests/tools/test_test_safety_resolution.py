"""S7a automatic safety resolution (fake executor first)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

from test_safety.authorization import AUTH_AUTHORIZED, AUTH_DENIED, bind_test_safety_authorization
from test_safety.plan_fingerprint import compute_plan_fingerprint
from test_safety.runner_wedge import prepare_evaluation_and_authorization
from test_safety.safety_resolution import (
    RESOLUTION_AWAITING_HUMAN_APPROVAL,
    RESOLUTION_BLOCKED,
    RESOLUTION_ERROR,
    RESOLUTION_RESOLVED,
    RESOLUTION_SKIPPED,
    RESOLUTION_UNRESOLVED,
    ResolutionRunState,
    authorization_is_valid,
    resolve_test_safety,
    run_explicit_test_with_auto_resolution,
)
from test_safety.shadow_gate import evaluate_shadow_gate
from test_safety.validator import evaluate_test_plan

REPO = Path(__file__).resolve().parents[2]
EVAL_SCHEMA = REPO / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO / "registry" / "schema" / "test_safety_shadow_gate.schema.json"

PLAN_OK = {
    "plan_id": "s7a-ok",
    "commands": ["echo runner-ok"],
    "declared_primary_risk_level": "LEVEL_1",
    "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
}

PLAN_STALE = {**PLAN_OK, "commands": ["echo stale"]}

PLAN_GPU_UNKNOWN = {
    "plan_id": "gpu-u",
    "commands": ["python -m pytest tests/system/gpu/test_gpu_status.py -q"],
    "declared_primary_risk_level": "LEVEL_2",
    "declared_dimensions": {"gpu": "UNKNOWN", "llm": "NONE"},
}

EXTERNAL = {
    "plan_id": "ext",
    "commands": ["python call_external.py --url https://api.example.com"],
    "declared_primary_risk_level": "LEVEL_3",
    "declared_dimensions": {"network": "PRESENT", "external_service": "PRESENT", "llm": "NONE"},
}


def _preflight() -> None:
    p = evaluate_test_plan(
        {
            "plan_id": "s7a-pf",
            "commands": [
                f"{sys.executable} -m pytest tests/tools/test_test_safety_resolution.py -q -k 'not s7a2_controlled_real'",
            ],
            "declared_primary_risk_level": "LEVEL_1",
            "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
        },
        repo_root=None,
    )
    g = evaluate_shadow_gate(p, schema_path=EVAL_SCHEMA)
    if g["gate_decision"] != "PASS":
        pytest.skip(str(g.get("blocked_reasons")))


@pytest.fixture(scope="module", autouse=True)
def _module_preflight():
    _preflight()


def _fake_exec(collector: list):
    def run(_commands):
        collector.append(1)
        return {"ok": True, "returncode": 0}

    return run


def _prepare(action_id: str = "A1"):
    return prepare_evaluation_and_authorization(
        PLAN_OK,
        action_id=action_id,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )


def test_a_valid_auth_resolution_skipped_executor_once():
    calls: list[int] = []
    _, _, auth = _prepare()
    assert authorization_is_valid(auth, action_id="A1", current_plan=PLAN_OK)
    out = run_explicit_test_with_auto_resolution(
        action_id="A1",
        current_plan=PLAN_OK,
        authorization_packet=auth,
        executor=_fake_exec(calls),
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_SKIPPED
    assert out["resolution"]["resolution_skipped"] is True
    assert len(calls) == 1
    assert out["executor_called"] is True


def test_b_missing_auth_auto_resolve_pass_executor_once():
    calls: list[int] = []
    out = run_explicit_test_with_auto_resolution(
        action_id="A1",
        current_plan=PLAN_OK,
        authorization_packet=None,
        executor=_fake_exec(calls),
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_RESOLVED
    assert out["resolution"]["action_id"] == "A1"
    assert len(calls) == 1


def test_c_missing_blocked_executor_never_called():
    calls: list[int] = []
    out = run_explicit_test_with_auto_resolution(
        action_id="A1",
        current_plan=PLAN_GPU_UNKNOWN,
        authorization_packet=None,
        executor=_fake_exec(calls),
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_BLOCKED
    assert not calls
    assert out["executor_called"] is False
    assert out["test_failed"] is False


def test_d_human_approval_executor_never_called():
    calls: list[int] = []
    out = run_explicit_test_with_auto_resolution(
        action_id="A1",
        current_plan=EXTERNAL,
        authorization_packet=None,
        executor=_fake_exec(calls),
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_AWAITING_HUMAN_APPROVAL
    assert not calls
    assert out["executor_called"] is False


def test_e_validator_failure_executor_never_called():
    calls: list[int] = []
    with mock.patch(
        "test_safety.safety_resolution.prepare_evaluation_and_authorization",
        side_effect=RuntimeError("validator boom"),
    ):
        out = run_explicit_test_with_auto_resolution(
            action_id="A1",
            current_plan=PLAN_OK,
            authorization_packet=None,
            executor=_fake_exec(calls),
        )
    assert out["resolution"]["resolution_result"] == RESOLUTION_ERROR
    assert not calls


def test_f_binder_denied_executor_never_called():
    calls: list[int] = []
    ev, gate, auth_denied = _prepare()
    assert auth_denied["authorization"] == AUTH_AUTHORIZED

    def fake_prepare(*_a, **_k):
        return ev, gate, {
            **auth_denied,
            "authorization": AUTH_DENIED,
            "reasons": ["GATE_BLOCKED"],
            "gate_decision": "BLOCKED",
        }

    with mock.patch("test_safety.safety_resolution.prepare_evaluation_and_authorization", fake_prepare):
        out = run_explicit_test_with_auto_resolution(
            action_id="A1",
            current_plan=PLAN_OK,
            authorization_packet=None,
            executor=_fake_exec(calls),
        )
    assert out["resolution"]["resolution_result"] == RESOLUTION_BLOCKED
    assert not calls


def test_g_stale_auth_triggers_new_resolution():
    calls: list[int] = []
    _, _, auth_a = _prepare("A1")
    out = run_explicit_test_with_auto_resolution(
        action_id="A1",
        current_plan=PLAN_STALE,
        authorization_packet=auth_a,
        executor=_fake_exec(calls),
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_RESOLVED
    assert out["resolution"]["resolution_attempted"] is True
    assert len(calls) == 1


def test_h_action_id_preserved():
    res = resolve_test_safety(
        action_id="KEEP-42",
        current_plan=PLAN_OK,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert res["action_id"] == "KEEP-42"
    assert res["original_action_preserved"] is True


def test_i_plan_fingerprint_preserved():
    fp = compute_plan_fingerprint(PLAN_OK)
    res = resolve_test_safety(
        action_id="A1",
        current_plan=PLAN_OK,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert res["plan_fingerprint"] == fp


def test_j_loop_second_automatic_resolution_unresolved():
    state = ResolutionRunState()
    first = resolve_test_safety(
        action_id="A1",
        current_plan=PLAN_GPU_UNKNOWN,
        state=state,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert first["resolution_result"] == RESOLUTION_BLOCKED
    second = resolve_test_safety(
        action_id="A1",
        current_plan=PLAN_GPU_UNKNOWN,
        state=state,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert second["resolution_result"] == RESOLUTION_UNRESOLVED
    assert state.automatic_resolution_attempts == 1


def test_k_runner_final_verify_blocks_tampered_plan():
    calls: list[int] = []
    _, _, auth = _prepare()
    out = run_explicit_test_with_auto_resolution(
        action_id="A1",
        current_plan=PLAN_OK,
        authorization_packet=auth,
        executor=_fake_exec(calls),
        runner_plan_override=PLAN_STALE,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_SKIPPED
    assert not calls
    assert out["executor_called"] is False
    runner = out.get("runner_evidence") or {}
    assert runner.get("execution_verification") == "DENIED"


def test_s7a2_controlled_real_pytest():
    plan = {
        "plan_id": "s7a2",
        "commands": [
            f"{sys.executable} -m pytest tests/tools/test_test_safety_authorization.py::test_h_deterministic_fingerprint -q",
        ],
        "declared_primary_risk_level": "LEVEL_1",
        "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE", "subprocess": "CONTROLLED"},
    }
    out = run_explicit_test_with_auto_resolution(
        action_id="S7A2-REAL",
        current_plan=plan,
        authorization_packet=None,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_RESOLVED
    assert out["executor_called"] is True
    assert out["runner_evidence"]["execution_result"]["ok"] is True
