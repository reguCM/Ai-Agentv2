"""Precondition Contract v0 — shared structured preconditions.

Canonical schema: registry/schema/precondition_contract.schema.json

A precondition definition existing on a record does NOT mean it is satisfied.
Use evaluation.status explicitly; default new definitions to UNKNOWN.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, RefResolver

CONTRACT_VERSION = "0.1"

STATUS_UNKNOWN = "UNKNOWN"
STATUS_SATISFIED = "SATISFIED"
STATUS_UNSATISFIED = "UNSATISFIED"
STATUS_WAITING = "WAITING"
STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"

EVALUATION_STATUSES = frozenset(
    {
        STATUS_UNKNOWN,
        STATUS_SATISFIED,
        STATUS_UNSATISFIED,
        STATUS_WAITING,
        STATUS_NOT_APPLICABLE,
    }
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "registry" / "schema" / "precondition_contract.schema.json"


@dataclass
class PreconditionEvaluation:
    status: str = STATUS_UNKNOWN
    evidence_refs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass
class Precondition:
    precondition_id: str
    key: str
    description: str
    blocking: bool = True
    source: str = ""
    evaluation: PreconditionEvaluation = field(default_factory=PreconditionEvaluation)

    def as_dict(self) -> dict[str, Any]:
        return {
            "precondition_id": self.precondition_id,
            "key": self.key,
            "description": self.description,
            "blocking": self.blocking,
            "source": self.source,
            "evaluation": self.evaluation.as_dict(),
        }


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _record_validator() -> Draft202012Validator:
    schema = _load_schema()
    return Draft202012Validator(
        schema["$defs"]["precondition_record"],
        resolver=RefResolver.from_schema(schema),
    )


def mint_precondition_id() -> str:
    return f"pc-{uuid.uuid4().hex[:12]}"


def precondition_definition(
    *,
    key: str,
    description: str,
    source: str,
    blocking: bool = True,
    precondition_id: str | None = None,
) -> Precondition:
    """Create a precondition record with evaluation.status=UNKNOWN."""
    return Precondition(
        precondition_id=precondition_id or mint_precondition_id(),
        key=key,
        description=description,
        blocking=blocking,
        source=source,
        evaluation=PreconditionEvaluation(status=STATUS_UNKNOWN, evidence_refs=[]),
    )


def precondition_evaluated(
    *,
    key: str,
    description: str,
    source: str,
    status: str,
    evidence_refs: Sequence[str] | None = None,
    blocking: bool = True,
    precondition_id: str | None = None,
) -> Precondition:
    if status not in EVALUATION_STATUSES:
        raise ValueError(f"invalid evaluation status: {status}")
    return Precondition(
        precondition_id=precondition_id or mint_precondition_id(),
        key=key,
        description=description,
        blocking=blocking,
        source=source,
        evaluation=PreconditionEvaluation(
            status=status,
            evidence_refs=[str(item) for item in (evidence_refs or []) if str(item).strip()],
        ),
    )


def is_precondition_satisfied(precondition: Precondition | Mapping[str, Any]) -> bool:
    if isinstance(precondition, Precondition):
        return precondition.evaluation.status == STATUS_SATISFIED
    evaluation = precondition.get("evaluation") if isinstance(precondition, Mapping) else None
    if not isinstance(evaluation, Mapping):
        return False
    return str(evaluation.get("status") or "") == STATUS_SATISFIED


def preconditions_all_satisfied(preconditions: Sequence[Precondition | Mapping[str, Any]]) -> bool:
    if not preconditions:
        return True
    return all(is_precondition_satisfied(item) for item in preconditions)


def validate_precondition_dict(payload: Mapping[str, Any]) -> list[str]:
    errors = sorted(
        error.message for error in _record_validator().iter_errors(dict(payload))
    )
    status = ""
    evaluation = payload.get("evaluation")
    if isinstance(evaluation, Mapping):
        status = str(evaluation.get("status") or "")
    refs = []
    if isinstance(evaluation, Mapping):
        refs = list(evaluation.get("evidence_refs") or [])
    if status == STATUS_SATISFIED and not refs:
        errors.append("evaluation.evidence_refs: SATISFIED requires at least one evidence ref in v0")
    if status == STATUS_UNKNOWN and refs:
        errors.append("evaluation.evidence_refs: UNKNOWN must not carry evidence_refs in v0")
    return errors


def validate_preconditions(payload: Sequence[Mapping[str, Any]] | None) -> list[str]:
    if payload is None:
        return []
    errors: list[str] = []
    if not isinstance(payload, list):
        return ["preconditions: must be an array when present"]
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping):
            errors.append(f"preconditions[{index}]: must be an object")
            continue
        for message in validate_precondition_dict(row):
            errors.append(f"preconditions[{index}]: {message}")
    return errors


def preconditions_from_dicts(rows: Sequence[Mapping[str, Any]]) -> list[Precondition]:
    items: list[Precondition] = []
    for row in rows:
        evaluation_raw = row.get("evaluation") or {}
        if not isinstance(evaluation_raw, Mapping):
            evaluation_raw = {}
        items.append(
            Precondition(
                precondition_id=str(row.get("precondition_id") or mint_precondition_id()),
                key=str(row.get("key") or ""),
                description=str(row.get("description") or ""),
                blocking=bool(row.get("blocking")),
                source=str(row.get("source") or ""),
                evaluation=PreconditionEvaluation(
                    status=str(evaluation_raw.get("status") or STATUS_UNKNOWN),
                    evidence_refs=[
                        str(item)
                        for item in (evaluation_raw.get("evidence_refs") or [])
                        if str(item).strip()
                    ],
                ),
            )
        )
    return items


def preconditions_to_dicts(items: Sequence[Precondition]) -> list[dict[str, Any]]:
    return [item.as_dict() for item in items]


def serialize_preconditions(items: Sequence[Precondition]) -> str:
    return json.dumps(preconditions_to_dicts(items), ensure_ascii=False, indent=2)


def restore_preconditions(serialized: str) -> list[Precondition]:
    payload = json.loads(serialized)
    if not isinstance(payload, list):
        raise ValueError("preconditions payload must be a JSON array")
    errors = validate_preconditions(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return preconditions_from_dicts(payload)


def tetris_handoff_precondition_fixtures() -> list[Precondition]:
    """Tetris E2E derived examples — definitions only (UNKNOWN until evaluated)."""
    return [
        precondition_definition(
            key="tech_spec_exists",
            description="Tech spec artifact exists before goal-handoff / implementation.",
            source="goal-handoff:planning-and-task-breakdown",
            blocking=True,
            precondition_id="pc-tetris-tech-spec",
        ),
        precondition_definition(
            key="task_ids_unique",
            description="Handoff implementation_tasks ids are unique T1..Tn.",
            source="goal-handoff:schema_validation",
            blocking=True,
            precondition_id="pc-tetris-task-ids",
        ),
        precondition_definition(
            key="dependency_refs_resolved",
            description="Task dependencies reference existing task ids only.",
            source="goal-handoff:normalize_implementation_tasks",
            blocking=True,
            precondition_id="pc-tetris-deps",
        ),
    ]


__all__ = [
    "CONTRACT_VERSION",
    "EVALUATION_STATUSES",
    "Precondition",
    "PreconditionEvaluation",
    "SCHEMA_PATH",
    "STATUS_NOT_APPLICABLE",
    "STATUS_SATISFIED",
    "STATUS_UNKNOWN",
    "STATUS_UNSATISFIED",
    "STATUS_WAITING",
    "is_precondition_satisfied",
    "mint_precondition_id",
    "precondition_definition",
    "precondition_evaluated",
    "preconditions_all_satisfied",
    "preconditions_from_dicts",
    "preconditions_to_dicts",
    "restore_preconditions",
    "serialize_preconditions",
    "tetris_handoff_precondition_fixtures",
    "validate_precondition_dict",
    "validate_preconditions",
]
