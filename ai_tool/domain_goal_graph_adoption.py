"""Wedge A: adopt a domain outcome goal graph into completion_runtime snapshot form."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from tools.ai.task_runtime import GoalNode, GoalStatus

RUNTIME_ROOT_GOAL_ID = "G1"
DOMAIN_GOAL_ADOPTION_SOURCE = "domain_goal_graph"


class DomainGoalGraphValidationError(ValueError):
    """Invalid domain goal graph input."""


@dataclass
class DomainGoalAdoptionResult:
    source_root_goal_id: str
    runtime_root_goal_id: str
    goal_id_mapping: dict[str, str]
    snapshot: dict[str, Any] = field(default_factory=dict)


def _runtime_goal_id(source_id: str, root_source_id: str) -> str:
    if source_id == root_source_id:
        return RUNTIME_ROOT_GOAL_ID
    return source_id


def _outcome_completion_conditions(
    row: Mapping[str, Any],
    *,
    statement_key: str = "statement",
) -> list[str]:
    explicit = row.get("completion_conditions")
    if isinstance(explicit, list):
        cleaned = [str(item).strip() for item in explicit if str(item).strip()]
        if cleaned:
            return cleaned
    statement = str(row.get(statement_key) or "").strip()
    if not statement:
        raise DomainGoalGraphValidationError("goal statement or completion_conditions required")
    return [statement]


def validate_domain_goal_graph(graph: Mapping[str, Any]) -> None:
    root = graph.get("root_goal")
    if not isinstance(root, Mapping):
        raise DomainGoalGraphValidationError("root_goal is required")
    root_id = str(root.get("goal_id") or "").strip()
    if not root_id:
        raise DomainGoalGraphValidationError("root_goal.goal_id is required")
    _outcome_completion_conditions(root)

    subgoals_raw = graph.get("subgoals") or []
    if not isinstance(subgoals_raw, list):
        raise DomainGoalGraphValidationError("subgoals must be a list")

    seen: set[str] = {root_id}
    nodes: list[tuple[str, str | None]] = [(root_id, None)]

    for item in subgoals_raw:
        if not isinstance(item, Mapping):
            raise DomainGoalGraphValidationError("subgoal rows must be mappings")
        goal_id = str(item.get("goal_id") or "").strip()
        if not goal_id:
            raise DomainGoalGraphValidationError("subgoal.goal_id is required")
        if goal_id in seen:
            raise DomainGoalGraphValidationError(f"duplicate goal_id: {goal_id}")
        seen.add(goal_id)
        parent = str(item.get("parent_goal_id") or "").strip() or None
        if parent == goal_id:
            raise DomainGoalGraphValidationError(f"self parent_goal_id: {goal_id}")
        nodes.append((goal_id, parent))
        _outcome_completion_conditions(item)

    known = seen
    for goal_id, parent in nodes[1:]:
        if not parent:
            raise DomainGoalGraphValidationError(f"orphan subgoal (no parent): {goal_id}")
        if parent not in known:
            raise DomainGoalGraphValidationError(f"unknown parent_goal_id: {parent} for {goal_id}")

    parent_of: dict[str, str | None] = {root_id: None}
    for goal_id, parent in nodes[1:]:
        assert parent is not None
        parent_of[goal_id] = parent

    for start_id in known:
        seen: set[str] = set()
        current: str | None = start_id
        while current is not None:
            if current in seen:
                raise DomainGoalGraphValidationError("goal graph cycle detected")
            seen.add(current)
            current = parent_of.get(current)


def build_goal_rows_from_domain_goal_graph(graph: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    validate_domain_goal_graph(graph)
    root = graph["root_goal"]
    assert isinstance(root, Mapping)
    root_source_id = str(root["goal_id"]).strip()
    mapping = {root_source_id: RUNTIME_ROOT_GOAL_ID}

    subgoals = [item for item in (graph.get("subgoals") or []) if isinstance(item, Mapping)]
    for item in subgoals:
        source_id = str(item["goal_id"]).strip()
        mapping[source_id] = _runtime_goal_id(source_id, root_source_id)

    children_by_source: dict[str, list[str]] = {root_source_id: []}
    for item in subgoals:
        parent_source = str(item.get("parent_goal_id") or "").strip()
        child_source = str(item["goal_id"]).strip()
        children_by_source.setdefault(parent_source, []).append(child_source)

    rows: list[dict[str, Any]] = []

    def append_goal(source_row: Mapping[str, Any], parent_source: str | None) -> None:
        source_id = str(source_row["goal_id"]).strip()
        runtime_id = mapping[source_id]
        parent_runtime = (
            mapping.get(parent_source) if parent_source else None
        )
        child_sources = children_by_source.get(source_id) or []
        child_runtime = [mapping[cid] for cid in child_sources]
        node = GoalNode(
            runtime_id,
            str(source_row.get("statement") or "").strip(),
            parent_goal_id=parent_runtime,
            completion_conditions=_outcome_completion_conditions(source_row),
            child_goal_ids=child_runtime,
            task_ids=[],
            status=GoalStatus.PENDING.value,
        )
        rows.append(asdict(node))

    append_goal(root, None)
    for item in sorted(subgoals, key=lambda row: str(row.get("goal_id") or "")):
        append_goal(item, str(item.get("parent_goal_id") or "").strip())

    return rows, mapping


def build_completion_runtime_snapshot_from_domain_goal_graph(
    graph: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    goal_rows, mapping = build_goal_rows_from_domain_goal_graph(graph)
    root = graph["root_goal"]
    assert isinstance(root, Mapping)
    snapshot = {
        "current_goal_id": RUNTIME_ROOT_GOAL_ID,
        "current_task_id": "",
        "goals": goal_rows,
        "tasks": [],
        "evidence": [],
        "directory_listings": {},
        "search_observations": [],
        "domain_goal_adoption": {
            "source": DOMAIN_GOAL_ADOPTION_SOURCE,
            "source_root_goal_id": str(root["goal_id"]).strip(),
            "runtime_root_goal_id": RUNTIME_ROOT_GOAL_ID,
            "goal_id_mapping": dict(mapping),
        },
    }
    return snapshot, mapping


def adopt_domain_goal_graph(orchestrator: Any, domain_goal_graph: Mapping[str, Any]) -> DomainGoalAdoptionResult:
    """Validate graph, build completion_runtime snapshot, reuse orchestrator graph replace."""
    snapshot, mapping = build_completion_runtime_snapshot_from_domain_goal_graph(domain_goal_graph)
    root = domain_goal_graph["root_goal"]
    assert isinstance(root, Mapping)
    orchestrator._replace_runtime_graph_from_snapshot(snapshot)
    orchestrator.current_goal_id = RUNTIME_ROOT_GOAL_ID
    orchestrator.current_task_id = ""
    if hasattr(orchestrator, "task_graph_projection_sidecar"):
        orchestrator.task_graph_projection_sidecar = []
    result = DomainGoalAdoptionResult(
        source_root_goal_id=str(root["goal_id"]).strip(),
        runtime_root_goal_id=RUNTIME_ROOT_GOAL_ID,
        goal_id_mapping=dict(mapping),
        snapshot=snapshot,
    )
    orchestrator.domain_goal_adoption_result = result
    return result


__all__ = [
    "DOMAIN_GOAL_ADOPTION_SOURCE",
    "RUNTIME_ROOT_GOAL_ID",
    "DomainGoalAdoptionResult",
    "DomainGoalGraphValidationError",
    "adopt_domain_goal_graph",
    "build_completion_runtime_snapshot_from_domain_goal_graph",
    "build_goal_rows_from_domain_goal_graph",
    "validate_domain_goal_graph",
]
