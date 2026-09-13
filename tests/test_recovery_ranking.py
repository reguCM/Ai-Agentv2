"""Recovery Strategy Policy (P2-12) Synthetic Tests。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.system.context_monitor.recovery import recommend_recovery_strategies
from tools.system.context_monitor.recovery_evidence import (
    append_strategy_evidence,
    classify_evidence_polarity,
    import_p11_compare_evidence,
    load_strategy_evidence,
    record_strategy_outcome,
)
from tools.system.context_monitor.recovery_ranking import (
    analyze_situation,
    rank_recovery_candidates,
    score_strategy,
)


@pytest.fixture
def policy_v3(tmp_path, monkeypatch):
    policy = tmp_path / "recovery_policy.json"
    data = {
        "automatic_recovery_enabled": False,
        "compare_strategies": [
            "retry_same_context",
            "reduce_tool_result",
            "narrow_search_scope",
            "increase_context",
            "retry_with_explicit_tool_instruction",
        ],
        "situation_thresholds": {"large_result_match_count": 30, "large_payload_bytes": 8000},
        "ranking_signals": {
            "retry_same_context": {
                "base_score": 10,
                "timeout_retry_penalty": -20,
                "flag_adjustments": {},
                "evidence_adjustments": {},
            },
            "reduce_tool_result": {
                "base_score": 20,
                "flag_adjustments": {
                    "large_tool_result": 25,
                    "truncated_result": 15,
                    "timeout_failure": 20,
                    "large_payload": 10,
                },
                "evidence_adjustments": {
                    "success_rate_gte_0_5": 20,
                    "success_rate_eq_0": -10,
                },
            },
            "narrow_search_scope": {
                "base_score": 15,
                "flag_adjustments": {},
                "evidence_adjustments": {},
            },
            "increase_context": {
                "base_score": 15,
                "flag_adjustments": {"context_limit_failure": 25},
                "evidence_adjustments": {
                    "success_rate_eq_0": -25,
                    "increase_failed_with_large_result": -25,
                },
            },
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
        "gpu_ranking_observation": {
            "vram_free_tight_mib": 600,
            "increase_context_score_delta_on_tight": -10,
        },
        "evidence_confidence": {
            "high_min_candidate_observations": 10,
            "medium_min_candidate_observations": 5,
            "low_min_candidate_observations": 1,
        },
    }
    policy.write_text(json.dumps(data), encoding="utf-8")
    ev_path = tmp_path / "strategy_evidence.jsonl"
    monkeypatch.setattr("tools.system.context_monitor.recovery.RECOVERY_POLICY_JSON", policy)
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery_evidence.STRATEGY_EVIDENCE_JSONL", ev_path
    )
    return data, ev_path


def _execution(failure_type="TIMEOUT"):
    return {
        "execution_id": "e1",
        "model": "qwen3:14b",
        "profile_id": "qwen3_14b",
        "configured_context": 16384,
        "runtime_context": 16384,
        "task_type": "search_read",
        "failure_classification": {"failure_type": failure_type, "execution_result": "failure"},
        "gpu_state": {"vram_total_mib": 12288, "vram_free_mib": 450},
    }


def _search_payload(count=50, bytes_=10345, truncated=True):
    return {"match_count": count, "payload_bytes": bytes_, "truncated": truncated}


def _p11_evidence_rows(ev_path: Path) -> None:
    """P2-11 相当の Positive / Negative Evidence を Synthetic 登録。"""
    base = {
        "source": "p2-11_live_strategy_compare",
        "failure_type": "TIMEOUT",
        "configured_context": 16384,
        "runtime_context": 16384,
        "tool_result_count": 50,
        "payload_bytes": 10345,
        "truncated": True,
        "phase": "recovery",
    }
    append_strategy_evidence(
        {
            **base,
            "strategy": "reduce_tool_result",
            "tool_call_success": True,
            "tool_execution_success": True,
            "timeout": False,
            "latency_ms": 20627,
            "recovery_result": "success",
        },
        path=ev_path,
    )
    append_strategy_evidence(
        {
            **base,
            "strategy": "increase_context",
            "runtime_context": 32768,
            "tool_call_success": False,
            "timeout": True,
            "latency_ms": 90325,
            "recovery_result": "failure",
        },
        path=ev_path,
    )
    append_strategy_evidence(
        {
            **base,
            "strategy": "retry_with_explicit_tool_instruction",
            "tool_call_success": True,
            "tool_execution_success": True,
            "timeout": False,
            "latency_ms": 77587,
            "recovery_result": "success",
        },
        path=ev_path,
    )


def test_a_large_result_timeout_prefers_reduce(policy_v3):
    policy, _ = policy_v3
    situation = analyze_situation(
        _execution("TIMEOUT"),
        search_payload=_search_payload(),
        policy=policy,
    )
    reduce = score_strategy("reduce_tool_result", situation, [], policy)
    retry = score_strategy("retry_same_context", situation, [], policy)
    assert reduce["rank_score"] > retry["rank_score"]


def test_b_context_limit_boosts_increase(policy_v3):
    policy, _ = policy_v3
    situation = analyze_situation(
        _execution("CONTEXT_LIMIT"),
        search_payload=_search_payload(count=5, bytes_=1000, truncated=False),
        policy=policy,
    )
    inc = score_strategy("increase_context", situation, [], policy)
    reduce = score_strategy("reduce_tool_result", situation, [], policy)
    assert inc["rank_score"] > reduce["rank_score"]


def test_c_p11_increase_failure_lowers_rank(policy_v3, monkeypatch):
    policy, ev_path = policy_v3
    _p11_evidence_rows(ev_path)
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.get_configured_context",
        lambda profile=None: 16384,
    )
    rec = recommend_recovery_strategies(
        _execution("TIMEOUT"),
        search_payload=_search_payload(),
        policy=policy,
        import_p11_evidence=False,
    )
    ranked = {r["candidate_strategy"]: r for r in rec["recommendations"]}
    assert "increase_context" not in ranked
    assert rec["recommendations"][0]["candidate_strategy"] == "reduce_tool_result"
    assert rec["context_expansion"]["gate_status"] == "BLOCKED"


def test_d_p11_reduce_success_raises_rank(policy_v3, monkeypatch):
    policy, ev_path = policy_v3
    _p11_evidence_rows(ev_path)
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.get_configured_context",
        lambda profile=None: 16384,
    )
    rec = recommend_recovery_strategies(
        _execution("TIMEOUT"),
        search_payload=_search_payload(),
        policy=policy,
        import_p11_evidence=False,
    )
    reduce = next(r for r in rec["recommendations"] if r["candidate_strategy"] == "reduce_tool_result")
    assert reduce["evidence_count"] >= 1
    assert reduce["rank_score"] >= 70


def test_e_multiple_strategies_ranked(policy_v3, monkeypatch):
    policy, ev_path = policy_v3
    _p11_evidence_rows(ev_path)
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.get_configured_context",
        lambda profile=None: 16384,
    )
    rec = recommend_recovery_strategies(
        _execution("TIMEOUT"),
        search_payload=_search_payload(),
        policy=policy,
        import_p11_evidence=False,
    )
    ranks = [r["strategy_rank"] for r in rec["recommendations"]]
    assert len(ranks) >= 3
    assert ranks == sorted(ranks)
    assert rec["recommendations"][0]["candidate_strategy"] == "reduce_tool_result"


def test_f_positive_negative_evidence_distinction(policy_v3):
    pos = classify_evidence_polarity({"tool_call_success": True, "recovery_result": "success"})
    neg = classify_evidence_polarity({"tool_call_success": False, "timeout": True, "recovery_result": "failure"})
    assert pos == "positive"
    assert neg == "negative"
    _, ev_path = policy_v3
    rec = record_strategy_outcome(
        strategy="increase_context",
        tool_call_success=False,
        timeout=True,
        recovery_result="failure",
        evidence_source="test",
        path=ev_path,
    )
    assert rec["evidence_polarity"] == "negative"


def test_g_single_evidence_not_high_confidence(policy_v3):
    policy, ev_path = policy_v3
    append_strategy_evidence(
        {"phase": "recovery", "strategy": "reduce_tool_result", "tool_call_success": True},
        path=ev_path,
    )
    situation = analyze_situation(_execution(), search_payload=_search_payload(), policy=policy)
    score = score_strategy(
        "reduce_tool_result", situation, load_strategy_evidence(path=ev_path), policy
    )
    assert score["confidence"] in ("LOW", "UNKNOWN")


def test_h_candidate_generation_does_not_execute_recovery(policy_v3, monkeypatch):
    policy, _ = policy_v3
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.get_configured_context",
        lambda profile=None: 16384,
    )
    with patch("tools.system.context_monitor.recovery.execute_recovery_retry") as exec_mock:
        rec = recommend_recovery_strategies(
            _execution("TIMEOUT"),
            search_payload=_search_payload(),
            policy=policy,
            import_p11_evidence=False,
        )
    exec_mock.assert_not_called()
    assert rec["recommendations"]


def test_i_automatic_recovery_off(policy_v3, monkeypatch):
    policy, _ = policy_v3
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.get_configured_context",
        lambda profile=None: 16384,
    )
    rec = recommend_recovery_strategies(
        _execution(),
        search_payload=_search_payload(),
        policy=policy,
        import_p11_evidence=False,
    )
    assert rec["automatic_recovery_enabled"] is False
    assert all(r["automatic_execution_allowed"] is False for r in rec["recommendations"])


def test_import_p11_evidence(tmp_path, monkeypatch):
    compare_dir = tmp_path / "runs" / "ai_tool" / "20260902_test_recovery_strategy_compare_p211"
    compare_dir.mkdir(parents=True)
    compare_path = compare_dir / "compare.json"
    compare_path.write_text(
        json.dumps(
            {
                "task_id": "FILE-TOOLS-RECOVERY-STRATEGY-COMPARE-P2-11",
                "shared_search_payload": {"result_count": 50, "payload_bytes": 10345, "truncated": True},
                "cycles": [
                    {
                        "scenario_id": "t1",
                        "configured_context": 16384,
                        "baseline": {
                            "failure_type": "TIMEOUT",
                            "context": 16384,
                            "tool_call_recovery": "FAILURE",
                            "timeout": True,
                            "result_count": 50,
                            "payload_bytes": 10345,
                            "truncated": True,
                        },
                        "strategies": {
                            "reduce_tool_result": {
                                "tool_call_recovery": "SUCCESS",
                                "timeout": False,
                                "latency_ms": 20627,
                            },
                            "increase_context": {
                                "tool_call_recovery": "FAILURE",
                                "timeout": True,
                                "latency_ms": 90325,
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ev_path = tmp_path / "strategy_evidence.jsonl"
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery_evidence._repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery_evidence.STRATEGY_EVIDENCE_JSONL",
        ev_path,
    )
    result = import_p11_compare_evidence(compare_path)
    assert result["imported"] >= 3
    rows = load_strategy_evidence(path=ev_path)
    polarities = {r["strategy"]: r.get("evidence_polarity") for r in rows if r.get("phase") == "recovery"}
    assert polarities.get("reduce_tool_result") == "positive"
    assert polarities.get("increase_context") == "negative"
