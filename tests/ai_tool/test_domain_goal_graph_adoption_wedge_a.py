from __future__ import annotations

import inspect
from dataclasses import fields

from ai_tool.chat_interface import agent_turn
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.domain_goal_graph_adoption import (
    RUNTIME_ROOT_GOAL_ID,
    DomainGoalGraphValidationError,
    adopt_domain_goal_graph,
    build_completion_runtime_snapshot_from_domain_goal_graph,
)
from tools.ai.task_runtime import TaskRecord


def _minimal_domain_goal_graph() -> dict:
    return {
        "root_goal": {
            "goal_id": "goal-root-fixture",
            "statement": "成果として要求されたシステム状態が成立している",
            "completion_conditions": ["required outcome goals are satisfied"],
        },
        "subgoals": [
            {
                "goal_id": "grp-functional",
                "statement": "機能として必要な成果状態が成立している",
                "parent_goal_id": "goal-root-fixture",
            },
            {
                "goal_id": "leaf-outcome-a",
                "statement": "成果Aの状態が画面上で確認できる状態が成立している",
                "parent_goal_id": "grp-functional",
            },
            {
                "goal_id": "leaf-outcome-b",
                "statement": "成果Bの操作手段が利用可能な状態が成立している",
                "parent_goal_id": "grp-functional",
            },
            {
                "goal_id": "grp-lifecycle",
                "statement": "ライフサイクル上の成果状態が成立している",
                "parent_goal_id": "goal-root-fixture",
            },
            {
                "goal_id": "leaf-lifecycle",
                "statement": "開始および停止の成果状態が成立している",
                "parent_goal_id": "grp-lifecycle",
            },
        ],
    }


def _goal_topology(runtime) -> dict[str, tuple[str | None, list[str], list[str]]]:
    out: dict[str, tuple[str | None, list[str], list[str]]] = {}
    for goal_id, goal in runtime.goals.items():
        out[goal_id] = (
            goal.parent_goal_id,
            list(goal.child_goal_ids),
            list(goal.task_ids),
        )
    return out


def test_a_domain_graph_snapshot_replace_matches_topology():
    orchestrator = ChatTaskOrchestrator("wedge-a", "domain goal request")
    graph = _minimal_domain_goal_graph()
    adopt_domain_goal_graph(orchestrator, graph)

    assert RUNTIME_ROOT_GOAL_ID in orchestrator.runtime.goals
    assert "G1.1" not in orchestrator.runtime.goals
    assert "G1.2" not in orchestrator.runtime.goals
    assert orchestrator.runtime.goals["grp-functional"].parent_goal_id == RUNTIME_ROOT_GOAL_ID
    assert set(orchestrator.runtime.goals[RUNTIME_ROOT_GOAL_ID].child_goal_ids) == {
        "grp-functional",
        "grp-lifecycle",
    }
    assert orchestrator.runtime.tasks == {}


def test_b_default_initialize_keeps_observe_synthesize():
    orchestrator = ChatTaskOrchestrator("wedge-a-default", "plain request")
    orchestrator.initialize()
    assert "G1.1" in orchestrator.runtime.goals
    assert "G1.2" in orchestrator.runtime.goals
    assert "T1" in orchestrator.runtime.tasks
    assert "T2" in orchestrator.runtime.tasks


def test_c_initialize_with_domain_graph_does_not_inject_observe_synthesize():
    orchestrator = ChatTaskOrchestrator("wedge-a-branch", "domain request")
    orchestrator.initialize(domain_goal_graph=_minimal_domain_goal_graph())
    titles = {goal.title for goal in orchestrator.runtime.goals.values()}
    assert "Observe the facts required by the request" not in titles
    assert "Synthesize the answer from known evidence" not in titles
    assert "Produce the requested result" not in titles


def test_d_goal_conditions_are_outcomes_not_task_methods():
    orchestrator = ChatTaskOrchestrator("wedge-a-outcome", "x")
    adopt_domain_goal_graph(orchestrator, _minimal_domain_goal_graph())
    banned = ("pytest", "testを", "ファイルを作", "関数を書")
    for goal in orchestrator.runtime.goals.values():
        for condition in goal.completion_conditions:
            lowered = condition.lower()
            assert not any(token in lowered for token in banned)


