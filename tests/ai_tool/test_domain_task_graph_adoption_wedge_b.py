from __future__ import annotations

from dataclasses import fields

from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.domain_task_graph_adoption import (
    TASK_GRAPH_PROJECTION_SIDECAR_KEY,
    DomainTaskGraphValidationError,
    adopt_domain_goal_and_task_graph,
)
from ai_tool.domain_goal_graph_adoption import RUNTIME_ROOT_GOAL_ID
from tools.ai.task_runtime import TaskRecord


def _minimal_goal_graph() -> dict:
    return {
        "root_goal": {
            "goal_id": "goal-root-fixture",
            "statement": "Root outcome established",
            "completion_conditions": ["root outcome satisfied"],
        },
        "subgoals": [
            {
                "goal_id": "goal-a",
                "statement": "Outcome A established",
                "parent_goal_id": "goal-root-fixture",
            },
            {
                "goal_id": "goal-b",
                "statement": "Outcome B established",
                "parent_goal_id": "goal-root-fixture",
            },
            {
                "goal_id": "goal-c",
                "statement": "Outcome C established",
                "parent_goal_id": "goal-root-fixture",
            },
        ],
    }


def _minimal_task_graph() -> dict:
    return {
        "graph_id": "wedge-b-fixture",
        "tasks": [
            {
                "task_id": "task-t1",
                "title": "Shared work for A and B",
                "purpose": "deliver_shared_ab",
                "task_kind": "IMPLEMENTATION",
                "supports_goal_ids": ["goal-a", "goal-b"],
                "depends_on": [],
                "verification_refs": ["vf-shared-ab"],
                "completion_state": "Shared deliverable for A and B is in place",
            },
            {
                "task_id": "task-t2",
                "title": "Work for B only",
                "purpose": "deliver_b",
                "task_kind": "IMPLEMENTATION",
                "supports_goal_ids": ["goal-b"],
                "depends_on": ["task-t1"],
                "verification_refs": [],
                "completion_state": "B-specific deliverable is in place",
            },
            {
                "task_id": "task-t3",
                "title": "Work for C",
                "purpose": "deliver_c",
                "task_kind": "VERIFICATION",
                "supports_goal_ids": ["goal-c"],
                "depends_on": [],
                "verification_refs": ["vf-c-only"],
                "completion_state": "C deliverable is in place",
            },
        ],
    }


def _sidecar_by_task(orchestrator: ChatTaskOrchestrator) -> dict[str, dict]:
    return {row["task_id"]: row for row in orchestrator.task_graph_projection_sidecar}


def test_a_wedge_a_goals_only_path_unchanged():
    orchestrator = ChatTaskOrchestrator("wb-a", "x")
    orchestrator.initialize(domain_goal_graph=_minimal_goal_graph())
    assert orchestrator.runtime.tasks == {}
    assert orchestrator.task_graph_projection_sidecar == []


