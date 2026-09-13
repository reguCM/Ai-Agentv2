"""Progress Classification v0 tests."""
from __future__ import annotations

import json
from pathlib import Path

from ai_tool.chat_interface.goal_continuation_progress import GapSnapshot
from ai_tool.chat_interface.progress_classification_v0 import (
    ProgressStateSnapshot,
    classify_progress_transition,
    classify_runtime_turn_end,
)
from ai_tool.tetris_code_specialization_lab.progress_classification_adapter import (
    classify_lab_steps,
    classify_summary_worker_steps,
    snapshot_from_case001_canonical,
    snapshot_from_production_replay_summary,
    snapshot_from_tetris_evaluation,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
LAB_RUNS = REPO_ROOT / "runs" / "tetris_code_specialization_lab"


def test_goal_progress_from_gap_snapshot():
    prior = ProgressStateSnapshot.from_gap_snapshot(
        GapSnapshot(
            gap_kind="fact_gap",
            gap_resolved=False,
            answer_gate_verified=False,
            unsatisfied_conditions=["B"],
            satisfied_conditions=["A"],
        )
    )
    current = ProgressStateSnapshot.from_gap_snapshot(
        GapSnapshot(
            gap_kind="fact_gap",
            gap_resolved=False,
            answer_gate_verified=False,
            unsatisfied_conditions=[],
            satisfied_conditions=["A", "B"],
        )
    )
    result = classify_progress_transition(prior, current)
    assert result.goal_progress is True
    assert result.regression is False
    assert "conditions_satisfied:B" in result.goal_progress_reasons[0]


def test_observation_only_progress():
    prior = ProgressStateSnapshot(evidence_count=2, verified_evidence_ids=["E1", "E2"])
    current = ProgressStateSnapshot(evidence_count=5, verified_evidence_ids=["E1", "E2", "E3"])
    result = classify_progress_transition(prior, current)
    assert result.observation_progress is True
    assert result.goal_progress is False
    assert result.stagnation is True


def test_stagnation_on_flat_repair_attempt():
    prior = snapshot_from_case001_canonical(
        {
            "passed_count": 0,
            "total_count": 4,
            "completion_ratio": 0.0,
            "failed_condition_ids": ["update_no_runtime_error"],
            "exception_message": "No module named 'workspace'",
            "conditions": [],
        }
    )
    current = snapshot_from_case001_canonical(
        {
            "passed_count": 0,
            "total_count": 4,
            "completion_ratio": 0.0,
            "failed_condition_ids": ["update_no_runtime_error"],
            "exception_message": "No module named 'workspace'",
            "conditions": [],
        }
    )
    result = classify_progress_transition(prior, current)
    assert result.stagnation is True
    assert result.goal_progress is False
    assert result.observation_progress is False


def test_genuine_regression_loses_passed_condition():
    prior = ProgressStateSnapshot(
        passed_condition_ids=["a", "b"],
        completion_ratio=1.0,
        requirements_passed=2,
        requirements_total=2,
    )
    current = ProgressStateSnapshot(
        passed_condition_ids=["a"],
        completion_ratio=0.5,
        requirements_passed=1,
        requirements_total=2,
    )
    result = classify_progress_transition(prior, current)
    assert result.regression is True
    assert any("conditions_lost:b" in reason for reason in result.regression_reasons)


def test_newly_exposed_failure_after_blocker_release_not_regression():
    prior = ProgressStateSnapshot(
        pytest_passed=15,
        pytest_failed=0,
        pytest_blocked=3,
        feature_units_passed={"startup_window": False, "tetromino": True},
        feature_units_observable={"startup_window": False, "tetromino": True},
        failure_signature="ModuleNotFoundError: No module named 'workspace'",
    )
    current = ProgressStateSnapshot(
        pytest_passed=17,
        pytest_failed=1,
        pytest_blocked=0,
        feature_units_passed={"startup_window": False, "tetromino": True},
        feature_units_observable={"startup_window": True, "tetromino": True},
        failure_signature="TypeError: 'NoneType' object is not subscriptable",
    )
    result = classify_progress_transition(prior, current)
    assert result.regression is False
    assert result.observation_progress is True
    assert result.newly_exposed_failure is True
    assert result.goal_progress is False or result.observation_progress is True


def test_progress_plus_newly_exposed_failure_simultaneous():
    prior = ProgressStateSnapshot(
        pytest_passed=10,
        pytest_failed=0,
        pytest_blocked=8,
        feature_units_observable={"startup_window": False},
        failure_signature="collection blocked",
    )
    current = ProgressStateSnapshot(
        pytest_passed=12,
        pytest_failed=1,
        pytest_blocked=5,
        feature_units_observable={"startup_window": True},
        failure_signature="AssertionError: grid mismatch",
        completion_ratio=0.5,
        requirements_passed=1,
        requirements_total=2,
    )
    prior.requirements_passed = 0
    prior.requirements_total = 2
    prior.completion_ratio = 0.0
    result = classify_progress_transition(prior, current)
    assert result.goal_progress is True
    assert result.observation_progress is True
    assert result.newly_exposed_failure is True
    assert result.regression is False


def test_new_failure_count_alone_is_not_regression():
    prior = ProgressStateSnapshot(
        pytest_passed=15,
        pytest_failed=0,
        pytest_blocked=3,
        feature_units_passed={"startup_window": False},
        feature_units_observable={"startup_window": False},
    )
    current = ProgressStateSnapshot(
        pytest_passed=17,
        pytest_failed=1,
        pytest_blocked=0,
        feature_units_passed={"startup_window": False},
        feature_units_observable={"startup_window": True},
        failure_signature="TypeError: demo",
    )
    result = classify_progress_transition(prior, current)
    assert result.regression is False


def test_runtime_turn_end_wrapper():
    result = classify_runtime_turn_end(
        prior_gap_snapshot=None,
        current_gap_snapshot={
            "gap_kind": "fact_gap",
            "gap_resolved": False,
            "answer_gate_verified": False,
            "unsatisfied_conditions": ["x"],
            "satisfied_conditions": [],
        },
        prior_evidence_count=0,
        current_evidence_count=3,
    )
    assert result.observation_progress is True


def test_case001_repair_qwen_progress():
    summary_path = LAB_RUNS / "case_001_repair_loop_20260911T031321Z" / "case_001_repair_loop_20260911T031321Z_summary.json"
    if not summary_path.is_file():
        return
    steps = classify_summary_worker_steps(summary_path, worker_id="qwen3_14b", evaluation_key="canonical")
    assert steps[1].goal_progress is True
    assert steps[1].regression is False


def test_case001_repair_deepseek_stagnation():
    summary_path = LAB_RUNS / "case_001_repair_loop_20260911T031321Z" / "case_001_repair_loop_20260911T031321Z_summary.json"
    if not summary_path.is_file():
        return
    steps = classify_summary_worker_steps(summary_path, worker_id="deepseek_coder_v2_16b", evaluation_key="canonical")
    assert steps[1].stagnation is True
    assert steps[2].stagnation is True


def test_production_replay_observation_progress_goal_stagnation():
    summary_path = (
        LAB_RUNS
        / "case_001_current_replay_20260911T025536Z"
        / "case_001_current_replay_20260911T025536Z_summary.json"
    )
    if not summary_path.is_file():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    current = snapshot_from_production_replay_summary(summary)
    current.evidence_count = int(
        summary["run_chat_turn_summary"]["runtime_status_report"]["evidence_count"]
    )
    result = classify_progress_transition(ProgressStateSnapshot.empty(), current)
    assert result.observation_progress is True
    assert result.goal_progress is False
    assert result.stagnation is True


def test_full_tetris_qwen_hypothesis_final_progress():
    summary_path = (
        LAB_RUNS
        / "full_tetris_hypothesis_revision_20260911T035103Z"
        / "full_tetris_hypothesis_revision_20260911T035103Z_summary.json"
    )
    if not summary_path.is_file():
        return
    steps = classify_summary_worker_steps(summary_path, worker_id="qwen3_14b")
    assert steps[3].observation_progress is True
    assert steps[3].regression is False


def test_full_tetris_deepseek_control_final_progress():
    summary_path = (
        LAB_RUNS
        / "full_tetris_control_repair_20260911T040339Z"
        / "full_tetris_control_repair_20260911T040339Z_summary.json"
    )
    if not summary_path.is_file():
        return
    steps = classify_summary_worker_steps(summary_path, worker_id="deepseek_coder_v2_16b")
    assert steps[3].observation_progress is True
    assert steps[3].regression is False


def test_full_tetris_blocker_breakthrough_classifies_newly_exposed():
    summary_path = (
        LAB_RUNS
        / "full_tetris_hypothesis_revision_20260911T035103Z"
        / "full_tetris_hypothesis_revision_20260911T035103Z_summary.json"
    )
    if not summary_path.is_file():
        return
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    cycles = data["workers"]["qwen3_14b"]["cycles"]
    results = classify_lab_steps(cycles)
    assert results[3].newly_exposed_failure is True
    assert results[3].regression is False
