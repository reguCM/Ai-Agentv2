from types import SimpleNamespace

from ai_tool.chat_interface.capability_resolution import (
    CapabilityResolution,
    confirm_tool_gap,
    infer_required_capability,
    required_capabilities,
    resolve_capability,
)
from ai_tool.chat_interface.concept_resolution import load_workspace_index
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.run_human_summary import build_human_summary, human_summary_markdown
from tools.ai.task_runtime import AgentTaskRuntime, EvidenceRecord, GoalNode, TaskRecord


INDEX = load_workspace_index()


def _task(text: str, task_id: str = "T1"):
    return SimpleNamespace(task_id=task_id, title=text, instruction=text, completion_conditions=[])


def _tool(name: str, capability: str, visibility: str = "agent"):
    return {
        "name": name,
        "capabilities": [capability],
        "visibility": visibility,
        "module": f"tools.fake.{name}",
        "function": name,
        "input": {},
    }


def test_capability_classification_read_edit_create_and_pytest():
    assert required_capabilities(_task("ファイルの内容を読む")) == ["workspace_file_read"]
    # H4 Core: bare 「修正する」 is not a mutation keyword. Classifier B does not
    # map this to workspace_file_edit. Empty-tools test_execution is not reached
    # by keyword reverse lookup after _RULES removal.
    assert "workspace_file_edit" not in required_capabilities(_task("既存コードを修正する"))
    assert "workspace_file_create" in required_capabilities(_task("新規ファイルを作る"))
    assert "test_execution" not in required_capabilities(_task("pytestを実行する"))


def test_audit_of_pytest_capability_requires_registry_read_not_test_execution():
    task = _task("pytest実行Capabilityが存在するかRegistryを調査してください")
    assert infer_required_capability(task) == "registry_read"


def test_capability_index_names_only_real_registry_tools():
    registry = {item["name"]: item for item in load_registry_tools()}
    for spec in INDEX["capabilities"].values():
        for name in spec.get("tools") or []:
            assert name in registry
            assert registry[name].get("visibility") == "agent"


def test_different_tool_name_matches_capability_metadata():
    result = resolve_capability(
        _task("ファイルを編集して"),
        capability="workspace_file_edit",
        capability_index=INDEX,
        registry_tools=[_tool("patch_workspace", "workspace_file_edit")],
    )
    assert result.status == "RESOLVED"
    assert result.selected_tool == "patch_workspace"


def test_nonexistent_guessed_tool_name_does_not_confirm_gap():
    result = resolve_capability(
        _task("ファイルを編集して"),
        capability="workspace_file_edit",
        capability_index=INDEX,
        registry_tools=[],
    )
    assert result.status == "NO_MATCH"
    assert result.tool_gap_confirmed is False
    assert "edit_file" not in result.existing_candidates


def test_non_agent_visibility_is_rejected():
    result = resolve_capability(
        _task("ファイルを編集して"),
        capability="workspace_file_edit",
        capability_index=INDEX,
        registry_tools=[_tool("patch_workspace", "workspace_file_edit", "pipeline")],
    )
    assert result.candidate_tools == []
    assert result.rejection_reasons == [
        {"tool": "patch_workspace", "reason": "visibility_not_agent"}
    ]


def test_multiple_equivalent_tools_are_recorded():
    result = resolve_capability(
        _task("ファイルの内容を読む"),
        capability="workspace_file_read",
        capability_index=INDEX,
        registry_tools=[
            _tool("read_file", "workspace_file_read"),
            _tool("read_text", "workspace_file_read"),
        ],
    )
    assert result.candidate_tools == ["read_file", "read_text"]
    assert result.status == "CANDIDATES_AVAILABLE"
    assert result.selected_tool is None
    assert result.tool_gap_confirmed is False


