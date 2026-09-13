"""Wedge B: adopt a domain task graph into completion_runtime snapshot + trace sidecar."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from ai_tool.domain_goal_graph_adoption import (
    RUNTIME_ROOT_GOAL_ID,
    DomainGoalAdoptionResult,
    DomainGoalGraphValidationError,
    build_goal_rows_from_domain_goal_graph,
    validate_domain_goal_graph,
)
from tools.ai.task_runtime import TaskRecord, TaskStatus

TASK_GRAPH_PROJECTION_SIDECAR_KEY = "task_graph_projection_sidecar"
DOMAIN_TASK_GRAPH_SOURCE = "domain_task_graph"


class DomainTaskGraphValidationError(ValueError):
    """Invalid domain task graph input."""


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _primary_runtime_goal_id(
    supports_goal_ids: list[str],
    goal_id_mapping: Mapping[str, str],
) -> str:
    """PHASE 2N: first entry in supports_goal_ids (scheduling relevance)."""
    if not supports_goal_ids:
        raise DomainTaskGraphValidationError("supports_goal_ids is required")
    primary_source = supports_goal_ids[0]
    runtime_id = goal_id_mapping.get(primary_source)
    if not runtime_id:
        raise DomainTaskGraphValidationError(f"unknown supports_goal_id: {primary_source}")
    return runtime_id


def _map_supports_goal_ids(
    supports_goal_ids: list[str],
    goal_id_mapping: Mapping[str, str],
) -> tuple[str, list[str], list[str]]:
    source_ids = _coerce_str_list(supports_goal_ids)
    if not source_ids:
        raise DomainTaskGraphValidationError("supports_goal_ids is required")
    runtime_ids: list[str] = []
    for source_id in source_ids:
        runtime_id = goal_id_mapping.get(source_id)
        if not runtime_id:
            raise DomainTaskGraphValidationError(f"unknown supports_goal_id: {source_id}")
        if runtime_id not in runtime_ids:
            runtime_ids.append(runtime_id)
    primary_runtime = _primary_runtime_goal_id(source_ids, goal_id_mapping)
    return primary_runtime, source_ids, runtime_ids


def _task_completion_conditions(row: Mapping[str, Any]) -> list[str]:
    explicit = row.get("completion_conditions")
    if isinstance(explicit, list):
        cleaned = [str(item).strip() for item in explicit if str(item).strip()]
        if cleaned:
            return cleaned
    completion_state = str(row.get("completion_state") or "").strip()
    if not completion_state:
        raise DomainTaskGraphValidationError(
            f"completion_state required for task {row.get('task_id')!r}"
        )
    return [completion_state]


def validate_domain_task_graph(
    task_graph: Mapping[str, Any],
    *,
    goal_id_mapping: Mapping[str, str],
) -> None:
    tasks_raw = task_graph.get("tasks")
    if not isinstance(tasks_raw, list) or not tasks_raw:
        raise DomainTaskGraphValidationError("tasks must be a non-empty list")

    seen_task_ids: set[str] = set()
    task_ids: set[str] = set()

    for item in tasks_raw:
        if not isinstance(item, Mapping):
            raise DomainTaskGraphValidationError("task rows must be mappings")
        task_id = str(item.get("task_id") or "").strip()
        if not task_id:
            raise DomainTaskGraphValidationError("task_id is required")
        if task_id in seen_task_ids:
            raise DomainTaskGraphValidationError(f"duplicate task_id: {task_id}")
        seen_task_ids.add(task_id)
        task_ids.add(task_id)
        _map_supports_goal_ids(_coerce_str_list(item.get("supports_goal_ids")), goal_id_mapping)
        _task_completion_conditions(item)

    for item in tasks_raw:
        assert isinstance(item, Mapping)
        task_id = str(item["task_id"]).strip()
        for dep in _coerce_str_list(item.get("depends_on")):
            if dep == task_id:
                raise DomainTaskGraphValidationError(f"self dependency: {task_id}")
            if dep not in task_ids:
                raise DomainTaskGraphValidationError(f"unknown dependency: {dep} for {task_id}")

    visiting: set[str] = set()
    visited: set[str] = set()
    deps_by_task: dict[str, list[str]] = {
        str(row["task_id"]).strip(): _coerce_str_list(row.get("depends_on"))
        for row in tasks_raw
        if isinstance(row, Mapping)
    }

    def visit(node: str) -> None:
        if node in visiting:
            raise DomainTaskGraphValidationError("task dependency cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for dep in deps_by_task.get(node) or []:
            visit(dep)
        visiting.remove(node)
        visited.add(node)

    for task_id in sorted(task_ids):
        visit(task_id)


def build_task_rows_and_sidecar(
    task_graph: Mapping[str, Any],
    *,
    goal_id_mapping: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validate_domain_task_graph(task_graph, goal_id_mapping=goal_id_mapping)
    task_rows: list[dict[str, Any]] = []
    sidecar_rows: list[dict[str, Any]] = []

    for item in task_graph.get("tasks") or []:
        if not isinstance(item, Mapping):
            continue
        task_id = str(item["task_id"]).strip()
        primary_runtime, source_goal_ids, runtime_goal_ids = _map_supports_goal_ids(
            _coerce_str_list(item.get("supports_goal_ids")),
            goal_id_mapping,
        )
        title = str(item.get("title") or task_id).strip()
        instruction = str(item.get("purpose") or title).strip()
        completion = _task_completion_conditions(item)
        for condition in completion:
            if "vf-" in condition:
                raise DomainTaskGraphValidationError(
                    "verification identity must not be merged into completion_conditions"
                )
        record = TaskRecord(
            task_id=task_id,
            goal_id=primary_runtime,
            title=title,
            instruction=instruction,
            completion_conditions=completion,
            depends_on=_coerce_str_list(item.get("depends_on")),
            status=TaskStatus.PENDING.value,
            source=DOMAIN_TASK_GRAPH_SOURCE,
        )
        task_rows.append(asdict(record))
        sidecar_row: dict[str, Any] = {
            "task_id": task_id,
            "source_goal_ids": source_goal_ids,
            "runtime_goal_ids": runtime_goal_ids,
            "primary_runtime_goal_id": primary_runtime,
            "verification_refs": _coerce_str_list(item.get("verification_refs")),
        }
        source_refs = _coerce_str_list(item.get("source_refs"))
        if source_refs:
            sidecar_row["source_refs"] = source_refs
        constraint_refs = _coerce_str_list(item.get("constraint_refs"))
        if constraint_refs:
            sidecar_row["constraint_refs"] = constraint_refs
        task_kind = str(item.get("task_kind") or "").strip()
        if task_kind:
            sidecar_row["task_kind"] = task_kind
        sidecar_rows.append(sidecar_row)

    return task_rows, sidecar_rows


def _first_runnable_task_id(task_rows: list[dict[str, Any]]) -> str:
    by_id = {str(row["task_id"]): row for row in task_rows}
    for row in task_rows:
        task_id = str(row["task_id"])
        deps = [str(item) for item in (row.get("depends_on") or [])]
        if all(
            str(by_id[dep].get("status") or TaskStatus.COMPLETE.value)
            == TaskStatus.COMPLETE.value
            for dep in deps
            if dep in by_id
        ):
            return task_id
    return str(task_rows[0]["task_id"])


def build_completion_runtime_snapshot_from_domain_goal_and_task_graph(
    domain_goal_graph: Mapping[str, Any],
    task_graph: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str], list[dict[str, Any]]]:
    validate_domain_goal_graph(domain_goal_graph)
    goal_rows, goal_id_mapping = build_goal_rows_from_domain_goal_graph(domain_goal_graph)
    task_rows, sidecar_rows = build_task_rows_and_sidecar(
        task_graph,
        goal_id_mapping=goal_id_mapping,
    )
    root = domain_goal_graph["root_goal"]
    assert isinstance(root, Mapping)
    first_task = _first_runnable_task_id(task_rows) if task_rows else ""
    snapshot: dict[str, Any] = {
        "current_goal_id": RUNTIME_ROOT_GOAL_ID,
        "current_task_id": first_task,
        "goals": goal_rows,
        "tasks": task_rows,
        "evidence": [],
        "directory_listings": {},
        "search_observations": [],
        "domain_goal_adoption": {
            "source": "domain_goal_graph",
            "source_root_goal_id": str(root["goal_id"]).strip(),
            "runtime_root_goal_id": RUNTIME_ROOT_GOAL_ID,
            "goal_id_mapping": dict(goal_id_mapping),
        },
        TASK_GRAPH_PROJECTION_SIDECAR_KEY: sidecar_rows,
    }
    return snapshot, dict(goal_id_mapping), sidecar_rows


def adopt_domain_goal_and_task_graph(
    orchestrator: Any,
    domain_goal_graph: Mapping[str, Any],
    task_graph: Mapping[str, Any],
) -> tuple[DomainGoalAdoptionResult, list[dict[str, Any]]]:
    snapshot, goal_id_mapping, sidecar_rows = (
        build_completion_runtime_snapshot_from_domain_goal_and_task_graph(
            domain_goal_graph,
            task_graph,
        )
    )
    root = domain_goal_graph["root_goal"]
    assert isinstance(root, Mapping)
    orchestrator._replace_runtime_graph_from_snapshot(snapshot)
    orchestrator.current_goal_id = RUNTIME_ROOT_GOAL_ID
    orchestrator.current_task_id = str(snapshot.get("current_task_id") or "")
    orchestrator.task_graph_projection_sidecar = [dict(row) for row in sidecar_rows]
    goal_result = DomainGoalAdoptionResult(
        source_root_goal_id=str(root["goal_id"]).strip(),
        runtime_root_goal_id=RUNTIME_ROOT_GOAL_ID,
        goal_id_mapping=dict(goal_id_mapping),
        snapshot=snapshot,
    )
    orchestrator.domain_goal_adoption_result = goal_result
    return goal_result, orchestrator.task_graph_projection_sidecar


__all__ = [
    "DOMAIN_TASK_GRAPH_SOURCE",
    "TASK_GRAPH_PROJECTION_SIDECAR_KEY",
    "DomainTaskGraphValidationError",
    "adopt_domain_goal_and_task_graph",
    "build_completion_runtime_snapshot_from_domain_goal_and_task_graph",
    "build_task_rows_and_sidecar",
    "validate_domain_task_graph",
]
