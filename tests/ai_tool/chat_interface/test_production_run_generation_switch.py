from __future__ import annotations

from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import (
    _archive_active_production_run_for_new_handoff,
    run_chat_turn,
)
from ai_tool.chat_interface.chat_session import empty_session, load_session
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementDecomposition,
    RequirementStatus,
)
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_REQUIREMENTS_RESOLVED,
    RequirementResolutionBundle,
    StructuredRequirement,
)
from ai_tool.dev_skill_pipeline import build_handoff_packet
from ai_tool.goal_handoff_source_binding import build_handoff_source_binding
from ai_tool.mission_memory.store import MissionMemoryStore
from tools.ai.sandbox_workspace import SandboxSession


def test_new_handoff_archives_old_active_run_and_clears_resume_state():
    session = {
        "production_handoff_packet": {"handoff_id": "gh-old"},
        "production_meaning_context": {"identity": {"handoff_id": "gh-old"}},
        "production_run_contract": {"started_execution_id": "exec-old"},
        "production_runtime_snapshot": {"sandbox_session": {"session_id": "S-old"}},
        "production_runtime_handoff_integrity": {"handoff_id": "gh-old"},
        "production_acceptance_readiness": {"acceptance_ready": True},
        "production_acceptance_evaluation": {"handoff_id": "gh-old"},
        "production_goal_acceptance_judgment": {"handoff_id": "gh-old"},
    }

    assert _archive_active_production_run_for_new_handoff(
        session, {"handoff_id": "gh-new"}
    ) is True
    assert "production_runtime_snapshot" not in session
    assert "production_run_contract" not in session
    archive = session["production_run_generations"][0]
    assert archive["reason"] == "new_goal_handoff"
    assert archive["handoff_id"] == "gh-old"
    assert archive["production_run_contract"]["started_execution_id"] == "exec-old"
    assert archive["production_runtime_snapshot"]["sandbox_session"]["session_id"] == "S-old"


def test_same_handoff_does_not_create_an_archive():
    session = {"production_handoff_packet": {"handoff_id": "gh-same"}}
    assert _archive_active_production_run_for_new_handoff(
        session, {"handoff_id": "gh-same"}
    ) is False
    assert "production_run_generations" not in session


def _generation_packet(*, goal: str, requirement_ids: list[str], slug: str) -> dict:
    return build_handoff_packet(
        initial_request=goal,
        aligned_spec={
            "summary": goal,
            "numbered_conditions": [goal],
            "non_goals": [],
            "acceptance_criteria": [goal],
        },
        prd_rel="design/prd.md",
        tech_spec_rel="design/tech-spec.md",
        plan_rel="design/plan.md",
        todo_rel="design/todo.md",
        tech_spec={"summary": goal, "modules": [{"path": "app/main.py"}]},
        plan={
            "tasks": [
                {
                    "id": "T1",
                    "title": goal,
                    "acceptance": [goal],
                    "verification": ["run the focused check"],
                    "affected_paths": ["app/main.py"],
                    "size": "S",
                    "dependencies": [],
                }
            ]
        },
        skill_steps=["write-prd", "tech-spec", "planning-and-task-breakdown", "goal-handoff"],
        handoff_slug=slug,
        source_binding={"mission_id": "pending", "requirement_ids": requirement_ids},
    )


def _isolate_generation_switch_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission-memory",
    )


