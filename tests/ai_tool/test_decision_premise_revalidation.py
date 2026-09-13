"""Decision premise revalidation after Human Decision supersede."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    supersede_decision,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.decision_premise_revalidation import (
    build_premise_revalidation_case,
    run_premise_revalidations,
)
from ai_tool.dev_skill_pipeline import normalize_implementation_tasks
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.human_decision_premise import tasks_needing_revalidation
from ai_tool.mission_memory.chat_persist import bind_execution_identity, persist_chat_execution
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.production_handoff_bridge import build_production_handoff_packet, prepare_production_handoff_orchestrator
from tests.ai_tool.test_production_handoff_decision_supply import (
    D_GUI_V1,
    D_JSON_V1,
    D_JSON_V2,
    KEY_GUI,
    KEY_JSON,
    _decisions,
    _plan_tasks,
)


@pytest.fixture
def mission_store(tmp_path, monkeypatch):
    root = tmp_path / "mission_memory"
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: root,
    )
    return MissionMemoryStore(root)


def _response_json(payload: dict):
    import json

    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))


def _chat_fixed(payload: dict):
    def chat(**_kwargs):
        return _response_json(payload)

    return chat


def _seed_handoff_orchestrator(mission_store) -> ChatTaskOrchestrator:
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
    prepare_production_handoff_orchestrator(exec2, store=mission_store)
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
        store=mission_store,
        handoff_slug="revalidation-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    return exec2


def test_json_task_revalidated_as_needs_revision_after_markdown_supersede(mission_store):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    supersede_decision(
        orchestrator,
        D_JSON_V1,
        {
            "decision_id": D_JSON_V2,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "Markdown",
            "dimension": "acceptance",
        },
        execution_id=orchestrator.execution_id,
    )
    assert [row["task_id"] for row in tasks_needing_revalidation(orchestrator)] == ["gh-T2"]

    case = build_premise_revalidation_case(orchestrator, "gh-T2")
    assert case is not None
    assert case["missing_fields"] == []
    assert case["premise_pairs"][0]["active_decision"]["text"] == "Markdown"

    results = run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed(
            {
                "outcome": "needs_revision",
                "reason": "Task requires JSON output but active decision is Markdown.",
            }
        ),
        model="fake",
    )
    assert len(results) == 1
    assert results[0]["task_id"] == "gh-T2"
    assert results[0]["outcome"] == "needs_revision"
    task = orchestrator.runtime.tasks["gh-T2"]
    assert task.status in {"pending", "in_progress"}
    assert task.revalidation["needs_revalidation"] is True
    assert task.revalidation["premise_revalidation"]["outcome"] == "needs_revision"
    assert task.revalidation["premise_revalidation"]["active_decision_ids"][KEY_JSON] == D_JSON_V2
    assert task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V1


def test_premise_provenance_persists_through_supersede_revalidate_resupersede_cycle(mission_store):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    task = orchestrator.runtime.tasks["gh-T2"]
    assert task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V1
    assert task.revalidation["needs_revalidation"] is False

    supersede_decision(
        orchestrator,
        D_JSON_V1,
        {
            "decision_id": D_JSON_V2,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "Markdown",
            "dimension": "acceptance",
        },
        execution_id=orchestrator.execution_id,
    )
    assert task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V1
    assert task.revalidation["needs_revalidation"] is True
    assert task.revalidation["stale_decision_ids"] == [D_JSON_V1]

    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed(
            {
                "outcome": "still_valid",
                "reason": "Markdown output still satisfies this task.",
            }
        ),
        model="fake",
    )
    assert task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V2
    assert task.revalidation["needs_revalidation"] is False

    supersede_decision(
        orchestrator,
        D_JSON_V2,
        {
            "decision_id": "d-json-v3",
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "YAML",
            "dimension": "acceptance",
        },
        execution_id=orchestrator.execution_id,
    )
    assert task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V2
    assert task.revalidation["needs_revalidation"] is True
    assert task.revalidation["stale_decision_ids"] == [D_JSON_V2]


def test_unaffected_gui_task_stays_valid_and_clears_revalidation_when_semantically_stable(
    mission_store,
):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    gui_task = orchestrator.runtime.tasks["gh-T3"]
    gui_task.revalidation = {
        "needs_revalidation": True,
        "affected": True,
        "decision_premises": gui_task.decision_premises,
        "stale_decision_ids": [D_GUI_V1],
        "active_decision_ids": {KEY_GUI: D_GUI_V1},
    }
    results = run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed(
            {
                "outcome": "still_valid",
                "reason": "GUI scope decision still supports this task.",
            }
        ),
        model="fake",
    )
    assert len(results) == 1
    assert results[0]["outcome"] == "still_valid"
    assert orchestrator.runtime.tasks["gh-T3"].revalidation["needs_revalidation"] is False
    assert orchestrator.runtime.tasks["gh-T3"].revalidation["premise_revalidation"]["outcome"] == "still_valid"
    assert [row["task_id"] for row in tasks_needing_revalidation(orchestrator)] == []
