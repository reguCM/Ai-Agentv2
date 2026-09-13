"""Human Decision premise tracking for Handoff / Runtime tasks.

Minimal vertical slice: record which decision_id a task was derived from,
preserve it across completion_runtime restore, and flag stale premises after
decision_key supersede. Not a universal dependency graph.
"""
from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping, Sequence

from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    active_decision_for_key,
    is_active_confirmed,
    new_decision_id,
)
from ai_tool.revalidation_protocol import SEMANTIC_REVALIDATION_OUTCOMES as _PREMISE_REVALIDATION_OUTCOMES

INITIAL_GRILL_SEMANTIC_DECISION_KEY = "target:identity"
INITIAL_GRILL_DECISION_KEY_PREFIX = INITIAL_GRILL_SEMANTIC_DECISION_KEY
INITIAL_GRILL_DECISION_KEY = INITIAL_GRILL_SEMANTIC_DECISION_KEY
INITIAL_GRILL_SOURCE = "grill"
BOUNDARY_GRILL_SOURCE = "boundary_grill"

# Production Conversation Grill (apply_human_grill_answer) only opens for
# goal_read_target.uniqueness_class == IDENTITY_UNRESOLVED today.
INITIAL_GRILL_SEMANTIC_KEYS: dict[str, str] = {
    "IDENTITY_UNRESOLVED": INITIAL_GRILL_SEMANTIC_DECISION_KEY,
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug_token(text: str, *, max_len: int = 48) -> str:
    token = _SLUG_RE.sub("-", str(text or "").casefold()).strip("-")
    return token[:max_len] or "unscoped"


def _primary_goal_search_row(orchestrator: Any) -> Mapping[str, Any] | None:
    candidate_sets = getattr(orchestrator, "search_candidate_sets", None) or {}
    if hasattr(candidate_sets, "values"):
        rows = list(candidate_sets.values())
    elif isinstance(candidate_sets, Mapping):
        rows = list(candidate_sets.values())
    else:
        rows = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("observation_role") or "") == "goal_request":
            return row
    for row in rows:
        if isinstance(row, Mapping):
            return row
    return None


def initial_grill_semantic_decision_key(orchestrator: Any) -> str:
    """Semantic decision_key for Initial Grill. Not derived from question wording."""
    target = dict(getattr(orchestrator, "goal_read_target", None) or {})
    uniqueness = str(target.get("uniqueness_class") or "IDENTITY_UNRESOLVED").strip()
    return INITIAL_GRILL_SEMANTIC_KEYS.get(uniqueness, INITIAL_GRILL_SEMANTIC_DECISION_KEY)


def initial_grill_question_id_for_orchestrator(orchestrator: Any) -> str:
    """Instance id for one Initial Grill prompt. Not a semantic decision_key."""
    mission_id = _slug_token(str(getattr(orchestrator, "mission_id", "") or "mission"))
    target = dict(getattr(orchestrator, "goal_read_target", None) or {})
    parts = ["initial_grill", mission_id, _slug_token(str(target.get("reason") or "unscoped"))]
    primary = _primary_goal_search_row(orchestrator)
    if primary is not None:
        query = _slug_token(str(primary.get("query") or ""))
        path = _slug_token(str(primary.get("path") or ""))
        if query:
            parts.append(f"q-{query}")
        if path:
            parts.append(f"p-{path}")
    round_index = len(getattr(orchestrator, "_human_grill_answers", None) or [])
    parts.append(f"round-{round_index}")
    return ":".join(parts)


def initial_grill_decision_key_for_orchestrator(orchestrator: Any) -> str:
    """Backward-compatible alias. Semantic key is stable; use question_id for instances."""
    return INITIAL_GRILL_SEMANTIC_DECISION_KEY


