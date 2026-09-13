from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from .output_check import check_output_schema_against_fixture
from .safety_rules import check_structural_safety

_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _ROOT / "tool_spec.schema.json"


@dataclass
class ValidationResult:
    verdict: str  # ACCEPT | REJECT
    spec_path: str | None = None
    tool_id: str | None = None
    schema_errors: list[str] = field(default_factory=list)
    safety_issues: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_tool_spec(
    spec: dict[str, Any],
    *,
    spec_path: str | None = None,
    base_dir: Path | None = None,
) -> ValidationResult:
    """Structure-only validation. Does not prove the tool behaves correctly."""
    tool_id = spec.get("tool_id")
    schema = _load_schema()
    validator = Draft202012Validator(schema)

    schema_errors: list[str] = []
    for error in sorted(validator.iter_errors(spec), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.path) or "(root)"
        schema_errors.append(f"{path}: {error.message}")

    safety_issues = check_structural_safety(spec)
    if base_dir is not None:
        safety_issues.extend(check_output_schema_against_fixture(spec, base_dir=base_dir))
    elif spec_path:
        safety_issues.extend(
            check_output_schema_against_fixture(
                spec, base_dir=Path(spec_path).resolve().parent.parent
            )
        )
    warnings = [i["message"] for i in safety_issues if i["severity"] == "warning"]
    errors = [i for i in safety_issues if i["severity"] == "error"]

    if schema_errors or errors:
        verdict = "REJECT"
    else:
        verdict = "ACCEPT"

    return ValidationResult(
        verdict=verdict,
        spec_path=spec_path,
        tool_id=str(tool_id) if tool_id else None,
        schema_errors=schema_errors,
        safety_issues=safety_issues,
        warnings=warnings,
    )


def validate_tool_spec_file(path: Path) -> ValidationResult:
    spec = json.loads(path.read_text(encoding="utf-8"))
    base_dir = path.resolve().parent.parent
    return validate_tool_spec(spec, spec_path=str(path), base_dir=base_dir)
