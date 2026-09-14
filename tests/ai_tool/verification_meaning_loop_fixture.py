"""Production-compatible saved Session builder for the Verification Meaning Loop E2E."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from ai_tool.acceptance_meaning_completion import assess_acceptance_meaning_completion_eligibility
from ai_tool.acceptance_meaning_verification_reentry import build_acceptance_meaning_verification_reentry
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.dev_skill_pipeline import build_handoff_packet, validate_handoff_packet
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.production_meaning_context import build_meaning_context_v0
from ai_tool.production_run_contract import build_production_run_contract
from tools.ai.task_runtime import ActionRecord, EvidenceRecord, TaskStatus


def _create_fixture_dedicated_sandbox(orchestrator: ChatTaskOrchestrator, tmp_path) -> Any:
    """Create the same real dedicated worktree identity used by Production Runtime."""
    source = Path(tmp_path) / "source"
    source.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    git("init")
    git("config", "user.name", "Verification Fixture")
    git("config", "user.email", "verification-fixture@example.invalid")
    (source / "README.md").write_text("verification fixture\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "fixture base")
    return orchestrator.runtime.start_dedicated_sandbox(source, Path(tmp_path) / "sandboxes")


def build_verification_meaning_loop_fixture(tmp_path) -> dict[str, Any]:
    """Build canonical saved inputs only; it never invokes ``/run`` or a tool."""
    mission = {
        "schema_version": "1", "mission_id": "m-verification-loop", "original_goal": "高品質なテトリスを作って",
        "explicit_conditions": [], "explicit_constraints": [], "user_confirmed_supplements": [],
        "confirmed_clarifications": [{"decision_id": "d1", "decision_key": "quality", "status": "confirmed", "source": "requirement_resolution", "text": "controls", "human_confirmed": True, "revision": 1}],
        "structured_requirements": [
            {"requirement_id": "req-r3", "source_text": "操作応答", "source_span": [0, 4], "disposition": "GOAL", "resolution_status": "resolved", "provenance": "human_confirmed", "materiality": "blocks_design", "normalized_meaning": "操作に素直に応答する"},
            {"requirement_id": "req-r8", "source_text": "別条件", "source_span": [5, 8], "disposition": "GOAL", "resolution_status": "resolved", "provenance": "user_explicit", "materiality": "informational", "normalized_meaning": "別条件"},
        ],
    }
    handoff = build_handoff_packet(
        initial_request=mission["original_goal"], aligned_spec={"summary": mission["original_goal"], "numbered_conditions": ["操作に素直に応答する"], "non_goals": [], "acceptance_criteria": ["操作応答"]},
        prd_rel="prd.md", tech_spec_rel="tech.md", plan_rel="plan.md", todo_rel="todo.md",
        tech_spec={"summary": "tetris", "modules": [{"path": "tetris/main.py"}]},
        plan={"tasks": [{"id": "T2", "title": "controls", "acceptance": ["操作応答"], "verification": ["pytest tests/test_tetris.py"], "affected_paths": ["tetris/main.py"], "size": "S", "dependencies": []}]},
        skill_steps=["goal-handoff"], handoff_slug="verification-meaning-loop",
        source_binding={"mission_id": mission["mission_id"], "requirement_ids": ["req-r3", "req-r8"]},
    )
    source_task_id = handoff["implementation_tasks"][0]["id"]
    acceptance_id = handoff["implementation_tasks"][0]["maps_to_acceptance"][0]
    handoff["acceptance_criteria"].append(
        {"id": "A8", "statement": "other", "verification": "manual"}
    )
    handoff["implementation_tasks"].append(
        {"id": "T8", "title": "other", "acceptance": ["other"], "verification": ["manual"], "dependencies": [], "size": "S", "maps_to_acceptance": ["A8"]}
    )
    handoff["requirement_bindings"] = [
        {"requirement_id": "req-r3", "task_ids": [source_task_id], "acceptance_ids": [acceptance_id]},
        {"requirement_id": "req-r8", "task_ids": ["T8"], "acceptance_ids": ["A8"]},
    ]
    handoff_errors = validate_handoff_packet(handoff)
    assert not handoff_errors, handoff_errors
    orchestrator = ChatTaskOrchestrator("verification-loop", mission["original_goal"])
    seed_orchestrator_from_handoff(orchestrator, handoff)
    runtime_task_id = f"gh-{source_task_id}"
    task = orchestrator.runtime.tasks[runtime_task_id]
    task.status = TaskStatus.COMPLETE.value
    orchestrator.runtime.record_action(ActionRecord("A5", "gh-T8", "tool_call", "create_file", {}, "success"))
    orchestrator.runtime.add_evidence(EvidenceRecord("E5", "tool", "tool://wrong", "wrong", "A5"), ["gh-T8"])
    sandbox = _create_fixture_dedicated_sandbox(orchestrator, tmp_path)
    snapshot = orchestrator.snapshot()
    context = build_meaning_context_v0(mission, handoff)
    handoff_hash = sha256(json.dumps(handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    contract = build_production_run_contract(started_execution_id="exec-verification-loop", mission=mission, handoff=handoff, meaning_context=context, starting_task_id=runtime_task_id, handoff_canonical_hash=handoff_hash)
    acceptance = {"status": "PASS", "criterion_trace": [{"acceptance_id": acceptance_id, "evidence_requirement_trace": {"coverage": "MISMATCH", "expected_requirement_ids": ["req-r3"]}}], "meaning_trace_audit": {"criteria_count": 1, "coverage_counts": {"MATCH": 0, "PARTIAL": 0, "MISMATCH": 1, "UNTRACEABLE": 0}, "criteria": [{"acceptance_id": acceptance_id, "acceptance_judgment": "PASS", "meaning_coverage": "MISMATCH", "expected_requirement_ids": ["req-r3"], "observed_requirement_ids": ["req-r8"], "evidence_ids": ["E5"]}]}}
    eligibility = assess_acceptance_meaning_completion_eligibility(acceptance)
    reentry = build_acceptance_meaning_verification_reentry(acceptance, handoff_packet=handoff, mission=mission, runtime=orchestrator.runtime)
    session = empty_session(); session.update({"last_mission_id": mission["mission_id"], "production_handoff_packet": handoff, "production_run_contract": contract, "production_runtime_snapshot": snapshot, "production_acceptance_evaluation": {"handoff_id": handoff["handoff_id"], "canonical_hash": handoff_hash, "result": acceptance}, "production_goal_acceptance_judgment": {"handoff_id": handoff["handoff_id"], "canonical_hash": handoff_hash, "acceptance_status": "PASS", "goal_id": "G1", "goal_completed": False, "completion_eligibility": eligibility, "verification_reentry": reentry}})
    return {"mission": mission, "handoff_packet": handoff, "run_contract": contract, "runtime_snapshot": snapshot, "session": session, "sandbox": sandbox, "before_acceptance": acceptance, "before_goal_judgment": session["production_goal_acceptance_judgment"]}
