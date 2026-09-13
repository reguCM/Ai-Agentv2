from __future__ import annotations

from pathlib import Path

import pytest

from validator.validate import validate_tool_spec_file


def _reject_reasons(result) -> list[str]:
    reasons: list[str] = []
    reasons.extend(result.schema_errors)
    reasons.extend(
        i["message"]
        for i in result.safety_issues
        if i.get("severity") == "error"
    )
    return reasons


@pytest.mark.parametrize(
    "fc_name,expected_code_fragment",
    [
        ("fc01_missing_required.json", "tool_id"),
        ("fc02_type_mismatch.json", "boolean"),
        ("fc03_invalid_provider.json", "provider"),
        ("fc04_side_effect_conflict.json", "SIDE_EFFECT_NETWORK_CONFLICT"),
        ("fc05_missing_risk.json", "risk_level"),
        ("fc06_output_schema_mismatch.json", "OUTPUT_SCHEMA_MISMATCH"),
        ("fc07_missing_side_effect.json", "side_effect"),
        ("fc08_invalid_catalog_hints.json", "INVALID_CATALOG_HINTS"),
    ],
)
def test_failure_cases_reject_with_traceable_reason(
    tool_creation_root: Path,
    fc_name: str,
    expected_code_fragment: str,
) -> None:
    path = tool_creation_root / "failure_cases" / fc_name
    result = validate_tool_spec_file(path)
    assert result.verdict == "REJECT", f"{fc_name} should REJECT: {result.to_dict()}"
    reasons = _reject_reasons(result)
    assert reasons, f"{fc_name}: REJECT reason must not be empty"
    joined = " ".join(reasons) + " " + " ".join(
        i.get("code", "") for i in result.safety_issues
    )
    assert expected_code_fragment.lower() in joined.lower(), (
        f"{fc_name}: expected fragment {expected_code_fragment!r} in {reasons}"
    )


def test_all_eight_failure_cases_reject(failure_case_paths: list[Path]) -> None:
    assert len(failure_case_paths) == 8
    for path in failure_case_paths:
        result = validate_tool_spec_file(path)
        assert result.verdict == "REJECT", path.name
        assert _reject_reasons(result), path.name
