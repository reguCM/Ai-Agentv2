"""P2a — development policy final answer boundary on run_chat_turn."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_tool.chat_interface.agent_turn import (
    apply_development_policy_final_answer_boundary,
    run_chat_turn,
)
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.policy.enforce import apply_final_answer_policy


def test_t1_normal_answer_unchanged():
    result = {"answer": "GPU 温度は Tool 結果の 62 です。", "route": "chat"}
    apply_development_policy_final_answer_boundary(result)
    assert result["answer"] == "GPU 温度は Tool 結果の 62 です。"
    assert result["policy_final_enforce"]["applied"] is False


def test_t2_completion_claim_notice():
    result = {"answer": "実装完了しました。すべて仕様完成です。"}
    apply_development_policy_final_answer_boundary(result)
    assert result["policy_final_enforce"]["applied"] is True
    assert "DEVELOPMENT_POLICY" in result["answer"]
    assert "may_claim_specification_complete=false" in result["answer"]


def test_t3_policy_does_not_flip_turn_error_flags():
    normal = {"answer": "通常の回答です。", "is_error": False, "ok": True}
    apply_development_policy_final_answer_boundary(normal)
    assert normal.get("is_error") is False
    assert normal.get("ok") is True

    claim = {"answer": "実装完了しました。すべて仕様完成です。", "is_error": False}
    apply_development_policy_final_answer_boundary(claim)
    assert claim.get("is_error") is False
    assert claim["policy_final_enforce"]["applied"] is True


def test_t4_spec_proposal_policy_eval_preserved(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    session = empty_session("p2a-spec")
    record = {
        "ok": True,
        "proposal_id": "p1",
        "request_id": "r1",
        "version": 1,
        "parse_status": "ok",
        "answer": "仕様候補です。",
        "events": [],
        "human_confirmation_required": [],
        "policy_eval": {
            "specification_status": "PARTIAL",
            "may_proceed_implementation": True,
        },
    }

    with patch(
        "ai_tool.chat_interface.agent_turn._spec_proposal_turn",
        return_value={
            "route": "development",
            "answer": record["answer"],
            "events": [],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "spec_proposal": record,
            "proposal": {"proposal_id": "p1", "request_id": "r1"},
        },
    ):
        with patch("ai_tool.chat_interface.agent_turn.classify_request", return_value="development"):
            result = run_chat_turn(session, "dev spec", model="fake")

    assert result["spec_proposal"]["policy_eval"]["specification_status"] == "PARTIAL"
    assert "policy_final_enforce" in result


def test_t5_help_route_passes_boundary():
    session = empty_session("p2a-help")
    result = run_chat_turn(session, "/h", model="fake")
    assert result.get("route") == "help"
    assert "policy_final_enforce" in result


def test_t6_apply_final_answer_called_exactly_once(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    session = empty_session("p2a-once")
    with patch(
        "ai_tool.policy.enforce.apply_final_answer_policy",
        wraps=apply_final_answer_policy,
    ) as mocked:
        with patch("ai_tool.chat_interface.agent_turn.classify_request", return_value="chat"):
            with patch(
                "ai_tool.chat_interface.agent_turn.is_agent_task",
                return_value=False,
            ):
                with patch(
                    "ai_tool.chat_interface.agent_turn.ollama_chat",
                    return_value={"message": {"content": "ok"}},
                ):
                    run_chat_turn(session, "hi", model="fake")
    assert mocked.call_count == 1


def test_t8_policy_load_failure_blocks_complete_claim(monkeypatch):
    result = {"answer": "実装完了しました。すべて仕様完成です。"}

    def _boom(*_a, **_k):
        raise RuntimeError("policy_eval_failed")

    with patch(
        "ai_tool.policy.enforce.apply_final_answer_policy",
        side_effect=_boom,
    ):
        apply_development_policy_final_answer_boundary(result)

    assert result["policy_final_enforce"].get("completion_claim_verification_failed") is True
    assert "completion_claim_verification_failed" in result["answer"]
    assert "NOT_OBSERVED" in result["answer"]
