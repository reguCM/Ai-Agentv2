#!/usr/bin/env python3
"""Smaller Dev Skill pipeline E2E for daily iteration (no Production Chat)."""
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
from ai_tool.dev_skill_pipeline import (
    VAGUE_REQUEST_EXAMPLE,
    composition_steps,
    run_dev_skill_pipeline,
    validate_handoff_packet,
)
from ai_tool.pipeline_observations import PipelineObserver
from tools.system.config import get_llm_profile

SMOKE_BUDGET_SECONDS = 600.0
SMOKE_MAX_GRILL_ROUNDS = 3
SMOKE_MIN_GRILL_ROUNDS_BEFORE_SCORE = 1


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    run_id = _utc_stamp() + "_pipeline_smoke"
    run_dir = _REPO / "logs" / "_e2e_pipeline_smoke" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    live, live_err = ollama_available()
    model = None
    model_err = None
    try:
        model = get_llm_profile().get("model")
    except Exception as exc:  # noqa: BLE001
        model_err = f"{type(exc).__name__}: {exc}"

    composition_id = "tetris-sandbox-e2e"
    observer = PipelineObserver(
        run_dir,
        budget_seconds=SMOKE_BUDGET_SECONDS,
        e2e_kind="pipeline_smoke",
    )
    observer.set_work_plan(
        composition_steps=composition_steps(composition_id),
        include_production_chat=False,
    )

    summary: dict[str, Any] = {
        "run_id": run_id,
        "experiment": "dev_skill_pipeline_smoke_e2e",
        "composition_id": composition_id,
        "vague_prompt": VAGUE_REQUEST_EXAMPLE,
        "budget_seconds": SMOKE_BUDGET_SECONDS,
        "ollama_available": live,
        "ollama_error": live_err,
        "configured_model": model,
        "model_config_error": model_err,
        "status": "NOT_RUN",
    }

    if not live:
        summary["status"] = "SKIP"
        summary["judgment"] = "NOT_OBSERVED"
        observer.e2e_end(status="skipped", notes=["ollama_unavailable"])
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    started = time.perf_counter()
    pipeline = run_dev_skill_pipeline(
        VAGUE_REQUEST_EXAMPLE,
        composition_id=composition_id,
        model=str(model),
        output_dir=run_dir,
        auto_select="test_auto_recommendation",
        max_grill_rounds=SMOKE_MAX_GRILL_ROUNDS,
        min_grill_rounds_before_score=SMOKE_MIN_GRILL_ROUNDS_BEFORE_SCORE,
        budget_seconds=SMOKE_BUDGET_SECONDS,
        observer=observer,
        emit_e2e_end=True,
    )
    elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))

    pipeline_payload = pipeline.as_dict()
    if pipeline.timing_summary is not None:
        pipeline_payload["timing_summary"] = pipeline.timing_summary
    if pipeline.budget_report is not None:
        pipeline_payload["budget_report"] = pipeline.budget_report
    (run_dir / "pipeline_result.json").write_text(
        json.dumps(pipeline_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    handoff_errors = (
        validate_handoff_packet(pipeline.handoff_packet)
        if pipeline.handoff_packet
        else ["missing handoff packet"]
    )
    budget_status = (pipeline.budget_report or {}).get("status")
    summary.update(
        {
            "status": "RAN",
            "elapsed_ms": elapsed_ms,
            "phase1_spec_finalized": pipeline.phase1_spec_finalized,
            "step_status": {step.skill_id: step.status for step in pipeline.step_results},
            "handoff_valid": not handoff_errors,
            "timing_summary": pipeline.timing_summary,
            "budget_report": pipeline.budget_report,
            "errors": pipeline.errors,
            "judgment": (
                "BUDGET_EXCEEDED"
                if budget_status == "exceeded"
                else ("PARTIAL_PASS" if not handoff_errors else "PARTIAL_PASS")
            ),
        }
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if budget_status != "exceeded" and not handoff_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
