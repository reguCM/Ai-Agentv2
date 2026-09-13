from __future__ import annotations

import json
from pathlib import Path

from ai_tool.dev_skill_pipeline import (
    _aligned_spec_from_prd,
    build_handoff_packet,
    composition_steps,
    handoff_to_implementation_prompt,
    normalize_implementation_tasks,
    run_dev_skill_pipeline,
    validate_handoff_packet,
)
GRILL_ALIGNED = {
    "title": "Dedicated Sandbox 最小テトリス",
    "summary": "Dedicated Sandbox 内に最小テトリスを作成する。",
    "numbered_conditions": ["tetris/main.py exists in Dedicated Sandbox"],
    "non_goals": ["No production writes"],
    "acceptance_criteria": ["tetris/main.py exists"],
}


def _mock_chat(**kwargs):
    messages = kwargs.get("messages") or []
    system = str(messages[0]["content"]) if messages else ""
    user = str(messages[-1]["content"])
    if "Ask exactly ONE question" in system:
        return type(
            "Resp",
            (),
            {
                "message": type(
                    "Msg",
                    (),
                    {
                        "content": json.dumps(
                            {
                                "question": "Where should Tetris live?",
                                "recommended_answer": "Dedicated Sandbox tetris/main.py",
                                "dimension": "boundaries",
                                "rationale": "isolate from production",
                            },
                            ensure_ascii=False,
                        )
                    },
                )()
            },
        )()
    if "You are scoring" in system:
        return type(
            "Resp",
            (),
            {
                "message": type(
                    "Msg",
                    (),
                    {
                        "content": json.dumps(
                            {
                                "dimensions": {
                                    "goals": 0.0,
                                    "acceptance": 0.0,
                                    "boundaries": 0.0,
                                    "alternatives": 0.0,
                                    "assumptions": 0.0,
                                },
                                "aggregate": 0.0,
                                "weakest": [],
                                "ready_to_exit": True,
                                "aligned_spec": GRILL_ALIGNED,
                            },
                            ensure_ascii=False,
                        )
                    },
                )()
            },
        )()
    if "Emit PRD_JSON" in user:
        return type(
            "Resp",
            (),
            {
                "message": type(
                    "Msg",
                    (),
                    {
                        "content": json.dumps(
                            {
                                "title": "Tetris PRD",
                                "problem": "Need minimal Tetris",
                                "goals": "Console Tetris in Sandbox",
                                "requirements": "tetris/main.py",
                                "non_goals": "No production writes",
                                "constraints": "Dedicated Sandbox only",
                                "acceptance_criteria": ["tetris/main.py exists"],
                                "recommended_answer": "approve",
                            },
                            ensure_ascii=False,
                        )
                    },
                )()
            },
        )()
    if "Emit TECH_SPEC_JSON" in user:
        return type(
            "Resp",
            (),
            {
                "message": type(
                    "Msg",
                    (),
                    {
                        "content": json.dumps(
                            {
                                "summary": "Single-file console Tetris",
                                "modules": ["tetris/main.py"],
                                "sequencing": ["create file"],
                                "sandbox_constraints": "Dedicated Sandbox only",
                                "implementation_tasks": [
                                    {
                                        "id": "T1",
                                        "title": "Create tetris/main.py",
                                        "acceptance": ["file exists"],
                                        "size": "S",
                                    }
                                ],
                                "recommended_answer": "approve",
                            },
                            ensure_ascii=False,
                        )
                    },
                )()
            },
        )()
    if "Emit PLAN_JSON" in user:
        return type(
            "Resp",
            (),
            {
                "message": type(
                    "Msg",
                    (),
                    {
                        "content": json.dumps(
                            {
                                "plan_markdown": "# Plan\n\nCreate tetris/main.py",
                                "todo_markdown": "- [ ] T1",
                                "tasks": [
                                    {
                                        "id": "T1",
                                        "title": "Create tetris/main.py",
                                        "acceptance": ["file exists"],
                                        "verification": ["read_file tetris/main.py"],
                                        "size": "S",
                                        "dependencies": [],
                                    }
                                ],
                                "recommended_answer": "approve",
                            },
                            ensure_ascii=False,
                        )
                    },
                )()
            },
        )()
    raise AssertionError(f"Unexpected mock chat prompt: system={system[:80]} user={user[:80]}")


def test_composition_steps_include_tetris_pipeline() -> None:
    steps = composition_steps("tetris-sandbox-e2e")
    assert steps[0] == "write-prd"
    assert "grill-me" not in steps
    assert steps[-1] == "goal-handoff"


def test_aligned_spec_from_prd_builds_numbered_conditions() -> None:
    spec = _aligned_spec_from_prd(
        {
            "title": "Tetris",
            "goals": "Sandbox tetris",
            "acceptance_criteria": ["tetris/main.py exists"],
            "non_goals": "- no GUI",
        },
        "テトリスを作って",
    )
    assert spec["numbered_conditions"] == ["tetris/main.py exists"]
    assert spec["non_goals"] == ["no GUI"]


