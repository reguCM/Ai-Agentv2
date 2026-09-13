from __future__ import annotations

from pathlib import Path

import pytest

from validator.catalog_draft import generate_catalog_draft
from validator.validate import validate_tool_spec_file

from conftest import load_json


def _reject_reasons(result) -> list[str]:
    reasons: list[str] = []
    reasons.extend(result.schema_errors)
    reasons.extend(
        i["message"]
        for i in result.safety_issues
        if i.get("severity") == "error"
    )
    return reasons


@pytest.mark.regression
def test_phase2_valid_specs_count_and_accept(valid_spec_paths: list[Path]) -> None:
    """Gold set: current specs/ — false_reject 0 is relative to this set only."""
    assert len(valid_spec_paths) == 4
    for path in valid_spec_paths:
        result = validate_tool_spec_file(path)
        assert result.verdict == "ACCEPT", path.name


@pytest.mark.regression
def test_phase2_failure_cases_count_and_reject(failure_case_paths: list[Path]) -> None:
    assert len(failure_case_paths) == 8
    for path in failure_case_paths:
        result = validate_tool_spec_file(path)
        assert result.verdict == "REJECT", path.name
        assert _reject_reasons(result), path.name


@pytest.mark.regression
def test_phase2_false_accept_zero(
    valid_spec_paths: list[Path],
    failure_case_paths: list[Path],
) -> None:
    valid_reject = sum(
        1 for p in valid_spec_paths if validate_tool_spec_file(p).verdict != "ACCEPT"
    )
    invalid_accept = sum(
        1 for p in failure_case_paths if validate_tool_spec_file(p).verdict != "REJECT"
    )
    false_accept = valid_reject + invalid_accept
    assert false_accept == 0, f"false_accept={false_accept}"


@pytest.mark.regression
def test_phase2_false_reject_zero_gold_set(valid_spec_paths: list[Path]) -> None:
    """false_reject=0 applies only to the current gold spec definitions."""
    false_reject = sum(
        1 for p in valid_spec_paths if validate_tool_spec_file(p).verdict != "ACCEPT"
    )
    assert false_reject == 0


@pytest.mark.regression
def test_phase2_pipeline_generates_draft_and_skeleton(
    tool_creation_root: Path,
    valid_spec_paths: list[Path],
    tmp_path: Path,
) -> None:
    """Mirrors run_phase2 without writing to runs/ai_tool/."""
    from validator.test_skeleton import write_test_skeleton
    from validator.catalog_draft import write_catalog_draft

    for spec_path in valid_spec_paths:
        result = validate_tool_spec_file(spec_path)
        assert result.verdict == "ACCEPT"
        spec = load_json(spec_path)
        draft_path = write_catalog_draft(spec, tmp_path / "drafts")
        skel_path = write_test_skeleton(spec, tmp_path / "tests")
        assert draft_path.is_file()
        assert skel_path.is_file()
        draft = generate_catalog_draft(spec)
        assert draft["tool_id"] == spec["tool_id"]


@pytest.mark.regression
def test_phase2_frozen_results_unchanged(phase2_frozen_run_dir: Path) -> None:
    """Read-only check: frozen Phase 2 run still reports 2/8/0/0."""
    run_dir = phase2_frozen_run_dir
    if not run_dir.is_dir():
        pytest.skip("frozen Phase 2 run directory not present")
    import json

    summary = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))["summary"]
    assert summary["valid_specs_accept"] == 2
    assert summary["failure_cases_reject"] == 8
    assert summary["false_accept"] == 0
    assert summary["false_reject"] == 0
