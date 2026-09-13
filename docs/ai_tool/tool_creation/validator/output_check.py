from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def check_output_schema_against_fixture(
    spec: dict[str, Any],
    *,
    base_dir: Path,
) -> list[dict[str, str]]:
    """Optional semantic check when output_validation_fixture is set."""
    issues: list[dict[str, str]] = []
    fixture_rel = spec.get("output_validation_fixture")
    if not fixture_rel:
        return issues

    fixture_path = base_dir / fixture_rel
    if not fixture_path.is_file():
        issues.append(
            {
                "code": "OUTPUT_FIXTURE_MISSING",
                "severity": "error",
                "message": f"fixture not found: {fixture_rel}",
            }
        )
        return issues

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    sample_keys = set(fixture.get("sample_keys") or [])
    output_schema = spec.get("output_schema") or {}
    schema_props = set((output_schema.get("properties") or {}).keys())
    schema_required = set(output_schema.get("required") or [])

    if sample_keys and not sample_keys.intersection(schema_props):
        issues.append(
            {
                "code": "OUTPUT_SCHEMA_MISMATCH",
                "severity": "error",
                "message": (
                    "output_schema properties do not overlap implementation sample keys: "
                    f"schema={sorted(schema_props)} sample={sorted(sample_keys)}"
                ),
            }
        )

    missing_required = sample_keys - schema_props - schema_required
    if missing_required and schema_required:
        overlap = sample_keys - schema_required
        if len(overlap) > len(sample_keys) * 0.5:
            issues.append(
                {
                    "code": "OUTPUT_REQUIRED_MISMATCH",
                    "severity": "warning",
                    "message": f"implementation keys not in schema required: {sorted(missing_required)}",
                }
            )

    return issues
