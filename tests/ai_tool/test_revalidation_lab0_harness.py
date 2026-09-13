"""Lab-0 harness tests with deterministic synthetic chat_fn (no live LLM)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.revalidation_failure_class import (
    FAILURE_CLASS_RESOLVED,
    FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE,
)
from ai_tool.revalidation_lab_harness import (
    PRIMARY_LOCAL_MODEL,
    RevalidationLabFixture,
    build_lab0_fixtures,
    chat_fn_for_fixture,
    run_arm_a,
    run_arm_b,
    run_lab0,
    seed_lab0_handoff_orchestrator,
    summarize_lab0_results,
)
from ai_tool.task_upstream_supersession_revalidation import build_upstream_supersession_wave_case


@pytest.fixture
def lab0_orchestrator(tmp_path):
    store = MissionMemoryStore(tmp_path / "mission_memory")
    return seed_lab0_handoff_orchestrator(store)


def test_build_lab0_fixtures_includes_mechanical_and_semantic_cases(lab0_orchestrator):
    fixtures = build_lab0_fixtures(lab0_orchestrator)
    case_ids = {fixture.case_id for fixture in fixtures}
    assert "premise-semantic-ambiguous" in case_ids
    assert "premise-llm-schema-failure" in case_ids
    assert "premise-system-missing-inputs" in case_ids
    assert "premise-system-not-configured" in case_ids


def test_arm_b_improves_mechanical_resolution_over_arm_a(lab0_orchestrator):
    fixtures = build_lab0_fixtures(lab0_orchestrator)
    observations_a = run_arm_a(fixtures, chat_fn_for=chat_fn_for_fixture, model=PRIMARY_LOCAL_MODEL)
    observations_b = run_arm_b(fixtures, chat_fn_for=chat_fn_for_fixture, model=PRIMARY_LOCAL_MODEL)
    summary = summarize_lab0_results(observations_a + observations_b)

    assert summary["arm_a"]["success_rate"] < summary["arm_b"]["success_rate"]
    assert summary["arm_b"]["retry_attempts"] >= 4
    assert summary["arm_b"]["retry_effectiveness_rate"] == 1.0
    assert "premise-semantic-ambiguous" in summary["semantic_only_case_ids"]
    assert summary["lab1_ready"] is True


def test_lab0_writes_jsonl_and_summary(tmp_path, lab0_orchestrator):
    output_dir = tmp_path / "lab0"
    summary = run_lab0(lab0_orchestrator, output_dir=output_dir, model=PRIMARY_LOCAL_MODEL)
    assert summary["lab1_ready"] is True
    assert Path(summary["observations_jsonl"]).is_file()
    assert Path(summary["summary_json"]).is_file()


def test_upstream_fixture_can_be_appended(lab0_orchestrator):
    upstream_case = build_upstream_supersession_wave_case(
        lab0_orchestrator,
        downstream_task_id="gh-T2",
        upstream_changes=[{"old_task_id": "gh-T1", "new_task_id": "gh-T1"}],
    )
    assert upstream_case is not None
    extra = [
        RevalidationLabFixture(
            case_id="upstream-semantic-ambiguous",
            domain="upstream",
            description="upstream semantic cannot_determine",
            case=upstream_case,
            evaluate_fn="upstream",
            oracle_outcome="cannot_determine",
        )
    ]
    fixtures = build_lab0_fixtures(lab0_orchestrator, extra_fixtures=extra)
    obs = run_arm_a(fixtures, chat_fn_for=chat_fn_for_fixture, model=PRIMARY_LOCAL_MODEL)
    upstream_obs = next(row for row in obs if row.case_id == "upstream-semantic-ambiguous")
    assert upstream_obs.failure_class == FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE
