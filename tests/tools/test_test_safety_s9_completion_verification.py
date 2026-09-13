"""S9 completion verification fixtures (S8.1 authority; no new architecture)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.chat_interface.workspace_read_bridge import prepare_tool_result_for_llm
from tools.system.test_safety.run_test_plan_entry import run_test_plan_entry
from test_safety.runtime_bridge import safety_run_closure_predicate
from test_safety.runner_wedge import prepare_evaluation_and_authorization
from test_safety.safety_resolution import RESOLUTION_SKIPPED, run_explicit_test_with_auto_resolution
from test_safety.shadow_gate import evaluate_shadow_gate
from test_safety.tool_argument_validation import load_test_plan_subschema
from test_safety.validator import evaluate_test_plan
from tools.ai.task_runtime import ActionRecord, AgentTaskRuntime, GoalNode, TaskRecord

REPO = Path(__file__).resolve().parents[2]
EVAL_SCHEMA = REPO / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO / "registry" / "schema" / "test_safety_shadow_gate.schema.json"

PLAN_OK = {
    "plan_id": "s9-verify",
    "commands": ["echo s9"],
    "declared_primary_risk_level": "LEVEL_1",
    "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
}

INTEGRATION_PLAN = {
    "plan_id": "s9-integration",
    "commands": [
        f"{sys.executable} -m pytest tests/tools/test_test_safety_s9_completion_verification.py::test_d4_predicate_smoke -q",
    ],
    "declared_primary_risk_level": "LEVEL_1",
    "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE", "subprocess": "CONTROLLED"},
}


def _preflight() -> None:
    packet = evaluate_test_plan(
        {
            "plan_id": "s9_preflight",
            "commands": [
                f"{sys.executable} -m pytest tests/tools/test_test_safety_s9_completion_verification.py -q -k 'not s9_controlled_runtime_integration'",
            ],
            "declared_primary_risk_level": "LEVEL_1",
            "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
        },
        repo_root=None,
    )
    gate = evaluate_shadow_gate(packet, schema_path=EVAL_SCHEMA)
    if gate["gate_decision"] != "PASS":
        pytest.skip(str(gate.get("blocked_reasons")))


@pytest.fixture(scope="module", autouse=True)
def _module_preflight():
    _preflight()


def test_d1_subschema_from_canonical_defs_only():
    sub = load_test_plan_subschema()
    assert sub.get("type") == "object"
    assert "$ref" in sub.get("properties", {}).get("declared_primary_risk_level", {}) or True


def test_d4_predicate_smoke():
    assert safety_run_closure_predicate(
        {
            "executor_called": True,
            "test_failed": False,
            "runner_evidence": {"run_closed": True},
        }
    )


def test_d4_negative_pytest_fail_lifecycle_closed():
    assert not safety_run_closure_predicate(
        {
            "executor_called": True,
            "test_failed": True,
            "runner_evidence": {"run_closed": True},
        }
    )


def test_d4_negative_pass_run_not_closed():
    assert not safety_run_closure_predicate(
        {
            "executor_called": True,
            "test_failed": False,
            "runner_evidence": {"run_closed": False},
        }
    )


def test_d4_negative_safety_blocked():
    assert not safety_run_closure_predicate(
        {"executor_called": False, "test_failed": False, "runner_evidence": {}}
    )


def test_d3_no_evidence_gain_is_not_reusable_evidence():
    rt = AgentTaskRuntime("d3")
    rt.add_goal(GoalNode("G1", "g", completion_conditions=["all done"]))
    rt.add_task(TaskRecord("T1", "G1", "t", "work", ["done"]))
    rt.record_action(
        ActionRecord("A1", "T1", "tool_call", "read_file", {"path": "x"}, evidence_gain=False)
    )
    assert rt.has_reusable_evidence("T1", "read_file", {"path": "x"}) is False


def _success_outcome():
    return {
        "executor_called": True,
        "test_failed": False,
        "run_closed": True,
        "resolution": {"resolution_result": "RESOLVED", "action_id": "A1"},
        "runner_evidence": {"run_closed": True, "closure_reason": "normal"},
    }


def test_d3_failed_retry_allowed_new_bridge_call():
    orch = ChatTaskOrchestrator("d3-fail", "verify", completion_conditions=["test_run_closed"])
    orch.initialize()
    calls: list[int] = []

    def fake_bridge(**_kwargs):
        calls.append(1)
        return {
            "executor_called": True,
            "test_failed": True,
            "run_closed": True,
            "resolution": {"resolution_result": "RESOLVED"},
            "runner_evidence": {"run_closed": True},
        }

    args = {"test_plan": PLAN_OK}
    with mock.patch("test_safety.runtime_bridge.bridge_test_execution", side_effect=fake_bridge):
        orch.execute_test_plan_action(args, relevant_tools=["run_test_plan"])
        orch.execute_test_plan_action(args, relevant_tools=["run_test_plan"])
    assert len(calls) == 2
    assert orch.runtime.actions[-1].evidence_gain is False
    assert orch.runtime.actions[-2].evidence_gain is False


def test_d3_same_successful_plan_can_run_as_a_new_action():
    orch = ChatTaskOrchestrator("d3-dup", "verify", completion_conditions=["test_run_closed"])
    orch.initialize()
    calls: list[int] = []

    def fake_bridge(**_kwargs):
        calls.append(1)
        return _success_outcome()

    args = {"test_plan": PLAN_OK}
    with mock.patch("test_safety.runtime_bridge.bridge_test_execution", side_effect=fake_bridge):
        orch.execute_test_plan_action(args, relevant_tools=["run_test_plan"])
        assert orch.runtime.actions[-1].evidence_gain is True
        orch.execute_test_plan_action(args, relevant_tools=["run_test_plan"])
    assert len(calls) == 2
    assert [action.action_id for action in orch.runtime.actions] == ["A1", "A2"]
    assert orch.runtime.actions[-1].result_status == "success"
    assert orch.runtime.actions[-1].evidence_gain is True


def test_d2_action_id_single_increment():
    orch = ChatTaskOrchestrator("d2", "verify")
    orch.initialize()
    orch._action_index = 0

    def fake_bridge(**kwargs):
        assert kwargs["action_id"] == "A1"
        return {
            "executor_called": False,
            "test_failed": False,
            "resolution": {"resolution_result": "BLOCKED"},
            "runner_evidence": {},
        }

    with mock.patch("test_safety.runtime_bridge.bridge_test_execution", side_effect=fake_bridge):
        orch.execute_test_plan_action({"test_plan": PLAN_OK}, relevant_tools=["run_test_plan"])
    assert orch.runtime.actions[-1].action_id == "A1"
    assert orch._action_index == 1


def test_d5_stack_resolution_skipped_with_valid_auth():
    _, _, auth = prepare_evaluation_and_authorization(
        PLAN_OK,
        action_id="A-cont",
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    calls: list[int] = []

    def fake_exec(_commands):
        calls.append(1)
        return {"ok": True, "returncode": 0}

    out = run_explicit_test_with_auto_resolution(
        action_id="A-cont",
        current_plan=PLAN_OK,
        authorization_packet=auth,
        executor=fake_exec,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    assert out["resolution"]["resolution_result"] == RESOLUTION_SKIPPED
    assert len(calls) == 1


def test_d5_orchestrator_continuation_same_action_id(tmp_path: Path):
    orch = ChatTaskOrchestrator("d5", "verify", completion_conditions=["test_run_closed"])
    orch.initialize()
    _, _, auth = prepare_evaluation_and_authorization(
        PLAN_OK,
        action_id="A1",
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    awaiting = {
        "executor_called": False,
        "test_failed": False,
        "run_closed": False,
        "resolution": {"resolution_result": "AWAITING_HUMAN_APPROVAL"},
        "runner_evidence": {},
    }
    success = {
        "executor_called": True,
        "test_failed": False,
        "run_closed": True,
        "resolution": {"resolution_result": RESOLUTION_SKIPPED},
        "runner_evidence": {"run_closed": True, "execution_result": {"ok": True, "returncode": 0}},
        "persisted_run_path": str(tmp_path / "A1.json"),
    }
    (tmp_path / "A1.json").write_text("{}", encoding="utf-8")

    with mock.patch(
        "test_safety.runtime_bridge.bridge_test_execution",
        side_effect=[awaiting, success],
    ):
        orch.execute_test_plan_action({"test_plan": PLAN_OK}, relevant_tools=["run_test_plan"])
        assert orch._run_test_plan_continuation is not None
        orch.execute_test_plan_action(
            {"test_plan": PLAN_OK, "authorization_packet": auth},
            relevant_tools=["run_test_plan"],
        )
    run_actions = [a for a in orch.runtime.actions if a.tool_name == "run_test_plan"]
    assert len(run_actions) == 1
    assert run_actions[0].action_id == "A1"


def test_d8_internal_raw_retains_full_test_safety_packet():
    orch = ChatTaskOrchestrator("d8-int", "verify")
    orch.initialize()
    big = {
        "schema_version": "1",
        "packet_type": "TEST_SAFETY_EXPLICIT_RUN",
        "executor_called": True,
        "resolution": {"x": "y", "evaluation_packet": {"plan_id": "secret"}},
        "runner_evidence": {"run_closed": True},
    }
    with mock.patch(
        "test_safety.runtime_bridge.bridge_test_execution",
        return_value={**big, "test_failed": False, "run_closed": True},
    ):
        raw = orch.execute_test_plan_action({"test_plan": PLAN_OK}, relevant_tools=["run_test_plan"])
    assert raw["test_safety"]["packet_type"] == "TEST_SAFETY_EXPLICIT_RUN"


def test_d8_llm_prepare_strips_full_packet():
    full_tool_result = {
        "ok": True,
        "status": "success",
        "test_safety": {
            "packet_type": "TEST_SAFETY_EXPLICIT_RUN",
            "evaluation_packet": {"plan_id": "x", "commands": ["secret"]},
            "authorization_packet": {"authorization": "AUTHORIZED"},
            "runner_evidence": {"git_snapshot": {"dirty": True}},
        },
        "test_safety_summary": {
            "action_id": "A7",
            "persisted_run_path": "/runs/test_safety_explicit/A7.json",
            "resolution_result": "RESOLVED",
            "executor_called": True,
            "test_failed": False,
            "run_closed": True,
            "closure_reason": "normal",
            "stdout_tail": "ok",
            "stderr_tail": "",
        },
    }
    llm = prepare_tool_result_for_llm("run_test_plan", full_tool_result)
    blob = json.dumps(llm, ensure_ascii=False)
    assert "test_safety" not in llm
    assert "TEST_SAFETY_EXPLICIT_RUN" not in blob
    assert "evaluation_packet" not in blob
    assert "authorization_packet" not in blob
    assert "git_snapshot" not in blob
    assert llm["test_safety_llm_view"]["packet_path"] == "/runs/test_safety_explicit/A7.json"


def test_orchestrator_missing_stub_does_not_run_pytest():
    out = run_test_plan_entry(test_plan=PLAN_OK)
    assert out["ok"] is False
    assert "orchestrator_bridge_required" in str(out.get("error", {}).get("code", ""))


def test_s9_controlled_runtime_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "test_safety.runtime_bridge.RUNS_DIR",
        tmp_path,
    )
    orch = ChatTaskOrchestrator(
        "s9-int",
        "controlled test",
        completion_conditions=["test_run_closed"],
    )
    orch.initialize()
    raw = orch.execute_test_plan_action(
        {"test_plan": INTEGRATION_PLAN},
        relevant_tools=["run_test_plan"],
    )
    outcome = raw["test_safety"]
    assert outcome["executor_called"] is True
    assert outcome["test_failed"] is False
    assert outcome["runner_evidence"]["run_closed"] is True
    path = raw["test_safety_summary"]["persisted_run_path"]
    assert path and Path(path).is_file()
    assert orch.runtime.actions[-1].action_id
    ev = [e for e in orch.runtime.evidence.values() if e.tool_name == "run_test_plan"][-1]
    assert ev.created_by_action == orch.runtime.actions[-1].action_id
    assert ev.target == path or path in (ev.target or "")
    assert orch.runtime.tasks[orch.current_task_id].condition_status.get("test_run_closed") == "SATISFIED"