def test_gap_needs_index_registry_and_evidence_confirmation():
    base = CapabilityResolution(required_capability="workspace_file_edit", status="NO_MATCH")
    assert confirm_tool_gap(base, "E1").tool_gap_confirmed is False
    base.capability_index_checked = True
    base.registry_checked = True
    confirm_tool_gap(base, "E1")
    assert base.status == "TOOL_GAP_CONFIRMED"
    assert base.requires_human_approval is True


def test_runtime_accepts_only_evidence_backed_confirmed_gap():
    runtime = AgentTaskRuntime("r")
    runtime.add_goal(GoalNode("G1", "goal"))
    runtime.add_task(TaskRecord("T1", "G1", "edit", "edit", ["edited"]))
    assert runtime.record_confirmed_tool_gap(
        "T1", "workspace_file_edit", registry_checked=True,
        capability_index_checked=True, existing_candidates=[], rejected_candidates=[],
        suggested_minimal_tool="edit_file", evidence_ids=["missing"],
    ) is None
    runtime.add_evidence(
        EvidenceRecord("E1", "capability_registry_check", "registry/tools.json", "none", "resolver"),
        ["T1"],
    )
    gap = runtime.record_confirmed_tool_gap(
        "T1", "workspace_file_edit", registry_checked=True,
        capability_index_checked=True, existing_candidates=[], rejected_candidates=[],
        suggested_minimal_tool="edit_file", evidence_ids=["E1"],
    )
    assert gap is not None
    assert gap.certainty == "CONFIRMED"
    assert gap.requires_human_approval is True


def test_local_review_gate_task_does_not_default_read_look_first():
    orchestrator = ChatTaskOrchestrator("r", "repository audit")
    orchestrator.initialize()
    tools = [
        _tool("read_file", "workspace_file_read"),
        _tool("search_files", "workspace_file_search"),
    ]
    orchestrator.configure_tool_expectation(tools, registry_tools=tools)
    task = orchestrator.add_review_task(
        {
            "description": "Agent Tool Gateを確認する",
            "reason": "approval condition is unresolved",
            "supports_conditions": ["approval confirmed"],
            "source_problem": "approval unknown",
        }
    )
    rows = orchestrator.capability_resolutions[task.task_id]
    assert isinstance(rows, list)
    assert orchestrator.pending_capability_action() is None
    for item in rows:
        if item.selected_tool == "read_file":
            assert item.next_action is None


def test_bridge_observation_is_evidence_but_not_automatic_completion():
    orchestrator = ChatTaskOrchestrator(
        "r", "pytest実行Capabilityが存在するかRegistryを調査してください",
        completion_conditions=["test_executionの有無が確認できている"],
    )
    orchestrator.initialize()
    tools = [_tool("read_file", "registry_read")]
    orchestrator.configure_tool_expectation(tools, registry_tools=tools)
    orchestrator.observe_tool(
        "read_file",
        {"path": "registry/tools.json"},
        {"ok": True, "status": "success", "error": None, "warnings": [], "data": {}},
        "Registry read",
        relevant_tools=["read_file"],
        raw_result={"lines": [{"text": "read_file is agent-visible"}]},
    )
    assert len(orchestrator.runtime.evidence) == 1
    assert orchestrator.runtime.tasks["T1"].status != "complete"


def test_capability_result_is_exposed_in_human_summary():
    task_runtime = {"goals": [], "tasks": [], "evidence": [], "replans": [], "local_reviews": []}
    record = {
        "prompt": "edit",
        "completion_coverage": {"completion_conditions": []},
        "capability_resolution": [{
            "required_capability": "workspace_file_edit", "status": "TOOL_GAP_CONFIRMED",
            "existing_candidates": [], "missing_capability": "workspace_file_edit",
            "suggested_minimal_tool": "edit_file",
        }],
        "runtime": {}, "tool": {}, "output": {}, "goal": {}, "evaluations": {},
    }
    summary = build_human_summary(record, task_runtime=task_runtime, turn={"tools": []})
    markdown = human_summary_markdown(summary)
    assert "workspace_file_edit" in markdown
    assert "edit_file" in markdown
    assert "Human Approval" in markdown