def test_e_task_record_dataclass_unchanged():
    names = {field.name for field in fields(TaskRecord)}
    expected = {
        "task_id",
        "goal_id",
        "title",
        "instruction",
        "completion_conditions",
        "status",
        "depends_on",
        "result_summary",
        "evidence_ids",
        "failure_history",
        "satisfied_conditions",
        "condition_status",
        "condition_evidence",
        "progress_state",
        "source",
        "source_task_id",
        "superseded_by_task_id",
        "supersedes_task_id",
        "decision_premises",
        "revalidation",
    }
    assert names == expected


def test_f_no_constraint_or_verification_tokens_in_goal_conditions():
    graph = _minimal_domain_goal_graph()
    graph["subgoals"][0]["acceptance_refs"] = ["vf-should-not-appear"]
    orchestrator = ChatTaskOrchestrator("wedge-a-clean", "x")
    adopt_domain_goal_graph(orchestrator, graph)
    joined = " ".join(
        condition
        for goal in orchestrator.runtime.goals.values()
        for condition in goal.completion_conditions
    )
    assert "vf-" not in joined
    assert "constraint-" not in joined


def test_g_false_success_guard_still_targets_root_g1():
    source = inspect.getsource(agent_turn)
    assert 'orchestrator.runtime.goals.get("G1")' in source
    assert "synthesis.get(\"ready\")" in source or "synthesis.get('ready')" in source


def test_h_snapshot_restore_preserves_domain_topology():
    orchestrator = ChatTaskOrchestrator("wedge-a-restore", "x")
    adopt_domain_goal_graph(orchestrator, _minimal_domain_goal_graph())
    before = _goal_topology(orchestrator.runtime)

    snapshot = orchestrator.completion_runtime_slice()
    resumed = ChatTaskOrchestrator("wedge-a-resumed", orchestrator.request)
    resumed.apply_completion_runtime(snapshot, replace_graph=True)

    after = _goal_topology(resumed.runtime)
    assert before == after
    assert RUNTIME_ROOT_GOAL_ID in resumed.runtime.goals


def test_i_invalid_child_reference_rejected():
    graph = _minimal_domain_goal_graph()
    graph["subgoals"].append(
        {
            "goal_id": "orphan",
            "statement": "孤立した成果状態",
            "parent_goal_id": "missing-parent",
        }
    )
    orchestrator = ChatTaskOrchestrator("wedge-a-invalid-parent", "x")
    try:
        adopt_domain_goal_graph(orchestrator, graph)
    except DomainGoalGraphValidationError as exc:
        assert "unknown parent" in str(exc)
    else:
        raise AssertionError("expected validation failure")


def test_j_cycle_rejected():
    graph = {
        "root_goal": {"goal_id": "goal-root", "statement": "root outcome"},
        "subgoals": [
            {"goal_id": "a", "statement": "a outcome", "parent_goal_id": "e"},
            {"goal_id": "b", "statement": "b outcome", "parent_goal_id": "a"},
            {"goal_id": "c", "statement": "c outcome", "parent_goal_id": "b"},
            {"goal_id": "d", "statement": "d outcome", "parent_goal_id": "c"},
            {"goal_id": "e", "statement": "e outcome", "parent_goal_id": "d"},
        ],
    }
    orchestrator = ChatTaskOrchestrator("wedge-a-cycle", "x")
    try:
        adopt_domain_goal_graph(orchestrator, graph)
    except DomainGoalGraphValidationError as exc:
        assert "cycle" in str(exc).lower()
    else:
        raise AssertionError("expected cycle rejection")


def test_k_duplicate_goal_id_rejected():
    graph = _minimal_domain_goal_graph()
    graph["subgoals"].append(
        {
            "goal_id": "leaf-outcome-a",
            "statement": "duplicate",
            "parent_goal_id": "grp-functional",
        }
    )
    orchestrator = ChatTaskOrchestrator("wedge-a-dup", "x")
    try:
        adopt_domain_goal_graph(orchestrator, graph)
    except DomainGoalGraphValidationError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected duplicate rejection")


def test_goal_id_mapping_preserves_source_trace():
    graph = _minimal_domain_goal_graph()
    snapshot, mapping = build_completion_runtime_snapshot_from_domain_goal_graph(graph)
    assert mapping["goal-root-fixture"] == RUNTIME_ROOT_GOAL_ID
    assert mapping["leaf-outcome-a"] == "leaf-outcome-a"
    assert snapshot["domain_goal_adoption"]["source_root_goal_id"] == "goal-root-fixture"
