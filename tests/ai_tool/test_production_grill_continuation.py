from __future__ import annotations

import json

from ai_tool.grill_me_loop import format_production_prior_context
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version
from ai_tool.production_handoff_bridge import (
    apply_production_grill_human_answer,
    run_production_grill_phase1,
    run_production_spec_handoff_pipeline,
)


QUALITY = "操作応答が良く、基本ルールが正しく動き、見た目も最低限整っている"


def _response(payload: dict):
    content = json.dumps(payload, ensure_ascii=False)
    return type("R", (), {"message": type("M", (), {"content": content})()})()


def _messages(kwargs: dict) -> tuple[str, str]:
    rows = kwargs.get("messages") or []
    system = "\n".join(str(row.get("content") or "") for row in rows if row.get("role") == "system")
    user = "\n".join(str(row.get("content") or "") for row in rows if row.get("role") == "user")
    return system, user


def _mission(mission_id: str = "m-quality") -> dict:
    return {
        "schema_version": schema_version(),
        "mission_id": mission_id,
        "original_goal": "高品質なテトリスを作って",
        "explicit_conditions": [QUALITY, "テトリスを作る"],
        "explicit_constraints": [],
        "user_confirmed_supplements": [
            {"text": QUALITY, "source": "requirement_resolution"}
        ],
        "confirmed_clarifications": [],
        "structured_requirements": [
            {
                "requirement_id": "req-quality",
                "source_text": "高品質な",
                "source_span": [0, 5],
                "disposition": "AMBIGUOUS_REQUIREMENT",
                "resolution_status": "resolved",
                "provenance": "human_confirmed",
                "materiality": "blocks_design",
                "normalized_meaning": QUALITY,
            },
            {
                "requirement_id": "req-goal",
                "source_text": "テトリスを作って",
                "source_span": [5, 14],
                "disposition": "GOAL",
                "resolution_status": "resolved",
                "provenance": "user_explicit",
                "materiality": "blocks_design",
                "normalized_meaning": "テトリスを作る",
            },
        ],
        "requirement_resolution_phase": "REQUIREMENTS_RESOLVED",
    }


def test_prior_context_uses_mission_canonical_requirement_fields():
    mission = _mission()
    rendered = format_production_prior_context(
        mission["structured_requirements"], mission["confirmed_clarifications"]
    )
    assert "高品質な" in rendered
    assert QUALITY in rendered
    assert "human_confirmed" in rendered
    assert "blocks_design" in rendered


def test_unresolved_dimension_returns_one_human_ui_question_without_reasking_quality(tmp_path):
    store = MissionMemoryStore(tmp_path / "memory")
    mission = _mission()
    store.put_mission(mission)
    calls: list[dict] = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        system, _ = _messages(kwargs)
        if "scoring a grill-me interview" in system:
            return _response(
                {
                    "dimensions": {"goals": 0, "acceptance": 0.75, "boundaries": 0, "alternatives": 0, "assumptions": 0},
                    "aggregate": 0.25,
                    "weakest": ["acceptance"],
                    "ready_to_exit": False,
                    "aligned_spec": {},
                }
            )
        if "semantic duplicate-question auditor" in system:
            return _response({"reasks_resolved": False, "reason": "new acceptance detail"})
        return _response(
            {
                "question": "完成と判定する具体的な確認項目を指定してください。",
                "recommended_answer": "基本ルール、操作応答、最低限の表示を確認する",
                "dimension": "acceptance",
            }
        )

    step = run_production_grill_phase1(mission=mission, chat_fn=fake_chat, model="test", store=store)
    assert step["status"] == "awaiting_human"
    assert step["question_contract"]["question"].startswith("完成と判定")
    assert step["question_contract"]["decision_key"] == "spec:acceptance"
    assert QUALITY in _messages(calls[0])[1]
    assert "LOCKED" in _messages(calls[1])[0]
    assert "semantic duplicate-question auditor" in _messages(calls[2])[0]
    assert "高品質とは" not in step["question_contract"]["question"]


