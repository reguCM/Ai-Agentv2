"""S9 — Validate run_test_plan tool arguments against canonical evaluation schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_evaluation.schema.json"


def load_test_plan_subschema(eval_schema_path: Path | None = None) -> dict[str, Any]:
    path = eval_schema_path or DEFAULT_EVAL_SCHEMA
    doc = json.loads(path.read_text(encoding="utf-8"))
    sub = doc.get("$defs", {}).get("test_plan")
    if not isinstance(sub, dict):
        raise ValueError("evaluation schema missing $defs.test_plan")
    return sub


def validate_test_plan_object(
    test_plan: Mapping[str, Any],
    *,
    eval_schema_path: Path | None = None,
) -> None:
    import jsonschema

    path = eval_schema_path or DEFAULT_EVAL_SCHEMA
    doc = json.loads(path.read_text(encoding="utf-8"))
    subschema = load_test_plan_subschema(eval_schema_path)
    # Validate against $defs/test_plan while resolving sibling $defs ($ref) from the full file.
    validator = jsonschema.Draft202012Validator(doc)
    validator.evolve(schema=subschema).validate(dict(test_plan))


def extract_test_plan_from_arguments(
    arguments: Mapping[str, Any],
    *,
    eval_schema_path: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(arguments, Mapping):
        raise ValueError("arguments must be an object")
    raw = arguments.get("test_plan")
    if not isinstance(raw, Mapping):
        raise ValueError("arguments.test_plan is required")
    plan = dict(raw)
    validate_test_plan_object(plan, eval_schema_path=eval_schema_path)
    return plan


def extract_optional_authorization_packet(
    arguments: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Resume-only optional packet; not used for plan fingerprint."""
    raw = arguments.get("authorization_packet")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("authorization_packet must be an object when present")
    return dict(raw)
