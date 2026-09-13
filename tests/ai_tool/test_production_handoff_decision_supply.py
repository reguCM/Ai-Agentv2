"""Cross-execution Production Handoff supply for active Human Decisions."""
from __future__ import annotations

import pytest

from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    DECISION_STATUS_SUPERSEDED,
    supersede_decision,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.dev_skill_pipeline import normalize_implementation_tasks, validate_handoff_packet
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.human_decision_premise import tasks_needing_revalidation
from ai_tool.mission_memory.chat_persist import (
    bind_execution_identity,
    persist_chat_execution,
)
from ai_tool.mission_memory.clarifications import load_confirmed_clarifications_for_mission
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.production_handoff_bridge import (
    build_production_handoff_packet,
    prepare_production_handoff_orchestrator,
    production_handoff_decision_catalog,
)

KEY_JSON = "acceptance:output_format"
KEY_GUI = "scope:gui"
D_JSON_V1 = "d-json-v1"
D_GUI_V1 = "d-gui-v1"
D_JSON_V2 = "d-json-v2"


@pytest.fixture
def mission_store(tmp_path, monkeypatch):
    root = tmp_path / "mission_memory"
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: root,
    )
    return MissionMemoryStore(root)


def _decisions() -> list[dict]:
    return [
        {
            "decision_id": D_JSON_V1,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "JSON",
            "dimension": "acceptance",
        },
        {
            "decision_id": D_GUI_V1,
            "decision_key": KEY_GUI,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "GUIあり",
            "dimension": "scope",
        },
    ]


def _plan_tasks() -> list[dict]:
    return [
        {
            "id": "T1",
            "title": "Shared setup",
            "acceptance": ["project scaffold exists"],
            "verification": ["repo ready"],
            "dependencies": [],
            "size": "S",
        },
        {
            "id": "T2",
            "title": "Emit JSON API output",
            "acceptance": ["JSON response available"],
            "verification": ["json endpoint returns payload"],
            "dependencies": ["T1"],
            "size": "S",
            "premise_decision_keys": [KEY_JSON],
        },
        {
            "id": "T3",
            "title": "Build GUI screen",
            "acceptance": ["GUI visible"],
            "verification": ["manual UI check"],
            "dependencies": ["T1"],
            "size": "M",
            "premise_decision_keys": [KEY_GUI],
        },
    ]


def test_execution_one_persists_confirmed_clarifications_to_mission(mission_store):
    orchestrator = ChatTaskOrchestrator("exec-1", "build service")
    bind_execution_identity(orchestrator)
    orchestrator.confirmed_clarifications = list(_decisions())
    recorded = persist_chat_execution(
        orchestrator,
        stop_reason="DETERMINED",
        determined=True,
        answer="decisions saved",
        store=mission_store,
    )
    mission = mission_store.get_mission(recorded["mission_id"])
    assert mission is not None
    assert len(mission.get("confirmed_clarifications") or []) == 2
    restored = load_confirmed_clarifications_for_mission(
        recorded["mission_id"],
        store=mission_store,
    )
    assert {row["decision_id"] for row in restored} == {D_JSON_V1, D_GUI_V1}


def test_execution_two_resume_builds_production_handoff_with_per_task_premises(
    mission_store,
):
    exec1 = ChatTaskOrchestrator("exec-1", "build service")
    bind_execution_identity(exec1)
    exec1.confirmed_clarifications = list(_decisions())
    recorded = persist_chat_execution(
        exec1,
        stop_reason="DETERMINED",
        determined=True,
        answer="decisions saved",
        store=mission_store,
    )

    exec2 = ChatTaskOrchestrator("exec-2", "build service")
    bind_execution_identity(exec2, resume_mission_id=recorded["mission_id"])
    assert exec2.confirmed_clarifications == []
    prepare_production_handoff_orchestrator(exec2, store=mission_store)

    catalog = production_handoff_decision_catalog(exec2, store=mission_store)
    assert set(catalog) == {KEY_JSON, KEY_GUI}

    plan_tasks = normalize_implementation_tasks(
        _plan_tasks(),
        default_acceptance=["done"],
        default_verification=["check"],
    )
    packet = build_production_handoff_packet(
        exec2,
        initial_request="build service",
        plan={"tasks": plan_tasks},
        tech_spec={"summary": "service"},
        prd_rel="docs/prd.md",
        tech_spec_rel="docs/tech.md",
        plan_rel="tasks/plan.md",
        todo_rel="tasks/todo.md",
        store=mission_store,
        handoff_slug="production-cross-exec",
    )
    assert not validate_handoff_packet(packet)
    tasks = {row["id"]: row for row in packet["implementation_tasks"]}
    assert "decision_premises" not in tasks["T1"]
    assert tasks["T2"]["decision_premises"] == [
        {"decision_key": KEY_JSON, "derived_from_decision_id": D_JSON_V1}
    ]
    assert tasks["T3"]["decision_premises"] == [
        {"decision_key": KEY_GUI, "derived_from_decision_id": D_GUI_V1}
    ]

    exec2.confirmed_clarifications = load_confirmed_clarifications_for_mission(
        recorded["mission_id"],
        store=mission_store,
    )
    seed_orchestrator_from_handoff(exec2, packet)

    supersede_decision(
        exec2,
        D_JSON_V1,
        {
            "decision_id": D_JSON_V2,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "Markdown",
            "dimension": "acceptance",
        },
        execution_id=exec2.execution_id,
    )

    assert exec2.runtime.tasks["gh-T1"].revalidation is None
    assert exec2.runtime.tasks["gh-T2"].revalidation["needs_revalidation"] is True
    assert exec2.runtime.tasks["gh-T3"].revalidation["needs_revalidation"] is False
    assert [row["task_id"] for row in tasks_needing_revalidation(exec2)] == ["gh-T2"]

    active = [
        row
        for row in exec2.confirmed_clarifications
        if row.get("status") != DECISION_STATUS_SUPERSEDED
        and row.get("decision_key") == KEY_JSON
    ]
    assert len(active) == 1
    assert active[0]["decision_id"] == D_JSON_V2
    assert active[0]["text"] == "Markdown"
