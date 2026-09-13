from __future__ import annotations

import json
import time

import pytest

from ai_tool.pipeline_observations import (
    OBSERVATIONS_FILENAME,
    PipelineBudgetExceeded,
    PipelineObserver,
)


def test_observer_writes_v0_events_and_summarizes(tmp_path) -> None:
    observer = PipelineObserver(tmp_path, budget_seconds=60.0, e2e_kind="test")
    observer.set_work_plan(composition_steps=["write-prd", "goal-handoff"])
    observer.phase_start("phase1_grill")
    observer.skill_start("phase1_grill", "grill-me")
    call_id = observer.llm_start(
        phase="phase1_grill",
        skill_id="grill-me",
        model="gemma4:12b",
        round_index=1,
    )
    observer.llm_end(
        call_id,
        phase="phase1_grill",
        skill_id="grill-me",
        model="gemma4:12b",
        status="ok",
        round_index=1,
    )
    observer.skill_end("phase1_grill", "grill-me", status="done")
    observer.phase_end("phase1_grill", status="done")
    observer.e2e_end(status="completed")

    path = tmp_path / OBSERVATIONS_FILENAME
    assert path.is_file()
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    event_names = [row["event"] for row in events]
    assert event_names == [
        "PHASE_START",
        "SKILL_START",
        "LLM_START",
        "LLM_END",
        "SKILL_END",
        "PHASE_END",
        "E2E_END",
    ]
    llm_end = next(row for row in events if row["event"] == "LLM_END")
    assert llm_end["model"] == "gemma4:12b"
    assert llm_end["round"] == 1
    assert isinstance(llm_end["elapsed_ms"], int)

    summary = observer.summarize_timing()
    assert summary["llm_call_count"] == 1
    assert summary["llm_total_ms"] == llm_end["elapsed_ms"]
    assert summary["by_phase_ms"]["phase1_grill"] > 0
    assert summary["by_skill_ms"]["grill-me"] > 0


def test_budget_exceeded_raises_with_snapshot(tmp_path) -> None:
    observer = PipelineObserver(tmp_path, budget_seconds=0.001, e2e_kind="test")
    observer.set_work_plan(composition_steps=["write-prd"], include_production_chat=True)
    observer._current_phase = "phase1_grill"
    time.sleep(0.01)
    with pytest.raises(PipelineBudgetExceeded) as excinfo:
        observer.check_budget()
    snapshot = excinfo.value.snapshot
    assert snapshot["status"] == "exceeded"
    assert snapshot["reached_phase"] == "phase1_grill"
    assert "write-prd" in snapshot["remaining_work"]
    assert "production_chat" in snapshot["remaining_work"]
