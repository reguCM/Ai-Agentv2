"""Goal Completion Gate v0: undetermined Goal meaning asks Human; System judges.

README.md is the first connected resume case, not a Mission-state picker.
Other Human answers stop as unsupported.
"""
from __future__ import annotations

from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.goal_completion_gate import (
    GOAL_COMPLETION_HUMAN_REASON,
    GOAL_MEANING_ABSENCE_COMPLETES,
    GOAL_MEANING_CONTENT_REQUIRED,
    GOAL_MEANING_OPTIONS,
    NAMED_PATH_OMITTED_CASE,
    existing_specs_uniquely_determine_goal_completion,
    interpret_goal_completion_answer,
    match_omitted_path_goal_meaning,
    needs_goal_completion_human,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.mission_memory.store import MissionMemoryStore
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_h4_selection_core import _observe_root_listing

REGISTRY = load_registry_tools()
README_E2E_REQUEST = (
    "README.md がワークスペースにあるか確認して、ファイルの先頭1行を報告してください。"
)
ROOT_WITHOUT_NAMED_FILE = [{"name": "AGENTS.md", "path": "AGENTS.md", "type": "file"}]
ABSENCE_COMPLETES_REPLY = "存在しないことを確認できれば完了です"


def _orchestrator(request: str) -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("gcg", request)
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    return orchestrator


def _listing_execute():
    listing = {
        "ok": True,
        "status": "success",
        "error": None,
        "warnings": [],
        "base": ".",
        "truncated": False,
        "has_more": False,
        "entries": ROOT_WITHOUT_NAMED_FILE,
    }

    def execute(name, arguments, **_kwargs):
        if name == "list_files":
            return listing
        return {
            "ok": False,
            "status": "failure",
            "error": {"code": "path_not_found", "message": "missing", "path": arguments},
            "warnings": [],
        }

    return execute


def test_existing_specs_do_not_uniquely_determine_goal_completion():
    orchestrator = _orchestrator(README_E2E_REQUEST)
    assert existing_specs_uniquely_determine_goal_completion(orchestrator) is False


def test_readme_case_asks_goal_meaning_not_mission_states():
    orchestrator = _orchestrator(README_E2E_REQUEST)
    _observe_root_listing(orchestrator, ROOT_WITHOUT_NAMED_FILE)
    assert orchestrator.needs_goal_completion_human() is True
    answer, gate = orchestrator.gate_answer("存在しません")
    packet = gate["goal_completion_human"]
    assert gate["reason"] == "awaiting_goal_completion_human"
    assert packet["reason"] == GOAL_COMPLETION_HUMAN_REASON
    assert packet["case"] == NAMED_PATH_OMITTED_CASE
    assert [item["id"] for item in packet["goal_meaning_options"]] == [
        item["id"] for item in GOAL_MEANING_OPTIONS
    ]
    assert "options" not in packet
    assert "achieved" not in answer
    assert "ended_incomplete" not in answer
    assert "paused" not in answer
    assert "needs_continuation" not in answer
    assert "この Goal では何をもって完了としますか" in answer
    orchestrator.finish(answer)
    assert orchestrator.runtime.tasks["T1"].status == "complete"
    assert orchestrator.runtime.tasks["T2"].status == "complete"
    assert orchestrator.runtime.goals["G1"].status == "complete"
    assert orchestrator.needs_goal_completion_human() is True


def test_same_path_fires_for_non_readme_named_file():
    orchestrator = _orchestrator("NOTES.md の先頭1行を報告してください。")
    _observe_root_listing(orchestrator, ROOT_WITHOUT_NAMED_FILE)
    omitted = [item.casefold() for item in orchestrator.omitted_request_named_paths()]
    assert "notes.md" in omitted
    assert needs_goal_completion_human(orchestrator) is True


def test_present_named_file_does_not_ask_goal_completion():
    orchestrator = _orchestrator("README.md の先頭1行を報告して")
    _observe_root_listing(
        orchestrator,
        [{"name": "README.md", "path": "README.md", "type": "file"}],
    )
    assert orchestrator.needs_goal_completion_human() is False


def test_listing_without_named_path_does_not_ask_goal_completion():
    orchestrator = _orchestrator("repository audit")
    _observe_root_listing(orchestrator, ROOT_WITHOUT_NAMED_FILE)
    assert orchestrator.needs_goal_completion_human() is False


def test_connected_answers_map_to_system_mission_state():
    absence = interpret_goal_completion_answer(
        ABSENCE_COMPLETES_REPLY, case=NAMED_PATH_OMITTED_CASE
    )
    assert absence["status"] == "judged"
    assert absence["execution_end_state"] == "achieved"
    assert absence["goal_achievement_result"] == "achieved"
    assert match_omitted_path_goal_meaning("1") == GOAL_MEANING_ABSENCE_COMPLETES
    content = interpret_goal_completion_answer("2", case=NAMED_PATH_OMITTED_CASE)
    assert content["goal_meaning"] == GOAL_MEANING_CONTENT_REQUIRED
    assert content["execution_end_state"] == "ended_incomplete"
    assert content["goal_achievement_result"] == "not_achieved"


def test_unconnected_answer_stops_without_mission_state():
    judgment = interpret_goal_completion_answer(
        "続けてほかのファイルも探してください",
        case=NAMED_PATH_OMITTED_CASE,
    )
    assert judgment["status"] == "unsupported"
    assert judgment["execution_end_state"] is None
    other_case = interpret_goal_completion_answer(
        ABSENCE_COMPLETES_REPLY, case="not_connected_case"
    )
    assert other_case["status"] == "unsupported"
    assert other_case["reason"] == "GOAL_COMPLETION_CASE_NOT_CONNECTED"


def test_chat_turn_readme_case_persists_not_judged(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("gcg-readme")
    result = run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    assert result.get("awaiting_goal_completion_human") is True
    assert result["answer_gate"]["reason"] == "awaiting_goal_completion_human"
    packet = result["goal_completion_human"]
    assert packet["case"] == NAMED_PATH_OMITTED_CASE
    assert "achieved" not in result["answer"]
    resume = result["goal_completion_resume"]
    assert resume["mission_id"] == result["mission_memory"]["mission_id"]
    recorded = result["mission_memory"]
    execution = MissionMemoryStore.from_default().get_execution(
        recorded["mission_id"], recorded["execution_id"]
    )
    assert execution is not None
    assert execution["execution_end_state_judgment"] == "not_judged"
    assert execution["goal_achievement_performed"] is False
    assert execution["stop_reason"] == "GOAL_COMPLETION_HUMAN"
    tools = result.get("tools") or []
    assert any(item.get("name") == "list_files" and item.get("status") == "success" for item in tools)
    runtime = result["task_runtime"]
    task_status = {item["task_id"]: item["status"] for item in runtime["tasks"]}
    goal_status = {item["goal_id"]: item["status"] for item in runtime["goals"]}
    assert task_status["T1"] == "complete"
    assert task_status["T2"] == "complete"
    assert goal_status["G1"] == "complete"
    assert runtime["awaiting_goal_completion_human"] is True
    slice_tasks = {
        item["task_id"]: item["status"]
        for item in resume["completion_runtime"]["tasks"]
    }
    assert slice_tasks["T1"] == "complete"
    assert slice_tasks["T2"] == "complete"
    saved = session["turns"][-1]
    saved_tasks = {item["task_id"]: item["status"] for item in saved["task_runtime"]["tasks"]}
    assert saved_tasks["T1"] == "complete"
    assert saved_tasks["T2"] == "complete"
    assert saved["awaiting_goal_completion_human"] is True
    assert saved["mission_memory"]["execution_end_state_judgment"] == "not_judged"


def test_human_answer_resumes_same_mission_and_system_judges(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("gcg-resume")
    first = run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    mission_id = first["mission_memory"]["mission_id"]
    first_execution = first["mission_memory"]["execution_id"]
    second = run_chat_turn(
        session,
        ABSENCE_COMPLETES_REPLY,
        chat_fn=_chat_sequence(_response("should not be needed")),
        model="fake",
    )
    assert second.get("awaiting_goal_completion_human") is False
    recorded = second["mission_memory"]
    assert recorded["mission_id"] == mission_id
    assert recorded["execution_id"] != first_execution
    assert recorded["execution_end_state_judgment"] == "judged"
    assert recorded["execution_end_state"] == "achieved"
    store = MissionMemoryStore.from_default()
    execution = store.get_execution(mission_id, recorded["execution_id"])
    assert execution is not None
    assert execution["goal_achievement_performed"] is True
    assert execution["goal_achievement_result"] == "achieved"
    assert execution["stop_reason"] == "GOAL_COMPLETION_JUDGED"
    assert execution["evidence_refs"] == first["mission_memory"]["evidence_refs"]
    mission = store.get_mission(mission_id)
    assert mission is not None
    assert mission["original_goal"] == README_E2E_REQUEST
    assert any(item.get("source") == "goal_completion" for item in mission["user_confirmed_supplements"])
    listed = store.list_executions(mission_id)
    assert [item["execution_id"] for item in listed] == [
        first_execution,
        recorded["execution_id"],
    ]
    runtime = second["task_runtime"]
    task_status = {item["task_id"]: item["status"] for item in runtime["tasks"]}
    goal_status = {item["goal_id"]: item["status"] for item in runtime["goals"]}
    assert task_status["T1"] == "complete"
    assert task_status["T2"] == "complete"
    assert goal_status["G1"] == "complete"
    assert "Mission 状態: achieved" in second["answer"]
    assert runtime["awaiting_goal_completion_human"] is False
    saved = session["turns"][-1]
    saved_tasks = {item["task_id"]: item["status"] for item in saved["task_runtime"]["tasks"]}
    assert saved_tasks["T1"] == "complete"
    assert saved_tasks["T2"] == "complete"
    assert saved["mission_memory"]["execution_end_state"] == "achieved"


def test_unconnected_human_answer_stops_same_mission_not_judged(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("gcg-stop")
    first = run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    second = run_chat_turn(
        session,
        "ほかの場所も探してください",
        chat_fn=_chat_sequence(_response("should not be needed")),
        model="fake",
    )
    assert second["goal_completion_judgment"]["status"] == "unsupported"
    recorded = second["mission_memory"]
    assert recorded["mission_id"] == first["mission_memory"]["mission_id"]
    assert recorded["execution_end_state_judgment"] == "not_judged"
    execution = MissionMemoryStore.from_default().get_execution(
        recorded["mission_id"], recorded["execution_id"]
    )
    assert execution is not None
    assert "execution_end_state" not in execution
    assert execution["stop_reason"] == "GOAL_COMPLETION_UNSUPPORTED"
    assert execution["goal_achievement_performed"] is False
    runtime = second["task_runtime"]
    task_status = {item["task_id"]: item["status"] for item in runtime["tasks"]}
    goal_status = {item["goal_id"]: item["status"] for item in runtime["goals"]}
    assert task_status["T1"] == "complete"
    assert task_status["T2"] == "complete"
    assert goal_status["G1"] == "complete"
    assert recorded["execution_end_state_judgment"] == "not_judged"
