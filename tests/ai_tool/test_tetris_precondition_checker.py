from __future__ import annotations

import json
from pathlib import Path

from ai_tool.dev_skill_pipeline import build_handoff_packet
from ai_tool.precondition_contract import STATUS_SATISFIED, STATUS_UNKNOWN, STATUS_UNSATISFIED
from ai_tool.tetris_precondition_checker import (
    build_precondition_evaluation_bundle,
    evaluate_tetris_handoff_preconditions,
    load_handoff_artifact,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sample_handoff() -> dict:
    return build_handoff_packet(
        initial_request="テトリスを作って",
        prd={"title": "Tetris", "acceptance_criteria": ["tetris/main.py exists"]},
        prd_rel="logs/x/design/prd.md",
        tech_spec_rel="logs/x/design/tech-spec.md",
        plan_rel="logs/x/design/plan.md",
        todo_rel="logs/x/design/todo.md",
        tech_spec={"summary": "sandbox tetris"},
        plan={
            "tasks": [
                {"id": "T1", "title": "A", "dependencies": []},
                {"id": "T2", "title": "B", "dependencies": ["T1"]},
            ]
        },
        skill_steps=["write-prd", "planning-and-task-breakdown"],
    )


def test_no_handoff_yields_unknown_preconditions() -> None:
    items = evaluate_tetris_handoff_preconditions(handoff_packet=None, repo_root=REPO_ROOT)
    assert len(items) == 3
    assert all(item.evaluation.status == STATUS_UNKNOWN for item in items)


def test_duplicate_task_ids_unsatisfied(tmp_path: Path) -> None:
    handoff = _sample_handoff()
    handoff["implementation_tasks"] = [
        {"id": "T0", "title": "A", "acceptance": ["ok"], "verification": ["v"], "size": "S"},
        {"id": "T0", "title": "B", "acceptance": ["ok"], "verification": ["v"], "size": "S"},
    ]
    items = evaluate_tetris_handoff_preconditions(handoff_packet=handoff, repo_root=REPO_ROOT)
    by_key = {item.key: item for item in items}
    assert by_key["task_ids_unique"].evaluation.status == STATUS_UNSATISFIED
    assert "known_issue:task_id_t0_duplicate" in by_key["task_ids_unique"].evaluation.evidence_refs


def test_valid_handoff_task_and_dependency_checks_satisfied() -> None:
    handoff = _sample_handoff()
    items = evaluate_tetris_handoff_preconditions(handoff_packet=handoff, repo_root=REPO_ROOT)
    by_key = {item.key: item for item in items}
    assert by_key["task_ids_unique"].evaluation.status == STATUS_SATISFIED
    assert by_key["dependency_refs_resolved"].evaluation.status == STATUS_SATISFIED


def test_tech_spec_exists_from_pipeline_smoke_artifact() -> None:
    smoke_dir = REPO_ROOT / "logs" / "_e2e_pipeline_smoke" / "20260910T171748Z_pipeline_smoke"
    if not (smoke_dir / "design" / "handoff.json").is_file():
        return
    handoff, _ = load_handoff_artifact(smoke_dir)
    items = evaluate_tetris_handoff_preconditions(handoff_packet=handoff, repo_root=REPO_ROOT)
    by_key = {item.key: item for item in items}
    assert by_key["tech_spec_exists"].evaluation.status == STATUS_SATISFIED
    assert by_key["tech_spec_exists"].evaluation.evidence_refs


def test_tech_spec_empty_response_pipeline_error_unsatisfied() -> None:
    handoff = _sample_handoff()
    items = evaluate_tetris_handoff_preconditions(
        handoff_packet=handoff,
        repo_root=REPO_ROOT,
        pipeline_errors=["tech-spec: LLMEmptyResponseError: empty response"],
        step_status={"tech-spec": "error"},
    )
    by_key = {item.key: item for item in items}
    assert by_key["tech_spec_exists"].evaluation.status == STATUS_UNSATISFIED
    assert "pipeline:error:tech_spec_empty_response" in by_key["tech_spec_exists"].evaluation.evidence_refs


def test_tech_spec_empty_error_ignored_when_step_done(tmp_path: Path) -> None:
    tech_path = tmp_path / "tech-spec.md"
    tech_path.write_text("# Tech spec\n", encoding="utf-8")
    handoff = _sample_handoff()
    handoff["source"]["documents"]["tech_spec"] = str(tech_path)
    items = evaluate_tetris_handoff_preconditions(
        handoff_packet=handoff,
        repo_root=REPO_ROOT,
        pipeline_errors=["tech-spec: LLMEmptyResponseError: empty response (recovered)"],
        step_status={"tech-spec": "done"},
    )
    by_key = {item.key: item for item in items}
    assert by_key["tech_spec_exists"].evaluation.status == STATUS_SATISFIED


def test_evaluation_bundle_validates() -> None:
    handoff = _sample_handoff()
    bundle = build_precondition_evaluation_bundle(handoff_packet=handoff, repo_root=REPO_ROOT)
    assert bundle["policy"]["llm_prefault_does_not_set_status"] is True
    assert not bundle["validation_errors"]
    assert len(bundle["preconditions"]) == 6
    assert len(bundle["precondition_groups"]["handoff"]) == 3
    assert len(bundle["precondition_groups"]["environment"]) == 3
