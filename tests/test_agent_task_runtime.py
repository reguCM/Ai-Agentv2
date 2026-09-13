import pytest

from tools.ai.agent_runtime import AgentRuntime, AgentRuntimeState
from tools.ai.task_runtime import (
    ActionRecord,
    AgentTaskRuntime,
    EvidenceRecord,
    FailureRecord,
    GoalNode,
    ReplanRecord,
    TaskRecord,
)


def runtime():
    rt = AgentTaskRuntime("r1")
    rt.add_goal(GoalNode("G1", "Final", completion_conditions=["all done"]))
    rt.add_goal(GoalNode("G1.1", "Inspect", parent_goal_id="G1"))
    rt.add_task(TaskRecord("T1", "G1.1", "Read contract", "read", ["file read"]))
    rt.add_task(
        TaskRecord(
            "T2", "G1.1", "Use schema", "design", ["schema used"], depends_on=["T1"]
        )
    )
    return rt


def test_01_recursive_goal_tree():
    rt = runtime()
    rt.add_goal(GoalNode("G1.1.1", "Deep", parent_goal_id="G1.1"))
    assert rt.goals["G1"].child_goal_ids == ["G1.1"]
    assert rt.goals["G1.1"].child_goal_ids == ["G1.1.1"]


def test_02_task_conditions_and_dependency_are_saved():
    rt = runtime()
    assert rt.tasks["T1"].completion_conditions == ["file read"]
    assert rt.tasks["T2"].depends_on == ["T1"]


def test_03_tool_success_does_not_complete_task():
    rt = runtime()
    rt.record_action(ActionRecord("A1", "T1", "tool_call", "search_files", result_status="success"))
    assert not rt.evaluate_task("T1", [])


def test_04_evidence_can_be_shared_between_tasks():
    rt = runtime()
    rt.add_evidence(EvidenceRecord("E1", "file", "docs/x", "four fields", "A1"), ["T1", "T2"])
    assert rt.tasks["T1"].evidence_ids == ["E1"]
    assert rt.tasks["T2"].evidence_ids == ["E1"]


def test_05_small_hint_reuses_known_evidence():
    rt = runtime()
    rt.add_evidence(EvidenceRecord("E1", "file", "docs/x", "four fields", "A1"), ["T2"])
    assert "four fields" in rt.small_task_hint("T2")


def test_06_evidence_gain_suppresses_duplicate_action():
    rt = runtime()
    rt.record_action(ActionRecord("A1", "T1", "tool_call", "read_file", {"path": "x"}, evidence_gain=True))
    assert not rt.should_execute("T1", "read_file", {"path": "x"})


def test_07_action_without_evidence_can_be_retried():
    rt = runtime()
    rt.record_action(ActionRecord("A1", "T1", "tool_call", "read_file", {"path": "x"}))
    assert rt.should_execute("T1", "read_file", {"path": "x"})


def test_08_repeated_identical_failure_is_stagnation():
    rt = runtime()
    for index in range(2):
        rt.record_failure(FailureRecord(f"F{index}", "T1", f"A{index}", "read_file", {"path": "bad"}, "path_not_found"))
    assert rt.is_stagnating("T1")
    assert rt.tasks["T1"].progress_state == "stagnation"


def test_09_different_failure_arguments_are_not_stagnation():
    rt = runtime()
    rt.record_failure(FailureRecord("F1", "T1", "A1", "read_file", {"path": "a"}, "not_found"))
    rt.record_failure(FailureRecord("F2", "T1", "A2", "read_file", {"path": "b"}, "not_found"))
    assert not rt.is_stagnating("T1")


def test_10_failure_with_evidence_is_not_stagnation():
    rt = runtime()
    rt.record_failure(FailureRecord("F1", "T1", "A1", "read_file", {"path": "a"}, "partial", True))
    rt.record_failure(FailureRecord("F2", "T1", "A2", "read_file", {"path": "a"}, "partial", True))
    assert not rt.is_stagnating("T1")


