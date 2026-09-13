"""Premise revalidation persistence across execution resume and supersede cycles."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    supersede_decision,
)
from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityId,
    GapResolutionDecision,
    build_goal_continuation_resume,
)
from ai_tool.chat_interface.goal_continuation_resume import (
    restore_orchestrator_from_goal_continuation,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.decision_premise_revalidation import run_premise_revalidations
from ai_tool.dev_skill_pipeline import normalize_implementation_tasks
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.human_decision_premise import tasks_needing_revalidation
from ai_tool.mission_memory.chat_persist import bind_execution_identity, persist_chat_execution
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.production_handoff_bridge import (
    build_production_handoff_packet,
    prepare_production_handoff_orchestrator,
)
from tests.ai_tool.test_production_handoff_decision_supply import (
    D_JSON_V1,
    D_JSON_V2,
    KEY_JSON,
    _decisions,
    _plan_tasks,
)

D_JSON_V3 = "d-json-v3"


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
        handoff_slug="revalidation-persist-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    return exec2


def test_revalidation_semantics_persist_through_goal_continuation_resume(mission_store):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    task = orchestrator.runtime.tasks["gh-T2"]
    assert task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V1

    chat = _chat_fixed(
        {
            "outcome": "still_valid",
            "reason": "Markdown output still satisfies this task.",
        }
    )
    llm_calls: list[dict] = []

    def counting_chat(**kwargs):
        llm_calls.append(kwargs)
        return chat(**kwargs)

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
        chat_fn=counting_chat,
        run_premise_revalidation=True,
    )
    assert len(llm_calls) == 1
    assert task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V2
    assert task.revalidation["premise_revalidation"]["outcome"] == "still_valid"
    assert task.revalidation["premise_revalidation"]["evaluated_against_decision_ids"] == {
        KEY_JSON: D_JSON_V2,
    }

    persist_chat_execution(
        orchestrator,
        stop_reason="PREMISE_REVALIDATED",
        determined=True,
        answer="premise revalidated",
        store=mission_store,
    )
    mission_runtime = mission_store.get_mission(orchestrator.mission_id)
    assert mission_runtime is not None
    assert mission_runtime.get("completion_runtime") is not None

    packet = build_goal_continuation_resume(
        orchestrator,
        decision=GapResolutionDecision(
            gap_kind="spec_meaning_gap",
            gap_resolved=False,
            winner=CapabilityId.TOOL_EVIDENCE.value,
        ),
        recorded={"mission_id": orchestrator.mission_id, "execution_id": orchestrator.execution_id},
        correlation_id="resume-1",
    )
    packet["completion_runtime"] = {"tasks": [], "goals": []}
    resumed = restore_orchestrator_from_goal_continuation("resume-1", packet)
    resumed_task = resumed.runtime.tasks["gh-T2"]
    assert resumed_task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert resumed_task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V2
    assert resumed_task.revalidation["needs_revalidation"] is False
    assert resumed_task.revalidation["premise_revalidation"]["outcome"] == "still_valid"
    assert resumed_task.revalidation["premise_revalidation"]["evaluated_against_decision_ids"] == {
        KEY_JSON: D_JSON_V2,
    }

    llm_calls.clear()
    assert run_premise_revalidations(resumed, chat_fn=counting_chat, model="fake") == []
    assert llm_calls == []
    assert [row["task_id"] for row in tasks_needing_revalidation(resumed)] == []

    supersede_decision(
        resumed,
        D_JSON_V2,
        {
            "decision_id": D_JSON_V3,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "YAML",
            "dimension": "acceptance",
        },
        execution_id=resumed.execution_id,
    )
    assert resumed_task.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert resumed_task.decision_premises[0]["validated_against_decision_id"] == D_JSON_V2
    assert resumed_task.revalidation["needs_revalidation"] is True
    assert resumed_task.revalidation["stale_decision_ids"] == [D_JSON_V2]

    llm_calls.clear()
    results = run_premise_revalidations(
        resumed,
        chat_fn=counting_chat,
        model="fake",
    )
    assert len(results) == 1
    assert len(llm_calls) == 1
    assert results[0]["outcome"] == "still_valid"


def test_completion_runtime_restore_preserves_semantic_revalidation(mission_store):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    task = orchestrator.runtime.tasks["gh-T2"]
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

    snapshot = orchestrator.completion_runtime_slice()
    resumed = ChatTaskOrchestrator("completion-resume", orchestrator.request)
    resumed.confirmed_clarifications = list(orchestrator.confirmed_clarifications)
    resumed.apply_completion_runtime(snapshot, replace_graph=True)

    restored = resumed.runtime.tasks["gh-T2"]
    assert restored.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert restored.decision_premises[0]["validated_against_decision_id"] == D_JSON_V2
    assert restored.revalidation["needs_revalidation"] is False
    assert restored.revalidation["premise_revalidation"]["outcome"] == "still_valid"
    assert restored.revalidation["premise_revalidation"]["evaluated_against_decision_ids"] == {
        KEY_JSON: D_JSON_V2,
    }
