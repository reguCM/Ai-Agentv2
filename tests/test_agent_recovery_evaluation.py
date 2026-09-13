"""Agent Recovery 評価・Context Gate（P2-13）Synthetic Tests。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.system.context_monitor.agent_recovery_bridge import (
    prepare_agent_recovery_evaluation,
    submit_agent_recovery_selection,
)
from tools.system.context_monitor.agent_recovery_evaluation import (
    append_agent_recovery_evaluation,
    build_agent_evaluation_record,
    compare_ranking_vs_agent,
    load_agent_recovery_evaluations,
    parse_agent_recovery_selection,
    record_agent_recovery_outcome,
    resolve_agent_selection_for_execution,
)
from tools.system.context_monitor.context_expansion_gate import evaluate_context_expansion_gate
from tools.system.context_monitor.recovery import RecoverySession, recommend_recovery_strategies


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
                "flag_adjustments": {"large_tool_result": 25, "truncated_result": 15, "timeout_failure": 20, "large_payload": 10},
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
        "increase_context_failure_types": ["TOOL_CALL_NOT_GENERATED", "TIMEOUT", "CONTEXT_LIMIT"],
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
    monkeypatch.setattr("tools.system.context_monitor.recovery.RECOVERY_POLICY_JSON", policy)
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_evaluation.AGENT_RECOVERY_EVALUATIONS_JSONL",
        ev_path,
    )
    return data, ev_path


def _execution(failure_type="TIMEOUT"):
    return {
        "execution_id": "e-p213",
        "model": "qwen3:14b",
        "profile_id": "qwen3_14b",
        "configured_context": 16384,
        "runtime_context": 16384,
        "task_type": "search_read",
        "expected_tool": "read_file",
        "failure_classification": {"failure_type": failure_type, "execution_result": "failure"},
        "gpu_state": {"vram_total_mib": 12288, "vram_free_mib": 800},
    }


def _search_payload():
    return {"match_count": 50, "payload_bytes": 10345, "truncated": True}


def _recommendation(policy, monkeypatch):
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.get_configured_context",
        lambda profile=None: 16384,
    )
    return recommend_recovery_strategies(
        _execution(),
        search_payload=_search_payload(),
        policy=policy,
        import_p11_evidence=False,
    )


def test_a_ranking_agent_match(policy_v4, monkeypatch):
    policy, _ = policy_v4
    rec = _recommendation(policy, monkeypatch)
    top = rec["recommendations"][0]["candidate_strategy"]
    agent = {
        "selected_strategy": top,
        "reason": "Evidence ranking と一致",
        "confidence": "LOW",
    }
    assert compare_ranking_vs_agent(top, agent["selected_strategy"]) == "MATCH"


def test_b_ranking_agent_different(policy_v4, monkeypatch):
    policy, _ = policy_v4
    rec = _recommendation(policy, monkeypatch)
    top = rec["recommendations"][0]["candidate_strategy"]
    agent = {
        "selected_strategy": "retry_same_context",
        "reason": "再試行を選ぶ",
        "confidence": "LOW",
    }
    assert top != agent["selected_strategy"]
    assert compare_ranking_vs_agent(top, agent["selected_strategy"]) == "DIFFERENT"


def test_c_agent_reason_and_confidence(policy_v4):
    parsed = parse_agent_recovery_selection(
        {
            "selected_strategy": "reduce_tool_result",
            "reason": "大量Result後のTimeout",
            "confidence": "LOW",
            "alternatives_considered": [{"strategy": "retry_same_context", "reason": "timeout evidence"}],
        }
    )
    assert parsed["reason"]
    assert parsed["confidence"] == "LOW"
    assert len(parsed["alternatives_considered"]) == 1


def test_d_agent_selection_separate_from_recovery(policy_v4, tmp_path, monkeypatch):
    _, ev_path = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.agent_recovery_evaluation.AGENT_RECOVERY_EVALUATIONS_JSONL",
        ev_path,
    )
    outcome = record_agent_recovery_outcome(
        evaluation_id="eval-1",
        agent_selection={"selected_strategy": "reduce_tool_result", "reason": "x", "confidence": "LOW"},
        recovery_execution={"executed": True, "recovery_result": "success", "tool_call_recovery": "SUCCESS"},
        task_result="FAILURE",
        path=ev_path,
    )
    assert outcome["agent_selection"]["selected_strategy"] == "reduce_tool_result"
    assert outcome["recovery_execution"]["recovery_result"] == "success"
    assert outcome["task_result"] == "FAILURE"


def test_e_recovery_success_task_failure(policy_v4, tmp_path, monkeypatch):
    _, ev_path = policy_v4
    outcome = record_agent_recovery_outcome(
        evaluation_id="eval-2",
        agent_selection={"selected_strategy": "increase_context", "reason": "ctx", "confidence": "LOW"},
        recovery_execution={"executed": True, "recovery_result": "success"},
        task_result="FAILURE",
        path=ev_path,
    )
    assert outcome["recovery_execution"]["recovery_result"] == "success"
    assert outcome["task_result"] == "FAILURE"


def test_f_increase_context_blocked_without_gate(policy_v4, monkeypatch):
    policy, _ = policy_v4
    rec = _recommendation(policy, monkeypatch)
    agent = {"selected_strategy": "increase_context", "reason": "ctx up", "confidence": "LOW"}
    plan = resolve_agent_selection_for_execution(
        agent, rec, _execution(), cycle_state={}, human_approved=True
    )
    assert plan["execution_status"] == "BLOCKED"
    assert plan["blocked_by"] == "context_expansion_gate"


def test_g_gate_allows_when_conditions_met(policy_v4, monkeypatch):
    policy, _ = policy_v4
    rec = _recommendation(policy, monkeypatch)
    cycle = {
        "normal_recovery_attempted": True,
        "task_unresolved": True,
        "recovery_failed": True,
        "tried_strategies": [r["candidate_strategy"] for r in rec["recommendations"]],
        "context_expansion_used": False,
    }
    gate = evaluate_context_expansion_gate(
        execution=_execution(),
        cycle_state=cycle,
        context_expansion_decision=rec["context_expansion"].get("decision"),
        normal_recommendations=rec["recommendations"],
        policy=policy,
        human_approved=True,
        check_approval=True,
    )
    assert gate["gate_status"] == "ALLOWED"
    plan = resolve_agent_selection_for_execution(
        {"selected_strategy": "increase_context", "reason": "last resort", "confidence": "LOW"},
        rec,
        _execution(),
        cycle_state=cycle,
        human_approved=True,
    )
    assert plan["execution_status"] == "APPROVAL_READY"


def test_h_no_double_context_expansion(policy_v4, monkeypatch):
    policy, _ = policy_v4
    rec = _recommendation(policy, monkeypatch)
    cycle = {
        "normal_recovery_attempted": True,
        "task_unresolved": True,
        "tried_strategies": [r["candidate_strategy"] for r in rec["recommendations"]],
        "context_expansion_used": True,
    }
    gate = evaluate_context_expansion_gate(
        execution=_execution(),
        cycle_state=cycle,
        context_expansion_decision=rec["context_expansion"].get("decision"),
        normal_recommendations=rec["recommendations"],
        policy=policy,
        human_approved=True,
    )
    assert gate["gate_status"] == "BLOCKED"
    assert "context_expansion_already_used_this_cycle" in gate["blocked_reasons"]


def test_i_agent_override_recorded(policy_v4, tmp_path, monkeypatch):
    policy, ev_path = policy_v4
    rec = _recommendation(policy, monkeypatch)
    execution = _execution()
    agent = {
        "selected_strategy": "retry_with_explicit_tool_instruction",
        "reason": "Tool Call生成問題",
        "confidence": "LOW",
    }
    result = submit_agent_recovery_selection(
        execution,
        agent,
        recommendation=rec,
        record=True,
    )
    assert result["ranking_vs_agent"] == "DIFFERENT"
    rows = load_agent_recovery_evaluations(path=ev_path)
    assert any(r.get("ranking_vs_agent") == "DIFFERENT" for r in rows)


def test_j_prepare_brief_and_no_auto_execution(policy_v4, monkeypatch):
    policy, _ = policy_v4
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.get_configured_context",
        lambda profile=None: 16384,
    )
    prepared = prepare_agent_recovery_evaluation(_execution(), search_payload=_search_payload())
    assert prepared["agent_brief"]["current_situation"]["failure_type"] == "TIMEOUT"
    assert prepared["automatic_recovery_enabled"] is False
    assert "increase_context" not in [
        s["strategy"] for s in prepared["agent_brief"]["evidence_ranking"]
    ]
