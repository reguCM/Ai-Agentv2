"""Thin shared protocol for semantic revalidation outcomes and change lineage.

Decision premise revalidation and Task upstream supersession revalidation
share these low-level pieces. Case builders, orchestration, and metadata
keys remain domain-specific.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Mapping, Sequence

from ai_tool.llm_json_parse import parse_llm_json_response

SemanticRevalidationOutcome = Literal[
    "still_valid",
    "needs_revision",
    "invalid",
    "cannot_determine",
]

SEMANTIC_REVALIDATION_OUTCOMES: frozenset[str] = frozenset(
    {
        "still_valid",
        "needs_revision",
        "invalid",
        "cannot_determine",
    }
)

SEMANTIC_REVALIDATION_OUTCOME_ENUM_TEXT = (
    "still_valid|needs_revision|invalid|cannot_determine"
)

SEMANTIC_REVALIDATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["outcome", "reason"],
    "properties": {
        "outcome": {
            "type": "string",
            "enum": sorted(SEMANTIC_REVALIDATION_OUTCOMES),
        },
        "reason": {"type": "string"},
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_semantic_revalidation_outcome(raw: Any) -> SemanticRevalidationOutcome:
    token = str(raw or "").strip()
    if token in SEMANTIC_REVALIDATION_OUTCOMES:
        return token  # type: ignore[return-value]
    return "cannot_determine"


def is_semantic_revalidation_outcome(raw: Any) -> bool:
    return str(raw or "").strip() in SEMANTIC_REVALIDATION_OUTCOMES


def semantic_revalidation_result_missing_inputs(
    missing_fields: Sequence[str],
) -> dict[str, Any]:
    return {
        "outcome": "cannot_determine",
        "reason": "missing_required_inputs",
        "missing_fields": list(missing_fields),
        "evaluated_at": utc_now_iso(),
    }


def semantic_revalidation_result_missing_chat_fn() -> dict[str, Any]:
    return {
        "outcome": "cannot_determine",
        "reason": "chat_fn_not_configured",
        "missing_fields": ["chat_fn"],
        "evaluated_at": utc_now_iso(),
    }


def semantic_revalidation_result_invalid_schema(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "outcome": "cannot_determine",
        "reason": "invalid_llm_schema",
        "missing_fields": ["outcome"],
        "evaluated_at": utc_now_iso(),
        "llm_payload": dict(payload),
    }


def evaluate_semantic_revalidation_llm(
    *,
    prompt: str,
    chat_fn: Callable[..., Any],
    model: str = "fake",
    num_predict: int = 800,
) -> dict[str, Any]:
    """Prompt-independent LLM call, JSON parse, outcome normalize, schema guard."""
    response = chat_fn(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[],
        format=SEMANTIC_REVALIDATION_OUTPUT_SCHEMA,
        execution_profile="structured_output",
        options={"temperature": 0, "num_predict": num_predict},
    )
    payload = parse_llm_json_response(response)
    outcome = normalize_semantic_revalidation_outcome(payload.get("outcome"))
    if outcome == "cannot_determine" and payload.get("outcome") not in SEMANTIC_REVALIDATION_OUTCOMES:
        return semantic_revalidation_result_invalid_schema(payload)
    reason = str(payload.get("reason") or "").strip() or None
    return {
        "outcome": outcome,
        "reason": reason,
        "evaluated_at": utc_now_iso(),
        "llm_payload": payload,
    }


@dataclass(frozen=True)
class ChangeLineagePair:
    """Canonical old->new lineage pair. Task callers use old_task_id/new_task_id keys."""

    old_id: str
    new_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "old_task_id": str(self.old_id or "").strip(),
            "new_task_id": str(self.new_id or "").strip(),
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any] | tuple[str, str]) -> ChangeLineagePair | None:
        if isinstance(row, tuple) and len(row) == 2:
            old_id = str(row[0] or "").strip()
            new_id = str(row[1] or "").strip()
        elif isinstance(row, Mapping):
            old_id = str(
                row.get("old_task_id")
                or row.get("old_upstream_task_id")
                or row.get("old_id")
                or ""
            ).strip()
            new_id = str(
                row.get("new_task_id")
                or row.get("new_upstream_task_id")
                or row.get("new_id")
                or ""
            ).strip()
        else:
            return None
        if not old_id or not new_id:
            return None
        return cls(old_id=old_id, new_id=new_id)


def normalize_change_lineage_pair(old_id: str, new_id: str) -> dict[str, str]:
    pair = ChangeLineagePair(old_id=old_id, new_id=new_id)
    return pair.as_dict()


def canonical_change_lineage_set(
    changes: Sequence[Mapping[str, Any] | tuple[str, str] | ChangeLineagePair] | None,
) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for row in changes or []:
        if isinstance(row, ChangeLineagePair):
            parsed = row
        else:
            parsed = ChangeLineagePair.from_mapping(row)
        if parsed is None:
            continue
        pairs.append((parsed.old_id, parsed.new_id))
    return tuple(sorted(set(pairs)))


def change_lineage_set_identity(
    change_set: Sequence[Mapping[str, Any] | tuple[str, str] | ChangeLineagePair]
    | tuple[tuple[str, str], ...],
) -> str:
    return "|".join(f"{old}->{new}" for old, new in canonical_change_lineage_set(change_set))


@dataclass
class PropagationRunReport:
    """Task change propagation observation. Not used for Decision orchestration."""

    propagation_id: str
    completed_wave_count: int
    stop_reason: str
    converged: bool
    processed_change_sets: list[str] = field(default_factory=list)
    successor_history: list[dict[str, Any]] = field(default_factory=list)
    held_tasks: list[dict[str, Any]] = field(default_factory=list)
    waves: list[dict[str, Any]] = field(default_factory=list)
    completed_wave_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_propagation_run_report(
    *,
    propagation_id: str,
    completed_wave_count: int,
    processed_change_sets: Sequence[str],
    successor_history: Sequence[Mapping[str, Any]],
    held_tasks: Sequence[Mapping[str, Any]],
    stop_reason: str,
    waves: Sequence[Mapping[str, Any]],
    converged_stop_reason: str,
) -> dict[str, Any]:
    converged = stop_reason == converged_stop_reason
    completed_wave_index = (
        max(0, completed_wave_count - 1) if completed_wave_count else None
    )
    return PropagationRunReport(
        propagation_id=propagation_id,
        completed_wave_count=completed_wave_count,
        completed_wave_index=completed_wave_index,
        processed_change_sets=list(processed_change_sets),
        successor_history=[dict(row) for row in successor_history],
        held_tasks=[dict(row) for row in held_tasks],
        stop_reason=stop_reason,
        waves=[dict(row) for row in waves],
        converged=converged,
    ).as_dict()


__all__ = [
    "ChangeLineagePair",
    "PropagationRunReport",
    "SEMANTIC_REVALIDATION_OUTCOME_ENUM_TEXT",
    "SEMANTIC_REVALIDATION_OUTCOMES",
    "SEMANTIC_REVALIDATION_OUTPUT_SCHEMA",
    "SemanticRevalidationOutcome",
    "build_propagation_run_report",
    "canonical_change_lineage_set",
    "change_lineage_set_identity",
    "evaluate_semantic_revalidation_llm",
    "is_semantic_revalidation_outcome",
    "normalize_change_lineage_pair",
    "normalize_semantic_revalidation_outcome",
    "semantic_revalidation_result_invalid_schema",
    "semantic_revalidation_result_missing_chat_fn",
    "semantic_revalidation_result_missing_inputs",
    "utc_now_iso",
]
