"""Structure validation for frozen Mission / Execution / Evidence draft records.

Does not persist records, assign production paths, or connect Chat / Runtime.
Does not prove goal achievement, reverification, or operational completeness.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
MISSION_SCHEMA_PATH = SCHEMA_DIR / "mission.schema.json"
EXECUTION_SCHEMA_PATH = SCHEMA_DIR / "execution.schema.json"
EVIDENCE_SCHEMA_PATH = SCHEMA_DIR / "evidence.schema.json"

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _load_schema(path: Path) -> dict[str, Any]:
    key = str(path)
    cached = _SCHEMA_CACHE.get(key)
    if cached is None:
        cached = json.loads(path.read_text(encoding="utf-8"))
        _SCHEMA_CACHE[key] = cached
    return cached


def schema_version() -> str:
    """Draft schema_version from the Mission schema const. Do not duplicate the literal."""
    schema = _load_schema(MISSION_SCHEMA_PATH)
    return str(schema["properties"]["schema_version"]["const"])


@dataclass
class ValidationResult:
    verdict: str
    schema_errors: list[str] = field(default_factory=list)
    join_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _schema_errors(instance: Any, schema: dict[str, Any], *, prefix: str) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        path = ".".join(str(part) for part in error.path) or "(root)"
        errors.append(f"{prefix}{path}: {error.message}")
    return errors


def _finish(schema_errors: list[str], join_errors: list[str]) -> ValidationResult:
    verdict = "ACCEPT" if not schema_errors and not join_errors else "REJECT"
    return ValidationResult(
        verdict=verdict,
        schema_errors=schema_errors,
        join_errors=join_errors,
    )


def validate_mission(record: dict[str, Any], *, prefix: str = "mission.") -> ValidationResult:
    errors = _schema_errors(record, _load_schema(MISSION_SCHEMA_PATH), prefix=prefix)
    return _finish(errors, [])


def validate_execution(record: dict[str, Any], *, prefix: str = "execution.") -> ValidationResult:
    errors = _schema_errors(record, _load_schema(EXECUTION_SCHEMA_PATH), prefix=prefix)
    return _finish(errors, [])


def validate_evidence(record: dict[str, Any], *, prefix: str = "evidence.") -> ValidationResult:
    errors = _schema_errors(record, _load_schema(EVIDENCE_SCHEMA_PATH), prefix=prefix)
    return _finish(errors, [])


def validate_bundle(
    *,
    mission: dict[str, Any] | None = None,
    executions: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> ValidationResult:
    """Validate provided records and Join among the sets that are present.

    Omitted sets are not treated as empty. An empty list is an explicit provided set.
    """
    schema_errors: list[str] = []
    join_errors: list[str] = []

    if mission is not None:
        schema_errors.extend(
            validate_mission(mission, prefix="mission.").schema_errors
        )

    execution_by_id: dict[str, dict[str, Any]] = {}
    sequences_by_mission: dict[str, dict[int, str]] = {}
    if executions is not None:
        for index, record in enumerate(executions):
            prefix = f"executions[{index}]."
            schema_errors.extend(
                validate_execution(record, prefix=prefix).schema_errors
            )
            execution_id = record.get("execution_id")
            mission_id = record.get("mission_id")
            sequence = record.get("execution_sequence")
            if isinstance(execution_id, str) and execution_id:
                if execution_id in execution_by_id:
                    join_errors.append(
                        f"{prefix}execution_id: DUPLICATE_EXECUTION_ID {execution_id}"
                    )
                else:
                    execution_by_id[execution_id] = record
            if (
                isinstance(mission_id, str)
                and mission_id
                and isinstance(sequence, int)
            ):
                seen = sequences_by_mission.setdefault(mission_id, {})
                previous = seen.get(sequence)
                if previous is not None:
                    join_errors.append(
                        f"{prefix}execution_sequence: EXECUTION_SEQUENCE_DUPLICATE "
                        f"mission_id={mission_id} sequence={sequence} "
                        f"other_execution_id={previous}"
                    )
                elif isinstance(execution_id, str) and execution_id:
                    seen[sequence] = execution_id
            if (
                mission is not None
                and isinstance(mission_id, str)
                and mission_id
                and mission_id != mission.get("mission_id")
            ):
                join_errors.append(
                    f"{prefix}mission_id: EXECUTION_MISSION_MISMATCH "
                    f"execution.mission_id={mission_id} "
                    f"mission.mission_id={mission.get('mission_id')}"
                )

    evidence_by_id: dict[str, dict[str, Any]] = {}
    if evidence is not None:
        for index, record in enumerate(evidence):
            prefix = f"evidence[{index}]."
            schema_errors.extend(
                validate_evidence(record, prefix=prefix).schema_errors
            )
            persistent_id = record.get("persistent_evidence_id")
            if isinstance(persistent_id, str) and persistent_id:
                if persistent_id in evidence_by_id:
                    join_errors.append(
                        f"{prefix}persistent_evidence_id: DUPLICATE_EVIDENCE_ID "
                        f"{persistent_id}"
                    )
                else:
                    evidence_by_id[persistent_id] = record
            created_by = record.get("created_by_execution_id")
            created_in = record.get("created_in_mission_id")
            if executions is not None and isinstance(created_by, str) and created_by:
                creator = execution_by_id.get(created_by)
                if creator is None:
                    join_errors.append(
                        f"{prefix}created_by_execution_id: "
                        f"EVIDENCE_CREATED_BY_EXECUTION_MISSING {created_by}"
                    )
                elif (
                    isinstance(created_in, str)
                    and created_in
                    and creator.get("mission_id") != created_in
                ):
                    join_errors.append(
                        f"{prefix}created_in_mission_id: "
                        f"EVIDENCE_PROVENANCE_MISSION_MISMATCH "
                        f"created_in_mission_id={created_in} "
                        f"created_by_execution.mission_id={creator.get('mission_id')}"
                    )

    if executions is not None and evidence is not None:
        for index, record in enumerate(executions):
            refs = record.get("evidence_refs")
            if not isinstance(refs, list):
                continue
            for ref_index, ref in enumerate(refs):
                if isinstance(ref, str) and ref and ref not in evidence_by_id:
                    join_errors.append(
                        f"executions[{index}].evidence_refs[{ref_index}]: "
                        f"EVIDENCE_REF_UNRESOLVED {ref}"
                    )

    return _finish(schema_errors, join_errors)