def test_new_goal_archives_old_run_then_starts_new_run_in_new_sandbox(monkeypatch, tmp_path):
    """Production-compatible E2E: a new /goal cannot resume the old Run generation."""
    _isolate_generation_switch_session(monkeypatch, tmp_path)
    store = MissionMemoryStore.from_default()
    store.put_mission(
        {
            "schema_version": "1",
            "mission_id": "m-old-generation",
            "original_goal": "old calculator goal",
            "explicit_conditions": [],
            "explicit_constraints": [],
            "user_confirmed_supplements": [],
            "structured_requirements": [
                {
                    "requirement_id": "req-old",
                    "source_text": "old calculator goal",
                    "source_span": [0, 19],
                    "disposition": "GOAL",
                    "resolution_status": "resolved",
                    "provenance": "user_explicit",
                    "materiality": "blocks_design",
                    "normalized_meaning": "old calculator goal",
                }
            ],
            "confirmed_clarifications": [],
        }
    )
    old_packet = _generation_packet(
        goal="old calculator goal", requirement_ids=["req-old"], slug="old-generation"
    )
    old_packet["source_binding"] = build_handoff_source_binding(
        store.get_mission("m-old-generation")
    )
    session = empty_session()
    session.update(
        {
            "last_mission_id": "m-old-generation",
            "production_handoff_packet": old_packet,
            "production_meaning_context": {"identity": {"handoff_id": old_packet["handoff_id"]}},
            "production_run_contract": {
                "handoff_id": old_packet["handoff_id"],
                "started_execution_id": "exec-old",
            },
            "production_runtime_snapshot": {
                "sandbox_session": {"session_id": "S-old", "status": "ACTIVE"},
                "actions": [{"action_id": "A-old"}],
            },
            "production_runtime_handoff_integrity": {
                "handoff_id": old_packet["handoff_id"],
                "canonical_hash": "old-hash",
            },
        }
    )

    new_goal = "new tetris goal"
    bundle = RequirementResolutionBundle(
        original_goal=new_goal,
        structured_requirements=[
            StructuredRequirement(
                requirement_id="req-new-goal",
                source_text=new_goal,
                source_span=[0, len(new_goal)],
                disposition="GOAL",
                resolution_status="resolved",
                provenance="user_explicit",
                materiality="blocks_design",
                normalized_meaning=new_goal,
            )
        ],
        requirement_resolution_phase=PHASE_REQUIREMENTS_RESOLVED,
    )
    new_packet = _generation_packet(
        goal=new_goal, requirement_ids=["req-new-goal"], slug="new-generation"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition([], RequirementStatus.READY.value),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.prepare_implementation_entry_bundle",
        lambda *_args, **_kwargs: bundle,
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
                "summary": new_goal,
                "numbered_conditions": [new_goal],
                "non_goals": [],
                "acceptance_criteria": [new_goal],
            },
            "generated_aligned_spec": {},
            "semantic_preservation": {"final": {"status": "preserved"}},
            "ambiguity_report": {},
        },
    )

    def fake_spec_pipeline(**kwargs):
        mission = store.get_mission(kwargs["mission_id"])
        new_packet["source_binding"] = build_handoff_source_binding(mission)
        return {
            "production_status": "SPEC_AND_HANDOFF_READY",
            "prd": {"goal": new_goal},
            "tech_spec": {"summary": new_goal},
            "plan": {"tasks": new_packet["implementation_tasks"]},
            "handoff_packet": new_packet,
            "semantic_trace": {"handoff": "PRESERVED"},
            "runtime_started": False,
        }

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_spec_handoff_pipeline",
        fake_spec_pipeline,
    )
    goal_result = run_chat_turn(session, f"/goal {new_goal}", model="test")

    assert goal_result["handoff_packet"]["handoff_id"] == new_packet["handoff_id"]
    assert session["production_handoff_packet"]["handoff_id"] == new_packet["handoff_id"]
    assert "production_runtime_snapshot" not in session
    assert "production_run_contract" not in session
    archive = session["production_run_generations"][-1]
    assert archive["handoff_id"] == old_packet["handoff_id"]
    assert archive["production_run_contract"]["started_execution_id"] == "exec-old"
    assert archive["production_runtime_snapshot"]["sandbox_session"]["session_id"] == "S-old"
    session = load_session(session["session_id"])
    assert session["production_handoff_packet"]["handoff_id"] == new_packet["handoff_id"]
    assert "production_runtime_snapshot" not in session
    assert "production_run_contract" not in session
    assert session["production_run_generations"][-1] == archive

    sandbox_root = tmp_path / "new-sandbox"
    sandbox_root.mkdir()
    new_sandbox = SandboxSession(
        session_id="S-new",
        sandbox_root=str(sandbox_root),
        branch="agent-sandbox/S-new",
        base_head="head-new",
        current_head="head-new",
        status="ACTIVE",
        created_at="2026-09-15T00:00:00+00:00",
        production_applied=False,
        git_base="HEAD:head-new",
        workspace_base="working-tree-sha256:new",
        session_kind="DEDICATED",
    )
    newest_sandbox_root = tmp_path / "newest-sandbox"
    newest_sandbox_root.mkdir()
    newest_sandbox = SandboxSession(
        session_id="S-newest",
        sandbox_root=str(newest_sandbox_root),
        branch="agent-sandbox/S-newest",
        base_head="head-newest",
        current_head="head-newest",
        status="ACTIVE",
        created_at="2026-09-15T00:00:00+00:00",
        production_applied=False,
        git_base="HEAD:head-newest",
        workspace_base="working-tree-sha256:newest",
        session_kind="DEDICATED",
    )
    starts = {"count": 0}

    def start_sandbox(runtime, _source, _parent):
        starts["count"] += 1
        sandbox = (new_sandbox, newest_sandbox)[starts["count"] - 1]
        runtime.sandbox_session = sandbox
        return sandbox

    monkeypatch.setattr("tools.ai.task_runtime.AgentTaskRuntime.start_dedicated_sandbox", start_sandbox)
    monkeypatch.setattr("tools.ai.task_runtime.verify_sandbox_identity", lambda value: value)
    monkeypatch.setattr("tools.ai.sandbox_workspace.verify_sandbox_identity", lambda value, **_kwargs: value)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.resolve_configured_sandbox_parent",
        lambda _source: tmp_path / "sandboxes",
    )
    monkeypatch.setattr("ai_tool.chat_interface.agent_turn.restore_mission_clarifications", lambda _orchestrator: None)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_handoff_pipeline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("/run regenerated a handoff")),
    )

    def execute(name, arguments, *, sandbox_session=None, **_kwargs):
        assert name == "create_file"
        assert sandbox_session.session_id in {"S-new", "S-newest"}
        return {
            "ok": True,
            "status": "success",
            "path": arguments["path"],
            "mutation": {
                "tool": name,
                "sandbox_session_id": sandbox_session.session_id,
                "relative_path": arguments["path"],
                "action": "create",
                "before_hash": None,
                "after_hash": "new-e2e-hash",
                "changed": True,
                "timestamp": "2026-09-15T00:00:00+00:00",
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
    chat = lambda **_kwargs: SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    function=SimpleNamespace(
                        name="create_file",
                        arguments={"path": "app/main.py", "content": "# new generation\n"},
                    )
                )
            ],
        )
    )

    run_result = run_chat_turn(session, "/run", chat_fn=chat, model="test")

    assert run_result["runtime_started"] is True
    assert run_result["runtime_resumed"] is False
    assert run_result["sandbox_started"] is True
    assert starts["count"] == 1
    assert run_result["run_contract"]["handoff_id"] == new_packet["handoff_id"]
    assert run_result["run_contract"]["started_execution_id"] != "exec-old"
    assert run_result["task_runtime"]["sandbox_session"]["session_id"] == "S-new"
    assert session["production_runtime_snapshot"]["sandbox_session"]["session_id"] == "S-new"
    assert session["production_run_generations"][-1] == archive

    new_contract = dict(run_result["run_contract"])
    session = load_session(session["session_id"])
    resumed = run_chat_turn(session, "/run", chat_fn=chat, model="test")

    assert resumed["runtime_resumed"] is True
    assert resumed["sandbox_started"] is False
    assert starts["count"] == 1
    assert resumed["run_contract"] == new_contract
    assert resumed["task_runtime"]["sandbox_session"]["session_id"] == "S-new"
    assert session["production_run_generations"][-1] == archive

    newest_goal = "new calculator goal"
    newest_bundle = RequirementResolutionBundle(
        original_goal=newest_goal,
        structured_requirements=[
            StructuredRequirement(
                requirement_id="req-newest-goal",
                source_text=newest_goal,
                source_span=[0, len(newest_goal)],
                disposition="GOAL",
                resolution_status="resolved",
                provenance="user_explicit",
                materiality="blocks_design",
                normalized_meaning=newest_goal,
            )
        ],
        requirement_resolution_phase=PHASE_REQUIREMENTS_RESOLVED,
    )
    newest_packet = _generation_packet(
        goal=newest_goal, requirement_ids=["req-newest-goal"], slug="newest-generation"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.prepare_implementation_entry_bundle",
        lambda *_args, **_kwargs: newest_bundle,
    )

    def fake_newest_spec_pipeline(**kwargs):
        mission = store.get_mission(kwargs["mission_id"])
        newest_packet["source_binding"] = build_handoff_source_binding(mission)
        return {
            "production_status": "SPEC_AND_HANDOFF_READY",
            "prd": {"goal": newest_goal},
            "tech_spec": {"summary": newest_goal},
            "plan": {"tasks": newest_packet["implementation_tasks"]},
            "handoff_packet": newest_packet,
            "semantic_trace": {"handoff": "PRESERVED"},
            "runtime_started": False,
        }

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_spec_handoff_pipeline",
        fake_newest_spec_pipeline,
    )
    newest_goal_result = run_chat_turn(session, f"/goal {newest_goal}", model="test")

    assert newest_goal_result["handoff_packet"]["handoff_id"] == newest_packet["handoff_id"]
    assert "production_runtime_snapshot" not in session
    assert "production_run_contract" not in session
    generations = session["production_run_generations"]
    assert [row["handoff_id"] for row in generations] == [
        old_packet["handoff_id"],
        new_packet["handoff_id"],
    ]
    assert generations[0] == archive
    assert generations[1]["production_run_contract"] == new_contract
    assert generations[1]["production_runtime_snapshot"]["sandbox_session"]["session_id"] == "S-new"

    newest_run = run_chat_turn(session, "/run", chat_fn=chat, model="test")

    assert newest_run["runtime_resumed"] is False
    assert newest_run["sandbox_started"] is True
    assert starts["count"] == 2
    assert newest_run["run_contract"]["handoff_id"] == newest_packet["handoff_id"]
    assert newest_run["run_contract"]["started_execution_id"] != new_contract["started_execution_id"]
    assert newest_run["task_runtime"]["sandbox_session"]["session_id"] == "S-newest"
    assert [row["handoff_id"] for row in session["production_run_generations"]] == [
        old_packet["handoff_id"],
        new_packet["handoff_id"],
    ]

    newest_contract = dict(newest_run["run_contract"])
    session = load_session(session["session_id"])
    assert [row["handoff_id"] for row in session["production_run_generations"]] == [
        old_packet["handoff_id"],
        new_packet["handoff_id"],
    ]
    assert session["production_handoff_packet"]["handoff_id"] == newest_packet["handoff_id"]
    assert session["production_run_contract"] == newest_contract
    assert session["production_runtime_snapshot"]["sandbox_session"]["session_id"] == "S-newest"

    newest_resumed = run_chat_turn(session, "/run", chat_fn=chat, model="test")

    assert newest_resumed["runtime_resumed"] is True
    assert newest_resumed["sandbox_started"] is False
    assert starts["count"] == 2
    assert newest_resumed["run_contract"] == newest_contract
    assert newest_resumed["task_runtime"]["sandbox_session"]["session_id"] == "S-newest"
    assert [row["handoff_id"] for row in session["production_run_generations"]] == [
        old_packet["handoff_id"],
        new_packet["handoff_id"],
    ]
