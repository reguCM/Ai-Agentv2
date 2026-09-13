"""Golden Path E2E: Phase 0-5 cross-connection in one mission."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.gap_resolution_router import CapabilityId, CONTINUATION_WINNERS
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare_paths_only,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_goal_continuation_phase2 import _continuation_event
from tests.ai_tool.chat_interface.test_goal_continuation_phase3 import (
    _capability_event,
    _evidence_count,
)
from tests.ai_tool.chat_interface.test_gap_resolution_phase1 import _gap_event

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE_REL_DIR = "local_state/_golden_path_e2e_probe"
PROBE_DIR = REPO_ROOT / Path(PROBE_REL_DIR)
PROBE_REL = f"{PROBE_REL_DIR}/probe.txt"
PROBE_LINE = "PROBE-GOLDEN-LINE1"

GOLDEN_PATH_REQUEST = (
    f"{PROBE_REL} の先頭1行を read_file で確認して報告する。\n"
    "報告形式は次の2通りがともに妥当ですが、どちらを採用するか未決です。\n"
    "A: 原文をそのまま報告する\n"
    "B: VALUE=先頭1行 の形式で報告する\n"
    "事実確認後、既存仕様から一意に決められない場合のみ確認する。"
)


def _event_types(result: dict) -> list[str]:
    return [str(item.get("type") or "") for item in result.get("events") or []]


def _boundary_grill_event(result: dict) -> dict | None:
    for item in result.get("events") or []:
        if item.get("type") == "boundary_grill_launched":
            return item
    return None


def _boundary_answer_event(result: dict) -> dict | None:
    for item in result.get("events") or []:
        if item.get("type") == "boundary_grill_answer_applied":
            return item
    return None


def _reroute_event(result: dict) -> dict | None:
    for item in result.get("events") or []:
        if item.get("type") == "boundary_grill_reroute":
            return item
    return None


@pytest.fixture
def golden_path_probe_files():
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    probe_file = PROBE_DIR / "probe.txt"
    probe_file.write_text(f"{PROBE_LINE}\n", encoding="utf-8")
    yield
    if probe_file.exists():
        probe_file.unlink()
    if PROBE_DIR.exists() and not any(PROBE_DIR.iterdir()):
        PROBE_DIR.rmdir()


@pytest.fixture
def boundary_grill_runtime_connected_registry(monkeypatch):
    from ai_tool.skill_applicability import load_registry

    registry = copy.deepcopy(load_registry())
    for row in registry.get("skills") or []:
        if str(row.get("id") or "") == "grill-me":
            row["runtime_connected"] = True
    monkeypatch.setattr("ai_tool.skill_applicability.load_registry", lambda: registry)
    monkeypatch.setattr(
        "ai_tool.chat_interface.boundary_grill.load_registry",
        lambda: registry,
    )
    return registry


def test_golden_path_fact_gap_to_boundary_grill_to_resolution(
    golden_path_probe_files,
    boundary_grill_runtime_connected_registry,
    monkeypatch,
    tmp_path,
):
    """FACT_GAP continuation → SPEC_MEANING_GAP Boundary Grill → Human resolution."""
    tool_state = {"allow_probe_read": False}

    def golden_tool_execute(name, arguments, **_kwargs):
        path = str(arguments.get("path") or "").replace("\\", "/")
        if name != "read_file":
            raise AssertionError(name)
        if path.endswith("probe.txt"):
            if not tool_state["allow_probe_read"]:
                return {
                    "ok": False,
                    "status": "failure",
                    "path": path,
                    "error": {"code": "path_not_found", "message": "temporary probe read failure"},
                }
            return {
                "ok": True,
                "status": "success",
                "path": path,
                "content": f"{PROBE_LINE}\n",
                "error": None,
            }
        raise AssertionError(f"unexpected path: {path}")

    _prepare_paths_only(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        golden_tool_execute,
    )
    session = empty_session("golden-path-phase0-5")

    # --- Execution N: transient tool failure → FACT_GAP continuation ---
    first = run_chat_turn(
        session,
        GOLDEN_PATH_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": PROBE_REL})]),
            _response("probe.txt の読取に一時的に失敗しました。"),
        ),
        model="fake",
    )
    first_events = _event_types(first)
    routed_n = _gap_event(first)
    resume_n = first.get("goal_continuation_resume")

    assert routed_n is not None
    assert routed_n.get("gap_kind") == "fact_gap"
    assert routed_n.get("winner") in CONTINUATION_WINNERS
    assert resume_n is not None
    assert first.get("awaiting_boundary_grill") is False
    assert _boundary_grill_event(first) is None
    assert "boundary_grill_launched" not in first_events
    assert first.get("awaiting_human_grill") is False
    assert first.get("awaiting_goal_completion_human") is False
    assert session.get("awaiting_goal_continuation") is True

    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")
    execution_n = str(first.get("mission_memory", {}).get("execution_id") or "")
    winner_n = str(resume_n.get("winner") or "")
    evidence_n = _evidence_count(first)
    assert mission_id and execution_n and winner_n

    # --- Execution N+1: continuation restore → observation success → Boundary Grill ---
    tool_state["allow_probe_read"] = True
    second = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": PROBE_REL})]),
            _response(f"{PROBE_LINE} を観測しました。報告形式は未決のままです。"),
        ),
        model="fake",
    )
    second_events = _event_types(second)
    routed_n1 = _gap_event(second)
    restored = _continuation_event(second)
    applied = _capability_event(second)

    assert restored is not None
    assert restored.get("mission_id") == mission_id
    assert restored.get("prior_execution_id") == execution_n
    assert applied is not None
    assert applied.get("router_winner") == winner_n
    assert str(second.get("mission_memory", {}).get("mission_id") or "") == mission_id
    execution_n1 = str(second.get("mission_memory", {}).get("execution_id") or "")
    assert execution_n1 and execution_n1 != execution_n
    assert _evidence_count(second) >= evidence_n
    assert routed_n1 is not None
    assert routed_n1.get("gap_kind") == "spec_meaning_gap"
    assert routed_n1.get("winner") == CapabilityId.SKILL_GRILL_ME.value
    assert second.get("awaiting_boundary_grill") is True
    assert second.get("goal_continuation_resume") is None
    assert session.get("awaiting_goal_continuation") is False
    assert session.get("awaiting_boundary_grill") is True
    assert "goal_continuation_restored" in second_events
    assert "boundary_grill_launched" in second_events
    assert "boundary_grill" in second_events
    assert second.get("awaiting_human_grill") is False
    assert second.get("awaiting_goal_completion_human") is False

    # --- Human answer: save decision → Router re-eval → gap resolved ---
    third = run_chat_turn(
        session,
        "A: 原文をそのまま報告する",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    third_events = _event_types(third)
    answer_evt = _boundary_answer_event(third)
    reroute_evt = _reroute_event(third)
    routed_n2 = _gap_event(third)

    assert answer_evt is not None
    assert answer_evt.get("applied") is True
    assert reroute_evt is not None
    assert reroute_evt.get("gap_resolved") is True
    assert reroute_evt.get("winner") != CapabilityId.SKILL_GRILL_ME.value
    assert routed_n2 is not None
    assert routed_n2.get("gap_resolved") is True
    assert routed_n2.get("winner") != CapabilityId.SKILL_GRILL_ME.value
    assert third.get("awaiting_boundary_grill") is not True
    assert third.get("awaiting_goal_continuation") is not True
    assert session.get("awaiting_boundary_grill") is not True
    assert session.get("boundary_grill_state") is None
    assert session.get("awaiting_goal_continuation") is not True
    assert session.get("goal_continuation_resume") is None
    assert third.get("awaiting_human_grill") is not True
    assert third.get("awaiting_goal_completion_human") is not True
    assert "boundary_grill_answer_proposed" in third_events
    assert "boundary_grill_answer_applied" in third_events
    assert "boundary_grill_reroute" in third_events
    assert "boundary_grill_launched" not in third_events
    assert str(third.get("mission_memory", {}).get("mission_id") or "") == mission_id
    execution_n2 = str(third.get("mission_memory", {}).get("execution_id") or "")
    assert execution_n2 and execution_n2 != execution_n1

    clarifications = []
    runtime = third.get("task_runtime") or {}
    for row in runtime.get("confirmed_clarifications") or []:
        if isinstance(row, dict) and row.get("source") == "boundary_grill":
            clarifications.append(row)
    assert clarifications
    assert any("原文" in str(row.get("text") or "") for row in clarifications)
