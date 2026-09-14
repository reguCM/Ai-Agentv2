from __future__ import annotations

import json
from types import SimpleNamespace

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
from ai_tool.goal_handoff_source_binding import build_handoff_source_binding
from ai_tool.mission_memory.store import MissionMemoryStore
from tools.ai.sandbox_workspace import SandboxSession
from tools.ai.task_runtime import ActionRecord, EvidenceRecord


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
        source_binding={
            "mission_id": "m-phase3a",
            "requirement_ids": ["req-goal", "req-quality"],
        },
    )
    assert not validate_handoff_packet(packet)
    return packet


def _put_phase3a_mission() -> None:
    MissionMemoryStore.from_default().put_mission(
        {
            "schema_version": "1",
            "mission_id": "m-phase3a",
            "original_goal": "test goal",
            "explicit_conditions": [],
            "explicit_constraints": [],
            "user_confirmed_supplements": [],
            "structured_requirements": [
                {
                    "requirement_id": requirement_id,
                    "source_text": requirement_id,
                    "source_span": [0, 0],
                    "disposition": "GOAL",
                    "resolution_status": "resolved",
                    "provenance": "user_explicit",
                    "materiality": "blocks_design",
                }
                for requirement_id in ("req-goal", "req-quality")
            ],
        }
    )


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
    _put_phase3a_mission()


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


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (
            lambda packet: packet["source_binding"].update(mission_id="m-other"),
            "source_mission_mismatch",
        ),
        (
            lambda packet: packet["source_binding"].update(
                requirement_ids=["req-goal", "req-unknown"]
            ),
            "source_requirement_mismatch",
        ),
    ],
)
def test_run_fails_closed_for_handoff_source_mismatch(
    monkeypatch, tmp_path, mutate, expected_error
):
    _isolate_session(monkeypatch, tmp_path)
    packet = _packet(
        goal="test goal", meaning="test meaning", path="app/main.py", slug="source-mismatch"
    )
    mutate(packet)
    session = empty_session()
    session["last_mission_id"] = "m-phase3a"
    session["production_handoff_packet"] = packet

    result = run_chat_turn(session, "/run", model="test")

    assert result["production_run_error"] == "missing_or_invalid_handoff"
    assert expected_error in result["handoff_validation_errors"]
    assert result["runtime_started"] is False
    assert result["task_runtime"] is None


