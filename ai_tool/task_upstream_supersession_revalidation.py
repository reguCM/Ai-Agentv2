"""Downstream revalidation when upstream tasks gain replacement/corrective successors."""
from __future__ import annotations

import uuid
from typing import Any, Callable, Mapping, Sequence

from ai_tool.decision_premise_revalidation import _task_evidence_summaries
from ai_tool.human_decision_premise import set_task_revalidation, task_snapshot_row
from ai_tool.revalidation_protocol import (
    SEMANTIC_REVALIDATION_OUTCOME_ENUM_TEXT,
    build_propagation_run_report,
    canonical_change_lineage_set,
    change_lineage_set_identity,
    evaluate_semantic_revalidation_llm,
    is_semantic_revalidation_outcome,
    normalize_change_lineage_pair,
    normalize_semantic_revalidation_outcome,
    semantic_revalidation_result_missing_chat_fn,
    semantic_revalidation_result_missing_inputs,
    utc_now_iso,
)
from ai_tool.premise_corrective_replan import (
    PREMISE_CORRECTIVE_OUTCOMES,
    add_premise_corrective_replan,
)
from ai_tool.premise_pending_replacement import (
    add_pending_replacement,
    downstream_dependent_task_ids,
)
from tools.ai.task_runtime import TaskStatus

WAVE_METADATA_KEY = "upstream_supersession_wave"
LEGACY_METADATA_KEY = "upstream_supersession"
PROPAGATION_CYCLE_ATTR = "upstream_supersession_cycle"
DEFAULT_MAX_PROPAGATION_WAVES = 32
STOP_REASON_CONVERGED = "converged"
STOP_REASON_MAX_WAVES_REACHED = "max_waves_reached"
STOP_REASON_REPEATED_CHANGE_SET = "repeated_change_set"
STOP_REASON_NO_ACTIVE_CHANGES = "no_active_changes"


def new_propagation_id() -> str:
    """Identify one upstream change propagation wave (distinct from execution_id)."""
    return f"pw-{uuid.uuid4().hex[:12]}"


def _task_row(orchestrator: Any, task_id: str) -> Any | None:
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return None
    return (getattr(runtime, "tasks", None) or {}).get(task_id)


def resolve_active_task_id(runtime: Any, task_id: str) -> str:
    """Follow supersession lineage to the current active successor."""
    token = str(task_id or "").strip()
    if not token:
        return token
    tasks = getattr(runtime, "tasks", None) or {}
    seen: set[str] = set()
    current = token
    while current and current not in seen:
        seen.add(current)
        task = tasks.get(current)
        if task is None:
            break
        successor = str(getattr(task, "superseded_by_task_id", "") or "").strip()
        if not successor:
            break
        current = successor
    return current


def normalize_change_pair(old_task_id: str, new_task_id: str) -> dict[str, str]:
    return normalize_change_lineage_pair(old_task_id, new_task_id)


def canonical_change_set(
    changes: Sequence[Mapping[str, Any] | tuple[str, str]] | None,
) -> tuple[tuple[str, str], ...]:
    return canonical_change_lineage_set(changes)


def change_set_identity(
    change_set: Sequence[Mapping[str, Any] | tuple[str, str]] | tuple[tuple[str, str], ...],
) -> str:
    return change_lineage_set_identity(change_set)


def _legacy_pair_to_changes(row: Mapping[str, Any]) -> list[dict[str, str]]:
    old_id = str(row.get("old_upstream_task_id") or "").strip()
    new_id = str(row.get("new_upstream_task_id") or "").strip()
    if not old_id or not new_id:
        nested = row.get("evaluated_against_upstream_pair")
        if isinstance(nested, Mapping):
            old_id = str(nested.get("old_upstream_task_id") or old_id).strip()
            new_id = str(nested.get("new_upstream_task_id") or new_id).strip()
    if old_id and new_id:
        return [normalize_change_pair(old_id, new_id)]
    return []


def _wave_row_from_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, Mapping):
        return None
    wave = metadata.get(WAVE_METADATA_KEY)
    if isinstance(wave, Mapping):
        return dict(wave)
    legacy = metadata.get(LEGACY_METADATA_KEY)
    if isinstance(legacy, Mapping):
        changes = _legacy_pair_to_changes(legacy)
        if not changes:
            return None
        evaluated = legacy.get("evaluated_against_change_set")
        if not isinstance(evaluated, list):
            evaluated = changes if is_semantic_revalidation_outcome(legacy.get("outcome")) else None
        return {
            "propagation_id": legacy.get("propagation_id"),
            "upstream_changes": changes,
            "evaluated_against_change_set": evaluated,
            "outcome": legacy.get("outcome"),
            "reason": legacy.get("reason"),
            "evaluated_at": legacy.get("evaluated_at"),
        }
    return None


def upstream_supersession_metadata(task: Any) -> dict[str, Any] | None:
    metadata = getattr(task, "revalidation", None)
    if isinstance(task, Mapping):
        metadata = task.get("revalidation")
    return _wave_row_from_metadata(metadata if isinstance(metadata, Mapping) else None)


def upstream_supersession_outcome(task: Any) -> str | None:
    wave = upstream_supersession_metadata(task)
    if not wave:
        return None
    outcome = str(wave.get("outcome") or "").strip()
    return outcome or None


def _task_status(task: Any) -> str:
    status = str(getattr(task, "status", "") or "")
    if isinstance(task, Mapping):
        status = str(task.get("status") or status)
    return status