def test_build_handoff_packet_validates_from_prd() -> None:
    packet = build_handoff_packet(
        initial_request="テトリスを作って",
        prd={
            "title": "Tetris",
            "goals": "Sandbox tetris",
            "acceptance_criteria": ["tetris/main.py exists"],
            "non_goals": "- no GUI",
        },
        prd_rel="logs/x/design/prd.md",
        tech_spec_rel="logs/x/design/tech-spec.md",
        plan_rel="logs/x/design/plan.md",
        todo_rel="logs/x/design/todo.md",
        tech_spec={"summary": "sandbox tetris"},
        plan={"tasks": []},
        skill_steps=composition_steps("tetris-sandbox-e2e"),
    )
    assert not validate_handoff_packet(packet)
    prompt = handoff_to_implementation_prompt(packet)
    assert "tetris/main.py" in prompt


def test_build_handoff_packet_normalizes_dependencies() -> None:
    packet = build_handoff_packet(
        initial_request="テトリスを作って",
        prd={"title": "Tetris", "acceptance_criteria": ["ok"]},
        prd_rel="prd.md",
        tech_spec_rel="tech.md",
        plan_rel="plan.md",
        todo_rel="todo.md",
        tech_spec={},
        plan={
            "tasks": [
                {"id": "T0", "title": "Foundation", "size": "S"},
                {
                    "id": "T0",
                    "title": "Integration",
                    "dependencies": ["1", "T1"],
                    "size": "M",
                },
            ]
        },
        skill_steps=["write-prd"],
    )
    tasks = packet["implementation_tasks"]
    assert [task["id"] for task in tasks] == ["T1", "T2"]
    assert tasks[1]["dependencies"] == ["T1"]
    assert not validate_handoff_packet(packet)


def test_normalize_implementation_tasks_single_task() -> None:
    tasks = normalize_implementation_tasks(
        [{"id": 0, "title": "Only", "acceptance": ["ok"]}],
        default_acceptance=["fallback"],
        default_verification=["verify"],
    )
    assert len(tasks) == 1
    assert tasks[0]["id"] == "T1"
    assert tasks[0]["dependencies"] == []


def test_normalize_implementation_tasks_duplicate_llm_ids() -> None:
    tasks = normalize_implementation_tasks(
        [
            {"id": 0, "title": "A"},
            {"id": 0, "title": "B"},
            {"id": "T0", "title": "C"},
            {"id": 0, "title": "D"},
        ],
        default_acceptance=["fallback"],
        default_verification=["verify"],
    )
    assert [task["id"] for task in tasks] == ["T1", "T2", "T3", "T4"]
    packet = build_handoff_packet(
        initial_request="テトリスを作って",
        prd={"title": "Tetris", "acceptance_criteria": ["ok"]},
        prd_rel="prd.md",
        tech_spec_rel="tech.md",
        plan_rel="plan.md",
        todo_rel="todo.md",
        tech_spec={},
        plan={"tasks": [{"id": 0, "title": f"T{i}"} for i in range(4)]},
        skill_steps=["write-prd"],
    )
    assert not validate_handoff_packet(packet)


def test_normalize_implementation_tasks_dependency_ordering_and_dedupe() -> None:
    tasks = normalize_implementation_tasks(
        [
            {"id": "alpha", "title": "First"},
            {"id": "beta", "title": "Second", "dependencies": ["1", "T1", "1"]},
            {"id": "gamma", "title": "Third", "dependencies": ["2", "T1", "T2"]},
        ],
        default_acceptance=["fallback"],
        default_verification=["verify"],
    )
    assert [task["id"] for task in tasks] == ["T1", "T2", "T3"]
    assert tasks[1]["dependencies"] == ["T1"]
    assert tasks[2]["dependencies"] == ["T1", "T2"]


def test_normalize_implementation_tasks_preserves_valid_existing_ids() -> None:
    tasks = normalize_implementation_tasks(
        [
            {"id": "T1", "title": "A", "size": "S"},
            {"id": "T2", "title": "B", "dependencies": ["T1"], "size": "M"},
        ],
        default_acceptance=["fallback"],
        default_verification=["verify"],
    )
    assert tasks[0]["id"] == "T1"
    assert tasks[1]["id"] == "T2"
    assert tasks[1]["dependencies"] == ["T1"]


