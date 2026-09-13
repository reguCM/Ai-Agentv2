"""Context Recovery Strategy ユニットテスト（Synthetic）。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.system.context_monitor.failure_classifier import (
    classify_execution_record,
    classify_llm_response,
    execution_needs_recovery,
)
from tools.system.context_monitor.recovery import (
    RecoverySession,
    build_execution_record,
    build_recovery_decision,
    execute_recovery_retry,
    gather_recovery_evidence,
    gpu_observation_allows_execution,
    is_automatic_recovery_enabled,
    next_context_step,
    propose_recovery,
    validate_candidate_context,
)


class _Fn:
    def __init__(self, name: str):
        self.name = name


class _Tc:
    def __init__(self, name: str):
        self.function = _Fn(name)


class _Msg:
    def __init__(self, *, tool_calls=None, thinking="", content=""):
        self.tool_calls = tool_calls or []
        self._thinking = thinking
        self._content = content

    def model_dump(self):
        return {"thinking": self._thinking, "content": self._content}


class _Resp:
    def __init__(self, msg: _Msg):
        self.message = msg


def _success_response(tool="read_file"):
    return _Resp(_Msg(tool_calls=[_Tc(tool)]))


def _not_generated_response():
    return _Resp(
        _Msg(
            thinking="I need to call read_file to inspect the registry file.",
            content="",
        )
    )


@pytest.fixture
def recovery_paths(tmp_path, monkeypatch):
    decisions = tmp_path / "recovery_decisions.jsonl"
    results = tmp_path / "recovery_results.jsonl"
    obs = tmp_path / "observations.jsonl"
    policy = tmp_path / "recovery_policy.json"
    policy.write_text(
        json.dumps(
            {
                "version": 1,
                "automatic_recovery_enabled": False,
                "max_recovery_attempts": 1,
                "max_context_changes_per_session": 1,
                "context_ladder": [4096, 8192, 16384, 32768],
                "model_context_limits": {"qwen3:14b": 40960, "qwen3_14b": 40960},
                "pc_context_limit": 32768,
                "increase_context_failure_types": [
                    "TOOL_CALL_NOT_GENERATED",
                    "CONTEXT_LIMIT",
                    "TIMEOUT",
                ],
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
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.RECOVERY_POLICY_JSON",
        policy,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.RECOVERY_DECISIONS_JSONL",
        decisions,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.recovery.RECOVERY_RESULTS_JSONL",
        results,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.record.OBSERVATIONS_JSONL",
        obs,
    )
    return {"decisions": decisions, "results": results, "obs": obs, "policy": policy}


def test_success_no_recovery():
    execution = build_execution_record(
        response=_success_response(),
        expected_tool="read_file",
        configured_context=16384,
        runtime_context=16384,
    )
    proposal = propose_recovery(execution)
    assert proposal["recovery_required"] is False
    assert proposal["decisions"] == []


def test_tool_call_not_generated_detected():
    cls = classify_llm_response(
        _not_generated_response(),
        expected_tool="read_file",
        tools_requested=True,
    )
    assert cls["failure_type"] == "TOOL_CALL_NOT_GENERATED"
    assert execution_needs_recovery(cls)


def test_increase_context_candidate_16384_to_32768(recovery_paths):
    decision = build_recovery_decision(
        parent_execution_id="exec-1",
        model="qwen3:14b",
        profile_id="qwen3_14b",
        configured_context=16384,
        current_context=16384,
        failure_type="TOOL_CALL_NOT_GENERATED",
        task_type="search_read",
        gpu_state={"vram_total_mib": 12288, "vram_free_mib": 500},
    )
    assert decision["candidate_strategy"] == "increase_context"
    assert decision["candidate_context"] == 32768
    assert decision["execution_allowed"] is True
    assert decision["automatic_execution_allowed"] is False


def test_model_limit_blocks_candidate(recovery_paths):
    validation = validate_candidate_context(
        32768,
        current=16384,
        model="qwen3:14b",
        profile_id="qwen3_14b",
    )
    assert validation["valid"] is True

    tiny_policy_path = recovery_paths["policy"]
    data = json.loads(tiny_policy_path.read_text(encoding="utf-8"))
    data["model_context_limits"]["qwen3:14b"] = 16384
    tiny_policy_path.write_text(json.dumps(data), encoding="utf-8")

    validation2 = validate_candidate_context(
        32768,
        current=16384,
        model="qwen3:14b",
        profile_id="qwen3_14b",
    )
    assert validation2["valid"] is False


def test_pc_limit_blocks_candidate(recovery_paths):
    data = json.loads(recovery_paths["policy"].read_text(encoding="utf-8"))
    data["pc_context_limit"] = 16384
    recovery_paths["policy"].write_text(json.dumps(data), encoding="utf-8")

    validation = validate_candidate_context(
        32768,
        current=8192,
        model="qwen3:14b",
        profile_id="qwen3_14b",
    )
    assert validation["valid"] is False


def test_gpu_unavailable_blocks_execution(recovery_paths):
    check = gpu_observation_allows_execution({"capture_error": True})
    assert check["execution_allowed"] is False
    assert check["block_reason"] == "gpu_observation_unavailable"


def test_recovery_session_prevents_loop(recovery_paths):
    session = RecoverySession()
    assert session.can_change_context(32768) is True
    session.record_attempt(context_used=16384)
    session.record_attempt(context_used=32768)
    assert session.can_attempt_recovery() is False
    assert session.can_change_context(32768) is False


def test_recovery_result_records_chain(recovery_paths):
    decision = build_recovery_decision(
        parent_execution_id="parent-1",
        model="qwen3:14b",
        profile_id="qwen3_14b",
        configured_context=16384,
        current_context=16384,
        failure_type="TOOL_CALL_NOT_GENERATED",
        gpu_state={"vram_total_mib": 12288, "vram_free_mib": 800},
    )

    def fake_chat(**kwargs):
        assert kwargs.get("runtime_context") == 32768
        return _success_response("read_file")

    with patch("tools.system.context_monitor.recovery.snapshot_gpu", return_value={"vram_total_mib": 12288, "vram_free_mib": 800}):
        result = execute_recovery_retry(
            decision,
            fake_chat,
            chat_kwargs={"tools": [{}], "expected_tool": "read_file"},
            approved=True,
            record=True,
        )

    assert result["recovery_result"] == "success"
    assert result["previous_context"] == 16384
    assert result["current_context"] == 32768
    assert result["configured_context"] == 16384
    assert recovery_paths["results"].exists()
    lines = recovery_paths["results"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["parent_execution_id"] == "parent-1"


def test_execute_without_approval(recovery_paths):
    decision = build_recovery_decision(
        parent_execution_id="p",
        model="qwen3:14b",
        profile_id="qwen3_14b",
        configured_context=16384,
        current_context=16384,
        failure_type="TOOL_CALL_NOT_GENERATED",
        gpu_state={"vram_total_mib": 12288},
    )
    result = execute_recovery_retry(
        decision,
        lambda **k: _success_response(),
        chat_kwargs={},
        approved=False,
    )
    assert result["recovery_result"] == "not_executed"


def test_automatic_recovery_off_by_default(recovery_paths):
    assert is_automatic_recovery_enabled() is False


def test_next_context_step():
    assert next_context_step(16384) == 32768
    assert next_context_step(32768) is None


def test_classify_execution_record_timeout():
    cls = classify_execution_record({"timeout": True})
    assert cls["failure_type"] == "TIMEOUT"


def test_gather_evidence_from_observations(recovery_paths):
    from tools.system.context_monitor.record import append_observation, build_observation

    for ctx, ok in [(16384, False), (16384, False), (32768, True), (32768, True)]:
        append_observation(
            build_observation(
                source="test",
                model="qwen3:14b",
                profile_id="qwen3_14b",
                context_size=ctx,
                tools_enabled=True,
                task_type="search_read",
                outcome={"success": ok, "native_tool_call": ok},
            ),
            path=recovery_paths["obs"],
        )
    evidence = gather_recovery_evidence(
        model="qwen3:14b",
        task_type="search_read",
        failure_type="TOOL_CALL_NOT_GENERATED",
        current_context=16384,
        candidate_context=32768,
        observations=None,
    )
    assert evidence["candidate_context_observations"] == 2
    assert evidence["historical_improvement_observed"] is True
