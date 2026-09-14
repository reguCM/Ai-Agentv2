"""Production Handoff coverage for canonical Constraint Requirements."""
from __future__ import annotations

import json
import re

from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version
from ai_tool.production_handoff_bridge import run_production_spec_handoff_pipeline


def _response(payload: dict):
    content = json.dumps(payload, ensure_ascii=False)
    return type("Response", (), {"message": type("Message", (), {"content": content})()})()


def _phase2_chat(**kwargs):
    user = "\n".join(
        str(row.get("content") or "")
        for row in (kwargs.get("messages") or [])
        if row.get("role") == "user"
    )
    if "Emit PRD_JSON" in user:
        return _response(
            {
                "title": "Tetris PRD",
                "problem": "Build a Tetris game. Do not delete existing files.",
                "goals": "Build a Tetris game.",
                "requirements": "Build a Tetris game. Do not delete existing files.",
                "non_goals": "Do not start Runtime.",
                "constraints": "Do not delete existing files.",
                "acceptance_criteria": ["Build a Tetris game. Do not delete existing files."],
            }
        )
    if "Emit TECH_SPEC_JSON" in user:
        return _response(
            {
                "summary": "Build a Tetris game. Do not delete existing files.",
                "modules": [{"path": "tetris/main.py", "responsibility": "Build a Tetris game."}],
                "sequencing": ["Do not delete existing files."],
                "sandbox_constraints": "Do not delete existing files.",
                "implementation_tasks": [
                    {
                        "id": "T1",
                        "title": "Implement Tetris without deleting existing files",
                        "acceptance": ["Build a Tetris game. Do not delete existing files."],
                        "size": "S",
                    }
                ],
            }
        )
    if "Emit PLAN_JSON" in user:
        requirement_ids = list(
            dict.fromkeys(re.findall(r'"requirement_id"\s*:\s*"([^"]+)"', user))
        )
        return _response(
            {
                "plan_markdown": "# Plan\n\nBuild a Tetris game. Do not delete existing files.",
                "todo_markdown": "- [ ] T1 Build a Tetris game. Do not delete existing files.",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "Implement Tetris without deleting existing files",
                        "acceptance": ["Build a Tetris game. Do not delete existing files."],
                        "verification": ["Build a Tetris game. Do not delete existing files."],
                        "affected_paths": ["tetris/main.py"],
                        "size": "S",
                        "dependencies": [],
                    }
                ],
                "requirement_bindings": [
                    {"requirement_id": requirement_id, "task_ids": ["T1"], "acceptance_ids": ["A1"]}
                    for requirement_id in requirement_ids
                ],
            }
        )
    raise AssertionError(f"unexpected Production pipeline prompt: {user[:100]}")


def test_production_handoff_binds_resolved_material_constraint_requirement(tmp_path):
    mission = {
        "schema_version": schema_version(),
        "mission_id": "m-production-constraint-binding",
        "original_goal": "Build a Tetris game without deleting existing files.",
        "explicit_conditions": ["Build a Tetris game."],
        "explicit_constraints": ["Do not delete existing files."],
        "user_confirmed_supplements": [],
        "confirmed_clarifications": [],
        "structured_requirements": [
            {
                "requirement_id": "req-goal",
                "source_text": "Build a Tetris game",
                "source_span": [0, 20],
                "disposition": "GOAL",
                "resolution_status": "resolved",
                "provenance": "user_explicit",
                "materiality": "blocks_design",
                "normalized_meaning": "Build a Tetris game.",
            },
            {
                "requirement_id": "req-constraint",
                "source_text": "without deleting existing files",
                "source_span": [21, 52],
                "disposition": "CONSTRAINT",
                "constraint_subtype": "prohibition",
                "resolution_status": "resolved",
                "provenance": "user_explicit",
                "materiality": "blocks_design",
                "normalized_meaning": "Do not delete existing files.",
            },
        ],
        "requirement_resolution_phase": "REQUIREMENTS_RESOLVED",
    }
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(mission)

    result = run_production_spec_handoff_pipeline(
        mission_id=mission["mission_id"],
        initial_request=mission["original_goal"],
        aligned_spec={
            "summary": mission["original_goal"],
            "numbered_conditions": [
                "Build a Tetris game.",
                "Do not delete existing files.",
            ],
            "non_goals": [],
            "acceptance_criteria": ["Build a Tetris game. Do not delete existing files."],
        },
        chat_fn=_phase2_chat,
        model="test",
        store=store,
        output_dir=tmp_path / "output",
    )

    handoff = result["handoff_packet"]
    constraint_binding = next(
        row
        for row in handoff["requirement_bindings"]
        if row["requirement_id"] == "req-constraint"
    )
    assert constraint_binding == {
        "requirement_id": "req-constraint",
        "task_ids": ["T1"],
        "acceptance_ids": ["A1"],
    }
    assert handoff["source_binding"]["requirement_ids"] == [
        "req-constraint",
        "req-goal",
    ]
    assert result["runtime_started"] is False