def test_human_answer_persists_then_resume_aligns_and_preserves_requirement_meaning(tmp_path):
    store = MissionMemoryStore(tmp_path / "memory")
    mission = _mission()
    store.put_mission(mission)
    state = {
        "mission_id": mission["mission_id"],
        "original_request": mission["original_goal"],
        "transcript": [],
        "active_contract": {
            "question_id": "production_grill_me:r1",
            "question": "完成条件は？",
            "dimension": "acceptance",
            "decision_key": "spec:acceptance",
            "decision_subject": "acceptance",
        },
    }
    answer = "基本ルール、操作応答、最低限の表示を確認できれば完成"
    updated, resumed = apply_production_grill_human_answer(state, answer, store=store)
    decision = updated["confirmed_clarifications"][-1]
    assert decision["text"] == answer
    assert decision["source"] == "grill"
    assert decision["human_confirmed"] is True
    assert decision["auto_selected"] is False
    assert resumed["transcript"][-1]["selected_answer"] == answer

    downstream_chat = _phase2_chat(QUALITY, "game/main.py")

    def aligned_chat(**kwargs):
        system, _ = _messages(kwargs)
        if "scoring a grill-me interview" not in system:
            return downstream_chat(**kwargs)
        return _response(
            {
                "dimensions": {"goals": 0, "acceptance": 0, "boundaries": 0, "alternatives": 0, "assumptions": 0},
                "aggregate": 0,
                "weakest": [],
                "ready_to_exit": True,
                "aligned_spec": {
                    "summary": "テトリスを実装する",
                    "numbered_conditions": [answer],
                    "non_goals": [],
                    "acceptance_criteria": [answer],
                },
            }
        )

    step = run_production_grill_phase1(
        mission=updated,
        transcript=resumed["transcript"],
        chat_fn=aligned_chat,
        model="test",
        store=store,
    )
    assert step["status"] == "aligned"
    assert step["semantic_preservation"]["generated"]["status"] == "missing"
    assert step["semantic_preservation"]["final"]["status"] == "preserved"
    assert step["semantic_preservation"]["canonical_projection_applied"] is True
    generated_represented = (
        step["generated_aligned_spec"]["numbered_conditions"]
        + step["generated_aligned_spec"]["acceptance_criteria"]
    )
    assert QUALITY not in generated_represented
    represented = step["aligned_spec"]["numbered_conditions"] + step["aligned_spec"]["acceptance_criteria"]
    assert QUALITY in represented
    persisted = store.get_mission(mission["mission_id"])
    quality = next(row for row in persisted["structured_requirements"] if row["requirement_id"] == "req-quality")
    assert quality["normalized_meaning"] == QUALITY
    assert quality["provenance"] == "human_confirmed"


def test_generated_quality_meaning_passes_without_canonical_projection():
    mission = _mission()
    goal_meaning = mission["structured_requirements"][1]["normalized_meaning"]

    def aligned_chat(**_kwargs):
        return _response(
            {
                "dimensions": {"goals": 0, "acceptance": 0, "boundaries": 0, "alternatives": 0, "assumptions": 0},
                "aggregate": 0,
                "weakest": [],
                "ready_to_exit": True,
                "aligned_spec": {
                    "title": "Tetris",
                    "summary": mission["original_goal"],
                    "numbered_conditions": [QUALITY, goal_meaning],
                    "non_goals": [],
                    "acceptance_criteria": [QUALITY],
                },
            }
        )

    step = run_production_grill_phase1(mission=mission, chat_fn=aligned_chat, model="test")
    assert step["semantic_preservation"]["generated"]["status"] == "preserved"
    assert step["semantic_preservation"]["final"]["status"] == "preserved"
    assert step["semantic_preservation"]["canonical_projection_applied"] is False
    assert step["generated_aligned_spec"] == step["aligned_spec"]