def build_initial_grill_decision_record(
    text: str,
    *,
    decision_key: str | None = None,
    question_id: str | None = None,
    extracted_path_grounds: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Normalize an Initial Grill Human answer into a Decision Record."""
    answer = str(text or "").strip()
    key = str(decision_key or "").strip() or INITIAL_GRILL_SEMANTIC_DECISION_KEY
    payload: dict[str, Any] = {
        "decision_id": new_decision_id(),
        "decision_key": key,
        "status": DECISION_STATUS_CONFIRMED,
        "source": INITIAL_GRILL_SOURCE,
        "text": answer,
        "extracted_path_grounds": [
            str(item) for item in (extracted_path_grounds or []) if str(item).strip()
        ],
        "role": "confirmed_clarification",
        "human_confirmed": True,
    }
    if question_id:
        payload["question_id"] = str(question_id)
    return payload


def normalize_decision_record(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Ensure minimum Decision Record fields for grill-sourced clarifications."""
    if not isinstance(row, Mapping):
        return None
    text = str(row.get("text") or "").strip()
    if not text and not str(row.get("decision_id") or "").strip():
        return None
    source = str(row.get("source") or INITIAL_GRILL_SOURCE).strip() or INITIAL_GRILL_SOURCE
    decision_key = str(row.get("decision_key") or "").strip()
    if not decision_key:
        if source == BOUNDARY_GRILL_SOURCE:
            dimension = str(row.get("dimension") or "acceptance").strip() or "acceptance"
            decision_key = (
                "acceptance:output_format"
                if dimension == "acceptance"
                else f"{dimension}:general"
            )
        else:
            decision_key = INITIAL_GRILL_SEMANTIC_DECISION_KEY
    decision_id = str(row.get("decision_id") or "").strip() or new_decision_id()
    status = str(row.get("status") or DECISION_STATUS_CONFIRMED).strip() or DECISION_STATUS_CONFIRMED
    payload: dict[str, Any] = {
        "decision_id": decision_id,
        "decision_key": decision_key,
        "status": status,
        "source": source,
    }
    if text:
        payload["text"] = text
    for key in (
        "dimension",
        "decision_subject",
        "option_id",
        "question_id",
        "human_confirmed",
        "auto_selected",
        "selection_policy",
        "supersedes",
        "superseded_by",
        "superseded_at_execution_id",
        "extracted_path_grounds",
        "role",
    ):
        if key in row and row.get(key) not in (None, "", []):
            payload[key] = row[key]
    return payload


def coerce_decision_premises(raw: Any) -> list[dict[str, str]]:
    """Normalize handoff / runtime decision premise rows."""
    if not isinstance(raw, list):
        return []
    premises: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        decision_key = str(item.get("decision_key") or "").strip()
        derived_from_decision_id = str(item.get("derived_from_decision_id") or "").strip()
        if not decision_key or not derived_from_decision_id:
            continue
        row = {
            "decision_key": decision_key,
            "derived_from_decision_id": derived_from_decision_id,
        }
        validated = str(item.get("validated_against_decision_id") or "").strip()
        if validated:
            row["validated_against_decision_id"] = validated
        if row not in premises:
            premises.append(row)
    return premises


def premise_validated_decision_id(premise: Mapping[str, str]) -> str:
    """Latest validated decision id, or derived provenance when never validated."""
    validated = str(premise.get("validated_against_decision_id") or "").strip()
    if validated:
        return validated
    return str(premise.get("derived_from_decision_id") or "").strip()


def initialize_premise_validation(premise: Mapping[str, str]) -> dict[str, str]:
    """Ensure validated baseline defaults to derived provenance at task creation."""
    row = dict(premise)
    derived = str(row.get("derived_from_decision_id") or "").strip()
    if derived and not str(row.get("validated_against_decision_id") or "").strip():
        row["validated_against_decision_id"] = derived
    return row


def normalize_task_decision_premises(task: Any) -> list[dict[str, str]]:
    premises = [initialize_premise_validation(row) for row in task_decision_premises(task)]
    if isinstance(task, Mapping):
        task["decision_premises"] = premises
    else:
        task.decision_premises = premises
    return premises


def task_decision_premises(task: Any) -> list[dict[str, str]]:
    if isinstance(task, Mapping):
        return coerce_decision_premises(task.get("decision_premises"))
    return coerce_decision_premises(getattr(task, "decision_premises", None))


def active_decision_id_for_key(
    clarifications: Sequence[Mapping[str, Any]] | None,
    decision_key: str,
) -> str | None:
    active = active_decision_for_key(
        [dict(item) for item in (clarifications or []) if isinstance(item, Mapping)],
        decision_key,
    )
    if not active:
        return None
    decision_id = str(active.get("decision_id") or "").strip()
    return decision_id or None


def evaluate_task_revalidation(
    task: Any,
    clarifications: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return revalidation metadata when validated baseline diverges from active decisions."""
    premises = normalize_task_decision_premises(task)
    if not premises:
        return None
    stale_decision_ids: list[str] = []
    active_decision_ids: dict[str, str | None] = {}
    validated_decision_ids: dict[str, str] = {}
    derived_decision_ids: dict[str, str] = {}
    for premise in premises:
        decision_key = premise["decision_key"]
        derived_id = premise["derived_from_decision_id"]
        baseline_id = premise_validated_decision_id(premise)
        active_id = active_decision_id_for_key(clarifications, decision_key)
        active_decision_ids[decision_key] = active_id
        validated_decision_ids[decision_key] = baseline_id
        derived_decision_ids[decision_key] = derived_id
        if active_id != baseline_id:
            stale_decision_ids.append(baseline_id)
    if not stale_decision_ids:
        return {
            "needs_revalidation": False,
            "affected": False,
            "decision_premises": premises,
            "active_decision_ids": active_decision_ids,
            "validated_decision_ids": validated_decision_ids,
            "derived_decision_ids": derived_decision_ids,
        }
    return {
        "needs_revalidation": True,
        "affected": True,
        "decision_premises": premises,
        "stale_decision_ids": stale_decision_ids,
        "active_decision_ids": active_decision_ids,
        "validated_decision_ids": validated_decision_ids,
        "derived_decision_ids": derived_decision_ids,
    }


def set_task_revalidation(task: Any, metadata: Mapping[str, Any] | None) -> None:
    if metadata:
        payload = dict(metadata)
    else:
        payload = None
    if isinstance(task, Mapping):
        task["revalidation"] = payload
        return
    setattr(task, "revalidation", payload)


def merge_premise_revalidation_metadata(
    prior: Mapping[str, Any] | None,
    computed: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Preserve recorded semantic outcomes when still evaluated against current active decisions."""
    if not computed:
        return dict(prior) if isinstance(prior, Mapping) else None
    merged = dict(computed)
    if not isinstance(prior, Mapping):
        return merged
    premise_rev = prior.get("premise_revalidation")
    if not isinstance(premise_rev, Mapping):
        return merged
    outcome = str(premise_rev.get("outcome") or "").strip()
    if outcome not in _PREMISE_REVALIDATION_OUTCOMES:
        return merged
    evaluated_against = dict(
        premise_rev.get("evaluated_against_decision_ids")
        or premise_rev.get("active_decision_ids")
        or {}
    )
    current_active = dict(computed.get("active_decision_ids") or {})
    if not evaluated_against or evaluated_against != current_active:
        return merged
    merged["premise_revalidation"] = dict(premise_rev)
    if outcome == "still_valid":
        merged["needs_revalidation"] = False
        merged["affected"] = False
        merged.pop("stale_decision_ids", None)
        if isinstance(prior.get("validated_decision_ids"), Mapping):
            merged["validated_decision_ids"] = dict(prior["validated_decision_ids"])
    return merged


def refresh_task_revalidation(
    orchestrator: Any,
    *,
    preserve_semantic: bool = True,
) -> list[str]:
    """Recompute revalidation metadata for all runtime tasks."""
    clarifications = getattr(orchestrator, "confirmed_clarifications", None) or []
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return []
    affected: list[str] = []
    for task_id, task in (getattr(runtime, "tasks", None) or {}).items():
        prior = getattr(task, "revalidation", None)
        if isinstance(task, Mapping):
            prior = task.get("revalidation")
        metadata = evaluate_task_revalidation(task, clarifications)
        if preserve_semantic:
            metadata = merge_premise_revalidation_metadata(prior, metadata)
            if isinstance(prior, Mapping) and isinstance(prior.get("upstream_supersession_wave"), Mapping):
                metadata = dict(metadata or {})
                metadata["upstream_supersession_wave"] = dict(prior["upstream_supersession_wave"])
        set_task_revalidation(task, metadata)
        if metadata and metadata.get("needs_revalidation"):
            affected.append(str(task_id))
    return affected


def tasks_needing_revalidation(orchestrator: Any) -> list[dict[str, Any]]:
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return []
    rows: list[dict[str, Any]] = []
    for task_id, task in (getattr(runtime, "tasks", None) or {}).items():
        metadata = getattr(task, "revalidation", None)
        if isinstance(task, Mapping):
            metadata = task.get("revalidation")
        if isinstance(metadata, Mapping) and metadata.get("needs_revalidation"):
            payload = dict(metadata)
            payload["task_id"] = str(task_id)
            rows.append(payload)
    return rows


def task_snapshot_row(task: Any) -> dict[str, Any]:
    if isinstance(task, Mapping):
        return dict(task)
    if is_dataclass(task):
        return asdict(task)
    return dict(getattr(task, "__dict__", {}) or {})


def active_decision_catalog(
    clarifications: Sequence[Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Active confirmed Human Decisions keyed by decision_key."""
    catalog: dict[str, dict[str, Any]] = {}
    for row in clarifications or []:
        if not isinstance(row, Mapping):
            continue
        normalized = normalize_decision_record(row)
        if not normalized or not is_active_confirmed(normalized):
            continue
        decision_key = str(normalized.get("decision_key") or "").strip()
        decision_id = str(normalized.get("decision_id") or "").strip()
        if not decision_key or not decision_id:
            continue
        catalog[decision_key] = normalized
    return catalog


def format_active_decision_catalog_for_prompt(
    catalog: Mapping[str, Mapping[str, Any]],
) -> str:
    lines: list[str] = []
    for decision_key in sorted(catalog.keys()):
        row = dict(catalog[decision_key])
        lines.append(
            "- "
            f"decision_key={decision_key} "
            f"decision_id={row.get('decision_id')} "
            f"text={row.get('text')!r}"
        )
    return "\n".join(lines)


def _coerce_premise_decision_keys(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    keys: list[str] = []
    for item in raw:
        key = str(item or "").strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def resolve_task_premise_selection(
    task: Mapping[str, Any],
    catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, str]], list[str]]:
    """Resolve AI-selected premise_decision_keys into validated decision_premises."""
    task_id = str(task.get("id") or "").strip() or "task"
    errors: list[str] = []
    premises: list[dict[str, str]] = []

    ai_keys = _coerce_premise_decision_keys(task.get("premise_decision_keys"))
    if ai_keys:
        for decision_key in ai_keys:
            active = catalog.get(decision_key)
            if active is None:
                errors.append(f"{task_id}:unknown_decision_key:{decision_key}")
                continue
            derived_from_decision_id = str(active.get("decision_id") or "").strip()
            if not derived_from_decision_id:
                errors.append(f"{task_id}:missing_active_decision_id:{decision_key}")
                continue
            row = {
                "decision_key": decision_key,
                "derived_from_decision_id": derived_from_decision_id,
            }
            if row not in premises:
                premises.append(row)
        return premises, errors

    for premise in coerce_decision_premises(task.get("decision_premises")):
        decision_key = premise["decision_key"]
        derived_from_decision_id = premise["derived_from_decision_id"]
        active = catalog.get(decision_key)
        if active is None:
            errors.append(f"{task_id}:unknown_decision_key:{decision_key}")
            continue
        active_id = str(active.get("decision_id") or "").strip()
        if derived_from_decision_id != active_id:
            errors.append(
                f"{task_id}:inactive_decision_id:{decision_key}:{derived_from_decision_id}!={active_id}"
            )
            continue
        if premise not in premises:
            premises.append(premise)
    return premises, errors


def attach_handoff_decision_premises(
    tasks: Sequence[Mapping[str, Any]],
    clarifications: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate and attach decision_premises to handoff implementation tasks."""
    catalog = active_decision_catalog(clarifications)
    output: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in tasks:
        task = dict(row)
        premises, row_errors = resolve_task_premise_selection(task, catalog)
        errors.extend(row_errors)
        task.pop("premise_decision_keys", None)
        if premises:
            task["decision_premises"] = premises
        else:
            task.pop("decision_premises", None)
        output.append(task)
    return output, errors


def finalize_handoff_implementation_tasks(
    tasks: Sequence[Mapping[str, Any]],
    clarifications: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Reject unknown or inactive decision references during handoff build."""
    finalized, errors = attach_handoff_decision_premises(tasks, clarifications)
    if errors:
        raise ValueError("handoff decision premise errors: " + "; ".join(sorted(errors)))
    return finalized


__all__ = [
    "BOUNDARY_GRILL_SOURCE",
    "INITIAL_GRILL_DECISION_KEY",
    "INITIAL_GRILL_DECISION_KEY_PREFIX",
    "INITIAL_GRILL_SEMANTIC_DECISION_KEY",
    "INITIAL_GRILL_SOURCE",
    "active_decision_catalog",
    "active_decision_id_for_key",
    "attach_handoff_decision_premises",
    "build_initial_grill_decision_record",
    "coerce_decision_premises",
    "initialize_premise_validation",
    "normalize_task_decision_premises",
    "premise_validated_decision_id",
    "evaluate_task_revalidation",
    "finalize_handoff_implementation_tasks",
    "format_active_decision_catalog_for_prompt",
    "initial_grill_decision_key_for_orchestrator",
    "initial_grill_question_id_for_orchestrator",
    "initial_grill_semantic_decision_key",
    "INITIAL_GRILL_SEMANTIC_KEYS",
    "merge_premise_revalidation_metadata",
    "normalize_decision_record",
    "refresh_task_revalidation",
    "resolve_task_premise_selection",
    "set_task_revalidation",
    "task_decision_premises",
    "task_snapshot_row",
    "tasks_needing_revalidation",
]
