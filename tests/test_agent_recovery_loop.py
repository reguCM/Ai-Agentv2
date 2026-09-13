"""Agent Loop Recovery Evaluation Integration（P2-14）Synthetic Tests。"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.system.context_monitor.agent_recovery_evaluation import load_agent_recovery_evaluations
from tools.system.context_monitor.agent_recovery_loop import (
    agent_recovery_loop_enabled,
    handle_agent_recovery_failure,
    tool_result_is_execution_failure,
)


@pytest.fixture
def policy_v4(tmp_path, monkeypatch):
    policy = tmp_path / "recovery_policy.json"
    data = {
        "automatic_recovery_enabled": False,
        "max_recovery_attempts": 1,
        "max_context_changes_per_session": 1,
        "compare_strategies": [
            "retry_same_context",
            "reduce_tool_result",
            "narrow_search_scope",
            "increase_context",
            "retry_with_explicit_tool_instruction",
        ],
        "situation_thresholds": {"large_result_match_count": 30, "large_payload_bytes": 8000},
        "ranking_signals": {
            "retry_same_context": {"base_score": 10, "timeout_retry_penalty": -20, "flag_adjustments": {}, "evidence_adjustments": {}},
            "reduce_tool_result": {
                "base_score": 20,
                "flag_adjustments": {"large_tool_result": 25, "timeout_failure": 20},
                "evidence_adjustments": {"success_rate_gte_0_5": 20},
            },
            "narrow_search_scope": {"base_score": 15, "flag_adjustments": {}, "evidence_adjustments": {}},
            "increase_context": {"base_score": 15, "flag_adjustments": {}, "evidence_adjustments": {}},
            "retry_with_explicit_tool_instruction": {
                "base_score": 18,
                "flag_adjustments": {"tool_call_not_generated": 25},
                "evidence_adjustments": {},
            },
        },
        "context_ladder": [4096, 8192, 16384, 32768],
        "model_context_limits": {"qwen3:14b": 40960},
        "pc_context_limit": 32768,
        "strategy_params": {"reduce_tool_result": {"max_matches": 10}},
        "increase_context_failure_types": ["TOOL_CALL_NOT_GENERATED", "TIMEOUT", "CONTEXT_LIMIT", "TOOL_EXECUTION_FAILED"],
        "gpu_safety": {
            "require_observation_for_execution": True,
            "block_if_status_unavailable": True,
            "block_if_vram_total_unknown": True,
        },
        "evidence_confidence": {
            "high_min_candidate_observations": 10,
            "medium_min_candidate_observations": 5,
            "low_min_candidate_observations": 1,
        },
    }
    policy.write_text(json.dumps(data), encoding="utf-8")
    ev_path = tmp_path / "agent_recovery_evaluations.jsonl"
    dec_path = tmp_path / "recovery_decisions.jsonl"
    monkeypatch.setattr("tools.system.context_monitor.recovery.RECOVERY_POLICY_JSON", policy)
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_evaluation.AGENT_RECOVERY_EVALUATIONS_JSONL",
        ev_path,
    )
    monkeypatch.setattr("tools.system.context_monitor.recovery.RECOVERY_DECISIONS_JSONL", dec_path)
    monkeypatch.setenv("AI_AGENT_RECOVERY_OPT_IN", "1")
    return data, ev_path


class _Fn:
    def __init__(self, name):
        self.name = name


class _Msg:
    def __init__(self, *, tool_calls=None, thinking="", content=""):
        self.tool_calls = tool_calls or []
        self._thinking = thinking
        self._content = content

    def model_dump(self):
        return {"thinking": self._thinking, "content": self._content}


class _Resp:
    def __init__(self, msg):
        self.message = msg


def test_a_normal_success_no_recovery(policy_v4, monkeypatch):
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.get_configured_context",
        lambda profile=None: 16384,
    )
    resp = _Resp(_Msg(tool_calls=[SimpleNamespace(function=_Fn("read_file"))]))
    out = handle_agent_recovery_failure(response=resp, expected_tool="read_file")
    assert out is None


def test_b_tool_call_not_generated(policy_v4, monkeypatch):
    policy, ev_path = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.get_configured_context",
        lambda profile=None: 16384,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.snapshot_gpu",
        lambda: {"vram_total_mib": 12288, "vram_free_mib": 800},
    )
    resp = _Resp(_Msg(thinking="I need to call read_file", content=""))
    out = handle_agent_recovery_failure(
        response=resp,
        expected_tool="read_file",
        selection_override={
            "selected_strategy": "reduce_tool_result",
            "reason": "large result timeout pattern",
            "confidence": "LOW",
        },
    )
    assert out is not None
    assert out["stop"] is True
    assert out["status"] == "AWAITING_HUMAN_APPROVAL"
    assert out["automatic_recovery_enabled"] is False
    rows = load_agent_recovery_evaluations(path=ev_path)
    assert len(rows) == 1
    assert rows[0]["approval_status"] == "PENDING"
    assert rows[0]["execution_status"] in ("APPROVAL_REQUIRED", "BLOCKED", "NOT_EXECUTED")


def test_c_tool_execution_failure(policy_v4, monkeypatch):
    policy, ev_path = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.get_configured_context",
        lambda profile=None: 16384,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.snapshot_gpu",
        lambda: {"vram_total_mib": 12288, "vram_free_mib": 800},
    )
    resp = _Resp(_Msg(tool_calls=[SimpleNamespace(function=_Fn("read_file"))]))
    out = handle_agent_recovery_failure(
        response=resp,
        expected_tool="read_file",
        tool_execution_ok=False,
        selection_override={
            "selected_strategy": "retry_same_context",
            "reason": "retry once",
            "confidence": "LOW",
        },
    )
    assert out["stop"] is True
    assert out["status"] == "AWAITING_HUMAN_APPROVAL"


def test_d_timeout(policy_v4, monkeypatch):
    policy, ev_path = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.get_configured_context",
        lambda profile=None: 16384,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.snapshot_gpu",
        lambda: {"vram_total_mib": 12288, "vram_free_mib": 800},
    )
    out = handle_agent_recovery_failure(
        response=None,
        timeout=True,
        error="timeout",
        selection_override={
            "selected_strategy": "reduce_tool_result",
            "reason": "timeout with large payload",
            "confidence": "LOW",
        },
    )
    assert out["stop"] is True
    assert out["agent_selection"]["selected_strategy"] == "reduce_tool_result"


def test_e_invalid_selection(policy_v4, monkeypatch):
    policy, ev_path = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.get_configured_context",
        lambda profile=None: 16384,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.snapshot_gpu",
        lambda: {"vram_total_mib": 12288, "vram_free_mib": 800},
    )
    resp = _Resp(_Msg(thinking="read_file", content=""))
    out = handle_agent_recovery_failure(
        response=resp,
        expected_tool="read_file",
        selection_override="not valid json",
    )
    assert out["status"] == "SELECTION_INVALID"
    rows = load_agent_recovery_evaluations(path=ev_path)
    assert rows[0]["approval_status"] == "INVALID_SELECTION"
    assert rows[0]["selection_valid"] is False


def test_f_increase_context_blocked(policy_v4, monkeypatch):
    policy, ev_path = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.get_configured_context",
        lambda profile=None: 16384,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.snapshot_gpu",
        lambda: {"vram_total_mib": 12288, "vram_free_mib": 800},
    )
    resp = _Resp(_Msg(thinking="read_file", content=""))
    out = handle_agent_recovery_failure(
        response=resp,
        expected_tool="read_file",
        selection_override={
            "selected_strategy": "increase_context",
            "reason": "try bigger context",
            "confidence": "LOW",
        },
    )
    assert out["execution_plan"]["execution_status"] == "BLOCKED"
    assert out["execution_plan"]["blocked_by"] == "context_expansion_gate"
    assert out["execution"]["configured_context"] == 16384


def test_g_increase_context_gate_allowed_no_execution(policy_v4, monkeypatch):
    from tools.system.context_monitor.context_expansion_gate import evaluate_context_expansion_gate

    policy, ev_path = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.get_configured_context",
        lambda profile=None: 16384,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_loop.snapshot_gpu",
        lambda: {"vram_total_mib": 12288, "vram_free_mib": 800},
    )
    resp = _Resp(_Msg(thinking="read_file", content=""))
    rec = handle_agent_recovery_failure(
        response=resp,
        expected_tool="read_file",
        selection_override={"selected_strategy": "reduce_tool_result", "reason": "x", "confidence": "LOW"},
    )
    cycle = {
        "normal_recovery_attempted": True,
        "task_unresolved": True,
        "recovery_failed": True,
        "tried_strategies": [
            r["candidate_strategy"]
            for r in rec["recommendation"]["recommendations"]
        ],
        "context_expansion_used": False,
    }
    gate = evaluate_context_expansion_gate(
        execution=rec["execution"],
        cycle_state=cycle,
        context_expansion_decision=rec["recommendation"]["context_expansion"].get("decision"),
        normal_recommendations=rec["recommendation"]["recommendations"],
        policy=policy,
        human_approved=True,
        check_approval=True,
    )
    assert gate["gate_status"] == "ALLOWED"

    out = handle_agent_recovery_failure(
        response=resp,
        expected_tool="read_file",
        cycle_state=cycle,
        selection_override={
            "selected_strategy": "increase_context",
            "reason": "last resort",
            "confidence": "LOW",
        },
    )
    assert out["automatic_recovery_enabled"] is False
    assert out["execution"]["configured_context"] == 16384
    assert out["execution_plan"]["execution_status"] == "BLOCKED"


def test_h_separation_in_outcome_record(policy_v4, monkeypatch):
    from tools.system.context_monitor.agent_recovery_evaluation import record_agent_recovery_outcome

    _, ev_path = policy_v4
    outcome = record_agent_recovery_outcome(
        evaluation_id="eval-sep",
        agent_selection={"selected_strategy": "reduce_tool_result", "reason": "r", "confidence": "LOW"},
        recovery_execution={"executed": False, "recovery_result": None},
        task_result="UNKNOWN",
        path=ev_path,
    )
    assert outcome["agent_selection"]["selected_strategy"] == "reduce_tool_result"
    assert outcome["recovery_execution"]["executed"] is False
    assert outcome["task_result"] == "UNKNOWN"


def test_a_normal_tool_result_not_failure():
    assert tool_result_is_execution_failure({"ok": True}) is False
    assert tool_result_is_execution_failure({"ok": False, "blocked": True}) is False
    assert tool_result_is_execution_failure({"ok": False}) is True


def test_loop_disabled_without_opt_in(policy_v4, monkeypatch):
    monkeypatch.delenv("AI_AGENT_RECOVERY_OPT_IN", raising=False)
    assert agent_recovery_loop_enabled() is False
    resp = _Resp(_Msg(thinking="read_file", content=""))
    assert handle_agent_recovery_failure(response=resp, expected_tool="read_file") is None