def test_semantic_duplicate_question_is_rejected_before_human_ui():
    mission = _mission()
    question_round = {"n": 0}

    def fake_chat(**kwargs):
        system, user = _messages(kwargs)
        if "scoring a grill-me interview" in system:
            return _response(
                {
                    "dimensions": {"goals": 0.5, "acceptance": 0.5, "boundaries": 0, "alternatives": 0, "assumptions": 0},
                    "aggregate": 0.25,
                    "weakest": ["goals", "acceptance"],
                    "ready_to_exit": False,
                    "aligned_spec": {},
                }
            )
        if "semantic duplicate-question auditor" in system:
            duplicate = "高品質の意味" in user
            return _response({"reasks_resolved": duplicate, "reason": "duplicate" if duplicate else "new"})
        question_round["n"] += 1
        if question_round["n"] == 1:
            return _response(
                {
                    "question": "高品質の意味を具体化してください。",
                    "recommended_answer": QUALITY,
                    "dimension": "goals",
                }
            )
        return _response(
            {
                "question": "対象外にする機能を指定してください。",
                "recommended_answer": "ネットワーク対戦は対象外",
                "dimension": "boundaries",
            }
        )

    step = run_production_grill_phase1(mission=mission, chat_fn=fake_chat, model="test")
    assert step["status"] == "awaiting_human"
    assert step["question_contract"]["question"].startswith("対象外")
    assert question_round["n"] == 2


def test_clear_calculator_can_align_without_unnecessary_question():
    mission = _mission("m-calculator")
    mission["original_goal"] = "PythonでCLIの四則演算電卓を作って"
    mission["structured_requirements"] = [
        {
            "requirement_id": "req-calculator",
            "source_text": mission["original_goal"],
            "source_span": [0, len(mission["original_goal"])],
            "disposition": "GOAL",
            "resolution_status": "resolved",
            "provenance": "user_explicit",
            "materiality": "blocks_design",
            "normalized_meaning": "Pythonで動くCLI四則演算電卓を作る",
        }
    ]
    calls = {"count": 0}

    def clear_chat(**_kwargs):
        calls["count"] += 1
        return _response(
            {
                "dimensions": {"goals": 0, "acceptance": 0, "boundaries": 0, "alternatives": 0, "assumptions": 0},
                "aggregate": 0,
                "weakest": [],
                "ready_to_exit": True,
                "aligned_spec": {
                    "summary": mission["original_goal"],
                    "numbered_conditions": ["Pythonで動くCLI四則演算電卓を作る"],
                    "non_goals": [],
                    "acceptance_criteria": ["四則演算が正しい"],
                },
            }
        )

    step = run_production_grill_phase1(mission=mission, chat_fn=clear_chat, model="test")
    assert step["status"] == "aligned"
    assert step["question_contract"] is None
    assert calls["count"] == 1


def test_production_chat_receives_human_answer_and_resumes_phase1(monkeypatch, tmp_path):
    root = tmp_path / "memory"
    monkeypatch.setattr("ai_tool.mission_memory.store.default_store_root", lambda: root)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    store = MissionMemoryStore(root)
    mission = _mission("m-chat-resume")
    store.put_mission(mission)
    session = empty_session()
    session["awaiting_production_grill_me"] = True
    session["production_grill_me_state"] = {
        "mission_id": mission["mission_id"],
        "original_request": mission["original_goal"],
        "transcript": [],
        "active_contract": {
            "question_id": "production_grill_me:r1",
            "question": "完成条件は？",
            "dimension": "acceptance",
            "decision_key": "spec:acceptance",
            "decision_subject": "acceptance",
        },
    }
    answer = "基本ルール、操作応答、最低限の表示を確認できれば完成"
    downstream_chat = _phase2_chat(QUALITY, "game/main.py")

    def aligned_chat(**kwargs):
        system, _ = _messages(kwargs)
        if "scoring a grill-me interview" not in system:
            return downstream_chat(**kwargs)
        return _response(
            {
                "dimensions": {"goals": 0, "acceptance": 0, "boundaries": 0, "alternatives": 0, "assumptions": 0},
                "aggregate": 0,
                "weakest": [],
                "ready_to_exit": True,
                "aligned_spec": {
                    "summary": "テトリスを実装する",
                    "numbered_conditions": [answer],
                    "non_goals": [],
                    "acceptance_criteria": [answer],
                },
            }
        )

    result = run_chat_turn(session, answer, chat_fn=aligned_chat, model="test")
    assert result["awaiting_production_grill_me"] is False
    assert result["aligned_spec"]
    assert result["handoff_packet"]
    assert result["runtime_started"] is False
    assert session["production_grill_me_state"] is None
    assert session["production_aligned_spec"] == result["aligned_spec"]
    persisted = store.get_mission(mission["mission_id"])
    assert persisted["confirmed_clarifications"][-1]["text"] == answer


