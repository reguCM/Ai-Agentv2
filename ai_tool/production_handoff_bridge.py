"""Production Chat → Dev Skill Handoff bridge with Human Decision supply."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Sequence

from ai_tool.chat_interface.boundary_grill import (
    boundary_grill_open_dimensions,
    boundary_grill_runtime_connected,
    needs_boundary_spec_clarification,
    request_has_material_spec_fork,
)
from ai_tool.chat_interface.gap_resolution_router import GapKind, GapResolutionDecision
from ai_tool.dev_skill_pipeline import (
    _generate_plan,
    build_handoff_packet,
    load_registry,
    normalize_implementation_tasks,
    validate_handoff_packet,
)
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.human_decision_premise import (
    active_decision_catalog,
    refresh_task_revalidation,
)
from ai_tool.mission_memory.clarifications import (
    load_confirmed_clarifications_for_mission,
    restore_mission_clarifications,
)
from ai_tool.mission_memory.store import MissionMemoryStore
from tools.ai.task_runtime import GoalStatus

ProductionHandoffTrigger = Literal["auto", "explicit"]

_PRODUCTION_HANDOFF_TRIGGERS = frozenset(
    {
        "goal handoff",
        "production handoff",
        "goal handoff生成",
        "実装handoff",
        "handoff生成",
        "generate goal handoff",
    }
)
_SHORT_PREFIX_RE = re.compile(
    r"^(goal handoff|production handoff|handoff生成)\b",
    re.IGNORECASE,
)


@dataclass
class ProductionHandoffReadiness:
    ready: bool
    blockers: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def orchestrator_has_goal_handoff_seed(orchestrator: Any) -> bool:
    tasks = getattr(getattr(orchestrator, "runtime", None), "tasks", None) or {}
    for task in tasks.values():
        source = str(getattr(task, "source", None) or "")
        task_id = str(getattr(task, "task_id", None) or "")
        if source == "goal_handoff" or task_id.startswith("gh-"):
            return True
    return False


def session_has_production_handoff(session: Mapping[str, Any] | None) -> bool:
    if not isinstance(session, Mapping):
        return False
    if str(session.get("production_handoff_id") or "").strip():
        return True
    return bool(session.get("production_handoff_completed"))


def mark_session_production_handoff_completed(
    session: dict[str, Any],
    *,
    handoff_id: str,
) -> None:
    session["production_handoff_completed"] = True
    session["production_handoff_id"] = str(handoff_id or "")


def _awaiting_human_approval(orchestrator: Any) -> bool:
    gaps = getattr(getattr(orchestrator, "runtime", None), "tool_gaps", None) or {}
    for gap in gaps.values():
        if (
            str(getattr(gap, "status", "") or "") == "confirmed"
            and bool(getattr(gap, "requires_human_approval", False))
        ):
            return True
    return False


def _root_goal_graph_complete_without_handoff(orchestrator: Any) -> bool:
    """Runtime root goal node complete. Not Original Mission achieved."""
    if orchestrator_has_goal_handoff_seed(orchestrator):
        return False
    goals = getattr(getattr(orchestrator, "runtime", None), "goals", None) or {}
    root = goals.get("G1")
    if root is None:
        return False
    return str(getattr(root, "status", "") or "") == GoalStatus.COMPLETE.value


def _gap_decision_blocks_handoff(
    gap_decision: GapResolutionDecision | Mapping[str, Any] | None,
) -> bool:
    if gap_decision is None:
        return False
    row = (
        gap_decision
        if isinstance(gap_decision, Mapping)
        else gap_decision.as_dict()
    )
    if bool(row.get("gap_resolved")):
        return False
    gap_kind = str(row.get("gap_kind") or "")
    return gap_kind not in {GapKind.NONE.value, ""}


def assess_production_handoff_readiness(
    orchestrator: Any,
    *,
    session: Mapping[str, Any] | None = None,
    gap_decision: GapResolutionDecision | Mapping[str, Any] | None = None,
    awaiting_boundary_grill: bool = False,
    awaiting_decision_change_confirmation: bool = False,
    trigger: ProductionHandoffTrigger = "auto",
) -> ProductionHandoffReadiness:
    """System-only readiness for Production Handoff. No LLM judgment."""
    blockers: list[str] = []
    reasons: list[str] = []
    if orchestrator is None:
        return ProductionHandoffReadiness(False, ["missing_orchestrator"], [])

    mission_id = str(getattr(orchestrator, "mission_id", "") or "").strip()
    if not mission_id:
        blockers.append("missing_mission_id")

    if getattr(orchestrator, "needs_human_grill", lambda: False)():
        blockers.append("awaiting_initial_grill")
    if awaiting_boundary_grill or boundary_grill_open_dimensions(orchestrator):
        blockers.append("awaiting_boundary_grill")
    if awaiting_decision_change_confirmation:
        blockers.append("awaiting_decision_change_confirmation")
    if _awaiting_human_approval(orchestrator):
        blockers.append("awaiting_human_approval")
    if getattr(orchestrator, "needs_goal_completion_human", lambda: False)():
        blockers.append("awaiting_goal_completion_human")
    if needs_boundary_spec_clarification(orchestrator):
        blockers.append("boundary_spec_unresolved")
    if _gap_decision_blocks_handoff(gap_decision):
        blockers.append("blocking_gap_unresolved")
    if orchestrator_has_goal_handoff_seed(orchestrator) or session_has_production_handoff(session):
        blockers.append("handoff_already_issued")
    if _root_goal_graph_complete_without_handoff(orchestrator):
        blockers.append("root_goal_graph_complete")

    clarifications = [
        row
        for row in (getattr(orchestrator, "confirmed_clarifications", None) or [])
        if isinstance(row, dict)
    ]
    boundary_decisions = [
        row for row in clarifications if str(row.get("source") or "") == "boundary_grill"
    ]
    request = str(getattr(orchestrator, "request", "") or "")
    if trigger == "auto":
        if not boundary_grill_runtime_connected():
            blockers.append("boundary_grill_not_connected")
        if request_has_material_spec_fork(request) and not boundary_decisions:
            blockers.append("spec_decisions_missing")
        elif not boundary_decisions and not list(
            getattr(orchestrator, "user_explicit_conditions", None) or []
        ):
            blockers.append("spec_formation_incomplete")
        if gap_decision is not None:
            row = (
                gap_decision
                if isinstance(gap_decision, Mapping)
                else gap_decision.as_dict()
            )
            if str(row.get("gap_kind") or "") != GapKind.NONE.value:
                if "blocking_gap_unresolved" not in blockers:
                    blockers.append("blocking_gap_unresolved")
            if row.get("winner"):
                blockers.append("continuation_winner_pending")

    if not blockers:
        if boundary_decisions:
            reasons.append("boundary_grill_decisions_confirmed")
        if gap_decision is not None:
            row = (
                gap_decision
                if isinstance(gap_decision, Mapping)
                else gap_decision.as_dict()
            )
            if row.get("gap_resolved"):
                reasons.append("gap_resolved")
        if not boundary_grill_open_dimensions(orchestrator):
            reasons.append("boundary_dimensions_closed")

    return ProductionHandoffReadiness(ready=not blockers, blockers=blockers, reasons=reasons)


def is_explicit_production_handoff_trigger(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if normalized.casefold() in _PRODUCTION_HANDOFF_TRIGGERS:
        return True
    if len(normalized) <= 32 and _SHORT_PREFIX_RE.match(normalized):
        remainder = _SHORT_PREFIX_RE.sub("", normalized).strip(" .。!！?？,，")
        if not remainder or remainder.casefold() in {"してください", "please"}:
            return True
    return False


def resolve_active_clarifications(
    orchestrator: Any,
    *,
    store: MissionMemoryStore | None = None,
) -> list[dict[str, Any]]:
    """Prefer in-memory clarifications; fall back to mission.json on resume."""
    memory = store or MissionMemoryStore.from_default()
    mission_id = str(getattr(orchestrator, "mission_id", "") or "").strip()
    in_memory = [
        dict(item)
        for item in (getattr(orchestrator, "confirmed_clarifications", None) or [])
        if isinstance(item, dict)
    ]
    if in_memory:
        return in_memory
    if mission_id:
        return load_confirmed_clarifications_for_mission(mission_id, store=memory)
    return []


def resolve_pipeline_clarifications(
    *,
    orchestrator: Any | None = None,
    mission_id: str | None = None,
    confirmed_clarifications: Sequence[Mapping[str, Any]] | None = None,
    store: MissionMemoryStore | None = None,
) -> list[dict[str, Any]]:
    if confirmed_clarifications:
        return [dict(item) for item in confirmed_clarifications if isinstance(item, Mapping)]
    if orchestrator is not None:
        return resolve_active_clarifications(orchestrator, store=store)
    if mission_id:
        return load_confirmed_clarifications_for_mission(mission_id, store=store)
    return []


def build_production_handoff_packet(
    orchestrator: Any,
    *,
    initial_request: str,
    plan: Mapping[str, Any],
    tech_spec: Mapping[str, Any],
    prd_rel: str = "",
    tech_spec_rel: str = "",
    plan_rel: str = "",
    todo_rel: str = "",
    skill_steps: Sequence[str] | None = None,
    handoff_slug: str = "production-handoff",
    store: MissionMemoryStore | None = None,
) -> dict[str, Any]:
    """Build a validated handoff packet using active mission Human Decisions."""
    clarifications = resolve_active_clarifications(orchestrator, store=store)
    return build_handoff_packet(
        initial_request=initial_request,
        prd_rel=prd_rel,
        tech_spec_rel=tech_spec_rel,
        plan_rel=plan_rel,
        todo_rel=todo_rel,
        tech_spec=tech_spec,
        plan=dict(plan),
        skill_steps=list(skill_steps or ["planning-and-task-breakdown", "goal-handoff"]),
        handoff_slug=handoff_slug,
        confirmed_clarifications=clarifications,
    )


def run_production_handoff_pipeline(
    orchestrator: Any,
    *,
    initial_request: str,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
    plan_tasks: Sequence[Mapping[str, Any]] | None = None,
    tech_spec: Mapping[str, Any] | None = None,
    store: MissionMemoryStore | None = None,
    handoff_slug: str = "production-handoff",
) -> dict[str, Any]:
    """Run planning + handoff build on Production Chat mainline and seed Runtime."""
    prepare_production_handoff_orchestrator(orchestrator, store=store)
    clarifications = resolve_active_clarifications(orchestrator, store=store)
    registry = load_registry()
    if plan_tasks is not None:
        normalized_tasks = normalize_implementation_tasks(
            plan_tasks,
            default_acceptance=["task complete"],
            default_verification=["verify task"],
        )
        plan_payload = {"tasks": normalized_tasks}
    else:
        plan_payload = _generate_plan(
            model=model,
            tech_spec=dict(tech_spec or {"summary": initial_request}),
            registry=registry,
            chat_fn=chat_fn,
            confirmed_clarifications=clarifications,
        )
    packet = build_production_handoff_packet(
        orchestrator,
        initial_request=initial_request,
        plan=plan_payload,
        tech_spec=dict(tech_spec or {"summary": initial_request}),
        prd_rel="docs/prd.md",
        tech_spec_rel="docs/tech-spec.md",
        plan_rel="tasks/plan.md",
        todo_rel="tasks/todo.md",
        store=store,
        handoff_slug=handoff_slug,
    )
    errors = validate_handoff_packet(packet)
    if errors:
        raise ValueError("production handoff schema errors: " + "; ".join(errors))
    seed_orchestrator_from_handoff(orchestrator, packet)
    refresh_task_revalidation(orchestrator)
    return {
        "handoff_packet": packet,
        "plan": plan_payload,
        "decision_catalog": active_decision_catalog(clarifications),
        "clarifications": clarifications,
    }


def production_handoff_decision_catalog(
    orchestrator: Any,
    *,
    store: MissionMemoryStore | None = None,
) -> dict[str, dict[str, Any]]:
    return active_decision_catalog(resolve_active_clarifications(orchestrator, store=store))


def prepare_production_handoff_orchestrator(
    orchestrator: Any,
    *,
    store: MissionMemoryStore | None = None,
) -> list[dict[str, Any]]:
    """Restore mission clarifications before Production Handoff generation."""
    return restore_mission_clarifications(orchestrator, store=store)


__all__ = [
    "ProductionHandoffReadiness",
    "assess_production_handoff_readiness",
    "build_production_handoff_packet",
    "is_explicit_production_handoff_trigger",
    "mark_session_production_handoff_completed",
    "orchestrator_has_goal_handoff_seed",
    "prepare_production_handoff_orchestrator",
    "production_handoff_decision_catalog",
    "resolve_active_clarifications",
    "resolve_pipeline_clarifications",
    "run_production_handoff_pipeline",
    "session_has_production_handoff",
]
