from __future__ import annotations

import json
from types import SimpleNamespace

from ai_tool.e2e_cross_boundary_prefault import (
    _detect_observation_known_issues,
    _has_novel_failures,
    _heuristic_grade,
    _normalize_predictions,
    _prediction_known_issue_id,
    build_e2e_observation,
    compare_prefault_to_e2e,
    run_cross_boundary_prefault,
)


def test_normalize_predictions_caps_at_ten() -> None:
    raw = [{"prediction_id": f"P{i}", "boundary": f"b{i}", "failure_hypothesis": f"h{i}"} for i in range(15)]
    out = _normalize_predictions(raw)
    assert len(out) == 10
    assert out[0]["prediction_id"] == "P0"


def test_heuristic_exact_hit_on_task_id_duplicate() -> None:
    prediction = {
        "prediction_id": "P01",
        "boundary": "planning-and-task-breakdown → goal-handoff",
        "invariant": "implementation_tasks ids unique",
        "failure_hypothesis": "duplicate T0 task ids fail schema uniqueItems",
        "evidence": "dev_skill_pipeline.py",
        "suggested_test": "test handoff",
        "confidence": "high",
    }
    observation = {
        "errors": ["goal-handoff: ValueError: handoff schema errors: ['T0', 'T0'] has non-unique elements"],
        "step_status": {"goal-handoff": "error"},
    }
    grade, _ = _heuristic_grade(prediction, observation)
    assert grade in {"EXACT_HIT", "INVARIANT_HIT", "BOUNDARY_HIT"}


def test_known_issue_detection_for_task_id_duplicate() -> None:
    observation = {
        "errors": ["goal-handoff: ValueError: handoff schema errors: ['T0', 'T0'] has non-unique elements"],
        "step_status": {"goal-handoff": "error"},
    }
    assert "task_id_t0_duplicate" in _detect_observation_known_issues(observation)
    prediction = {
        "boundary": "planning-and-task-breakdown → goal-handoff",
        "invariant": "implementation_tasks ids unique",
        "failure_hypothesis": "duplicate T0 task ids fail schema uniqueItems",
        "evidence": "dev_skill_pipeline.py",
        "suggested_test": "test handoff",
    }
    assert _prediction_known_issue_id(prediction) == "task_id_t0_duplicate"


def test_prefault_includes_evaluated_preconditions_without_llm_status_change(tmp_path) -> None:
    preconditions = [
        {
            "precondition_id": "pc-tetris-tech-spec",
            "key": "tech_spec_exists",
            "description": "Tech spec artifact exists.",
            "blocking": True,
            "source": "tetris_precondition_checker:v0",
            "evaluation": {"status": "SATISFIED", "evidence_refs": ["artifact:logs/x/design/tech-spec.md"]},
        }
    ]

    def fake_chat(**_kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(
                content=json.dumps(
                    {
                        "predictions": [
                            {
                                "prediction_id": "P01",
                                "boundary": "write-prd -> tech-spec",
                                "invariant": "tech spec artifact exists",
                                "failure_hypothesis": "tech-spec step may fail",
                                "evidence": "dev_skill_pipeline.py",
                                "suggested_test": "run tech-spec standalone",
                                "confidence": "medium",
                            }
                        ]
                    }
                )
            )
        )

    result = run_cross_boundary_prefault(
        run_dir=tmp_path,
        model="test-model",
        preconditions=preconditions,
        precondition_evaluation={"preconditions": preconditions},
        handoff_packet={"handoff_id": "gh-test", "implementation_tasks": [{"id": "T1"}]},
        chat_fn=fake_chat,
    )
    assert result["evaluated_preconditions"] == preconditions
    assert result["predictions"][0]["failure_hypothesis"]
    assert all(
        row["evaluation"]["status"] == "SATISFIED" for row in result["evaluated_preconditions"]
    )


def test_known_issue_only_failure_excluded_from_novel_evaluation() -> None:
    observation = {
        "errors": ["goal-handoff: ValueError: handoff schema errors: ['T0', 'T0'] has non-unique elements"],
        "step_status": {"goal-handoff": "error"},
    }
    assert _detect_observation_known_issues(observation) == ["task_id_t0_duplicate"]
    assert not _has_novel_failures(observation)
    prefault = {
        "generated_at": "t",
        "predictions": [
            {
                "prediction_id": "P01",
                "boundary": "planning → goal-handoff",
                "invariant": "unique task ids",
                "failure_hypothesis": "duplicate T0",
                "evidence": "dev_skill_pipeline.py",
                "suggested_test": "handoff",
                "confidence": "high",
            }
        ],
    }
    result = compare_prefault_to_e2e(prefault=prefault, observation=observation)
    assert result["summary"]["known_issue_only_failure"] is True
    assert result["summary"]["preflight_catchable_before_e2e"] == "EXCLUDED_KNOWN_ISSUE"
    assert result["comparisons"][0]["grade"] == "EXCLUDED_KNOWN_ISSUE"


def test_compare_prefault_marks_miss_when_no_overlap() -> None:
    prefault = {
        "generated_at": "t",
        "predictions": [
            {
                "prediction_id": "P99",
                "boundary": "unrelated → boundary",
                "invariant": "nothing",
                "failure_hypothesis": "zzzz_unknown_symptom",
                "evidence": "nowhere.py",
                "suggested_test": "none",
                "confidence": "low",
            }
        ],
    }
    observation = build_e2e_observation(
        summary={"judgment": "PARTIAL_PASS", "skill_pipeline": {"errors": [], "step_status": {"write-prd": "done"}}},
    )
    result = compare_prefault_to_e2e(prefault=prefault, observation=observation)
    assert result["comparisons"][0]["grade"] == "MISS"
    assert result["summary"]["preflight_catchable_before_e2e"] == "NOT_APPLICABLE"