def test_production_spec_handoff_preserves_quality_and_does_not_start_runtime(tmp_path):
    quality = "操作応答が良く、基本ルールが正しく動き、見た目も最低限整っている"
    mission = _mission("m-phase2-quality")
    mission["original_goal"] = "高品質なテトリスを作って"
    mission["structured_requirements"][0]["source_text"] = "高品質な"
    mission["structured_requirements"][0]["normalized_meaning"] = quality
    mission["structured_requirements"][1]["source_text"] = "テトリスを作って"
    mission["structured_requirements"][1]["normalized_meaning"] = "テトリスを作る"
    aligned = {
        "summary": mission["original_goal"],
        "numbered_conditions": [quality, "テトリスを作る"],
        "non_goals": ["ネットワーク対戦は含めない"],
        "acceptance_criteria": [quality],
    }
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(mission)

    result = run_production_spec_handoff_pipeline(
        mission_id=mission["mission_id"],
        initial_request=mission["original_goal"],
        aligned_spec=aligned,
        chat_fn=_phase2_chat(f"{quality}。テトリスを作る", "game/main.py"),
        model="test",
        store=store,
        output_dir=tmp_path / "output",
    )

    assert result["production_status"] == "SPEC_AND_HANDOFF_READY"
    assert result["runtime_started"] is False
    assert set(result["semantic_trace"].values()) == {"PRESERVED"}
    assert quality in json.dumps(result["handoff_packet"], ensure_ascii=False)
    assert result["handoff_packet"]["runtime_boundary"]["production_connected"] is False


def test_production_spec_handoff_calculator_has_no_tetris_fallback(tmp_path):
    meaning = "Pythonで動くCLI四則演算電卓を作る"
    mission = _mission("m-phase2-calculator")
    mission["original_goal"] = "PythonでCLIの四則演算電卓を作って"
    mission["structured_requirements"] = [
        {
            "requirement_id": "req-calculator",
            "source_text": mission["original_goal"],
            "source_span": [0, len(mission["original_goal"])],
            "disposition": "GOAL",
            "resolution_status": "resolved",
            "provenance": "user_explicit",
            "materiality": "blocks_design",
            "normalized_meaning": meaning,
        }
    ]
    aligned = {
        "summary": mission["original_goal"],
        "numbered_conditions": [meaning],
        "non_goals": [],
        "acceptance_criteria": [meaning],
    }
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(mission)

    result = run_production_spec_handoff_pipeline(
        mission_id=mission["mission_id"],
        initial_request=mission["original_goal"],
        aligned_spec=aligned,
        chat_fn=_phase2_chat(meaning, "calculator/main.py"),
        model="test",
        store=store,
        output_dir=tmp_path / "output",
    )

    rendered = json.dumps(result, ensure_ascii=False).lower()
    assert "tetris" not in rendered
    assert "テトリス" not in rendered
    assert "calculator/main.py" in rendered
    assert result["runtime_started"] is False


def _phase2_chat(meaning: str, target_path: str):
    def fake_chat(**kwargs):
        _, user = _messages(kwargs)
        if "Emit PRD_JSON" in user:
            return _response(
                {
                    "title": "Approved requirement PRD",
                    "problem": meaning,
                    "goals": meaning,
                    "requirements": meaning,
                    "non_goals": "Out of scope work",
                    "constraints": "Do not start Runtime",
                    "acceptance_criteria": [meaning],
                }
            )
        if "Emit TECH_SPEC_JSON" in user:
            return _response(
                {
                    "summary": meaning,
                    "modules": [{"path": target_path, "responsibility": meaning}],
                    "sequencing": [meaning],
                    "sandbox_constraints": "Do not start Runtime",
                    "implementation_tasks": [{"id": "T1", "title": meaning, "acceptance": [meaning], "size": "S"}],
                }
            )
        if "Emit PLAN_JSON" in user:
            return _response(
                {
                    "plan_markdown": f"# Plan\n\n{meaning}",
                    "todo_markdown": f"- [ ] T1 {meaning}",
                    "tasks": [{"id": "T1", "title": meaning, "acceptance": [meaning], "verification": [meaning], "affected_paths": [target_path], "size": "S", "dependencies": []}],
                }
            )
        raise AssertionError(f"unexpected Phase 2 prompt: {user[:100]}")

    return fake_chat