def test_goal_command_reuses_specification_path_and_stops_with_saved_handoff(monkeypatch, tmp_path):
    _isolate_session(monkeypatch, tmp_path)
    request = "高品質なテトリスを作って"
    quality = "操作応答が良く、基本ルールが正しく動き、見た目も最低限整っている"
    packet = _packet(goal=request, meaning=quality, path="game/main.py", slug="phase3a-goal")
    packet["implementation_tasks"][0]["decision_premises"] = []
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
    def fake_spec_pipeline(**kwargs):
        mission = MissionMemoryStore.from_default().get_mission(kwargs["mission_id"])
        packet["source_binding"] = build_handoff_source_binding(mission)
        return {
            "production_status": "SPEC_AND_HANDOFF_READY",
            "prd": {"goals": quality},
            "tech_spec": {"summary": quality},
            "plan": {"tasks": packet["implementation_tasks"]},
            "handoff_packet": packet,
            "semantic_trace": {"handoff": "PRESERVED"},
            "runtime_started": False,
        }

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.run_production_spec_handoff_pipeline",
        fake_spec_pipeline,
    )
    session = empty_session()

    result = run_chat_turn(session, f"/goal {request}", model="test")

    assert captured["request"] == request
    assert result["handoff_packet"] == packet
    assert result["runtime_started"] is False
    assert result["task_runtime"] is None
    assert session["production_handoff_packet"] == packet
    assert result["meaning_context"] == session["production_meaning_context"]
    assert result["meaning_context"]["identity"]["mission_id"]
    assert result["meaning_context"]["identity"]["handoff_id"] == packet["handoff_id"]
    assert result["meaning_context"]["human_meaning"]["original_goal"] == request
    assert result["meaning_context"]["human_meaning"]["structured_requirements"][0][
        "normalized_meaning"
    ] == quality
    assert result["meaning_context"]["implementation_meaning"]["acceptance_criteria"] == packet[
        "acceptance_criteria"
    ]
    assert result["meaning_context_status"] == "partial"
    assert load_session(session["session_id"])["production_meaning_context"] == result[
        "meaning_context"
    ]


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
def test_run_executes_only_first_task_step_for_exact_saved_handoff(
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
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    sandbox = SandboxSession(
        session_id=f"sandbox-{slug}",
        sandbox_root=str(sandbox_root),
        branch=f"agent-sandbox/{slug}",
        base_head="head",
        current_head="head",
        status="ACTIVE",
        created_at="2026-09-13T00:00:00+00:00",
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
        "tools.ai.task_runtime.AgentTaskRuntime.start_dedicated_sandbox",
        start_sandbox,
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
                "text": meaning,
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
        target = sandbox_root / arguments["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(arguments["content"], encoding="utf-8")
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
                "after_hash": "test-hash",
                "changed": True,
                "timestamp": "2026-09-14T00:00:00+00:00",
            },
        }

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        execute,
    )
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
        if chat_calls["n"] == 2:
            return SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="create_file",
                                arguments={"path": "next-step.txt", "content": "continued\n"},
                            )
                        )
                    ],
                )
            )
        return SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        function=SimpleNamespace(
                            name="create_file",
                            arguments={"path": path, "content": f"# {meaning}\n"},
                        )
                    ),
                    SimpleNamespace(
                        function=SimpleNamespace(
                            name="create_file",
                            arguments={"path": "should-not-run.txt", "content": "blocked\n"},
                        )
                    ),
                ],
            )
        )

    result = run_chat_turn(session, "/run", chat_fn=chat, model="test")

    assert result["runtime_prepared"] is True
    assert result["runtime_started"] is True
    assert result["sandbox_started"] is True
    assert result["task_step_executed"] is True
    assert result["task_completion_boundary"]["task_id"] == "gh-T1"
    assert result["task_completion_boundary"]["completed"] is False
    assert result["task_completion_boundary"]["next_task_id"] is None
    assert result["task_completion_boundary"]["missing_conditions"]
    assert result["task_completion_boundary"]["stopped_before_next_task_execution"] is True
    assert result["handoff_packet"] == packet
    assert json.dumps(packet, ensure_ascii=False, sort_keys=True) == saved_json
    assert result["handoff_integrity"]["handoff_id"] == packet["handoff_id"]
    assert result["handoff_integrity"]["canonical_hash_equal"] is True
    assert result["handoff_integrity"]["immutable_fields_equal"] is True
    runtime = result["task_runtime"]
    assert runtime["sandbox_session"]["session_id"] == sandbox.session_id
    assert tool_calls["n"] == 1
    assert result.get("error") is None, result
    assert runtime["actions"][0]["tool_name"] == "create_file"
    assert len(runtime["actions"]) == 1
    assert runtime["mutations"][0]["relative_path"] == path
    assert len(runtime["mutations"]) == 1
    assert (sandbox_root / path).is_file()
    assert not (sandbox_root / "should-not-run.txt").exists()
    assert any(row["status"] == "in_progress" for row in runtime["tasks"])
    assert session["production_runtime_snapshot"] == runtime
    rendered = json.dumps(result, ensure_ascii=False)
    assert meaning in rendered
    assert path in rendered
    assert "quality:definition" in rendered
    if "電卓" in goal:
        assert "Tetris" not in rendered
        assert "テトリス" not in rendered
        assert "tetris/main.py" not in rendered

    _put_phase3a_mission()
    repeated = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    assert repeated["runtime_resumed"] is True
    assert repeated["task_step_executed"] is True
    assert repeated["sandbox_started"] is False
    assert sandbox_starts["n"] == 1
    assert tool_calls["n"] == 2
    assert len(repeated["task_runtime"]["actions"]) == 2
    assert (sandbox_root / "next-step.txt").is_file()

    _put_phase3a_mission()
    same_call_as_new_action = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    assert same_call_as_new_action["runtime_resumed"] is True
    assert same_call_as_new_action["task_step_executed"] is True
    assert len(same_call_as_new_action["task_runtime"]["actions"]) == 3
    assert tool_calls["n"] == 3
    assert [
        row["action_id"] for row in same_call_as_new_action["task_runtime"]["actions"]
    ] == ["A1", "A2", "A3"]
    actions = same_call_as_new_action["task_runtime"]["actions"]
    assert actions[0]["tool_name"] == actions[2]["tool_name"] == "create_file"
    assert actions[0]["arguments"] == actions[2]["arguments"]

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.restore_orchestrator_from_runtime_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("sandbox identity mismatch")),
    )
    _put_phase3a_mission()
    invalid_sandbox = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    assert invalid_sandbox["production_run_error"] == "runtime_resume_validation_failed"
    assert tool_calls["n"] == 3

    session["production_handoff_packet"]["goal"]["summary"] += " changed"
    _put_phase3a_mission()
    invalid_handoff = run_chat_turn(session, "/run", chat_fn=chat, model="test")
    assert invalid_handoff["production_run_error"] == "runtime_handoff_mismatch"
    assert tool_calls["n"] == 3