def test_b_goal_and_task_adoption():
    orchestrator = ChatTaskOrchestrator("wb-b", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    assert len(orchestrator.runtime.tasks) == 3


def test_c_task_record_count():
    orchestrator = ChatTaskOrchestrator("wb-c", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    assert len(orchestrator.runtime.tasks) == len(_minimal_task_graph()["tasks"])


def test_d_task_ids_preserved():
    orchestrator = ChatTaskOrchestrator("wb-d", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    assert set(orchestrator.runtime.tasks) == {"task-t1", "task-t2", "task-t3"}


def test_e_primary_goal_on_shared_task():
    orchestrator = ChatTaskOrchestrator("wb-e", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    assert orchestrator.runtime.tasks["task-t1"].goal_id == "goal-a"


def test_f_shared_task_single_record():
    orchestrator = ChatTaskOrchestrator("wb-f", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    matches = [
        task_id
        for task_id, task in orchestrator.runtime.tasks.items()
        if task.title.startswith("Shared work")
    ]
    assert matches == ["task-t1"]


def test_g_secondary_goals_in_sidecar():
    orchestrator = ChatTaskOrchestrator("wb-g", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    row = _sidecar_by_task(orchestrator)["task-t1"]
    assert row["runtime_goal_ids"] == ["goal-a", "goal-b"]
    assert row["primary_runtime_goal_id"] == "goal-a"


def test_h_verification_refs_in_sidecar():
    orchestrator = ChatTaskOrchestrator("wb-h", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    assert _sidecar_by_task(orchestrator)["task-t1"]["verification_refs"] == ["vf-shared-ab"]


def test_i_no_vf_in_completion_conditions():
    orchestrator = ChatTaskOrchestrator("wb-i", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    joined = " ".join(
        cond
        for task in orchestrator.runtime.tasks.values()
        for cond in task.completion_conditions
    )
    assert "vf-" not in joined


def test_j_depends_on_preserved():
    orchestrator = ChatTaskOrchestrator("wb-j", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    assert orchestrator.runtime.tasks["task-t2"].depends_on == ["task-t1"]


def test_k_completion_conditions_preserved():
    orchestrator = ChatTaskOrchestrator("wb-k", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    assert orchestrator.runtime.tasks["task-t3"].completion_conditions == [
        "C deliverable is in place"
    ]


def test_l_evidence_ids_empty():
    orchestrator = ChatTaskOrchestrator("wb-l", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    for task in orchestrator.runtime.tasks.values():
        assert task.evidence_ids == []


def test_m_snapshot_restore_tasks():
    orchestrator = ChatTaskOrchestrator("wb-m", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    before_ids = set(orchestrator.runtime.tasks)
    snapshot = orchestrator.completion_runtime_slice()
    resumed = ChatTaskOrchestrator("wb-m-r", "x")
    resumed.apply_completion_runtime(snapshot, replace_graph=True)
    assert set(resumed.runtime.tasks) == before_ids


def test_n_snapshot_restore_sidecar():
    orchestrator = ChatTaskOrchestrator("wb-n", "x")
    orchestrator.initialize(
        domain_goal_graph=_minimal_goal_graph(),
        domain_task_graph=_minimal_task_graph(),
    )
    snapshot = orchestrator.completion_runtime_slice()
    assert TASK_GRAPH_PROJECTION_SIDECAR_KEY in snapshot
    resumed = ChatTaskOrchestrator("wb-n-r", "x")
    resumed.apply_completion_runtime(snapshot, replace_graph=True)
    assert resumed.task_graph_projection_sidecar == orchestrator.task_graph_projection_sidecar


def test_o_default_observe_synthesize():
    orchestrator = ChatTaskOrchestrator("wb-o", "plain")
    orchestrator.initialize()
    assert "G1.1" in orchestrator.runtime.goals


def test_p_task_only_rejected():
    orchestrator = ChatTaskOrchestrator("wb-p", "x")
    try:
        orchestrator.initialize(domain_task_graph=_minimal_task_graph())
    except DomainTaskGraphValidationError as exc:
        assert "requires domain_goal_graph" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_q_duplicate_task_id_rejected():
    graph = _minimal_task_graph()
    graph["tasks"].append(dict(graph["tasks"][0]))
    orchestrator = ChatTaskOrchestrator("wb-q", "x")
    try:
        adopt_domain_goal_and_task_graph(orchestrator, _minimal_goal_graph(), graph)
    except DomainTaskGraphValidationError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected duplicate rejection")


def test_r_missing_goal_reference_rejected():
    graph = _minimal_task_graph()
    graph["tasks"][0]["supports_goal_ids"] = ["goal-missing"]
    orchestrator = ChatTaskOrchestrator("wb-r", "x")
    try:
        adopt_domain_goal_and_task_graph(orchestrator, _minimal_goal_graph(), graph)
    except DomainTaskGraphValidationError as exc:
        assert "unknown supports_goal_id" in str(exc)
    else:
        raise AssertionError("expected missing goal rejection")


def test_s_missing_dependency_rejected():
    graph = _minimal_task_graph()
    graph["tasks"][0]["depends_on"] = ["task-missing"]
    orchestrator = ChatTaskOrchestrator("wb-s", "x")
    try:
        adopt_domain_goal_and_task_graph(orchestrator, _minimal_goal_graph(), graph)
    except DomainTaskGraphValidationError as exc:
        assert "unknown dependency" in str(exc)
    else:
        raise AssertionError("expected missing dependency rejection")


def test_t_cycle_rejected():
    graph = {
        "graph_id": "cycle",
        "tasks": [
            {
                "task_id": "a",
                "title": "a",
                "supports_goal_ids": ["goal-a"],
                "depends_on": ["b"],
                "completion_state": "a done",
            },
            {
                "task_id": "b",
                "title": "b",
                "supports_goal_ids": ["goal-a"],
                "depends_on": ["a"],
                "completion_state": "b done",
            },
        ],
    }
    orchestrator = ChatTaskOrchestrator("wb-t", "x")
    try:
        adopt_domain_goal_and_task_graph(orchestrator, _minimal_goal_graph(), graph)
    except DomainTaskGraphValidationError as exc:
        assert "cycle" in str(exc).lower()
    else:
        raise AssertionError("expected cycle rejection")


def test_task_record_schema_unchanged():
    names = {field.name for field in fields(TaskRecord)}
    assert "goal_ids" not in names


def test_root_goal_mapped_to_g1_for_primary():
    orchestrator = ChatTaskOrchestrator("wb-g1", "x")
    graph = _minimal_goal_graph()
    tasks = {
        "graph_id": "root-task",
        "tasks": [
            {
                "task_id": "task-root-only",
                "title": "Root task",
                "supports_goal_ids": ["goal-root-fixture"],
                "depends_on": [],
                "completion_state": "Root scoped work complete",
            }
        ],
    }
    orchestrator.initialize(domain_goal_graph=graph, domain_task_graph=tasks)
    assert orchestrator.runtime.tasks["task-root-only"].goal_id == RUNTIME_ROOT_GOAL_ID