def test_build_handoff_packet_normalizes_task_ids_and_sizes() -> None:
    packet = build_handoff_packet(
        initial_request="テトリスを作って",
        prd={"title": "Tetris", "acceptance_criteria": ["ok"]},
        prd_rel="prd.md",
        tech_spec_rel="tech.md",
        plan_rel="plan.md",
        todo_rel="todo.md",
        tech_spec={
            "implementation_tasks": [
                {"id": "1", "title": "A", "size": "Small (1-2 files)"},
                {"id": "2", "title": "B", "size": "Medium (3-5 files)"},
            ]
        },
        plan={},
        skill_steps=["write-prd"],
    )
    tasks = packet["implementation_tasks"]
    assert tasks[0]["id"] == "T1"
    assert tasks[1]["id"] == "T2"
    assert tasks[0]["size"] == "S"
    assert tasks[1]["size"] == "M"
    assert not validate_handoff_packet(packet)


def test_run_dev_skill_pipeline_phase1_grill_then_value_loop(tmp_path: Path) -> None:
    result = run_dev_skill_pipeline(
        "テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        model="mock-model",
        output_dir=tmp_path,
        auto_select="test_auto_recommendation",
        chat_fn=_mock_chat,
        min_grill_rounds_before_score=1,
        max_grill_rounds=3,
    )
    grill = next(step for step in result.step_results if step.skill_id == "grill-me")
    assert grill.status == "done"
    assert "phase1_standalone_spec_gate" in grill.notes
    assert result.phase1_spec_finalized is True
    assert result.grill_report is not None
    assert result.grill_report.get("gate_passed") is True
    assert result.grill_report.get("human_response_kind") == "simulated_human"

    write_prd = next(step for step in result.step_results if step.skill_id == "write-prd")
    assert write_prd.status == "done"
    assert result.handoff_packet
    assert not validate_handoff_packet(result.handoff_packet)
    assert result.implementation_prompt
    assert result.value_consumption_report is not None
    assert "grill-me" in result.value_consumption_report["excluded_skill_ids"]
    assert (tmp_path / "design" / "aligned_spec.json").is_file()
    assert (tmp_path / "design" / "handoff.json").is_file()

    skill_ids = [item.skill_id for item in result.applicability_report.items]
    assert "grill-me" not in skill_ids
    assert skill_ids[0] == "write-prd"


def test_production_aligned_spec_skips_standalone_grill_and_builds_generic_handoff(
    tmp_path: Path,
) -> None:
    quality = "操作応答が良く、基本ルールが正しく動き、見た目も最低限整っている"
    aligned = {
        "summary": "高品質なテトリスを作る",
        "numbered_conditions": [quality],
        "non_goals": ["ネットワーク対戦は含めない"],
        "acceptance_criteria": [quality],
    }
    calls: list[str] = []

    def production_chat(**kwargs):
        _, user = (
            str((kwargs.get("messages") or [{}])[0].get("content") or ""),
            str((kwargs.get("messages") or [{}])[-1].get("content") or ""),
        )
        calls.append(user)
        if "Emit PRD_JSON" in user:
            return _response_for_test(
                {
                    "title": "Tetris PRD",
                    "problem": "高品質なテトリスが必要",
                    "goals": quality,
                    "requirements": quality,
                    "non_goals": "ネットワーク対戦は含めない",
                    "constraints": "Runtimeを開始しない",
                    "acceptance_criteria": [quality],
                }
            )
        if "Emit TECH_SPEC_JSON" in user:
            return _response_for_test(
                {
                    "summary": quality,
                    "modules": [{"path": "game/main.py", "responsibility": quality}],
                    "sequencing": [quality],
                    "sandbox_constraints": "Runtimeを開始しない",
                    "implementation_tasks": [{"id": "T1", "title": quality, "acceptance": [quality], "size": "S"}],
                }
            )
        if "Emit PLAN_JSON" in user:
            return _response_for_test(
                {
                    "plan_markdown": f"# Plan\n\n{quality}",
                    "todo_markdown": f"- [ ] T1 {quality}",
                    "tasks": [{"id": "T1", "title": quality, "acceptance": [quality], "verification": [quality], "affected_paths": ["game/main.py"], "size": "S", "dependencies": []}],
                }
            )
        raise AssertionError(f"standalone grill was unexpectedly invoked: {user[:100]}")

    result = run_dev_skill_pipeline(
        "高品質なテトリスを作って",
        composition_id="production-spec-handoff",
        model="test",
        output_dir=tmp_path,
        chat_fn=production_chat,
        consumer="codex",
        phase1_aligned_spec=aligned,
    )

    assert len(calls) == 3
    assert result.grill_report["source"] == "production_phase1_aligned_spec"
    assert result.grill_report["human_response_kind"] == "human_ui"
    assert result.prd and result.tech_spec and result.plan
    assert result.handoff_packet
    assert not validate_handoff_packet(result.handoff_packet)
    assert result.handoff_packet["runtime_boundary"]["production_connected"] is False
    assert "game/main.py" in result.handoff_packet["scope"]["affected_paths"]


def _response_for_test(payload: dict):
    return type(
        "Resp",
        (),
        {"message": type("Msg", (), {"content": json.dumps(payload, ensure_ascii=False)})()},
    )()
