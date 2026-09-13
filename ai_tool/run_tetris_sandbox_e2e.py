#!/usr/bin/env python3
"""Chat + Dedicated Sandbox E2E: Tetris via Dev Skill pipeline and Production Chat."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import ollama_available
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session, save_session
from ai_tool.dev_skill_pipeline import (
    VAGUE_REQUEST_EXAMPLE,
    composition_steps,
    run_dev_skill_pipeline,
    validate_handoff_packet,
)
from ai_tool.e2e_cross_boundary_prefault import (
    COMPARISON_FILENAME,
    PREFAULT_FILENAME,
    PRECONDITION_EVALUATION_FILENAME,
    build_e2e_observation,
    compare_prefault_to_e2e,
    run_cross_boundary_prefault,
    write_prefault_comparison,
)
from ai_tool.precondition_contract import preconditions_to_dicts
from ai_tool.tetris_execution_context import (
    EXECUTION_CONTEXT_FILENAME,
    build_tetris_golden_path_execution_context,
)
from ai_tool.environment_policy import evaluate_verify_only_gate, resolve_environment_policy
from ai_tool.tetris_precondition_checker import (
    build_precondition_evaluation_bundle,
    evaluate_all_tetris_preconditions,
)
from ai_tool.pipeline_observations import PipelineBudgetExceeded, PipelineObserver
from tools.system.config import get_llm_profile

TETRIS_FULL_BUDGET_SECONDS = 2400.0
PHASE_PRODUCTION_CHAT = "production_chat"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sandbox_root(snapshot: dict[str, Any] | None) -> Path | None:
    if not isinstance(snapshot, dict):
        return None
    sandbox = snapshot.get("sandbox_session")
    if not isinstance(sandbox, dict):
        return None
    for key in ("sandbox_root", "root", "workspace_root", "path"):
        raw = str(sandbox.get(key) or "").strip()
        if raw:
            return Path(raw)
    return None


def _list_sandbox_files(root: Path | None) -> list[str]:
    if root is None or not root.is_dir():
        return []
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    )


def _task_summary(runtime: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(runtime, dict):
        return {}
    goals = runtime.get("goals") or []
    tasks = runtime.get("tasks") or []
    return {
        "goals": [
            {
                "id": g.get("id"),
                "status": g.get("status"),
                "title": g.get("title"),
            }
            for g in goals
            if isinstance(g, dict)
        ],
        "tasks": [
            {
                "id": t.get("id"),
                "status": t.get("status"),
                "title": t.get("title"),
            }
            for t in tasks
            if isinstance(t, dict)
        ],
        "sandbox_session": runtime.get("sandbox_session"),
        "mission_id": runtime.get("mission_id"),
    }


def main() -> int:
    run_id = _utc_stamp() + "_tetris_sandbox"
    run_dir = _REPO / "logs" / "_e2e_tetris_sandbox" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    live, live_err = ollama_available()
    model = None
    model_err = None
    try:
        model = get_llm_profile().get("model")
    except Exception as exc:  # noqa: BLE001
        model_err = f"{type(exc).__name__}: {exc}"

    summary: dict[str, Any] = {
        "run_id": run_id,
        "experiment": "chat_sandbox_tetris_skill_pipeline_e2e_with_cross_boundary_prefault",
        "composition_id": "tetris-sandbox-e2e",
        "goal_text": VAGUE_REQUEST_EXAMPLE,
        "vague_prompt": VAGUE_REQUEST_EXAMPLE,
        "selection_policy": {
            "grill_me": "test_auto_recommendation",
            "human_response_kind": "simulated_human",
            "note": "E2E: Phase1 standalone grill-me auto-selects recommended answers; not real human approval.",
        },
        "ollama_available": live,
        "ollama_error": live_err,
        "configured_model": model,
        "model_config_error": model_err,
        "budget_seconds": TETRIS_FULL_BUDGET_SECONDS,
        "status": "NOT_RUN",
    }

    if not live:
        summary["status"] = "SKIP"
        summary["judgment"] = "NOT_OBSERVED"
        summary["reason"] = "Ollama unavailable"
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    composition_id = "tetris-sandbox-e2e"
    execution_context = build_tetris_golden_path_execution_context()
    (run_dir / EXECUTION_CONTEXT_FILENAME).write_text(
        json.dumps(execution_context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["execution_context"] = {
        "path": EXECUTION_CONTEXT_FILENAME,
        "golden_path": execution_context,
    }

    observer = PipelineObserver(
        run_dir,
        budget_seconds=TETRIS_FULL_BUDGET_SECONDS,
        e2e_kind="tetris_sandbox_full",
    )
    observer.set_work_plan(
        composition_steps=composition_steps(composition_id),
        include_production_chat=True,
    )

    phase_started = time.perf_counter()
    pipeline = run_dev_skill_pipeline(
        VAGUE_REQUEST_EXAMPLE,
        composition_id=composition_id,
        model=str(model),
        output_dir=run_dir,
        auto_select="test_auto_recommendation",
        budget_seconds=TETRIS_FULL_BUDGET_SECONDS,
        observer=observer,
    )
    pipeline_elapsed_ms = max(0, round((time.perf_counter() - phase_started) * 1000))
    pipeline_payload = pipeline.as_dict()
    if pipeline.timing_summary is not None:
        pipeline_payload["timing_summary"] = pipeline.timing_summary
    if pipeline.budget_report is not None:
        pipeline_payload["budget_report"] = pipeline.budget_report
    (run_dir / "pipeline_result.json").write_text(
        json.dumps(pipeline_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    handoff_errors = validate_handoff_packet(pipeline.handoff_packet) if pipeline.handoff_packet else ["missing handoff packet"]
    pipeline_done = all(step.status in {"done", "partial", "skipped"} for step in pipeline.step_results)
    prd_ok = any(
        step.skill_id == "write-prd" and step.status == "done"
        for step in pipeline.step_results
    )
    grill_ok = bool((pipeline.grill_report or {}).get("gate_passed"))

    applicability = (
        pipeline.applicability_report.as_dict()
        if pipeline.applicability_report is not None
        else None
    )
    summary["skill_pipeline"] = {
        "composition_id": pipeline.composition_id,
        "skill_steps": pipeline.skill_steps,
        "phase1_spec_finalized": pipeline.phase1_spec_finalized,
        "step_status": {step.skill_id: step.status for step in pipeline.step_results},
        "skill_applicability": applicability,
        "value_consumption": pipeline.value_consumption_report,
        "prd_generated": prd_ok,
        "grill_gate_passed": grill_ok,
        "grill_source": (pipeline.grill_report or {}).get("source"),
        "grill_human_response_kind": (pipeline.grill_report or {}).get("human_response_kind"),
        "handoff_valid": not handoff_errors,
        "handoff_id": (pipeline.handoff_packet or {}).get("handoff_id"),
        "errors": pipeline.errors,
        "elapsed_ms": pipeline_elapsed_ms,
        "timing_summary": pipeline.timing_summary,
        "budget_report": pipeline.budget_report,
    }
    summary["implementation_prompt"] = pipeline.implementation_prompt

    if (pipeline.budget_report or {}).get("status") == "exceeded":
        summary["status"] = "BUDGET_EXCEEDED"
        summary["judgment"] = "NOT_CONNECTED"
        summary["judgment_ja"] = "Budget 到達によりパイプライン停止。"
        observer.e2e_end(status="budget_exceeded", notes=["pipeline_budget_exceeded"])
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    if not pipeline.phase1_spec_finalized:
        summary["status"] = "ERROR"
        summary["judgment"] = "FAIL"
        summary["judgment_ja"] = "Phase1 standalone grill-me が仕様確定ゲートを通過しなかった。"
        observer.e2e_end(status="phase1_failed")
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    if not pipeline.implementation_prompt:
        summary["status"] = "ERROR"
        summary["judgment"] = "FAIL"
        summary["judgment_ja"] = "Skill パイプラインが implementation prompt を生成できなかった。"
        observer.e2e_end(status="pipeline_incomplete")
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    step_status = {step.skill_id: step.status for step in pipeline.step_results}
    precondition_items = evaluate_all_tetris_preconditions(
        handoff_packet=pipeline.handoff_packet,
        repo_root=_REPO,
        pipeline_errors=pipeline.errors,
        step_status=step_status,
        include_environment=True,
    )
    precondition_evaluation = build_precondition_evaluation_bundle(
        handoff_packet=pipeline.handoff_packet,
        repo_root=_REPO,
        pipeline_errors=pipeline.errors,
        step_status=step_status,
        handoff_path=str(run_dir / "design" / "handoff.json"),
        execution_context=execution_context,
        include_environment=True,
    )
    (run_dir / PRECONDITION_EVALUATION_FILENAME).write_text(
        json.dumps(precondition_evaluation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["precondition_evaluation"] = {
        "path": PRECONDITION_EVALUATION_FILENAME,
        "preconditions": precondition_evaluation.get("preconditions"),
        "policy": precondition_evaluation.get("policy"),
    }

    env_policy = resolve_environment_policy(execution_context)
    derived_lines: list[str] = []
    handoff = pipeline.handoff_packet or {}
    for task in handoff.get("implementation_tasks") or []:
        if isinstance(task, dict):
            derived_lines.append(str(task.get("title") or ""))
            derived_lines.append(str(task.get("description") or ""))
    env_gate = evaluate_verify_only_gate(
        environment_policy=env_policy,
        preconditions=precondition_items,
        goal_text=VAGUE_REQUEST_EXAMPLE,
        derived_spec_texts=derived_lines,
    )
    summary["environment_policy"] = env_gate.as_dict()
    summary["environment_policy_mode"] = env_policy
    if not env_gate.may_continue:
        summary["status"] = "ENV_BLOCKED"
        summary["judgment"] = "FAIL"
        summary["judgment_ja"] = env_gate.human_message or "環境前提が満たされないため停止しました。"
        observer.e2e_end(status="env_blocked", notes=env_gate.blocking_gaps or env_gate.mutations_detected)
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    prefault = run_cross_boundary_prefault(
        run_dir=run_dir,
        model=str(model),
        composition_id=composition_id,
        preconditions=preconditions_to_dicts(precondition_items),
        precondition_evaluation=precondition_evaluation,
        handoff_packet=pipeline.handoff_packet,
        execution_context=execution_context,
    )
    summary["cross_boundary_prefault"] = {
        "path": PREFAULT_FILENAME,
        "prediction_count": prefault.get("prediction_count"),
        "llm_status": prefault.get("llm_status"),
        "frozen_after_pipeline_before_production_chat": True,
        "no_production_fix_from_prediction": True,
        "prediction_does_not_set_precondition_status": True,
    }

    try:
        observer.check_budget()
    except PipelineBudgetExceeded as exc:
        summary.update(
            {
                "status": "BUDGET_EXCEEDED",
                "judgment": "NOT_CONNECTED",
                "judgment_ja": "Production Chat 前に Budget 到達。",
                "budget_report": exc.snapshot,
            }
        )
        observer.e2e_end(status="budget_exceeded", notes=["before_production_chat"])
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    session = empty_session(f"tetris-e2e-{run_id}")
    save_session(session)

    chat_started = time.perf_counter()
    observer.phase_start(PHASE_PRODUCTION_CHAT)
    try:
        result = run_chat_turn(
            session,
            pipeline.implementation_prompt,
            model=model,
            handoff_packet=pipeline.handoff_packet,
        )
    except Exception as exc:  # noqa: BLE001
        observer.phase_end(PHASE_PRODUCTION_CHAT, status="error")
        summary.update(
            {
                "status": "ERROR",
                "judgment": "FAIL",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "pipeline_phase": "production_chat",
            }
        )
        observer.e2e_end(status="error", notes=["production_chat_failed"])
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    observer.phase_end(PHASE_PRODUCTION_CHAT, status="done")
    runtime = result.get("task_runtime") if isinstance(result.get("task_runtime"), dict) else {}
    sandbox_root = _sandbox_root(runtime)
    sandbox_files = _list_sandbox_files(sandbox_root)
    tools = [
        {
            "name": t.get("name"),
            "status": t.get("status"),
            "target": t.get("target"),
        }
        for t in (result.get("tools") or [])
        if isinstance(t, dict)
    ]
    mutation_tools = [t for t in tools if t.get("name") in {"create_file", "edit_file"}]

    tetris_paths = [p for p in sandbox_files if "tetris" in p.lower() or p.endswith(".py")]

    chat_elapsed_ms = max(0, round((time.perf_counter() - chat_started) * 1000))
    summary.update(
        {
            "status": "RAN",
            "chat_elapsed_ms": chat_elapsed_ms,
            "session_id": session.get("session_id"),
            "correlation_id": result.get("correlation_id"),
            "model": result.get("model") or session.get("model"),
            "route": result.get("route"),
            "tools": tools,
            "mutation_tools_used": mutation_tools,
            "task_runtime": _task_summary(runtime),
            "mission_ui": result.get("mission_ui"),
            "stop_reason": result.get("stop_reason"),
            "awaiting_human_grill": result.get("awaiting_human_grill"),
            "requirement_decomposition": result.get("requirement_decomposition"),
            "answer_preview": str(result.get("answer") or "")[:1200],
            "sandbox_root": str(sandbox_root) if sandbox_root else None,
            "sandbox_files": sandbox_files,
            "tetris_candidate_files": tetris_paths,
            "events_tail": (result.get("events") or [])[-12:],
        }
    )

    created = bool(mutation_tools) and bool(tetris_paths)
    ran_py = any(p.endswith("main.py") for p in tetris_paths)
    goals_complete = all(
        g.get("status") == "complete"
        for g in (runtime.get("goals") or [])
        if isinstance(g, dict)
    )
    sandbox_started = runtime.get("sandbox_session") is not None

    design_ready = prd_ok and grill_ok and not handoff_errors
    if pipeline_done and design_ready and created and ran_py:
        summary["judgment"] = "PARTIAL_PASS"
        summary["judgment_ja"] = (
            "Skill パイプライン完了し Sandbox に tetris/main.py を作成。実行 Tool は未接続。"
        )
    elif pipeline_done and design_ready and sandbox_started and mutation_tools:
        summary["judgment"] = "PARTIAL_PASS"
        summary["judgment_ja"] = (
            "Skill パイプライン完了し Sandbox 起動・mutation を観測。ファイル確認は未達または一部。"
        )
    elif pipeline_done and design_ready:
        summary["judgment"] = "PARTIAL_PASS"
        summary["judgment_ja"] = (
            "Skill パイプラインと Handoff は完了。Production 実装フェーズは未完了または Sandbox 未観測。"
        )
    elif pipeline_done:
        summary["judgment"] = "PARTIAL_PASS"
        summary["judgment_ja"] = "Skill パイプラインは走ったが PRD/handoff の一部が未達。"
    else:
        summary["judgment"] = "NOT_CONNECTED"
        summary["judgment_ja"] = "Skill パイプライン未完了。"

    summary["goals_complete"] = goals_complete
    summary["production_connected"] = False
    summary["pipeline_phase_complete"] = pipeline_done and not handoff_errors
    summary["timing_summary"] = observer.summarize_timing()
    summary["budget_report"] = observer.budget_snapshot(status="completed")

    observer.e2e_end(
        status="completed" if pipeline_done and not handoff_errors else "partial",
        notes=[summary.get("judgment") or ""],
    )

    observation = build_e2e_observation(summary=summary, pipeline_result=pipeline_payload)
    prefault_comparison = compare_prefault_to_e2e(
        prefault=prefault,
        observation=observation,
        model=str(model),
    )
    write_prefault_comparison(run_dir, prefault_comparison)
    summary["cross_boundary_prefault_comparison"] = {
        "path": COMPARISON_FILENAME,
        "summary": prefault_comparison.get("summary"),
        "comparisons": [
            {
                "prediction_id": row.get("prediction_id"),
                "grade": row.get("grade"),
                "boundary": (row.get("prediction") or {}).get("boundary"),
            }
            for row in (prefault_comparison.get("comparisons") or [])
        ],
    }

    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "result_redacted.json").write_text(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"events"}
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
