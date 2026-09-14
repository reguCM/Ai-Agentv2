from __future__ import annotations

from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.dev_skill_pipeline import build_handoff_packet, validate_handoff_packet
from ai_tool.mission_memory.store import MissionMemoryStore
from tools.ai.sandbox_workspace import SandboxSession


MISSION_ID = "m-resume-meaning-e2e"
REQUIREMENT_IDS = ["req-goal", "req-quality"]


def _packet() -> dict:
    packet = build_handoff_packet(
        initial_request="Build a Tetris game",
        aligned_spec={
            "summary": "Build a Tetris game",
            "numbered_conditions": ["responsive controls", "correct core rules"],
            "non_goals": ["online play"],
            "acceptance_criteria": ["responsive controls"],
        },
        prd_rel="design/prd.md",
        tech_spec_rel="design/tech-spec.md",
        plan_rel="design/plan.md",
        todo_rel="design/todo.md",
        tech_spec={"summary": "Tetris implementation", "modules": [{"path": "tetris/main.py"}]},
        plan={
            "tasks": [
                {
                    "id": "T1",
                    "title": "Implement responsive Tetris controls",
                    "acceptance": ["responsive controls"],
                    "verification": ["manual smoke test"],
                    "affected_paths": ["tetris/main.py"],
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
        handoff_slug="resume-meaning-e2e",
        source_binding={"mission_id": MISSION_ID, "requirement_ids": REQUIREMENT_IDS},
    )
    assert not validate_handoff_packet(packet)
    return packet


def _mission(*, quality_meaning: str = "responsive controls and correct core rules") -> dict:
    return {
        "schema_version": "1",
        "mission_id": MISSION_ID,
        "original_goal": "Build a high-quality Tetris game",
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
        "structured_requirements": [
            {
                "requirement_id": "req-goal",
                "source_text": "Build a Tetris game",
                "source_span": [0, 0],
                "disposition": "GOAL",
                "resolution_status": "resolved",
                "provenance": "user_explicit",
                "materiality": "blocks_design",
                "normalized_meaning": "Implement a playable Tetris game.",
            },
            {
                "requirement_id": "req-quality",
                "source_text": "High quality",
                "source_span": [0, 0],
                "disposition": "GOAL",
                "resolution_status": "resolved",
                "provenance": "user_explicit",
                "materiality": "blocks_design",
                "normalized_meaning": quality_meaning,
            },
        ],
        "confirmed_clarifications": [
            {
                "decision_id": "decision-quality-v1",
                "decision_key": "quality:definition",
                "status": "confirmed",
                "source": "requirement_resolution",
                "text": quality_meaning,
                "human_confirmed": True,
            }
        ],
    }


def _isolate_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission-memory",
    )
    MissionMemoryStore.from_default().put_mission(_mission())


def test_production_run_resume_uses_meaning_projection_and_fails_closed_on_meaning_change(
    monkeypatch, tmp_path
):
    _isolate_session(monkeypatch, tmp_path)
    packet = _packet()
    session = empty_session()
    session["last_mission_id"] = MISSION_ID
    session["production_handoff_packet"] = packet
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    sandbox = SandboxSession(
        session_id="sandbox-resume-meaning-e2e",
        sandbox_root=str(sandbox_root),
        branch="agent-sandbox/resume-meaning-e2e",
        base_head="head",
        current_head="head",
        status="ACTIVE",
        created_at="2026-09-14T00:00:00+00:00",
        production_applied=False,
        git_base="HEAD:head",
        workspace_base="working-tree-sha256:test",
        session_kind="DEDICATED",
    )
    sandbox_starts = {"n": 0}

    def start_sandbox(runtime, _source, _parent):
        sandbox_starts["n"] += 1
        runtime.sandbox_session = sandbox
        return sandbox

    monkeypatch.setattr(
        "tools.ai.task_runtime.AgentTaskRuntime.start_dedicated_sandbox", start_sandbox
    )
    monkeypatch.setattr("tools.ai.task_runtime.verify_sandbox_identity", lambda value: value)
    monkeypatch.setattr(
        "tools.ai.sandbox_workspace.verify_sandbox_identity",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.resolve_configured_sandbox_parent",
        lambda _source: tmp_path / "sandboxes",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.restore_mission_clarifications",
        lambda orchestrator: orchestrator.confirmed_clarifications.append(
            {
                "decision_id": "decision-quality-v1",
                "decision_key": "quality:definition",
                "status": "confirmed",
                "human_confirmed": True,
                "text": "responsive controls and correct core rules",
            }
        ),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_handoff_pipeline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("handoff regenerated")),
    )
    tool_calls = {"n": 0}

    def execute(name, arguments, *, sandbox_session=None, **_kwargs):
        tool_calls["n"] += 1
        assert name == "create_file"
        (sandbox_root / arguments["path"]).write_text(arguments["content"], encoding="utf-8")
        return {
            "ok": True,
            "status": "success",
            "path": arguments["path"],
            "mutation": {
                "tool": "create_file",
                "sandbox_session_id": sandbox_session.session_id,
                "relative_path": arguments["path"],
                "action": "create",
                "before_hash": None,
                "after_hash": f"hash-{tool_calls['n']}",
                "changed": True,
                "timestamp": "2026-09-14T00:00:00+00:00",
            },
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    monkeypatch.setattr(
        "ai_tool.tool_calling_capability_bridge.apply_tool_calling_hard_capability_bridge",
        lambda *_args, **_kwargs: SimpleNamespace(
            capability_gap=False,
            routing_performed=False,
            selected_model="test",
            as_dict=lambda: {"capability_gap": False, "routing_performed": False},
        ),
    )
    chat_calls = {"n": 0}

    def chat(**_kwargs):
        chat_calls["n"] += 1
        return SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        function=SimpleNamespace(
                            name="create_file",
                            arguments={
                                "path": f"step-{chat_calls['n']}.txt",
                                "content": "e2e\n",
                            },
                        )
                    )
                ],
            )
        )

    first = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    contract = dict(first["run_contract"])
    sandbox_id = first["task_runtime"]["sandbox_session"]["session_id"]
    assert first["runtime_started"] is True
    assert first["sandbox_started"] is True
    assert tool_calls["n"] == 1

    updated = _mission()
    updated["completion_runtime"] = {"current_task_id": "gh-T1"}
    MissionMemoryStore.from_default().put_mission(updated)
    resumed = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    assert resumed["runtime_resumed"] is True
    assert resumed["sandbox_started"] is False
    assert resumed["run_contract"] == contract
    assert resumed["task_runtime"]["sandbox_session"]["session_id"] == sandbox_id
    assert sandbox_starts["n"] == 1
    assert tool_calls["n"] == 2

    MissionMemoryStore.from_default().put_mission(
        _mission(quality_meaning="Only high-score visual effects are required.")
    )
    blocked = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    assert blocked["production_run_error"] == "run_contract_mismatch"
    assert "run_contract_meaning_mismatch" in blocked["run_contract_validation_errors"]
    assert blocked["run_contract"] == contract
    assert tool_calls["n"] == 2
    assert sandbox_starts["n"] == 1

    revised = _mission()
    prior = revised["confirmed_clarifications"][0]
    prior["status"] = "superseded"
    prior["superseded_by"] = "decision-quality-v2"
    revised["confirmed_clarifications"].append(
        {
            "decision_id": "decision-quality-v2",
            "decision_key": "quality:definition",
            "status": "confirmed",
            "source": "boundary_grill",
            "text": "Use keyboard controls and a visible score.",
            "human_confirmed": True,
            "supersedes": "decision-quality-v1",
        }
    )
    MissionMemoryStore.from_default().put_mission(revised)
    decision_blocked = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    assert decision_blocked["production_run_error"] == "invalid_meaning_context"
    assert "inactive_or_missing_decision_premises:decision-quality-v1" in (
        decision_blocked["meaning_context_validation_errors"][0]
    )
    assert tool_calls["n"] == 2
    assert sandbox_starts["n"] == 1