def test_11_partial_with_evidence_is_progress():
    rt = runtime()
    rt.record_action(ActionRecord("A1", "T1", "tool_call", "search_files", result_status="partial", evidence_gain=True))
    assert rt.tasks["T1"].progress_state == "progress"


def test_12_single_no_evidence_action_is_not_premature_stagnation():
    rt = runtime()
    assert rt.assess_progress("T1", evidence_gain=False) == "unknown"


def test_13_regression_is_separate_from_task_status():
    rt = runtime()
    assert rt.assess_progress("T1", evidence_gain=False, regression=True) == "regression"
    assert rt.tasks["T1"].status == "pending"


def test_14_recovery_hint_forbids_repeated_action():
    rt = runtime()
    rt.record_failure(FailureRecord("F1", "T1", "A1", "read_file", {"path": "bad"}, "not_found"))
    hint = rt.recovery_hint("T1")
    assert "read_file" in hint and "Do not repeat" in hint


def test_15_irrelevant_action_is_rejected_before_evidence():
    rt = runtime()
    assert rt.audit_relevance("T1", tool_name="get_system_summary", relevant_tools=["read_file"]) == "REJECT_ACTION_RESULT"
    assert rt.tasks["T1"].evidence_ids == []


def test_16_relevant_action_is_accepted():
    rt = runtime()
    assert rt.audit_relevance("T1", tool_name="read_file", relevant_tools=["read_file"]) == "ACCEPT"


def test_17_existing_registry_tool_prevents_gap():
    rt = runtime()
    tools = [{"name": "git_branch_info", "description": "Git branch"}]
    assert rt.detect_tool_gap("T1", "Git branch", tools) is None


def test_18_missing_tool_creates_candidate_only():
    rt = runtime()
    gap = rt.detect_tool_gap("T1", "database export", [], candidate_tool="export_db")
    assert gap is not None and gap.status == "candidate"
    assert rt.actions == []


def test_19_recurring_gap_across_tasks_is_recommended():
    rt = runtime()
    rt.detect_tool_gap("T1", "Git branch", [], candidate_tool="git_branch_info")
    gap = rt.detect_tool_gap("T2", "Git branch", [])
    assert gap is not None and gap.status == "recommended" and gap.occurrences == 2


def test_20_local_replan_preserves_completed_work():
    rt = runtime()
    rt.evaluate_task("T1", ["file read"])
    record = ReplanRecord("R1", "G1.1", "new evidence")
    rt.replan_add_task(record, TaskRecord("T3", "G1.1", "Boundary", "inspect", ["defined"]))
    assert rt.tasks["T1"].status == "complete"
    assert record.added_task_ids == ["T3"]


def test_21_replan_rejects_task_outside_scope():
    rt = runtime()
    with pytest.raises(ValueError, match="scope goal"):
        rt.replan_add_task(
            ReplanRecord("R1", "G1.1", "boundary"),
            TaskRecord("T3", "G1", "wrong", "inspect", ["done"]),
        )


def test_22_goal_completion_requires_children_tasks_and_conditions():
    rt = runtime()
    rt.evaluate_task("T1", ["file read"])
    rt.evaluate_task("T2", ["schema used"])
    assert rt.evaluate_goal("G1.1", [])
    assert rt.evaluate_goal("G1", ["all done"])


def test_23_final_synthesis_reports_unresolved_tasks():
    rt = runtime()
    result = rt.final_synthesis_context("G1")
    assert not result["ready"]
    assert result["unresolved_items"] == ["T1", "T2"]


def test_24_final_synthesis_reuses_evidence_and_reassesses_goal():
    rt = runtime()
    rt.add_evidence(EvidenceRecord("E1", "file", "x", "contract confirmed", "A1"), ["T1"])
    rt.evaluate_task("T1", ["file read"])
    rt.evaluate_task("T2", ["schema used"])
    rt.evaluate_goal("G1.1", [])
    rt.evaluate_goal("G1", ["all done"])
    result = rt.final_synthesis_context("G1")
    assert result["ready"] and "contract confirmed" in result["evidence_summaries"]


