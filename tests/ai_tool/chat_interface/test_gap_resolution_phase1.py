"""Phase 1: gap resolution observation at execution end and session resume pointers."""
from __future__ import annotations

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.gap_resolution_router import CapabilityId
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_execution_end_invariants import (
    README_E2E_REQUEST,
    _listing_execute,
    _run_agent_completed,
    _run_goal_completion_judged,
)
def _gap_event(result: dict) -> dict | None:
    for item in result.get("events") or []:
        if item.get("type") == "gap_resolution_routed":
            return item
    return None


def test_agent_completed_records_gap_resolution_and_continuation_resume(
    monkeypatch, tmp_path
):
    result, session = _run_agent_completed(monkeypatch, tmp_path)
    routed = _gap_event(result)
    assert routed is not None
    assert routed.get("gap_kind") == "fact_gap"
    assert routed.get("winner") in {
        CapabilityId.TOOL_EVIDENCE.value,
        CapabilityId.RECOVERY.value,
        CapabilityId.REPLAN.value,
    }
    assert routed.get("candidates")
    assert routed.get("continuation_resume_persisted") is True
    assert routed.get("human_priority_blocked") is False
    resume = result.get("goal_continuation_resume")
    assert isinstance(resume, dict)
    assert resume.get("not_mission_canonical") is True
    assert resume.get("kind") == "goal_continuation_v0"
    assert resume.get("winner") == routed.get("winner")
    assert session.get("awaiting_goal_continuation") is True
    assert session.get("goal_continuation_resume") == resume


def test_goal_completion_human_records_gap_resolution_without_continuation_resume(
    monkeypatch, tmp_path
):
    session = empty_session("phase1-gc-human")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = {
        "kind": "goal_continuation_v0",
        "provisional": True,
        "not_mission_canonical": True,
        "winner": "replan",
    }
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    result = run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    routed = _gap_event(result)
    assert routed is not None
    assert routed.get("gap_kind") == "spec_meaning_gap"
    assert routed.get("winner") == CapabilityId.GOAL_COMPLETION_HUMAN.value
    assert routed.get("continuation_resume_persisted") is False
    assert routed.get("human_priority_blocked") is True
    assert result.get("goal_continuation_resume") is None
    assert session.get("awaiting_goal_continuation") is False
    assert session.get("goal_continuation_resume") is None
    assert result.get("awaiting_goal_completion_human") is True


def test_human_grill_clears_stale_goal_continuation_resume(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    session = empty_session("phase1-grill-clear")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = {
        "kind": "goal_continuation_v0",
        "winner": "tool_evidence",
    }
    request = "gridを検索して、その内容を要約してほしい。"

    def execute(name, arguments, **_kwargs):
        assert name == "search_files"
        return {
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter(
        [
            _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
            _response("候補が複数あります。"),
            _response("候補が複数あります。"),
        ]
    )
    result = run_chat_turn(
        session,
        request,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
    )
    routed = _gap_event(result)
    assert routed is not None
    assert routed.get("human_priority_blocked") is True
    assert routed.get("continuation_resume_persisted") is False
    assert session.get("awaiting_goal_continuation") is False
    assert session.get("goal_continuation_resume") is None


def test_human_priority_blocks_continuation_for_approval_stop_reason():
    from ai_tool.chat_interface.gap_resolution_router import (
        human_priority_blocks_continuation,
    )

    assert human_priority_blocks_continuation(stop_reason="APPROVAL_REQUIRED") is True
    assert human_priority_blocks_continuation(
        awaiting_human_review=True,
    ) is True


def test_partial_explicit_two_condition_fact_gap_keeps_continuation(
    monkeypatch,
    tmp_path,
):
    from tests.ai_tool.chat_interface.test_goal_continuation_phase3 import (
        PART_A_PATH,
        PART_A_REL,
        PART_B_REL,
        PROBE_DIR,
        _probe_tool_execute,
    )
    from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import _prepare_paths_only

    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    PART_A_PATH.write_text("GC-LIVE-PART-A-LINE1\n", encoding="utf-8")
    request = (
        "partial explicit probe。次を完了してください。\n"
        f"1. {PART_A_REL} の先頭1行を read_file で読み取り、内容を報告する\n"
        f"2. {PART_B_REL} の先頭1行を read_file で読み取り、内容を報告する"
    )
    _prepare_paths_only(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _probe_tool_execute,
    )
    session = empty_session("phase1-partial-explicit")
    result = run_chat_turn(
        session,
        request,
        chat_fn=_chat_sequence(
            _response(
                calls=[
                    _tool_call("read_file", {"path": PART_A_REL}),
                    _tool_call("read_file", {"path": PART_B_REL}),
                ]
            ),
            _response("part_a のみ確認できました。"),
        ),
        model="fake",
    )
    routed = _gap_event(result)
    assert routed is not None
    assert routed.get("gap_kind") == "fact_gap"
    assert routed.get("gap_resolved") is False
    assert routed.get("continuation_resume_persisted") is True
    assert result.get("goal_continuation_resume") is not None
    assert (result.get("requirement_decomposition") or {}).get("source") == "explicit"
    assert result.get("answer_gate", {}).get("verified") is False


def test_goal_completion_judged_clears_stale_goal_continuation_resume(
    monkeypatch, tmp_path
):
    session = empty_session("phase1-gc-judged-clear")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = {
        "kind": "goal_continuation_v0",
        "winner": "tool_evidence",
    }
    result, session = _run_goal_completion_judged(monkeypatch, tmp_path)
    assert session.get("awaiting_goal_continuation") is False
    assert session.get("goal_continuation_resume") is None
    assert result.get("goal_completion_judgment")