@pytest.mark.parametrize(
    ("acceptance_status", "expected_goal_status", "expected_goal_completed"),
    [("PASS", "complete", True), ("FAIL", "in_progress", False)],
)
def test_run_completes_current_task_from_evidence_selects_next_task_and_stops(
    monkeypatch,
    tmp_path,
    acceptance_status,
    expected_goal_status,
    expected_goal_completed,
):
    _isolate_session(monkeypatch, tmp_path)
    packet = _packet(
        goal="PythonでCLI電卓を作って",
        meaning="CLI電卓の実装が存在する",
        path="calculator/main.py",
        slug="task-completion-boundary",
    )
    second = dict(packet["implementation_tasks"][0])
    second.update(
        {
            "id": "T2",
            "title": "電卓を検証する",
            "acceptance": ["四則演算を検証できる"],
            "verification": ["pytestを実行する"],
            "dependencies": ["T1"],
        }
    )
    packet["implementation_tasks"].append(second)
    assert not validate_handoff_packet(packet)
    session = empty_session()
    session["last_mission_id"] = "m-phase3a"
    session["production_handoff_packet"] = packet
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    sandbox = SandboxSession(
        session_id="sandbox-task-boundary",
        sandbox_root=str(sandbox_root),
        branch="agent-sandbox/task-boundary",
        base_head="head",
        current_head="head",
        status="ACTIVE",
        created_at="2026-09-14T00:00:00+00:00",
        production_applied=False,
        git_base="HEAD:head",
        workspace_base="working-tree-sha256:test",
        session_kind="DEDICATED",
    )

    def start_sandbox(runtime, _source, _parent):
        runtime.sandbox_session = sandbox
        return sandbox

    def complete_one_task(*_args, orchestrator=None, **_kwargs):
        task = orchestrator.task
        action_id = f"A{len(orchestrator.runtime.actions) + 1}"
        evidence_id = f"E{len(orchestrator.runtime.evidence) + 1}"
        orchestrator.runtime.record_action(
            ActionRecord(action_id, task.task_id, "tool_call", "create_file", {}, "success")
        )
        orchestrator.runtime.add_evidence(
            EvidenceRecord(
                evidence_id,
                "tool_result",
                "tool://create_file",
                "implementation observed",
                action_id,
                tool_name="create_file",
                supported_completion_conditions=list(task.completion_conditions),
            ),
            [task.task_id],
        )
        orchestrator.runtime.support_completion_conditions(
            task.task_id, evidence_id, task.completion_conditions
        )
        return {"events": [], "task_runtime": orchestrator.snapshot()}

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
    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._chat_turn", complete_one_task)
    acceptance_calls = []

    def evaluate_once(orchestrator, **kwargs):
        acceptance_calls.append((orchestrator.snapshot(), kwargs))
        return {
            "status": acceptance_status,
            "failures": [] if acceptance_status == "PASS" else [{"code": "TEST_FAILURE"}],
            "criterion_trace": [],
        }

    monkeypatch.setattr(
        "ai_tool.production_verification_acceptance.evaluate_handoff_goal_acceptance",
        evaluate_once,
    )

    result = run_chat_turn(session, "/run", model="test")

    boundary = result["task_completion_boundary"]
    assert boundary == {
        "task_id": "gh-T1",
        "completed": True,
        "completion_evidence_ids": ["E1"],
        "missing_conditions": [],
        "next_task_id": "gh-T2",
        "stopped_before_next_task_execution": True,
    }
    assert result["production_status"] == "RUNTIME_TASK_COMPLETED_NEXT_READY"
    assert result["acceptance_ready"] is False
    assert result["acceptance_readiness"]["incomplete_task_ids"] == ["gh-T2"]
    assert session["production_acceptance_readiness"] == result["acceptance_readiness"]
    assert result["task_runtime"]["current_task_id"] == "gh-T2"
    assert next(row for row in result["task_runtime"]["tasks"] if row["task_id"] == "gh-T1")[
        "status"
    ] == "complete"
    assert not [
        row for row in result["task_runtime"]["actions"] if row["task_id"] == "gh-T2"
    ]

    ready = run_chat_turn(session, "/run", model="test")
    assert ready["task_completion_boundary"]["task_id"] == "gh-T2"
    assert ready["task_completion_boundary"]["completed"] is True
    assert ready["task_completion_boundary"]["next_task_id"] is None
    assert ready["acceptance_ready"] is True
    assert ready["production_status"] == "GOAL_ACCEPTANCE_EVALUATED"
    assert ready["acceptance_evaluated"] is True
    assert ready["acceptance_reused"] is False
    assert ready["acceptance_result"]["status"] == acceptance_status
    assert len(acceptance_calls) == 1
    assert ready["task_completion_boundary"]["stopped_before_next_task_execution"] is True
    assert session["production_acceptance_readiness"]["acceptance_ready"] is True
    assert session["production_acceptance_evaluation"]["handoff_id"] == packet["handoff_id"]
    assert next(
        row for row in ready["task_runtime"]["goals"] if row["goal_id"] == "G1"
    )["status"] == "in_progress"

    judged = run_chat_turn(session, "/run", model="test")
    assert judged["production_status"] == "GOAL_ACCEPTANCE_JUDGED"
    assert judged["acceptance_evaluated"] is True
    assert judged["acceptance_reused"] is True
    assert judged["acceptance_result"] == ready["acceptance_result"]
    assert judged["goal_acceptance_judgment"]["goal_completed"] is expected_goal_completed
    assert judged["goal_judgment_reused"] is False
    assert judged["task_step_executed"] is False
    assert judged["sandbox_started"] is False
    assert next(
        row for row in judged["task_runtime"]["goals"] if row["goal_id"] == "G1"
    )["status"] == expected_goal_status
    assert session["production_goal_acceptance_judgment"] == judged[
        "goal_acceptance_judgment"
    ]
    assert len(acceptance_calls) == 1

    reused = run_chat_turn(session, "/run", model="test")
    assert reused["production_status"] == "GOAL_ACCEPTANCE_JUDGED"
    assert reused["goal_judgment_reused"] is True
    assert reused["task_runtime"]["actions"] == judged["task_runtime"]["actions"]
    assert reused["task_runtime"]["goals"] == judged["task_runtime"]["goals"]
    assert reused["task_step_executed"] is False
    assert reused["sandbox_started"] is False
    assert len(acceptance_calls) == 1


def test_run_fails_closed_when_sandbox_bootstrap_fails(monkeypatch, tmp_path):
    _isolate_session(monkeypatch, tmp_path)
    packet = _packet(
        goal="PythonでCLI電卓を作って",
        meaning="四則演算が動く",
        path="calculator/main.py",
        slug="phase3b-sandbox-failure",
    )
    session = empty_session()
    session["last_mission_id"] = "m-phase3a"
    session["production_handoff_packet"] = packet
    monkeypatch.setattr(
        "tools.ai.task_runtime.AgentTaskRuntime.start_dedicated_sandbox",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("blocked")),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.resolve_configured_sandbox_parent",
        lambda _source: tmp_path / "sandboxes",
    )

    result = run_chat_turn(session, "/run", model="test")

    assert result["production_run_error"] == "sandbox_bootstrap_failed"
    assert result["runtime_prepared"] is True
    assert result["runtime_started"] is False
    assert result["sandbox_started"] is False
    assert result["task_runtime"]["sandbox_session"] is None
    assert "production_runtime_snapshot" not in session
