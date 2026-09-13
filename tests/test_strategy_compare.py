"""Recovery Strategy 比較（Synthetic）。"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tools.system.context_monitor.recovery import propose_all_recovery_candidates
from tools.system.context_monitor.recovery_strategies import (
    apply_strategy,
    narrow_search_payload,
    reduce_search_payload,
)
from tools.system.context_monitor.strategy_compare import (
    aggregate_strategy_evaluation,
    run_compare_cycle,
)


@pytest.fixture
def policy_paths(tmp_path, monkeypatch):
    policy = tmp_path / "recovery_policy.json"
    data = {
        "automatic_recovery_enabled": False,
        "max_recovery_attempts": 1,
        "max_context_changes_per_session": 1,
        "context_ladder": [4096, 8192, 16384, 32768],
        "model_context_limits": {"qwen3:14b": 40960},
        "pc_context_limit": 32768,
        "compare_strategies": [
            "retry_same_context",
            "reduce_tool_result",
            "narrow_search_scope",
            "increase_context",
            "retry_with_explicit_tool_instruction",
        ],
        "strategy_params": {
            "reduce_tool_result": {"max_matches": 10},
            "narrow_search_scope": {
                "search_paths": ["registry"],
                "query": "read_file",
            },
            "retry_with_explicit_tool_instruction": {
                "instruction": "Native Tool Call として read_file を呼び出してください。"
            },
        },
        "increase_context_failure_types": ["TOOL_CALL_NOT_GENERATED", "TIMEOUT"],
        "gpu_safety": {
            "require_observation_for_execution": True,
            "block_if_status_unavailable": True,
            "block_if_vram_total_unknown": True,
        },
        "evidence_confidence": {
            "high_min_candidate_observations": 10,
            "medium_min_candidate_observations": 5,
            "low_min_candidate_observations": 1,
            "improvement_rate_threshold": 0.15,
        },
    }
    policy.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.RECOVERY_POLICY_JSON",
        policy,
    )
    return policy, data


@pytest.fixture
def policy_dict(policy_paths):
    return policy_paths[1]


def test_reduce_tool_result():
    payload = {
        "ok": True,
        "match_count": 50,
        "truncated": True,
        "matches": [{"path": f"f{i}.txt", "line": 1, "text": "read_file"} for i in range(50)],
    }
    reduced = reduce_search_payload(payload, max_matches=10)
    assert reduced["match_count"] == 10
    assert reduced["recovery_meta"]["original_match_count"] == 50


def test_apply_strategy_reduce(policy_dict):
    payload = {"ok": True, "match_count": 40, "matches": [{"path": "a", "line": 1, "text": "x"}] * 40}
    applied = apply_strategy(
        "reduce_tool_result", search_payload=payload, configured_context=16384, policy=policy_dict
    )
    assert applied["runtime_context"] == 16384
    assert applied["strategy_params"]["reduced_to"] == 10
    assert len(applied["messages"]) >= 4


def test_apply_strategy_increase_context(policy_dict):
    payload = {"ok": True, "match_count": 5, "matches": []}
    applied = apply_strategy(
        "increase_context", search_payload=payload, configured_context=16384, policy=policy_dict
    )
    assert applied["runtime_context"] == 32768


def test_apply_strategy_explicit_instruction(policy_dict):
    payload = {"ok": True, "match_count": 5, "matches": []}
    applied = apply_strategy(
        "retry_with_explicit_tool_instruction",
        search_payload=payload,
        configured_context=16384,
        policy=policy_dict,
    )
    assert applied["messages"][-1]["role"] == "user"
    assert "Native Tool Call" in applied["messages"][-1]["content"]


def test_propose_all_recovery_candidates(policy_paths):
    execution = {
        "execution_id": "e1",
        "model": "qwen3:14b",
        "profile_id": "qwen3_14b",
        "configured_context": 16384,
        "runtime_context": 16384,
        "task_type": "search_read",
        "failure_classification": {"failure_type": "TOOL_CALL_NOT_GENERATED", "execution_result": "failure"},
        "gpu_state": {"vram_total_mib": 12288, "vram_free_mib": 800},
    }
    with patch(
        "tools.system.context_monitor.recovery.load_observations",
        return_value=[],
    ):
        proposal = propose_all_recovery_candidates(
            execution,
            search_payload={"match_count": 50, "truncated": True},
        )
    strategies = {d["candidate_strategy"] for d in proposal["decisions"]}
    assert "retry_same_context" in strategies
    assert "reduce_tool_result" in strategies
    assert "increase_context" in strategies
    assert all(d["automatic_execution_allowed"] is False for d in proposal["decisions"])


def test_compare_cycle_synthetic(policy_paths, monkeypatch):
    monkeypatch.setenv("AI_AGENT_CONTEXT_MONITOR", "0")

    class _Fn:
        def __init__(self, name, arguments=None):
            self.name = name
            self.arguments = arguments or {}

    class _Tc:
        def __init__(self, name):
            self.function = _Fn(name)

    class _Msg:
        def __init__(self, tool_calls=None, thinking=""):
            self.tool_calls = tool_calls or []

        def model_dump(self):
            return {"thinking": thinking, "content": ""}

    class _Resp:
        def __init__(self, msg):
            self.message = msg

    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        ctx = kwargs.get("runtime_context")
        if ctx == 32768 or calls["n"] > 2:
            return _Resp(_Msg(tool_calls=[_Tc("read_file")]))
        return _Resp(_Msg(thinking="need read_file"))

    payload = {
        "ok": True,
        "match_count": 50,
        "truncated": True,
        "matches": [{"path": "a", "line": 1, "text": "read_file"}],
    }

    with patch(
        "tools.system.context_monitor.strategy_compare.run_llm_attempt",
        side_effect=lambda *a, **k: {
            "execution": {
                "execution_id": f"ex-{calls['n']}",
                "execution_result": "failure" if calls["n"] <= 1 else "success",
                "tool_call_recovery": "FAILURE" if calls["n"] <= 1 else "SUCCESS",
                "task_result": "UNKNOWN",
                "failure_classification": {"failure_type": "TOOL_CALL_NOT_GENERATED"},
                "native_tool_call": calls["n"] > 1,
                "native_tool_names": ["read_file"] if calls["n"] > 1 else [],
                "model": "qwen3:14b",
            },
            "timeout": False,
            "elapsed_ms": 1000 * calls["n"],
            "gpu_before": {"vram_free_mib": 500},
            "gpu_after": {"vram_free_mib": 400},
        },
    ), patch(
        "tools.system.context_monitor.strategy_compare.get_configured_context",
        return_value=16384,
    ), patch(
        "tools.system.context_monitor.strategy_compare.append_recovery_decision",
    ), patch(
        "tools.system.context_monitor.strategy_compare.append_recovery_result",
    ):
        cycle = run_compare_cycle(
            scenario_id="syn_1",
            search_payload=payload,
            chat_fn=fake_chat,
            strategies=["retry_same_context", "increase_context"],
        )

    assert "baseline" in cycle
    assert len(cycle.get("recovery_candidates") or []) >= 2
    assert "retry_same_context" in cycle["strategies"]


def test_aggregate_evaluation():
    cycles = [
        {
            "baseline": {"failure_reproduced": True},
            "strategies": {
                "reduce_tool_result": {
                    "tool_call_recovery": "SUCCESS",
                    "tool_execution_success": True,
                    "timeout": False,
                    "latency_ms": 15000,
                    "vram_free_before_mib": 600,
                },
                "increase_context": {
                    "tool_call_recovery": "SUCCESS",
                    "timeout": True,
                    "latency_ms": 90000,
                    "vram_free_before_mib": 200,
                },
            },
        }
    ]
    ev = aggregate_strategy_evaluation(cycles)
    assert ev["by_strategy"]["reduce_tool_result"]["tool_call_success_count"] == 1
    assert ev["by_strategy"]["increase_context"]["timeout_count"] == 1