def _successor_artifact_fields(wave: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(wave, Mapping):
        return {}
    preserved: dict[str, Any] = {}
    for key in (
        "successor_change",
        "successor_consumed_change_set",
        "successor_consumed_change_set_identity",
        "successor_generated_at",
        "wave_index",
    ):
        if key in wave and wave.get(key) is not None:
            preserved[key] = wave.get(key)
    return preserved


def get_propagation_cycle(orchestrator: Any) -> dict[str, Any] | None:
    cycle = getattr(orchestrator, PROPAGATION_CYCLE_ATTR, None)
    if isinstance(cycle, Mapping):
        return dict(cycle)
    return None


def set_propagation_cycle(
    orchestrator: Any,
    *,
    propagation_id: str,
    completed_wave_index: int,
) -> dict[str, Any]:
    payload = {
        "propagation_id": str(propagation_id or "").strip(),
        "completed_wave_index": int(completed_wave_index),
    }
    setattr(orchestrator, PROPAGATION_CYCLE_ATTR, payload)
    return payload


def resolve_propagation_id(
    orchestrator: Any,
    propagation_id: str | None = None,
) -> str:
    token = str(propagation_id or "").strip()
    if token:
        return token
    cycle = get_propagation_cycle(orchestrator)
    if cycle and str(cycle.get("propagation_id") or "").strip():
        return str(cycle["propagation_id"])
    return new_propagation_id()


def resolve_wave_index(
    orchestrator: Any,
    wave_index: int | None = None,
) -> int:
    if wave_index is not None:
        return int(wave_index)
    cycle = get_propagation_cycle(orchestrator)
    if cycle is not None:
        return int(cycle.get("completed_wave_index", -1)) + 1
    return 0


def _pending_replacement_exists(runtime: Any, source_task_id: str) -> bool:
    from ai_tool.premise_pending_replacement import PREMISE_PENDING_REPLACEMENT_SOURCE

    for task in (getattr(runtime, "tasks", None) or {}).values():
        if str(getattr(task, "superseded_by_task_id", "") or "") == source_task_id:
            return True
        if (
            str(getattr(task, "source", "") or "") == PREMISE_PENDING_REPLACEMENT_SOURCE
            and str(getattr(task, "source_task_id", "") or "") == source_task_id
        ):
            return True
    return False


def _corrective_task_exists(runtime: Any, source_task_id: str) -> bool:
    from ai_tool.premise_corrective_replan import PREMISE_CORRECTIVE_SOURCE

    for task in (getattr(runtime, "tasks", None) or {}).values():
        if str(getattr(task, "source_task_id", "") or "") != source_task_id:
            continue
        if str(getattr(task, "source", "") or "") == PREMISE_CORRECTIVE_SOURCE:
            return True
    return False


def successor_already_generated(
    orchestrator: Any,
    downstream_task_id: str,
    change_set: tuple[tuple[str, str], ...],
) -> bool:
    task = _task_row(orchestrator, downstream_task_id)
    if task is None:
        return False
    identity = change_set_identity(change_set)
    wave = upstream_supersession_metadata(task) or {}
    successor = wave.get("successor_change")
    if isinstance(successor, Mapping):
        consumed_identity = str(wave.get("successor_consumed_change_set_identity") or "").strip()
        consumed_set = canonical_change_set(wave.get("successor_consumed_change_set"))
        if consumed_identity == identity or consumed_set == change_set:
            return bool(str(successor.get("old_task_id") or "").strip())
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return False
    status = _task_status(task)
    if status == TaskStatus.PENDING.value:
        return _pending_replacement_exists(runtime, downstream_task_id)
    if status == TaskStatus.COMPLETE.value:
        return _corrective_task_exists(runtime, downstream_task_id)
    if task_superseded(task):
        return bool(str(getattr(task, "superseded_by_task_id", "") or "").strip())
    return False


def task_superseded(task: Any) -> bool:
    superseded_by = str(getattr(task, "superseded_by_task_id", "") or "").strip()
    if superseded_by:
        return True
    if isinstance(task, Mapping):
        return bool(str(task.get("superseded_by_task_id") or "").strip())
    return False


def _record_successor_consumed(
    task: Any,
    *,
    successor_change: Mapping[str, str],
    change_set: tuple[tuple[str, str], ...],
) -> None:
    metadata = dict(getattr(task, "revalidation", None) or {})
    if isinstance(task, Mapping):
        metadata = dict(task.get("revalidation") or {})
    wave = dict(_wave_row_from_metadata(metadata) or {})
    wave["successor_change"] = dict(successor_change)
    wave["successor_consumed_change_set"] = [
        normalize_change_pair(old_id, new_id) for old_id, new_id in change_set
    ]
    wave["successor_consumed_change_set_identity"] = change_set_identity(change_set)
    wave["successor_generated_at"] = utc_now_iso()
    metadata[WAVE_METADATA_KEY] = wave
    metadata.pop(LEGACY_METADATA_KEY, None)
    set_task_revalidation(task, metadata)


def _merge_upstream_changes(
    existing: Sequence[Mapping[str, Any]] | None,
    incoming: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    merged: dict[tuple[str, str], dict[str, str]] = {}
    for row in list(existing or []) + list(incoming or []):
        if not isinstance(row, Mapping):
            continue
        pair = normalize_change_pair(
            str(row.get("old_task_id") or row.get("old_upstream_task_id") or ""),
            str(row.get("new_task_id") or row.get("new_upstream_task_id") or ""),
        )
        key = (pair["old_task_id"], pair["new_task_id"])
        if key[0] and key[1]:
            merged[key] = pair
    return [merged[key] for key in sorted(merged.keys())]


def wave_evaluation_already_current(task: Any, change_set: tuple[tuple[str, str], ...]) -> bool:
    wave = upstream_supersession_metadata(task)
    if not wave:
        return False
    evaluated = canonical_change_set(wave.get("evaluated_against_change_set"))
    if evaluated != change_set:
        return False
    outcome = str(wave.get("outcome") or "").strip()
    return is_semantic_revalidation_outcome(outcome)


def upstream_supersession_blocks_task_execution(task: Any) -> dict[str, Any] | None:
    wave = upstream_supersession_metadata(task)
    if not wave:
        return None
    outcome = str(wave.get("outcome") or "").strip()
    if outcome == "still_valid":
        return None
    task_id = str(getattr(task, "task_id", "") or "")
    if isinstance(task, Mapping):
        task_id = str(task.get("task_id") or task_id)
    return {
        "task_id": task_id,
        "reason": "upstream_supersession_execution_blocked",
        "outcome": outcome or "pending_evaluation",
        "propagation_id": wave.get("propagation_id"),
        "upstream_changes": list(wave.get("upstream_changes") or []),
        "supersession_reason": wave.get("reason"),
    }


def _task_profile(orchestrator: Any, task: Any) -> dict[str, Any]:
    snapshot = task_snapshot_row(task)
    instruction = str(snapshot.get("instruction") or "").strip()
    acceptance = [
        str(item).strip()
        for item in (snapshot.get("completion_conditions") or [])
        if str(item).strip()
    ]
    verification: list[str] = []
    if instruction:
        for line in instruction.splitlines():
            token = line.strip()
            if token.lower().startswith("verification:"):
                continue
            if token.startswith("- ") and "verification" in instruction.lower():
                verification.append(token[2:].strip())
    return {
        "task_id": str(snapshot.get("task_id") or ""),
        "title": str(snapshot.get("title") or "").strip(),
        "instruction": instruction,
        "acceptance": acceptance,
        "verification": verification,
        "evidence": _task_evidence_summaries(orchestrator, task),
    }


def _successor_change_from_row(row: Mapping[str, Any]) -> dict[str, str] | None:
    old_id = str(row.get("old_upstream_task_id") or row.get("source_task_id") or "").strip()
    new_id = str(
        row.get("new_upstream_task_id")
        or row.get("replacement_task_id")
        or row.get("corrective_task_id")
        or ""
    ).strip()
    if not old_id or not new_id:
        return None
    return normalize_change_pair(old_id, new_id)


def collect_downstream_wave_merges(
    orchestrator: Any,
    successor_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, list[dict[str, str]]]:
    """Merge successor changes per direct downstream task for one wave."""
    runtime = getattr(orchestrator, "runtime", None)
    downstream_map: dict[str, list[dict[str, str]]] = {}
    for row in successor_rows or []:
        change = _successor_change_from_row(row)
        if change is None:
            continue
        downstream_ids = [
            str(item).strip()
            for item in (row.get("downstream_task_ids") or row.get("redirected_dependents") or [])
            if str(item).strip()
        ]
        if not downstream_ids:
            downstream_ids = downstream_dependent_task_ids(runtime, change["old_task_id"])
            active_old = resolve_active_task_id(runtime, change["old_task_id"])
            if active_old and active_old != change["old_task_id"]:
                downstream_ids = sorted(
                    set(downstream_ids)
                    | set(downstream_dependent_task_ids(runtime, active_old))
                    | set(downstream_dependent_task_ids(runtime, change["new_task_id"]))
                )
        for downstream_id in downstream_ids:
            active_downstream_id = resolve_active_task_id(runtime, downstream_id) or downstream_id
            downstream_map[active_downstream_id] = _merge_upstream_changes(
                downstream_map.get(active_downstream_id),
                [change],
            )
    return downstream_map


def resolve_changes_for_propagation(
    orchestrator: Any,
    changes: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    """Keep lineage old/new pairs while dropping empty or no-op rows."""
    runtime = getattr(orchestrator, "runtime", None)
    resolved: list[dict[str, str]] = []
    for row in changes or []:
        old_id = str(row.get("old_task_id") or row.get("old_upstream_task_id") or "").strip()
        new_id = str(row.get("new_task_id") or row.get("new_upstream_task_id") or "").strip()
        if not old_id or not new_id:
            continue
        active_new = resolve_active_task_id(runtime, new_id) if runtime is not None else new_id
        active_new = str(active_new or new_id).strip()
        if old_id == active_new:
            continue
        resolved.append(normalize_change_pair(old_id, active_new))
    merged: dict[tuple[str, str], dict[str, str]] = {}
    for pair in resolved:
        key = (pair["old_task_id"], pair["new_task_id"])
        merged[key] = pair
    return [merged[key] for key in sorted(merged.keys())]


def changes_to_successor_rows(
    orchestrator: Any,
    changes: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Convert propagation change pairs into successor rows for one wave."""
    runtime = getattr(orchestrator, "runtime", None)
    rows: list[dict[str, Any]] = []
    for pair in resolve_changes_for_propagation(orchestrator, changes):
        old_id = pair["old_task_id"]
        new_id = pair["new_task_id"]
        active_old = resolve_active_task_id(runtime, old_id) if runtime is not None else old_id
        active_new = resolve_active_task_id(runtime, new_id) if runtime is not None else new_id
        dependents: set[str] = set()
        for token in (old_id, active_old, new_id, active_new):
            token = str(token or "").strip()
            if not token:
                continue
            for downstream_id in downstream_dependent_task_ids(runtime, token):
                active_downstream = resolve_active_task_id(runtime, downstream_id) or downstream_id
                dependents.add(str(active_downstream))
        rows.append(
            {
                "old_upstream_task_id": old_id,
                "new_upstream_task_id": new_id,
                "source_task_id": old_id,
                "downstream_task_ids": sorted(dependents),
            }
        )
    return rows


def _held_task_entries(
    orchestrator: Any,
    evaluations: Sequence[Mapping[str, Any]] | None,
    *,
    wave_index: int,
) -> list[dict[str, Any]]:
    runtime = getattr(orchestrator, "runtime", None)
    held: list[dict[str, Any]] = []
    for row in evaluations or []:
        downstream_id = str(row.get("downstream_task_id") or "").strip()
        if not downstream_id:
            continue
        task = _task_row(orchestrator, downstream_id)
        if task is None:
            continue
        outcome = str(row.get("outcome") or "").strip()
        status = _task_status(task)
        active_id = resolve_active_task_id(runtime, downstream_id) if runtime is not None else downstream_id
        if outcome == "cannot_determine" or (
            outcome in PREMISE_CORRECTIVE_OUTCOMES and status == TaskStatus.IN_PROGRESS.value
        ):
            held.append(
                {
                    "task_id": str(active_id or downstream_id),
                    "original_task_id": downstream_id,
                    "task_status": status,
                    "outcome": outcome,
                    "wave_index": wave_index,
                    "reason": row.get("reason"),
                    "change_set_identity": row.get("change_set_identity"),
                }
            )
    return held


def apply_wave_hold(
    orchestrator: Any,
    downstream_task_id: str,
    *,
    propagation_id: str,
    upstream_changes: Sequence[Mapping[str, str]],
    wave_index: int | None = None,
) -> dict[str, Any]:
    """Persist pending wave metadata for one downstream without evaluating yet."""
    task = _task_row(orchestrator, downstream_task_id)
    if task is None:
        raise ValueError(f"unknown task: {downstream_task_id}")
    metadata = dict(getattr(task, "revalidation", None) or {})
    if isinstance(task, Mapping):
        metadata = dict(task.get("revalidation") or {})
    prior_wave = _wave_row_from_metadata(metadata) or {}
    merged_changes = _merge_upstream_changes(
        prior_wave.get("upstream_changes"),
        upstream_changes,
    )
    change_set = canonical_change_set(merged_changes)
    evaluated = canonical_change_set(prior_wave.get("evaluated_against_change_set"))
    prior_outcome = str(prior_wave.get("outcome") or "").strip()
    if evaluated == change_set and is_semantic_revalidation_outcome(prior_outcome):
        outcome = prior_outcome
        evaluated_changes = list(prior_wave.get("evaluated_against_change_set") or merged_changes)
        reason = prior_wave.get("reason")
        evaluated_at = prior_wave.get("evaluated_at")
        identity = str(prior_wave.get("change_set_identity") or "").strip() or change_set_identity(change_set)
    else:
        outcome = None
        evaluated_changes = None
        reason = None
        evaluated_at = None
        identity = change_set_identity(change_set) if change_set else None
    wave_payload = {
        "propagation_id": propagation_id,
        "wave_index": wave_index if wave_index is not None else prior_wave.get("wave_index"),
        "upstream_changes": merged_changes,
        "evaluated_against_change_set": evaluated_changes,
        "outcome": outcome,
        "reason": reason,
        "evaluated_at": evaluated_at,
        "change_set_identity": identity,
        **_successor_artifact_fields(prior_wave),
    }
    metadata[WAVE_METADATA_KEY] = wave_payload
    metadata.pop(LEGACY_METADATA_KEY, None)
    set_task_revalidation(task, metadata)
    return wave_payload


def build_upstream_supersession_wave_case(
    orchestrator: Any,
    *,
    downstream_task_id: str,
    upstream_changes: Sequence[Mapping[str, str]],
) -> dict[str, Any] | None:
    downstream = _task_row(orchestrator, downstream_task_id)
    if downstream is None:
        return None
    missing_fields: list[str] = []
    old_upstreams: list[dict[str, Any]] = []
    new_upstreams: list[dict[str, Any]] = []
    for row in upstream_changes:
        old_id = str(row.get("old_task_id") or "").strip()
        new_id = str(row.get("new_task_id") or "").strip()
        old_task = _task_row(orchestrator, old_id)
        new_task = _task_row(orchestrator, new_id)
        if old_task is None:
            missing_fields.append(f"old_upstream_task_id:{old_id}")
            continue
        if new_task is None:
            missing_fields.append(f"new_upstream_task_id:{new_id}")
            continue
        old_upstreams.append(_task_profile(orchestrator, old_task))
        new_upstreams.append(_task_profile(orchestrator, new_task))
    downstream_profile = _task_profile(orchestrator, downstream)
    if not downstream_profile.get("title"):
        missing_fields.append("downstream_task_title")
    if not upstream_changes:
        missing_fields.append("upstream_changes")
    return {
        "downstream_task_id": downstream_task_id,
        "upstream_changes": [dict(row) for row in upstream_changes],
        "downstream": downstream_profile,
        "old_upstreams": old_upstreams,
        "new_upstreams": new_upstreams,
        "missing_fields": sorted(dict.fromkeys(missing_fields)),
        "original_request": str(getattr(orchestrator, "request", "") or ""),
    }


def _build_upstream_supersession_wave_prompt(case: Mapping[str, Any]) -> str:
    downstream = dict(case.get("downstream") or {})
    lines = [
        "You evaluate whether a downstream Runtime task remains valid after its upstream tasks were superseded.",
        f'Return JSON only: {{"outcome": "{SEMANTIC_REVALIDATION_OUTCOME_ENUM_TEXT}", "reason": "..."}}',
        "Do not propose replanning, replacement, or task deletion.",
        "",
        f"Downstream task ID: {case.get('downstream_task_id')}",
        f"Downstream title: {downstream.get('title')}",
        f"Downstream instruction: {downstream.get('instruction')}",
        f"Downstream acceptance: {downstream.get('acceptance')}",
        f"Downstream verification: {downstream.get('verification')}",
        "",
        "Upstream supersession changes:",
    ]
    for index, row in enumerate(case.get("upstream_changes") or [], 1):
        old_upstream = {}
        new_upstream = {}
        if index - 1 < len(case.get("old_upstreams") or []):
            old_upstream = dict((case.get("old_upstreams") or [])[index - 1])
        if index - 1 < len(case.get("new_upstreams") or []):
            new_upstream = dict((case.get("new_upstreams") or [])[index - 1])
        lines.extend(
            [
                f"- Change {index}: {row.get('old_task_id')} -> {row.get('new_task_id')}",
                f"  Old upstream title: {old_upstream.get('title')}",
                f"  Old upstream instruction: {old_upstream.get('instruction')}",
                f"  Old upstream acceptance: {old_upstream.get('acceptance')}",
                f"  Old upstream verification: {old_upstream.get('verification')}",
                f"  Old upstream evidence: {old_upstream.get('evidence')}",
                f"  New upstream title: {new_upstream.get('title')}",
                f"  New upstream instruction: {new_upstream.get('instruction')}",
                f"  New upstream acceptance: {new_upstream.get('acceptance')}",
                f"  New upstream verification: {new_upstream.get('verification')}",
                f"  New upstream evidence: {new_upstream.get('evidence')}",
            ]
        )
    lines.extend(
        [
            "",
            "Question: Assuming all new upstream tasks are the valid successors, are the downstream task's current instruction / acceptance / verification still valid?",
        ]
    )
    return "\n".join(lines)


def evaluate_upstream_supersession(
    case: Mapping[str, Any],
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
) -> dict[str, Any]:
    missing_fields = list(case.get("missing_fields") or [])
    if missing_fields:
        return semantic_revalidation_result_missing_inputs(missing_fields)
    if chat_fn is None:
        return semantic_revalidation_result_missing_chat_fn()
    return evaluate_semantic_revalidation_llm(
        prompt=_build_upstream_supersession_wave_prompt(case),
        chat_fn=chat_fn,
        model=model,
        num_predict=1200,
    )


def apply_upstream_supersession_result(
    orchestrator: Any,
    downstream_task_id: str,
    result: Mapping[str, Any],
    *,
    case: Mapping[str, Any] | None = None,
    propagation_id: str | None = None,
    wave_index: int | None = None,
) -> dict[str, Any]:
    task = _task_row(orchestrator, downstream_task_id)
    if task is None:
        raise ValueError(f"unknown task: {downstream_task_id}")
    metadata = dict(getattr(task, "revalidation", None) or {})
    if isinstance(task, Mapping):
        metadata = dict(task.get("revalidation") or {})
    prior_wave = _wave_row_from_metadata(metadata) or {}
    upstream_changes = _merge_upstream_changes(
        prior_wave.get("upstream_changes"),
        (case or {}).get("upstream_changes"),
    )
    change_set = canonical_change_set(upstream_changes)
    outcome = normalize_semantic_revalidation_outcome(result.get("outcome"))
    metadata[WAVE_METADATA_KEY] = {
        "propagation_id": propagation_id or prior_wave.get("propagation_id"),
        "wave_index": wave_index if wave_index is not None else prior_wave.get("wave_index"),
        "upstream_changes": upstream_changes,
        "evaluated_against_change_set": [
            normalize_change_pair(old_id, new_id)
            for old_id, new_id in change_set
        ],
        "outcome": outcome,
        "reason": result.get("reason"),
        "missing_fields": list(result.get("missing_fields") or []),
        "evaluated_at": result.get("evaluated_at") or utc_now_iso(),
        "change_set_identity": change_set_identity(change_set),
        **_successor_artifact_fields(prior_wave),
    }
    metadata.pop(LEGACY_METADATA_KEY, None)
    set_task_revalidation(task, metadata)
    return dict(metadata[WAVE_METADATA_KEY])


def consume_upstream_supersession_outcome(
    orchestrator: Any,
    downstream_task_id: str,
    *,
    wave_row: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Route one downstream upstream-supersession outcome to replacement/corrective."""
    task = _task_row(orchestrator, downstream_task_id)
    if task is None:
        return None
    wave = dict(wave_row or upstream_supersession_metadata(task) or {})
    outcome = str(wave.get("outcome") or "").strip()
    if outcome == "still_valid":
        return None
    if outcome not in PREMISE_CORRECTIVE_OUTCOMES:
        return None

    change_set = canonical_change_set(wave.get("evaluated_against_change_set"))
    if not change_set:
        change_set = canonical_change_set(wave.get("upstream_changes"))
    identity = str(wave.get("change_set_identity") or "").strip() or change_set_identity(change_set)
    if successor_already_generated(orchestrator, downstream_task_id, change_set):
        successor = wave.get("successor_change")
        if isinstance(successor, Mapping):
            return {
                "downstream_task_id": downstream_task_id,
                "old_task_id": str(successor.get("old_task_id") or downstream_task_id),
                "new_task_id": str(successor.get("new_task_id") or ""),
                "outcome": outcome,
                "change_set_identity": identity,
                "skipped": True,
            }
        return None

    status = _task_status(task)
    reason = str(wave.get("reason") or "").strip() or None
    if status == TaskStatus.PENDING.value:
        result = add_pending_replacement(
            orchestrator,
            downstream_task_id,
            outcome=outcome,
            reason=reason,
        )
        successor_source = "pending_replacement"
    elif status == TaskStatus.COMPLETE.value:
        result = add_premise_corrective_replan(
            orchestrator,
            downstream_task_id,
            outcome=outcome,
            reason=reason,
        )
        successor_source = "corrective_replan"
    elif status == TaskStatus.IN_PROGRESS.value:
        return None
    else:
        return None
    if result is None:
        return None

    new_task_id = str(
        result.get("replacement_task_id")
        or result.get("corrective_task_id")
        or result.get("new_upstream_task_id")
        or ""
    ).strip()
    if not new_task_id:
        return None

    source_task = _task_row(orchestrator, downstream_task_id) or task
    successor_change = normalize_change_pair(downstream_task_id, new_task_id)
    _record_successor_consumed(
        source_task,
        successor_change=successor_change,
        change_set=change_set,
    )
    return {
        "downstream_task_id": downstream_task_id,
        "old_task_id": downstream_task_id,
        "new_task_id": new_task_id,
        "outcome": outcome,
        "task_status": status,
        "successor_source": successor_source,
        "change_set_identity": identity,
        "propagation_id": wave.get("propagation_id"),
        "wave_index": wave.get("wave_index"),
        "reason": reason,
        "skipped": False,
        **result,
    }


def consume_upstream_supersession_outcomes(
    orchestrator: Any,
    revalidation_rows: Sequence[Mapping[str, Any]] | None,
    *,
    propagation_id: str | None = None,
    wave_index: int | None = None,
) -> dict[str, Any]:
    """Consume evaluated downstream outcomes without starting the next wave."""
    wave_id = resolve_propagation_id(orchestrator, propagation_id)
    completed_wave_index = resolve_wave_index(orchestrator, wave_index)
    successor_changes: list[dict[str, str]] = []
    consumed: list[dict[str, Any]] = []
    for row in revalidation_rows or []:
        downstream_id = str(row.get("downstream_task_id") or "").strip()
        if not downstream_id:
            continue
        task = _task_row(orchestrator, downstream_id)
        wave = upstream_supersession_metadata(task) if task is not None else None
        result = consume_upstream_supersession_outcome(
            orchestrator,
            downstream_id,
            wave_row=wave,
        )
        if result is None:
            continue
        consumed.append(result)
        if result.get("skipped"):
            successor_changes.append(
                normalize_change_pair(
                    str(result.get("old_task_id") or downstream_id),
                    str(result.get("new_task_id") or ""),
                )
            )
            continue
        successor_changes.append(
            normalize_change_pair(
                str(result.get("old_task_id") or downstream_id),
                str(result.get("new_task_id") or ""),
            )
        )
    successor_changes = [
        row
        for row in successor_changes
        if str(row.get("old_task_id") or "").strip() and str(row.get("new_task_id") or "").strip()
    ]
    set_propagation_cycle(
        orchestrator,
        propagation_id=wave_id,
        completed_wave_index=completed_wave_index,
    )
    return {
        "propagation_id": wave_id,
        "completed_wave_index": completed_wave_index,
        "successor_changes": successor_changes,
        "consumed": consumed,
    }


def run_upstream_supersession_revalidations(
    orchestrator: Any,
    successor_rows: Sequence[Mapping[str, Any]] | None,
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
    propagation_id: str | None = None,
    wave_index: int | None = None,
    evaluation_visited: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Freeze one propagation wave and evaluate each downstream task at most once."""
    wave_id = resolve_propagation_id(orchestrator, propagation_id)
    wave_idx = resolve_wave_index(orchestrator, wave_index)
    runtime = getattr(orchestrator, "runtime", None)
    downstream_map = collect_downstream_wave_merges(orchestrator, successor_rows)
    results: list[dict[str, Any]] = []
    for downstream_id in sorted(downstream_map.keys()):
        upstream_changes = downstream_map[downstream_id]
        active_downstream_id = (
            resolve_active_task_id(runtime, downstream_id) if runtime is not None else downstream_id
        )
        apply_wave_hold(
            orchestrator,
            active_downstream_id,
            propagation_id=wave_id,
            upstream_changes=upstream_changes,
            wave_index=wave_idx,
        )
    for downstream_id in sorted(downstream_map.keys()):
        upstream_changes = downstream_map[downstream_id]
        change_set = canonical_change_set(upstream_changes)
        active_downstream_id = (
            resolve_active_task_id(runtime, downstream_id) if runtime is not None else downstream_id
        )
        identity = change_set_identity(change_set)
        visit_key = (str(active_downstream_id), identity)
        task = _task_row(orchestrator, active_downstream_id)
        if evaluation_visited is not None and visit_key in evaluation_visited:
            wave = upstream_supersession_metadata(task) or {}
            results.append(
                {
                    "downstream_task_id": active_downstream_id,
                    "propagation_id": wave.get("propagation_id") or wave_id,
                    "wave_index": wave.get("wave_index", wave_idx),
                    "upstream_changes": list(wave.get("upstream_changes") or upstream_changes),
                    "change_set_identity": identity,
                    "outcome": wave.get("outcome"),
                    "reason": wave.get("reason"),
                    "revalidation": dict(getattr(task, "revalidation", None) or {}) if task else {},
                    "skipped": True,
                    "visit_skipped": True,
                }
            )
            continue
        if task is not None and wave_evaluation_already_current(task, change_set):
            wave = upstream_supersession_metadata(task) or {}
            identity = str(wave.get("change_set_identity") or "").strip() or change_set_identity(change_set)
            results.append(
                {
                    "downstream_task_id": active_downstream_id,
                    "propagation_id": wave.get("propagation_id"),
                    "wave_index": wave.get("wave_index"),
                    "upstream_changes": list(wave.get("upstream_changes") or []),
                    "change_set_identity": identity,
                    "outcome": wave.get("outcome"),
                    "reason": wave.get("reason"),
                    "revalidation": dict(getattr(task, "revalidation", None) or {}),
                    "skipped": True,
                }
            )
            if evaluation_visited is not None:
                evaluation_visited.add(visit_key)
            continue
        case = build_upstream_supersession_wave_case(
            orchestrator,
            downstream_task_id=active_downstream_id,
            upstream_changes=upstream_changes,
        )
        if case is None:
            continue
        evaluation = evaluate_upstream_supersession(case, chat_fn=chat_fn, model=model)
        metadata = apply_upstream_supersession_result(
            orchestrator,
            active_downstream_id,
            evaluation,
            case=case,
            propagation_id=wave_id,
            wave_index=wave_idx,
        )
        if evaluation_visited is not None:
            evaluation_visited.add(visit_key)
        results.append(
            {
                "downstream_task_id": active_downstream_id,
                "propagation_id": wave_id,
                "wave_index": wave_idx,
                "upstream_changes": list(metadata.get("upstream_changes") or []),
                "change_set_identity": change_set_identity(change_set),
                "outcome": evaluation.get("outcome"),
                "reason": evaluation.get("reason"),
                "revalidation": dict(getattr(task, "revalidation", None) or {}),
            }
        )
    return results


def run_upstream_supersession_wave(
    orchestrator: Any,
    successor_rows: Sequence[Mapping[str, Any]] | None,
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
    propagation_id: str | None = None,
    wave_index: int | None = None,
    consume_outcomes: bool = True,
    evaluation_visited: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Evaluate one propagation wave and optionally consume outcomes into successors."""
    wave_id = resolve_propagation_id(orchestrator, propagation_id)
    wave_idx = resolve_wave_index(orchestrator, wave_index)
    evaluations = run_upstream_supersession_revalidations(
        orchestrator,
        successor_rows,
        chat_fn=chat_fn,
        model=model,
        propagation_id=wave_id,
        wave_index=wave_idx,
        evaluation_visited=evaluation_visited,
    )
    payload: dict[str, Any] = {
        "propagation_id": wave_id,
        "wave_index": wave_idx,
        "evaluations": evaluations,
        "completed_wave_index": wave_idx,
        "successor_changes": [],
        "consumed": [],
    }
    if consume_outcomes:
        consumption = consume_upstream_supersession_outcomes(
            orchestrator,
            evaluations,
            propagation_id=wave_id,
            wave_index=wave_idx,
        )
        payload["completed_wave_index"] = consumption["completed_wave_index"]
        payload["successor_changes"] = consumption["successor_changes"]
        payload["consumed"] = consumption["consumed"]
    else:
        set_propagation_cycle(
            orchestrator,
            propagation_id=wave_id,
            completed_wave_index=wave_idx,
        )
    return payload


def run_task_change_propagation(
    orchestrator: Any,
    initial_changes: Sequence[Mapping[str, Any]] | None,
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
    propagation_id: str | None = None,
    max_waves: int = DEFAULT_MAX_PROPAGATION_WAVES,
) -> dict[str, Any]:
    """Iterate upstream supersession waves until changes converge or a safety limit is hit."""
    wave_id = resolve_propagation_id(orchestrator, propagation_id)
    wave_index = 0
    current_changes = resolve_changes_for_propagation(orchestrator, initial_changes)
    processed_change_sets: list[str] = []
    successor_history: list[dict[str, Any]] = []
    held_tasks: list[dict[str, Any]] = []
    waves: list[dict[str, Any]] = []
    evaluation_visited: set[tuple[str, str]] = set()
    stop_reason = STOP_REASON_CONVERGED
    completed_wave_count = 0

    while current_changes:
        if wave_index >= max(1, int(max_waves)):
            stop_reason = STOP_REASON_MAX_WAVES_REACHED
            break

        change_set_id = change_set_identity(current_changes)
        if change_set_id in processed_change_sets:
            stop_reason = STOP_REASON_REPEATED_CHANGE_SET
            break
        processed_change_sets.append(change_set_id)

        successor_rows = changes_to_successor_rows(orchestrator, current_changes)
        if not successor_rows:
            stop_reason = STOP_REASON_NO_ACTIVE_CHANGES
            break

        wave_result = run_upstream_supersession_wave(
            orchestrator,
            successor_rows,
            chat_fn=chat_fn,
            model=model,
            propagation_id=wave_id,
            wave_index=wave_index,
            consume_outcomes=True,
            evaluation_visited=evaluation_visited,
        )
        held_tasks.extend(
            _held_task_entries(
                orchestrator,
                wave_result.get("evaluations"),
                wave_index=wave_index,
            )
        )
        successor_changes = resolve_changes_for_propagation(
            orchestrator,
            wave_result.get("successor_changes"),
        )
        history_row = {
            "wave_index": wave_index,
            "input_changes": list(current_changes),
            "input_change_set_identity": change_set_id,
            "successor_changes": list(successor_changes),
            "evaluations": list(wave_result.get("evaluations") or []),
            "consumed": list(wave_result.get("consumed") or []),
        }
        successor_history.append(history_row)
        waves.append(wave_result)
        completed_wave_count += 1

        if not successor_changes:
            stop_reason = STOP_REASON_CONVERGED
            break

        current_changes = successor_changes
        wave_index += 1

    set_propagation_cycle(
        orchestrator,
        propagation_id=wave_id,
        completed_wave_index=max(0, completed_wave_count - 1),
    )
    payload = build_propagation_run_report(
        propagation_id=wave_id,
        completed_wave_count=completed_wave_count,
        processed_change_sets=processed_change_sets,
        successor_history=successor_history,
        held_tasks=held_tasks,
        stop_reason=stop_reason,
        waves=waves,
        converged_stop_reason=STOP_REASON_CONVERGED,
    )
    from ai_tool.task_change_propagation_guard import apply_propagation_guard_from_result

    apply_propagation_guard_from_result(orchestrator, payload)
    return payload


# Backward-compatible aliases
def upstream_supersession_already_current(
    task: Any,
    *,
    old_upstream_task_id: str,
    new_upstream_task_id: str,
) -> bool:
    change_set = canonical_change_set([normalize_change_pair(old_upstream_task_id, new_upstream_task_id)])
    return wave_evaluation_already_current(task, change_set)


def prepare_upstream_supersession_holds(
    orchestrator: Any,
    *,
    old_upstream_task_id: str,
    new_upstream_task_id: str,
    downstream_task_ids: Sequence[str] | None = None,
    propagation_id: str | None = None,
) -> list[str]:
    """Legacy entry: merge one change into the current wave hold for downstream tasks."""
    wave_id = str(propagation_id or new_propagation_id())
    runtime = getattr(orchestrator, "runtime", None)
    dependents = list(
        downstream_task_ids
        or downstream_dependent_task_ids(runtime, old_upstream_task_id)
    )
    change = normalize_change_pair(old_upstream_task_id, new_upstream_task_id)
    prepared: list[str] = []
    for downstream_id in dependents:
        apply_wave_hold(
            orchestrator,
            downstream_id,
            propagation_id=wave_id,
            upstream_changes=[change],
        )
        prepared.append(str(downstream_id))
    return prepared


def build_upstream_supersession_case(
    orchestrator: Any,
    *,
    downstream_task_id: str,
    old_upstream_task_id: str,
    new_upstream_task_id: str,
) -> dict[str, Any] | None:
    """Backward-compatible single-pair case builder."""
    return build_upstream_supersession_wave_case(
        orchestrator,
        downstream_task_id=downstream_task_id,
        upstream_changes=[normalize_change_pair(old_upstream_task_id, new_upstream_task_id)],
    )


__all__ = [
    "DEFAULT_MAX_PROPAGATION_WAVES",
    "LEGACY_METADATA_KEY",
    "PROPAGATION_CYCLE_ATTR",
    "STOP_REASON_CONVERGED",
    "STOP_REASON_MAX_WAVES_REACHED",
    "STOP_REASON_NO_ACTIVE_CHANGES",
    "STOP_REASON_REPEATED_CHANGE_SET",
    "WAVE_METADATA_KEY",
    "apply_upstream_supersession_result",
    "apply_wave_hold",
    "build_upstream_supersession_case",
    "build_upstream_supersession_wave_case",
    "canonical_change_set",
    "change_set_identity",
    "changes_to_successor_rows",
    "collect_downstream_wave_merges",
    "consume_upstream_supersession_outcome",
    "consume_upstream_supersession_outcomes",
    "evaluate_upstream_supersession",
    "get_propagation_cycle",
    "new_propagation_id",
    "prepare_upstream_supersession_holds",
    "resolve_active_task_id",
    "resolve_changes_for_propagation",
    "resolve_propagation_id",
    "resolve_wave_index",
    "run_task_change_propagation",
    "run_upstream_supersession_revalidations",
    "run_upstream_supersession_wave",
    "set_propagation_cycle",
    "successor_already_generated",
    "upstream_supersession_already_current",
    "upstream_supersession_blocks_task_execution",
    "upstream_supersession_metadata",
    "upstream_supersession_outcome",
    "wave_evaluation_already_current",
]
