"""S5a Authoritative Test Safety Authorization (synthetic; LEVEL_1 preflight)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from test_safety.authorization import (
    AUTH_AUTHORIZED,
    AUTH_DENIED,
    DENY_ACTION_ID_MISMATCH,
    DENY_EVALUATION_REF_MISMATCH,
    DENY_GATE_BLOCKED,
    DENY_INVALID_EVALUATION,
    DENY_PLAN_FINGERPRINT_MISMATCH,
    DENY_STALE_EVALUATION,
    authorization_binding_key,
    bind_test_safety_authorization,
    evaluation_ref_from_packet,
    validate_authorization_schema,
    verify_authorization_for_execution,
)
from test_safety.plan_fingerprint import compute_plan_fingerprint as fp_from_plan
from test_safety.shadow_gate import evaluate_shadow_gate
from test_safety.validator import evaluate_test_plan

REPO = Path(__file__).resolve().parents[2]
EVAL_SCHEMA = REPO / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO / "registry" / "schema" / "test_safety_shadow_gate.schema.json"
AUTH_SCHEMA = REPO / "registry" / "schema" / "test_safety_authorization.schema.json"

PLAN_A = {
    "plan_id": "plan-a",
    "description": "metadata only",
    "notes": "does not affect fingerprint",
    "commands": ["python -m pytest tests/foo.py -q"],
    "declared_primary_risk_level": "LEVEL_1",
    "declared_dimensions": {"llm": "NONE", "network": "NONE"},
}

PLAN_B = {
    **PLAN_A,
    "plan_id": "plan-b",
    "commands": ["python -m pytest tests/bar.py -q"],
}


def _preflight() -> None:
    packet = evaluate_test_plan(
        {
            "plan_id": "s5a_preflight",
            "commands": ["python -m pytest tests/tools/test_test_safety_authorization.py -q"],
            "declared_primary_risk_level": "LEVEL_1",
            "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
        },
        repo_root=None,
    )
    gate = evaluate_shadow_gate(packet, schema_path=EVAL_SCHEMA)
    assert gate["gate_decision"] == "PASS"


@pytest.fixture(scope="module", autouse=True)
def _module_preflight():
    _preflight()


def _chain(plan: dict, *, action_id: str = "A1", host_notes: list[str] | None = None):
    ev = evaluate_test_plan(plan, repo_root=None, host_process_notes=host_notes)
    gate = evaluate_shadow_gate(ev, schema_path=EVAL_SCHEMA)
    auth = bind_test_safety_authorization(
        action_id=action_id,
        current_plan=plan,
        evaluation_packet=ev,
        gate_packet=gate,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    return ev, gate, auth


def test_a_normal_pass_authorized():
    _, _, auth = _chain(PLAN_A)
    validate_authorization_schema(auth, AUTH_SCHEMA)
    assert auth["authorization"] == AUTH_AUTHORIZED
    assert auth["gate_decision"] == "PASS"
    assert auth["execution_connected"] is False
    assert auth["authorization_binding_key"]


def test_b_blocked_denied():
    ev, gate, _ = _chain(PLAN_A)
    gate = dict(gate)
    gate["gate_decision"] = "BLOCKED"
    auth = bind_test_safety_authorization(
        action_id="A1",
        current_plan=PLAN_A,
        evaluation_packet=ev,
        gate_packet=gate,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert auth["authorization"] == AUTH_DENIED
    assert DENY_GATE_BLOCKED in auth["reasons"]


def test_c_stale_plan_denied():
    ev, gate, auth_a = _chain(PLAN_A)
    assert auth_a["authorization"] == AUTH_AUTHORIZED
    auth_b = bind_test_safety_authorization(
        action_id="A1",
        current_plan=PLAN_B,
        evaluation_packet=ev,
        gate_packet=gate,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert auth_b["authorization"] == AUTH_DENIED
    assert DENY_PLAN_FINGERPRINT_MISMATCH in auth_b["reasons"]
    verified = verify_authorization_for_execution(auth_a, action_id="A1", current_plan=PLAN_B)
    assert verified["authorization"] == AUTH_DENIED
    assert DENY_STALE_EVALUATION in verified["reasons"]


def test_d_wrong_action_id_denied():
    _, _, auth_a = _chain(PLAN_A, action_id="A1")
    verified = verify_authorization_for_execution(auth_a, action_id="B2", current_plan=PLAN_A)
    assert verified["authorization"] == AUTH_DENIED
    assert DENY_ACTION_ID_MISMATCH in verified["reasons"]


def test_e_wrong_evaluation_ref_denied():
    ev, gate, _ = _chain(PLAN_A)
    bad_ref = evaluation_ref_from_packet(ev)
    bad_ref["generated_at"] = "1970-01-01T00:00:00+00:00"
    auth = bind_test_safety_authorization(
        action_id="A1",
        current_plan=PLAN_A,
        evaluation_packet=ev,
        gate_packet=gate,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
        expected_evaluation_ref=bad_ref,
    )
    assert auth["authorization"] == AUTH_DENIED
    assert DENY_EVALUATION_REF_MISMATCH in auth["reasons"]


def test_f_invalid_evaluation_denied():
    auth = bind_test_safety_authorization(
        action_id="A1",
        current_plan=PLAN_A,
        evaluation_packet={"packet_type": "WRONG"},
        gate_packet=None,
    )
    assert auth["authorization"] == AUTH_DENIED
    assert DENY_INVALID_EVALUATION in auth["reasons"] or "MISSING" in auth["reasons"][0]


def test_g_invalid_gate_packet_denied():
    ev, _, _ = _chain(PLAN_A)
    auth = bind_test_safety_authorization(
        action_id="A1",
        current_plan=PLAN_A,
        evaluation_packet=ev,
        gate_packet={"packet_type": "WRONG"},
        eval_schema_path=EVAL_SCHEMA,
    )
    assert auth["authorization"] == AUTH_DENIED


def test_h_deterministic_fingerprint():
    p1 = {"commands": ["python -m pytest x -q"], "declared_dimensions": {"llm": "NONE", "gpu": "NONE"}}
    p2 = {
        "plan_id": "different",
        "description": "x",
        "notes": "y",
        "commands": ["python -m pytest x -q"],
        "declared_dimensions": {"gpu": "NONE", "llm": "NONE"},
    }
    assert fp_from_plan(p1) == fp_from_plan(p2)


def test_i_safety_relevant_plan_change_changes_fingerprint():
    assert fp_from_plan(PLAN_A) != fp_from_plan(PLAN_B)


def test_j_host_observation_does_not_change_fingerprint():
    fp_base = fp_from_plan(PLAN_A)
    ev1, _, _ = _chain(PLAN_A, host_notes=None)
    ev2, _, _ = _chain(PLAN_A, host_notes=["ollama on host"])
    assert fp_from_plan(PLAN_A) == fp_base
    assert ev1["evaluation"] != ev2["evaluation"] or ev1.get("readonly_observations") != ev2.get(
        "readonly_observations"
    )


def test_k_required_postflight_preserved():
    plan = {
        "plan_id": "repo-write",
        "commands": ["python -m pytest tests/example.py -q"],
        "declared_primary_risk_level": "LEVEL_2",
        "declared_write_scope": ["repository runs/chat_ui/sessions"],
        "declared_dimensions": {"filesystem_write": "PRESENT", "llm": "NONE"},
    }
    _, _, auth = _chain(plan)
    assert auth["authorization"] == AUTH_AUTHORIZED
    assert auth["required_postflight"]["postflight_git_check_required"] is True


def test_binding_key_stable_for_same_identity():
    ev, gate, auth = _chain(PLAN_A, action_id="X1")
    key = authorization_binding_key(
        "X1",
        auth["plan_fingerprint"],
        auth["evaluation_ref"],
    )
    assert key == auth["authorization_binding_key"]
    key2 = authorization_binding_key(
        "X1",
        auth["plan_fingerprint"],
        auth["evaluation_ref"],
    )
    assert key == key2
    key3 = authorization_binding_key(
        "Y1",
        auth["plan_fingerprint"],
        auth["evaluation_ref"],
    )
    assert key != key3
