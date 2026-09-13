"""S5b runner wedge — fake executor first, then one controlled real pytest."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from test_safety.authorization import (
    AUTH_AUTHORIZED,
    AUTH_DENIED,
    bind_test_safety_authorization,
)
from test_safety.runner_wedge import (
    OUTCOME_ALREADY_CONSUMED,
    OUTCOME_EXECUTED,
    OUTCOME_SAFETY_DENIED,
    ConsumedAuthorizationRegistry,
    execute_authorized_test_plan,
    prepare_evaluation_and_authorization,
)
from test_safety.shadow_gate import evaluate_shadow_gate
from test_safety.validator import evaluate_test_plan

REPO = Path(__file__).resolve().parents[2]
EVAL_SCHEMA = REPO / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO / "registry" / "schema" / "test_safety_shadow_gate.schema.json"

PLAN_A = {
    "plan_id": "wedge-a",
    "commands": ["echo authorized"],
    "declared_primary_risk_level": "LEVEL_1",
    "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
}

PLAN_B = {**PLAN_A, "commands": ["echo stale"]}

EXTERNAL_PLAN = {
    "plan_id": "external",
    "commands": ["python scripts/call_external_api.py --url https://api.example.com/v1/run"],
    "declared_primary_risk_level": "LEVEL_3",
    "declared_dimensions": {"network": "PRESENT", "external_service": "PRESENT", "llm": "NONE"},
}

REPO_WRITE_PLAN = {
    "plan_id": "repo-write",
    "commands": ["python -m pytest tests/example.py -q"],
    "declared_primary_risk_level": "LEVEL_2",
    "declared_write_scope": ["repository runs/chat_ui/sessions"],
    "declared_dimensions": {"filesystem_write": "PRESENT", "llm": "NONE"},
}


def _preflight() -> None:
    packet = evaluate_test_plan(
        {
            "plan_id": "s5b_preflight",
            "commands": [
                f"{sys.executable} -m pytest tests/tools/test_test_safety_runner_wedge.py -q -k 'not s5b2_controlled_real_pytest'",
            ],
            "declared_primary_risk_level": "LEVEL_1",
            "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
        },
        repo_root=None,
    )
    gate = evaluate_shadow_gate(packet, schema_path=EVAL_SCHEMA)
    if gate["gate_decision"] != "PASS":
        pytest.skip(f"S5b preflight BLOCKED: {gate.get('blocked_reasons')}")


@pytest.fixture(scope="module", autouse=True)
def _module_preflight():
    _preflight()


def _auth_chain(plan: dict, action_id: str = "ACT-1"):
    return prepare_evaluation_and_authorization(
        plan,
        action_id=action_id,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )


def test_s5b1_a_authorized_calls_executor_once():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True, "returncode": 0}

    _, _, auth = _auth_chain(PLAN_A)
    reg = ConsumedAuthorizationRegistry()
    ev = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=PLAN_A,
        authorization_packet=auth,
        executor=fake,
        consumed_registry=reg,
    )
    assert ev["outcome"] == OUTCOME_EXECUTED
    assert ev["executor_called"] is True
    assert len(calls) == 1
    assert ev["test_failed"] is False


def test_s5b1_b_denied_never_calls_executor():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True}

    ev_p, gate_p, auth = _auth_chain(PLAN_A)
    gate = dict(gate_p)
    gate["gate_decision"] = "BLOCKED"
    auth = bind_test_safety_authorization(
        action_id="ACT-1",
        current_plan=PLAN_A,
        evaluation_packet=ev_p,
        gate_packet=gate,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert auth["authorization"] == AUTH_DENIED
    ev = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=PLAN_A,
        authorization_packet=auth,
        executor=fake,
    )
    assert ev["outcome"] == OUTCOME_SAFETY_DENIED
    assert ev["executor_called"] is False
    assert ev["test_failed"] is False
    assert not calls


def test_s5b1_c_stale_fingerprint_never_called():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True}

    _, _, auth = _auth_chain(PLAN_A)
    ev = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=PLAN_B,
        authorization_packet=auth,
        executor=fake,
    )
    assert ev["outcome"] == OUTCOME_SAFETY_DENIED
    assert ev["executor_called"] is False
    assert not calls


def test_s5b1_d_wrong_action_never_called():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True}

    _, _, auth = _auth_chain(PLAN_A, action_id="ACT-1")
    ev = execute_authorized_test_plan(
        action_id="ACT-OTHER",
        current_plan=PLAN_A,
        authorization_packet=auth,
        executor=fake,
    )
    assert ev["executor_called"] is False
    assert not calls


def test_s5b1_e_invalid_authorization_never_called():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True}

    ev = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=PLAN_A,
        authorization_packet={"authorization": AUTH_DENIED, "authorization_binding_key": ""},
        executor=fake,
    )
    assert ev["executor_called"] is False
    assert not calls


def test_s5b1_f_human_approval_never_called():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True}

    _, _, auth = _auth_chain(EXTERNAL_PLAN)
    assert auth["authorization"] == AUTH_DENIED
    assert auth["reasons"]
    ev = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=EXTERNAL_PLAN,
        authorization_packet=auth,
        executor=fake,
    )
    assert ev["executor_called"] is False
    assert not calls


def test_s5b1_g_required_postflight_preserved_and_run_not_closed():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True, "returncode": 0}

    def pf():
        return {
            "postflight_status": "PASS",
            "required_checks": ["git_repository_state"],
            "completed_checks": ["git_repository_state"],
            "warnings": [],
            "unexpected_changes": [],
        }

    _, _, auth = _auth_chain(REPO_WRITE_PLAN)
    assert auth["authorization"] == AUTH_AUTHORIZED
    ev = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=REPO_WRITE_PLAN,
        authorization_packet=auth,
        executor=fake,
        postflight_fn=pf,
    )
    assert ev["required_postflight"]["postflight_git_check_required"] is True
    assert ev["postflight_completed"] is True
    assert ev["run_closed"] is True


def test_s5b1_exactly_once_second_spawn_blocked():
    calls: list[list[str]] = []

    def fake(commands):
        calls.append(list(commands))
        return {"ok": True}

    _, _, auth = _auth_chain(PLAN_A)
    reg = ConsumedAuthorizationRegistry()
    first = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=PLAN_A,
        authorization_packet=auth,
        executor=fake,
        consumed_registry=reg,
    )
    second = execute_authorized_test_plan(
        action_id="ACT-1",
        current_plan=PLAN_A,
        authorization_packet=auth,
        executor=fake,
        consumed_registry=reg,
    )
    assert first["executor_called"] is True
    assert second["outcome"] == OUTCOME_ALREADY_CONSUMED
    assert second["executor_called"] is False
    assert len(calls) == 1


def test_s5b2_controlled_real_pytest():
    plan = {
        "plan_id": "s5b2-real",
        "commands": [
            f"{sys.executable} -m pytest tests/tools/test_test_safety_authorization.py::test_h_deterministic_fingerprint -q",
        ],
        "declared_primary_risk_level": "LEVEL_1",
        "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE", "subprocess": "CONTROLLED"},
    }
    pre = evaluate_test_plan(plan, repo_root=None)
    pg = evaluate_shadow_gate(pre, schema_path=EVAL_SCHEMA)
    assert pg["gate_decision"] == "PASS", pg.get("blocked_reasons")
    _, _, auth = _auth_chain(plan, action_id="S5B2-REAL-1")
    assert auth["authorization"] == AUTH_AUTHORIZED
    ev = execute_authorized_test_plan(
        action_id="S5B2-REAL-1",
        current_plan=plan,
        authorization_packet=auth,
        consumed_registry=ConsumedAuthorizationRegistry(),
    )
    assert ev["execution_verification"] == "VALID"
    assert ev["executor_called"] is True
    assert ev["execution_result"]["ok"] is True
    assert ev["test_failed"] is False