def test_25_save_and_load_round_trip(tmp_path):
    rt = runtime()
    rt.record_action(ActionRecord("A1", "T1", "tool_call", "read_file", {"path": "x"}, "success", evidence_gain=True))
    rt.add_evidence(EvidenceRecord("E1", "file", "x", "fact", "A1"), ["T1"])
    rt.record_failure(FailureRecord("F1", "T2", "A2", "search_files", {"q": "x"}, "empty"))
    rt.add_replan(ReplanRecord("R1", "G1.1", "refine"))
    rt.save(tmp_path)
    loaded = AgentTaskRuntime.load(tmp_path)
    assert loaded.goals["G1.1"].parent_goal_id == "G1"
    assert loaded.actions[0].arguments == {"path": "x"}
    assert loaded.evidence["E1"].summary == "fact"
    assert loaded.failures[0].failure_code == "empty"
    assert loaded.replans[0].reason == "refine"


def test_26_agent_runtime_event_bridge_is_optional_and_non_replacing():
    rt = runtime()
    agent = AgentRuntime(logger=None, event_sink=rt.observe_agent_runtime_event)
    agent.transition(AgentRuntimeState.TOOL_PARTIAL, tool="search_files")
    assert agent.current_state is AgentRuntimeState.TOOL_PARTIAL
    assert rt.agent_runtime_events[-1]["state"] == "TOOL_PARTIAL"


def test_27_duplicate_goal_is_rejected():
    rt = runtime()
    with pytest.raises(ValueError, match="duplicate goal_id"):
        rt.add_goal(GoalNode("G1", "duplicate"))


def test_28_unknown_parent_goal_is_rejected():
    rt = runtime()
    with pytest.raises(ValueError, match="unknown parent goal"):
        rt.add_goal(GoalNode("G2", "orphan", parent_goal_id="missing"))


def test_29_unknown_goal_for_task_is_rejected():
    rt = runtime()
    with pytest.raises(ValueError, match="unknown goal"):
        rt.add_task(TaskRecord("T3", "missing", "x", "x", ["done"]))


def test_30_task_requires_every_completion_condition():
    rt = runtime()
    rt.tasks["T1"].completion_conditions = ["read", "verified"]
    assert not rt.evaluate_task("T1", ["read"])
    assert rt.evaluate_task("T1", ["read", "verified"])


def test_31_shared_evidence_suppresses_duplicate_work_in_next_task():
    rt = runtime()
    action = ActionRecord(
        "A1", "T1", "tool_call", "read_file", {"path": "contract.md"}, evidence_gain=True
    )
    rt.record_action(action)
    rt.add_evidence(
        EvidenceRecord("E1", "file", "contract.md", "schema", "A1"), ["T1", "T2"]
    )
    assert not rt.should_execute("T2", "read_file", {"path": "contract.md"})


def test_32_partial_then_alternate_action_can_complete_task():
    rt = runtime()
    rt.record_action(
        ActionRecord("A1", "T1", "tool_call", "search_files", result_status="partial")
    )
    rt.record_action(
        ActionRecord(
            "A2", "T1", "tool_call", "read_file", result_status="success", evidence_gain=True
        )
    )
    assert rt.evaluate_task("T1", ["file read"])


def test_33_multiple_subgoals_are_saved_under_final_goal():
    rt = runtime()
    rt.add_goal(GoalNode("G1.2", "Verify", parent_goal_id="G1"))
    assert rt.goals["G1"].child_goal_ids == ["G1.1", "G1.2"]


def test_34_tool_gap_round_trips_with_runtime_state(tmp_path):
    rt = runtime()
    rt.detect_tool_gap("T1", "database export", [], candidate_tool="export_db")
    rt.save(tmp_path)
    loaded = AgentTaskRuntime.load(tmp_path)
    assert loaded.tool_gaps["database export"].candidate_tool == "export_db"
