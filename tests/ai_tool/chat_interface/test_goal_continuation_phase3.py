"""Phase 3: connect continuation Router winner to existing capabilities."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai_tool.agent_integration.gpu_process_e2e import ollama_available
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.gap_resolution_router import CapabilityId, CONTINUATION_WINNERS
from ai_tool.chat_interface.goal_continuation_resume import (
    apply_continuation_winner,
    restore_orchestrator_from_goal_continuation,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import FailureRecord
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _prepare_paths_only,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_execution_end_invariants import _run_agent_completed
from tests.ai_tool.chat_interface.test_gap_resolution_phase1 import _gap_event
from tests.ai_tool.chat_interface.test_goal_continuation_phase2 import (
    _continuation_event,
    _run_fact_gap_with_continuation,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE_REL_DIR = "local_state/_goal_continuation_live_probe"
PROBE_DIR = REPO_ROOT / Path(PROBE_REL_DIR)
PART_A_PATH = PROBE_DIR / "part_a.txt"
PART_B_REL = f"{PROBE_REL_DIR}/part_b.txt"
PART_A_REL = f"{PROBE_REL_DIR}/part_a.txt"
LIVE_CONTINUATION_REQUEST = (
    "Goal continuation live probe。"
    f"{PART_B_REL} の先頭1行だけを read_file で確認し、"
    "観測結果を報告してください。他のファイルは読まないでください。"
)


@pytest.fixture
def goal_continuation_live_probe_files():
    """One readable file and one intentionally missing file under the repo."""
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    PART_A_PATH.write_text("GC-LIVE-PART-A-LINE1\n", encoding="utf-8")
    if (PROBE_DIR / "part_b.txt").exists():
        (PROBE_DIR / "part_b.txt").unlink()
    yield
    if PART_A_PATH.exists():
        PART_A_PATH.unlink()
    if PROBE_DIR.exists() and not any(PROBE_DIR.iterdir()):
        PROBE_DIR.rmdir()


def _probe_tool_execute(name, arguments, **_kwargs):
    path = str(arguments.get("path") or "").replace("\\", "/")
    if name == "list_files" and path.rstrip("/").endswith(PROBE_REL_DIR):
        return {
            "ok": True,
            "status": "success",
            "error": None,
            "warnings": [],
            "base": path,
            "truncated": False,
            "has_more": False,
            "entries": [
                {
                    "name": "part_a.txt",
                    "path": PART_A_REL,
                    "type": "file",
                }
            ],
        }
    if path.endswith("part_a.txt"):
        return {
            "ok": True,
            "status": "success",
            "path": path,
            "content": "GC-LIVE-PART-A-LINE1\n",
            "error": None,
        }
    return {
        "ok": False,
        "status": "failure",
        "path": path,
        "error": {"code": "path_not_found", "message": "missing probe file"},
    }


def _evidence_count(result: dict) -> int:
    runtime = result.get("task_runtime") or {}
    evidence = runtime.get("evidence") or []
    if isinstance(evidence, dict):
        return len(evidence)
    return len(list(evidence))


def _capability_event(result: dict) -> dict | None:
    for item in result.get("events") or []:
        if item.get("type") == "goal_continuation_capability_applied":
            return item
    return None


def _stagnation_packet(
    orchestrator: ChatTaskOrchestrator,
    *,
    mission_id: str = "m-recovery",
    winner: str = CapabilityId.RECOVERY.value,
) -> dict:
    args = {"path": "a.txt"}
    for index in range(2):
        orchestrator.runtime.failures.append(
            FailureRecord(
                failure_id=f"f{index + 1}",
                task_id="T1",
                action_id=f"a{index + 1}",
                tool_name="read_file",
                arguments=args,
                failure_code="MISSING",
                evidence_gain=False,
                created_at="now",
            )
        )
        orchestrator.runtime.tasks["T1"].failure_history.append(f"f{index + 1}")
    return {
        "kind": "goal_continuation_v0",
        "mission_id": mission_id,
        "original_request": orchestrator.request,
        "winner": winner,
        "gap_kind": "fact_gap",
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "failure_tail": [
            {
                "failure_id": "f-tail-1",
                "task_id": "T1",
                "action_id": "a-tail-1",
                "tool_name": "read_file",
                "arguments": args,
                "failure_code": "MISSING",
                "evidence_gain": False,
                "created_at": "now",
            },
            {
                "failure_id": "f-tail-2",
                "task_id": "T1",
                "action_id": "a-tail-2",
                "tool_name": "read_file",
                "arguments": args,
                "failure_code": "MISSING",
                "evidence_gain": False,
                "created_at": "now",
            },
        ],
    }


def test_tool_evidence_winner_applies_open_task_and_matches_event(monkeypatch, tmp_path):
    first, session = _run_fact_gap_with_continuation(monkeypatch, tmp_path)
    winner = str(first.get("goal_continuation_resume", {}).get("winner") or "")
    assert winner == CapabilityId.TOOL_EVIDENCE.value

    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {
            "ok": True,
            "status": "success",
            "content": "updated evidence",
        },
    )
    second = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
            _response("evidence updated"),
        ),
        model="fake",
    )
    applied = _capability_event(second)
    assert applied is not None
    assert applied.get("router_winner") == CapabilityId.TOOL_EVIDENCE.value
    assert applied.get("capability_applied") == CapabilityId.TOOL_EVIDENCE.value
    assert applied.get("open_task_id")


def test_recovery_winner_applies_recovery_hint_and_replan(monkeypatch, tmp_path):
    orchestrator = ChatTaskOrchestrator("recovery", "repository audit plan")
    orchestrator.initialize()
    orchestrator.mission_id = "m-recovery"
    packet = _stagnation_packet(orchestrator)
    restored = restore_orchestrator_from_goal_continuation("corr-r", packet)
    capability = apply_continuation_winner(restored, packet)
    assert capability.capability_applied == CapabilityId.RECOVERY.value
    assert capability.recovery_hint_applied is True
    assert capability.recovery_hint
    assert capability.replan_created is True
    assert capability.replan_task_id
    assert restored.current_task_id == capability.replan_task_id

    _prepare(monkeypatch, tmp_path)
    session = empty_session("phase3-recovery")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = packet
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {
            "ok": True,
            "status": "success",
            "content": "list fallback",
        },
    )
    result = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("alternative observation complete"),
        ),
        model="fake",
    )
    applied = _capability_event(result)
    assert applied is not None
    assert applied.get("router_winner") == CapabilityId.RECOVERY.value
    assert applied.get("capability_applied") == CapabilityId.RECOVERY.value
    assert applied.get("recovery_hint_applied") is True
    assert applied.get("replan_created") is True


def test_replan_winner_creates_replan_task_and_advances(monkeypatch, tmp_path):
    orchestrator = ChatTaskOrchestrator("replan", "repository audit plan")
    orchestrator.initialize()
    packet = {
        "kind": "goal_continuation_v0",
        "mission_id": "m-replan",
        "original_request": orchestrator.request,
        "winner": CapabilityId.REPLAN.value,
        "gap_kind": "fact_gap",
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "failure_tail": [],
    }
    restored = restore_orchestrator_from_goal_continuation("corr-p", packet)
    capability = apply_continuation_winner(restored, packet)
    assert capability.capability_applied == CapabilityId.REPLAN.value
    assert capability.replan_created is True
    assert restored.runtime.replans
    assert restored.current_task_id == capability.replan_task_id

    _prepare(monkeypatch, tmp_path)
    session = empty_session("phase3-replan")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = packet
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {
            "ok": True,
            "status": "success",
            "content": "replan evidence",
        },
    )
    result = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("replan path observed"),
        ),
        model="fake",
    )
    applied = _capability_event(result)
    assert applied is not None
    assert applied.get("router_winner") == CapabilityId.REPLAN.value
    assert applied.get("capability_applied") == CapabilityId.REPLAN.value
    assert applied.get("replan_task_id")


def test_human_winner_is_not_auto_executed():
    orchestrator = ChatTaskOrchestrator("human", "request")
    orchestrator.initialize()
    packet = {
        "kind": "goal_continuation_v0",
        "mission_id": "m-human",
        "original_request": "request",
        "winner": CapabilityId.GOAL_COMPLETION_HUMAN.value,
        "gap_kind": "spec_meaning_gap",
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "failure_tail": [],
    }
    capability = apply_continuation_winner(orchestrator, packet)
    assert capability.skipped is True
    assert capability.capability_applied == "none"


def test_missing_file_probe_request_produces_continuation_deterministic(
    goal_continuation_live_probe_files,
    monkeypatch,
    tmp_path,
):
    """Same probe request as production live proof, with fake LLM/tooling."""
    _prepare_paths_only(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _probe_tool_execute,
    )
    session = empty_session("phase3-probe-det")
    first = run_chat_turn(
        session,
        LIVE_CONTINUATION_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": PART_B_REL})]),
            _response("part_b.txt は存在しませんでした。"),
        ),
        model="fake",
    )
    resume = first.get("goal_continuation_resume")
    assert resume is not None
    routed = _gap_event(first)
    assert routed is not None
    assert routed.get("gap_kind") == "fact_gap"
    assert routed.get("winner") in CONTINUATION_WINNERS
    assert first.get("answer_gate", {}).get("verified") is False
    assert (first.get("requirement_decomposition") or {}).get("source") == "not_enumerated"

    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")
    execution_n = str(first.get("mission_memory", {}).get("execution_id") or "")
    prior_evidence = _evidence_count(first)
    winner = str(resume.get("winner") or "")

    second = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": PART_B_REL})]),
            _response(calls=[_tool_call("read_file", {"path": PART_A_REL})]),
            _response("part_b は未観測のままです。"),
            _response("継続 Execution で part_b の観測を再試行しました。"),
        ),
        model="fake",
    )
    applied = _capability_event(second)
    assert applied is not None
    assert applied.get("router_winner") == winner
    assert applied.get("capability_applied") == winner
    assert _continuation_event(second) is not None
    assert str(second.get("mission_memory", {}).get("mission_id") or "") == mission_id
    assert str(second.get("mission_memory", {}).get("execution_id") or "") != execution_n
    assert (
        _evidence_count(second) >= prior_evidence
        or _gap_event(second) is not None
        or second.get("goal_continuation_resume")
    )


def test_live_goal_continuation_production_path(
    goal_continuation_live_probe_files,
    monkeypatch,
    tmp_path,
):
    """Production live proof: missing-file probe leaves FACT_GAP after Execution N."""
    live, err = ollama_available()
    if not live:
        pytest.skip(f"ollama unavailable: {err}")

    _prepare_paths_only(monkeypatch, tmp_path)
    session = empty_session("phase3-live-production")
    first = run_chat_turn(session, LIVE_CONTINUATION_REQUEST, model=None)

    resume = first.get("goal_continuation_resume")
    assert resume is not None, (
        "expected goal_continuation_resume after dual-file probe; "
        f"answer_gate={first.get('answer_gate')}; "
        f"gap_resolution={first.get('gap_resolution')}; "
        f"requirement={first.get('requirement_decomposition')}"
    )
    routed = _gap_event(first)
    assert routed is not None
    assert routed.get("gap_kind") == "fact_gap"
    winner = str(resume.get("winner") or "")
    assert winner in CONTINUATION_WINNERS

    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")
    execution_n = str(first.get("mission_memory", {}).get("execution_id") or "")
    assert mission_id and execution_n
    prior_evidence = _evidence_count(first)

    second = run_chat_turn(session, "継続", model=None)
    restored = _continuation_event(second)
    applied = _capability_event(second)
    assert restored is not None
    assert applied is not None
    assert applied.get("router_winner") == winner
    assert applied.get("capability_applied") == winner
    assert _continuation_event(second) is not None
    assert str(second.get("mission_memory", {}).get("mission_id") or "") == mission_id
    assert str(second.get("mission_memory", {}).get("execution_id") or "") != execution_n
    assert (
        _evidence_count(second) >= prior_evidence
        or _gap_event(second) is not None
        or second.get("goal_continuation_resume")
    )
