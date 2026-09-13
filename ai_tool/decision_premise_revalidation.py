"""Minimal Decision premise revalidation for stale Runtime tasks.

System prepares stale vs active premise pairs and records LLM semantic outcomes.
Does not replan, delete tasks, or roll back actions.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from ai_tool.chat_interface.decision_change_gate import active_decision_for_key
from ai_tool.human_decision_premise import (
    active_decision_id_for_key,
    premise_validated_decision_id,
    set_task_revalidation,
    task_decision_premises,
    task_snapshot_row,
    tasks_needing_revalidation,
)
from ai_tool.revalidation_protocol import (
    SEMANTIC_REVALIDATION_OUTCOME_ENUM_TEXT,
    SEMANTIC_REVALIDATION_OUTCOMES,
    SEMANTIC_REVALIDATION_OUTPUT_SCHEMA,
    SemanticRevalidationOutcome,
    evaluate_semantic_revalidation_llm,
    is_semantic_revalidation_outcome,
    normalize_semantic_revalidation_outcome,
    semantic_revalidation_result_missing_chat_fn,
    semantic_revalidation_result_missing_inputs,
    utc_now_iso,
)

RevalidationOutcome = SemanticRevalidationOutcome
REVALIDATION_OUTCOMES = SEMANTIC_REVALIDATION_OUTCOMES
PREMISE_REVALIDATION_OUTPUT_SCHEMA = SEMANTIC_REVALIDATION_OUTPUT_SCHEMA


def _decision_by_id(
    clarifications: Sequence[Mapping[str, Any]] | None,
    decision_id: str,
) -> dict[str, Any] | None:
    token = str(decision_id or "").strip()
    if not token:
        return None
    for row in clarifications or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("decision_id") or "").strip() == token:
            return dict(row)
    return None


def _task_row(orchestrator: Any, task_id: str) -> Any | None:
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return None
    return (getattr(runtime, "tasks", None) or {}).get(task_id)


def _task_evidence_summaries(orchestrator: Any, task: Any) -> list[dict[str, str]]:
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return []
    evidence_ids = list(getattr(task, "evidence_ids", None) or [])
    if isinstance(task, Mapping):
        evidence_ids = list(task.get("evidence_ids") or [])
    rows: list[dict[str, str]] = []
    for evidence_id in evidence_ids[:5]:
        record = (getattr(runtime, "evidence", None) or {}).get(str(evidence_id))
        if record is None:
            continue
        rows.append(
            {
                "evidence_id": str(evidence_id),
                "summary": str(getattr(record, "summary", "") or ""),
                "source": str(getattr(record, "source", "") or ""),
            }
        )
    return rows


def build_premise_revalidation_case(
    orchestrator: Any,
    task_id: str,
) -> dict[str, Any] | None:
    """System-side package for one task that currently needs_revalidation."""
    task = _task_row(orchestrator, task_id)
    if task is None:
        return None
    snapshot = task_snapshot_row(task)
    metadata = snapshot.get("revalidation") or {}
    if not isinstance(metadata, Mapping) or not metadata.get("needs_revalidation"):
        return None

    clarifications = [
        dict(item)
        for item in (getattr(orchestrator, "confirmed_clarifications", None) or [])
        if isinstance(item, dict)
    ]
    premises = task_decision_premises(task)
    premise_pairs: list[dict[str, Any]] = []
    missing_fields: list[str] = []
    for premise in premises:
        decision_key = str(premise.get("decision_key") or "").strip()
        derived_id = str(premise.get("derived_from_decision_id") or "").strip()
        baseline_id = premise_validated_decision_id(premise)
        if not decision_key:
            missing_fields.append("decision_key")
            continue
        if not derived_id:
            missing_fields.append(f"derived_from_decision_id:{decision_key}")
            continue
        if not baseline_id:
            missing_fields.append(f"validated_baseline:{decision_key}")
            continue
        active = active_decision_for_key(clarifications, decision_key)
        active_id = str((active or {}).get("decision_id") or "").strip() or None
        baseline = _decision_by_id(clarifications, baseline_id)
        if active is None or not active_id:
            missing_fields.append(f"active_decision:{decision_key}")
        premise_pairs.append(
            {
                "decision_key": decision_key,
                "derived_from_decision_id": derived_id,
                "validated_baseline_decision_id": baseline_id,
                "active_decision_id": active_id,
                "validated_baseline_decision": baseline,
                "active_decision": dict(active) if active else None,
            }
        )

    if not premises:
        missing_fields.append("decision_premises")

    title = str(snapshot.get("title") or "").strip()
    if not title:
        missing_fields.append("task_title")

    acceptance = [
        str(item).strip()
        for item in (snapshot.get("completion_conditions") or [])
        if str(item).strip()
    ]
    instruction = str(snapshot.get("instruction") or "").strip()
    verification: list[str] = []
    if instruction:
        for line in instruction.splitlines():
            token = line.strip()
            if token.lower().startswith("verification:"):
                continue
            if token.startswith("- ") and "verification" in instruction.lower():
                verification.append(token[2:].strip())

    return {
        "task_id": str(task_id),
        "task_title": title,
        "task_instruction": instruction,
        "acceptance": acceptance,
        "verification": verification,
        "decision_premises": premises,
        "premise_pairs": premise_pairs,
        "missing_fields": sorted(dict.fromkeys(missing_fields)),
        "user_explicit_conditions": list(
            getattr(orchestrator, "user_explicit_conditions", None) or []
        ),
        "evidence": _task_evidence_summaries(orchestrator, task),
        "original_request": str(getattr(orchestrator, "request", "") or ""),
    }


def _build_revalidation_prompt(case: Mapping[str, Any]) -> str:
    pairs = case.get("premise_pairs") or []
    lines = [
        "You evaluate whether a Runtime implementation task remains valid under active Human Decisions.",
        f"Return JSON only: {{\"outcome\": \"{SEMANTIC_REVALIDATION_OUTCOME_ENUM_TEXT}\", \"reason\": \"...\"}}",
        "Do not propose replanning or task deletion.",
        "",
        f"Task ID: {case.get('task_id')}",
        f"Task title: {case.get('task_title')}",
        f"Acceptance: {case.get('acceptance')}",
        f"Verification: {case.get('verification')}",
        f"Original request: {case.get('original_request')}",
        f"User explicit conditions: {case.get('user_explicit_conditions')}",
        "",
        "Decision premise changes:",
    ]
    for pair in pairs:
        baseline = dict(pair.get("validated_baseline_decision") or {})
        active = dict(pair.get("active_decision") or {})
        lines.append(
            f"- key={pair.get('decision_key')}: "
            f"derived_from={pair.get('derived_from_decision_id')}; "
            f"validated[{baseline.get('decision_id')}]={baseline.get('text')} -> "
            f"active[{active.get('decision_id')}]={active.get('text')}"
        )
    lines.append("")
    lines.append(
        "Question: Under the active decision(s), is this task still valid for achieving the Goal?"
    )
    return "\n".join(lines)


def _active_decision_ids_from_metadata(metadata: Mapping[str, Any] | None) -> dict[str, str | None]:
    if not isinstance(metadata, Mapping):
        return {}
    return {
        str(key): (str(value) if value is not None else None)
        for key, value in dict(metadata.get("active_decision_ids") or {}).items()
        if str(key)
    }


def premise_revalidation_already_current(task: Any) -> bool:
    """True when a semantic outcome is already recorded for the current active decision set."""
    metadata = getattr(task, "revalidation", None)
    if isinstance(task, Mapping):
        metadata = task.get("revalidation")
    if not isinstance(metadata, Mapping) or not metadata.get("needs_revalidation"):
        return False
    premise_rev = metadata.get("premise_revalidation")
    if not isinstance(premise_rev, Mapping):
        return False
    outcome = str(premise_rev.get("outcome") or "").strip()
    if not is_semantic_revalidation_outcome(outcome):
        return False
    evaluated_against = dict(
        premise_rev.get("evaluated_against_decision_ids")
        or premise_rev.get("active_decision_ids")
        or {}
    )
    current_active = _active_decision_ids_from_metadata(metadata)
    return bool(evaluated_against) and evaluated_against == current_active


def evaluate_premise_revalidation(
    case: Mapping[str, Any],
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
) -> dict[str, Any]:
    """LLM semantic judgment only. System already fixed stale vs active premises."""
    missing_fields = list(case.get("missing_fields") or [])
    if missing_fields:
        return semantic_revalidation_result_missing_inputs(missing_fields)
    if chat_fn is None:
        return semantic_revalidation_result_missing_chat_fn()
    return evaluate_semantic_revalidation_llm(
        prompt=_build_revalidation_prompt(case),
        chat_fn=chat_fn,
        model=model,
        num_predict=800,
    )


def apply_premise_revalidation_result(
    orchestrator: Any,
    task_id: str,
    result: Mapping[str, Any],
    *,
    case: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist structured revalidation outcome without changing TaskStatus."""
    task = _task_row(orchestrator, task_id)
    if task is None:
        raise ValueError(f"unknown task: {task_id}")

    metadata = dict(getattr(task, "revalidation", None) or {})
    if isinstance(task, Mapping):
        metadata = dict(task.get("revalidation") or {})

    outcome = normalize_semantic_revalidation_outcome(result.get("outcome"))
    premise_pairs = list((case or {}).get("premise_pairs") or [])
    active_decision_ids = {
        str(pair.get("decision_key") or ""): pair.get("active_decision_id")
        for pair in premise_pairs
        if str(pair.get("decision_key") or "")
    }
    validated_baseline_ids = {
        str(pair.get("decision_key") or ""): str(pair.get("validated_baseline_decision_id") or "")
        for pair in premise_pairs
        if str(pair.get("decision_key") or "")
    }

    metadata["premise_revalidation"] = {
        "outcome": outcome,
        "reason": result.get("reason"),
        "missing_fields": list(result.get("missing_fields") or []),
        "evaluated_at": result.get("evaluated_at") or utc_now_iso(),
        "validated_baseline_decision_ids": validated_baseline_ids,
        "active_decision_ids": active_decision_ids,
        "evaluated_against_decision_ids": active_decision_ids,
    }

    if outcome == "still_valid":
        metadata["needs_revalidation"] = False
        metadata["affected"] = False
        updated_premises = [dict(row) for row in task_decision_premises(task)]
        for premise in updated_premises:
            decision_key = str(premise.get("decision_key") or "")
            active_id = active_decision_ids.get(decision_key)
            if active_id:
                premise["validated_against_decision_id"] = str(active_id)
        if isinstance(task, Mapping):
            task["decision_premises"] = updated_premises
        else:
            task.decision_premises = updated_premises
        metadata["decision_premises"] = updated_premises
        metadata["validated_decision_ids"] = {
            str(row.get("decision_key") or ""): premise_validated_decision_id(row)
            for row in updated_premises
            if str(row.get("decision_key") or "")
        }
        metadata["derived_decision_ids"] = {
            str(row.get("decision_key") or ""): str(row.get("derived_from_decision_id") or "")
            for row in updated_premises
            if str(row.get("decision_key") or "")
        }
        metadata.pop("stale_decision_ids", None)
    else:
        metadata["needs_revalidation"] = True
        metadata["affected"] = True

    set_task_revalidation(task, metadata)
    return metadata


def run_premise_revalidations(
    orchestrator: Any,
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
) -> list[dict[str, Any]]:
    """Re-evaluate only tasks flagged needs_revalidation by System stale-premise detection."""
    results: list[dict[str, Any]] = []
    for row in tasks_needing_revalidation(orchestrator):
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        task = _task_row(orchestrator, task_id)
        if task is not None and premise_revalidation_already_current(task):
            continue
        case = build_premise_revalidation_case(orchestrator, task_id)
        if case is None:
            continue
        evaluation = evaluate_premise_revalidation(case, chat_fn=chat_fn, model=model)
        metadata = apply_premise_revalidation_result(
            orchestrator,
            task_id,
            evaluation,
            case=case,
        )
        results.append(
            {
                "task_id": task_id,
                "outcome": evaluation.get("outcome"),
                "reason": evaluation.get("reason"),
                "revalidation": metadata,
            }
        )
    return results


__all__ = [
    "PREMISE_REVALIDATION_OUTPUT_SCHEMA",
    "REVALIDATION_OUTCOMES",
    "RevalidationOutcome",
    "apply_premise_revalidation_result",
    "build_premise_revalidation_case",
    "evaluate_premise_revalidation",
    "premise_revalidation_already_current",
    "run_premise_revalidations",
]
