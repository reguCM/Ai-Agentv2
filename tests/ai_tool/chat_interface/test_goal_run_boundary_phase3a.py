from __future__ import annotations

import json

import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.requirement_decomposition import RequirementDecomposition, RequirementStatus
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_REQUIREMENTS_RESOLVED,
    RequirementResolutionBundle,
    StructuredRequirement,
)
from ai_tool.dev_skill_pipeline import build_handoff_packet, validate_handoff_packet


def _packet(*, goal: str, meaning: str, path: str, slug: str) -> dict:
    packet = build_handoff_packet(
        initial_request=goal,
        aligned_spec={
            "summary": goal,
            "numbered_conditions": [meaning, "Pythonのみを使用する"],
            "non_goals": ["仕様外の機能は含めない"],
            "acceptance_criteria": [meaning],
        },
        prd_rel="design/prd.md",
        tech_spec_rel="design/tech-spec.md",
        plan_rel="design/plan.md",
        todo_rel="design/todo.md",
        tech_spec={"summary": meaning, "modules": [{"path": path}]},
        plan={
            "tasks": [
                {
                    "id": "T1",
                    "title": meaning,
                    "acceptance": [meaning],
                    "verification": ["仕様との一致を確認する"],
                    "affected_paths": [path],
                    "decision_premises": [
                        {
                            "decision_key": "quality:definition",
                            "derived_from_decision_id": "decision-quality-v1",
                        }
                    ],
                    "size": "S",
                    "dependencies": [],
                }
            ]
        },
        skill_steps=["write-prd", "tech-spec", "planning-and-task-breakdown", "goal-handoff"],
        handoff_slug=slug,
    )
    assert not validate_handoff_packet(packet)
    return packet


def _isolate_session(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission-memory",
    )


def test_goal_without_content_returns_usage_and_does_not_start_runtime(monkeypatch, tmp_path):
    _isolate_session(monkeypatch, tmp_path)
    session = empty_session()
    result = run_chat_turn(session, "/goal", model="test")
    assert result["answer"] == "/goal <達成したい内容>"
    assert result["runtime_started"] is False
    assert result["task_runtime"] is None


def test_run_without_saved_handoff_fails_closed(monkeypatch, tmp_path):
    _isolate_session(monkeypatch, tmp_path)
    session = empty_session()
    result = run_chat_turn(session, "/run", model="test")
    assert result["production_run_error"] == "missing_or_invalid_handoff"
    assert result["runtime_prepared"] is False
    assert result["runtime_started"] is False
    assert result["task_runtime"] is None


def test_goal_command_reuses_specification_path_and_stops_with_saved_handoff(monkeypatch, tmp_path):
    _isolate_session(monkeypatch, tmp_path)
    request = "高品質なテトリスを作って"
    quality = "操作応答が良く、基本ルールが正しく動き、見た目も最低限整っている"
    packet = _packet(goal=request, meaning=quality, path="game/main.py", slug="phase3a-goal")
    bundle = RequirementResolutionBundle(
        original_goal=request,
        structured_requirements=[
            StructuredRequirement(
                requirement_id="req-quality",
                source_text="高品質な",
                source_span=[0, 5],
                disposition="AMBIGUOUS_REQUIREMENT",
                resolution_status="resolved",
                provenance="human_confirmed",
                materiality="blocks_design",
                normalized_meaning=quality,
            ),
            StructuredRequirement(
                requirement_id="req-goal",
                source_text="テトリスを作って",
                source_span=[5, len(request)],
                disposition="GOAL",
                resolution_status="resolved",
                provenance="user_explicit",
                materiality="blocks_design",
                normalized_meaning="テトリスを作る",
            ),
        ],
        requirement_resolution_phase=PHASE_REQUIREMENTS_RESOLVED,
    )
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition([], RequirementStatus.READY.value),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.prepare_implementation_entry_bundle",
        lambda text, **_kwargs: captured.setdefault("request", text) and bundle,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.should_run_semantic_revalidation_gate",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_grill_phase1",
        lambda **_kwargs: {
            "status": "aligned",
            "aligned_spec": {
                "summary": request,
                "numbered_conditions": [quality, "テトリスを作る"],
                "non_goals": [],
                "acceptance_criteria": [quality],
            },
            "generated_aligned_spec": {},
            "semantic_preservation": {"final": {"status": "preserved"}},
            "ambiguity_report": {},
        },
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_spec_handoff_pipeline",
        lambda **_kwargs: {
            "production_status": "SPEC_AND_HANDOFF_READY",
            "prd": {"goals": quality},
            "tech_spec": {"summary": quality},
            "plan": {"tasks": packet["implementation_tasks"]},
            "handoff_packet": packet,
            "semantic_trace": {"handoff": "PRESERVED"},
            "runtime_started": False,
        },
    )
    session = empty_session()

    result = run_chat_turn(session, f"/goal {request}", model="test")

    assert captured["request"] == request
    assert result["handoff_packet"] == packet
    assert result["runtime_started"] is False
    assert result["task_runtime"] is None
    assert session["production_handoff_packet"] == packet


@pytest.mark.parametrize(
    ("goal", "meaning", "path", "slug"),
    [
        (
            "高品質なテトリスを作って",
            "操作応答が良く、基本ルールが正しく動き、見た目も最低限整っている",
            "game/main.py",
            "phase3a-tetris",
        ),
        (
            "PythonでCLIの四則演算電卓を作って",
            "Pythonで動くCLI四則演算電卓を作る",
            "calculator/main.py",
            "phase3a-calculator",
        ),
    ],
)
def test_run_prepares_exact_saved_handoff_without_regeneration_or_execution(
    monkeypatch,
    tmp_path,
    goal,
    meaning,
    path,
    slug,
):
    _isolate_session(monkeypatch, tmp_path)
    packet = _packet(goal=goal, meaning=meaning, path=path, slug=slug)
    saved_json = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    session = empty_session()
    session["last_mission_id"] = "m-phase3a"
    session["production_handoff_packet"] = packet

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_handoff_pipeline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("handoff regenerated")),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._chat_turn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("agent loop started")),
    )

    result = run_chat_turn(session, "/run", model="test")

    assert result["runtime_prepared"] is True
    assert result["runtime_started"] is False
    assert result["sandbox_started"] is False
    assert result["handoff_packet"] == packet
    assert json.dumps(packet, ensure_ascii=False, sort_keys=True) == saved_json
    assert result["handoff_integrity"]["handoff_id"] == packet["handoff_id"]
    assert result["handoff_integrity"]["canonical_hash_equal"] is True
    assert result["handoff_integrity"]["immutable_fields_equal"] is True
    runtime = result["task_runtime"]
    assert runtime["sandbox_session"] is None
    assert all(row["status"] == "pending" for row in runtime["tasks"])
    rendered = json.dumps(result, ensure_ascii=False)
    assert meaning in rendered
    assert path in rendered
    assert "quality:definition" in rendered
    if "電卓" in goal:
        assert "Tetris" not in rendered
        assert "テトリス" not in rendered
        assert "tetris/main.py" not in rendered
