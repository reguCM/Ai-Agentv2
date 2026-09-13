"""Recovery Harness / Agent opt-in テスト。"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.system.context_monitor.agent_recovery_bridge import (
    evaluate_llm_round_for_recovery,
    recovery_opt_in_enabled,
)
from tools.system.context_monitor.recovery_harness import (
    _needs_recovery,
    build_fixed_payload_messages,
    run_harness_attempt,
)
from tools.system.context_monitor.recovery_helpers import (
    evaluate_tool_call_recovery,
    format_recovery_approval_summary,
)


class _Fn:
    def __init__(self, name: str, arguments=None):
        self.name = name
        self.arguments = arguments if arguments is not None else {}


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


def test_tool_call_recovery_success_separate_from_task():
    out = evaluate_tool_call_recovery(
        native_tool_call=True,
        native_tool_names=["read_file"],
        expected_tool="read_file",
        tool_execution_ok=True,
        timeout=False,
        execution_result="success",
    )
    assert out["tool_call_recovery"] == "SUCCESS"
    assert out["task_result"] == "UNKNOWN"


def test_tool_call_recovery_partial_on_timeout():
    out = evaluate_tool_call_recovery(
        native_tool_call=True,
        native_tool_names=["read_file"],
        expected_tool="read_file",
        tool_execution_ok=None,
        timeout=True,
        execution_result="failure",
    )
    assert out["tool_call_recovery"] == "PARTIAL"
    assert out["execution_result"] == "partial"


def test_needs_recovery_false_on_success():
    execution = {
        "native_tool_names": ["read_file"],
        "tool_call_recovery": "SUCCESS",
        "failure_classification": {"failure_type": "NONE"},
    }
    assert _needs_recovery(execution, expected_tool="read_file") is False


def test_harness_primary_success_no_recovery(recovery_paths, monkeypatch):
    monkeypatch.setenv("AI_AGENT_CONTEXT_MONITOR", "0")

    def fake_chat(**kwargs):
        return _Resp(_Msg(tool_calls=[_Tc("read_file")]))

    search_payload = {"match_count": 50, "matches": [], "truncated": True}
    with patch(
        "tools.system.context_monitor.recovery_harness.execute_registry_tool",
        return_value=SimpleNamespace(ok=True, result={"ok": True, "path": "x"}),
    ), patch(
        "tools.system.context_monitor.recovery_harness.snapshot_gpu",
        return_value={"vram_total_mib": 12288, "vram_free_mib": 800},
    ):
        attempt = run_harness_attempt(
            scenario_id="test_ok",
            search_payload=search_payload,
            approve_recovery=True,
            chat_fn=fake_chat,
        )
    assert attempt["recovery_outcome"] == "not_needed"
    assert attempt["primary"]["tool_call_recovery"] == "SUCCESS"


def test_harness_failure_then_recovery(recovery_paths, monkeypatch):
    monkeypatch.setenv("AI_AGENT_CONTEXT_MONITOR", "0")
    calls: list[int | None] = []

    def fake_chat(**kwargs):
        ctx = kwargs.get("runtime_context")
        calls.append(ctx)
        if ctx == 32768:
            return _Resp(_Msg(tool_calls=[_Tc("read_file")], thinking="call read_file"))
        return _Resp(_Msg(thinking="need read_file but no tool call"))

    search_payload = {"match_count": 50, "matches": [], "truncated": True}
    with patch(
        "tools.system.context_monitor.recovery_harness.execute_registry_tool",
        return_value=SimpleNamespace(ok=True, result={"ok": True}),
    ), patch(
        "tools.system.context_monitor.recovery_harness.snapshot_gpu",
        return_value={"vram_total_mib": 12288, "vram_free_mib": 800},
    ), patch(
        "tools.system.context_monitor.recovery_harness.get_configured_context",
        return_value=16384,
    ):
        attempt = run_harness_attempt(
            scenario_id="test_recover",
            search_payload=search_payload,
            primary_context=16384,
            approve_recovery=True,
            chat_fn=fake_chat,
        )

    assert attempt["recovery_outcome"] == "success"
    assert calls == [16384, 32768]
    assert attempt["recovery"]["tool_call_recovery"] == "SUCCESS"
    assert recovery_paths["results"].exists()


def test_agent_opt_in_approval_required(monkeypatch):
    monkeypatch.setenv("AI_AGENT_RECOVERY_OPT_IN", "1")
    assert recovery_opt_in_enabled() is True
    resp = _Resp(_Msg(thinking="I should read_file", content=""))
    with patch(
        "tools.system.context_monitor.agent_recovery_bridge.snapshot_gpu",
        return_value={"vram_total_mib": 12288, "vram_free_mib": 500},
    ), patch(
        "tools.system.context_monitor.agent_recovery_bridge.get_configured_context",
        return_value=16384,
    ):
        hit = evaluate_llm_round_for_recovery(resp, expected_tool="read_file", task_type="search_read")
    assert hit is not None
    assert hit["status"] == "AGENT_EVALUATION_REQUIRED"
    assert "Recovery 候補" in hit["approval_summary"]
    assert hit.get("agent_brief") is not None


def test_format_approval_summary():
    text = format_recovery_approval_summary(
        {
            "failure_type": "TOOL_CALL_NOT_GENERATED",
            "current_context": 16384,
            "configured_context": 16384,
            "candidate_strategy": "increase_context",
            "candidate_context": 32768,
            "confidence": "LOW",
            "reason": ["Native Tool Call が生成されなかった"],
            "execution_allowed": True,
            "automatic_execution_allowed": False,
        }
    )
    assert "16384" in text
    assert "32768" in text


@pytest.fixture
def recovery_paths(tmp_path, monkeypatch):
    decisions = tmp_path / "recovery_decisions.jsonl"
    results = tmp_path / "recovery_results.jsonl"
    experience = tmp_path / "recovery_experience.jsonl"
    policy = tmp_path / "recovery_policy.json"
    policy.write_text(
        json.dumps(
            {
                "automatic_recovery_enabled": False,
                "max_recovery_attempts": 1,
                "max_context_changes_per_session": 1,
                "context_ladder": [4096, 8192, 16384, 32768],
                "model_context_limits": {"qwen3:14b": 40960},
                "pc_context_limit": 32768,
                "increase_context_failure_types": [
                    "TOOL_CALL_NOT_GENERATED",
                    "TIMEOUT",
                    "CONTEXT_LIMIT",
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
        "tools.system.context_monitor.recovery_helpers.RECOVERY_EXPERIENCE_JSONL",
        experience,
    )
    return {"decisions": decisions, "results": results, "experience": experience, "policy": policy}
