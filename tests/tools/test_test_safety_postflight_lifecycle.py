"""S5c postflight lifecycle and run closure (fake executor / synthetic git)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from test_safety.authorization import AUTH_DENIED, bind_test_safety_authorization
from test_safety.postflight import (
    POSTFLIGHT_FAILED,
    POSTFLIGHT_INCOMPLETE,
    POSTFLIGHT_PASS,
    compare_git_postflight,
    evaluate_run_closure,
    path_matches_declared_write_scope,
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

PLAN_SIMPLE = {
    "plan_id": "s5c-simple",
    "commands": ["echo ok"],
    "declared_primary_risk_level": "LEVEL_1",
    "declared_dimensions": {"llm": "NONE", "network": "NONE"},
}

PLAN_REPO_WRITE = {
    "plan_id": "s5c-repo",
    "commands": ["echo ok"],
    "declared_primary_risk_level": "LEVEL_2",
    "declared_write_scope": ["repository runs/chat_ui/sessions (DECLARED)"],
    "declared_dimensions": {"filesystem_write": "PRESENT", "llm": "NONE"},
}


def _preflight() -> None:
    packet = evaluate_test_plan(
        {
            "plan_id": "s5c-preflight",
            "commands": [f"{sys.executable} -m pytest tests/tools/test_test_safety_postflight_lifecycle.py -q"],
            "declared_primary_risk_level": "LEVEL_1",
            "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
        },
        repo_root=None,
    )
    gate = evaluate_shadow_gate(packet, schema_path=EVAL_SCHEMA)
    if gate["gate_decision"] != "PASS":
        pytest.skip(f"S5c preflight BLOCKED: {gate.get('blocked_reasons')}")


@pytest.fixture(scope="module", autouse=True)
def _module_preflight():
    _preflight()


def _chain(plan: dict, action_id: str = "S5C-1"):
    return prepare_evaluation_and_authorization(
        plan,
        action_id=action_id,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )


def _fake_exec(ok: bool = True):
    def run(_commands):
        return {"ok": ok, "returncode": 0 if ok else 1}

    return run


def test_a_pass_no_postflight_closed():
    _, _, auth = _chain(PLAN_SIMPLE)
    ev = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_SIMPLE,
        authorization_packet=auth,
        executor=_fake_exec(),
        consumed_registry=ConsumedAuthorizationRegistry(),
    )
    assert ev["outcome"] == OUTCOME_EXECUTED
    assert ev["postflight_result"] is None
    assert ev["run_closed"] is True
    assert ev["test_failed"] is False


def test_b_required_postflight_not_run_not_closed():
    _, _, auth = _chain(PLAN_REPO_WRITE)
    ev = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_REPO_WRITE,
        authorization_packet=auth,
        executor=_fake_exec(),
        consumed_registry=ConsumedAuthorizationRegistry(),
        repo_root=None,
        postflight_fn=None,
    )
    assert ev["required_postflight"]["postflight_git_check_required"] is True
    assert ev["postflight_result"]["postflight_status"] == POSTFLIGHT_INCOMPLETE
    assert ev["run_closed"] is False
    assert ev["closure_reason"] == "POSTFLIGHT_INCOMPLETE"


def test_c_required_postflight_pass_closed():
    _, _, auth = _chain(PLAN_REPO_WRITE)

    def pf():
        return {
            "postflight_status": POSTFLIGHT_PASS,
            "required_checks": ["git_repository_state"],
            "completed_checks": ["git_repository_state"],
            "warnings": [],
            "unexpected_changes": [],
        }

    ev = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_REPO_WRITE,
        authorization_packet=auth,
        executor=_fake_exec(),
        consumed_registry=ConsumedAuthorizationRegistry(),
        postflight_fn=pf,
    )
    assert ev["run_closed"] is True
    assert ev["postflight_completed"] is True


def test_d_execution_fail_postflight_pass_run_closed():
    _, _, auth = _chain(PLAN_REPO_WRITE)

    def pf():
        return {
            "postflight_status": POSTFLIGHT_PASS,
            "required_checks": ["git_repository_state"],
            "completed_checks": ["git_repository_state"],
            "warnings": [],
            "unexpected_changes": [],
        }

    ev = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_REPO_WRITE,
        authorization_packet=auth,
        executor=_fake_exec(ok=False),
        consumed_registry=ConsumedAuthorizationRegistry(),
        postflight_fn=pf,
    )
    assert ev["test_failed"] is True
    assert ev["run_closed"] is True
    assert ev["closure_reason"] == "ALL_REQUIRED_POSTFLIGHT_PASS"


def test_e_unexpected_mutation_blocks_closure():
    _, _, auth = _chain(PLAN_REPO_WRITE)

    def pf():
        return {
            "postflight_status": POSTFLIGHT_FAILED,
            "required_checks": ["git_repository_state"],
            "completed_checks": ["git_repository_state"],
            "warnings": [],
            "unexpected_changes": ["ai_tool/unexpected_source.py"],
        }

    ev = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_REPO_WRITE,
        authorization_packet=auth,
        executor=_fake_exec(),
        consumed_registry=ConsumedAuthorizationRegistry(),
        postflight_fn=pf,
    )
    assert ev["run_closed"] is False
    assert ev["closure_reason"] in ("POSTFLIGHT_FAILED", "UNEXPECTED_REPOSITORY_CHANGES")


def test_f_denied_no_executor_not_test_failed():
    ev_p, gate_p, _ = _chain(PLAN_SIMPLE)
    gate = dict(gate_p)
    gate["gate_decision"] = "BLOCKED"
    auth = bind_test_safety_authorization(
        action_id="S5C-1",
        current_plan=PLAN_SIMPLE,
        evaluation_packet=ev_p,
        gate_packet=gate,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    calls = []

    def fake(_c):
        calls.append(1)
        return {"ok": True}

    ev = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_SIMPLE,
        authorization_packet=auth,
        executor=fake,
    )
    assert ev["outcome"] == OUTCOME_SAFETY_DENIED
    assert ev["test_failed"] is False
    assert not calls
    assert ev["postflight_result"] is None


def test_g_consumed_without_double_execution():
    _, _, auth = _chain(PLAN_SIMPLE)
    reg = ConsumedAuthorizationRegistry()
    first = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_SIMPLE,
        authorization_packet=auth,
        executor=_fake_exec(),
        consumed_registry=reg,
    )
    second = execute_authorized_test_plan(
        action_id="S5C-1",
        current_plan=PLAN_SIMPLE,
        authorization_packet=auth,
        executor=_fake_exec(),
        consumed_registry=reg,
    )
    assert first.get("execution_consumed") is True
    assert second["outcome"] == OUTCOME_ALREADY_CONSUMED
    assert second["executor_called"] is False


def test_declared_scope_allows_runs_path():
    assert path_matches_declared_write_scope(
        "runs/chat_ui/sessions/x.json",
        PLAN_REPO_WRITE["declared_write_scope"],
    )
    assert not path_matches_declared_write_scope(
        "ai_tool/agent_turn.py",
        PLAN_REPO_WRITE["declared_write_scope"],
    )


def test_compare_git_unexpected_undeclared():
    baseline = {"porcelain_lines": [], "head": "aaa", "branch": "main"}
    after = {
        "porcelain_lines": [" M ai_tool/foo.py"],
        "head": "aaa",
        "branch": "main",
    }
    result = compare_git_postflight(baseline, after, declared_write_scope=[])
    assert result["postflight_status"] == POSTFLIGHT_FAILED
    assert "ai_tool/foo.py" in result["unexpected_changes"]


def test_compare_git_declared_runs_ok():
    baseline = {"porcelain_lines": [], "head": "aaa"}
    after = {
        "porcelain_lines": ["?? runs/chat_ui/sessions/s.json"],
        "head": "aaa",
    }
    scope = PLAN_REPO_WRITE["declared_write_scope"]
    result = compare_git_postflight(baseline, after, declared_write_scope=scope)
    assert result["postflight_status"] == POSTFLIGHT_PASS
    assert not result["unexpected_changes"]


def test_evaluate_run_closure_unit():
    closed, reason = evaluate_run_closure(
        executor_called=True,
        safety_outcome=OUTCOME_EXECUTED,
        execution_result={"ok": False},
        required_postflight={"postflight_git_check_required": False},
        postflight_result=None,
    )
    assert closed is True
    assert reason == "NO_REQUIRED_POSTFLIGHT"
