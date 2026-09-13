"""Gap resolution router (Phase 0).

Classifies execution-end Goal Gaps and selects an existing capability route.
Does not execute recovery, replan, grill, or help — routing only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from ai_tool.chat_interface.goal_completion_gate import (
    existing_specs_uniquely_determine_goal_completion,
    needs_goal_completion_human,
)
from ai_tool.skill_applicability import (
    GapContext,
    SkillArtifacts,
    build_artifacts_from_router_input,
    load_registry,
    resolve_skill_applicability,
    should_execute,
)

_STAGNATION_STOP_REASONS = frozenset(
    {
        "STAGNATION_LIMIT",
        "SAME_FAILURE_LIMIT",
        "NO_EVIDENCE_LIMIT",
        "TOOL_HARD_LIMIT",
        "TASK_CHANGE_PROPAGATION_NON_CONVERGED",
    }
)


class GapKind(str, Enum):
    NONE = "none"
    FACT_GAP = "fact_gap"
    TARGET_IDENTITY_GAP = "target_identity_gap"
    CAPABILITY_GAP = "capability_gap"
    STAGNATION_EXHAUSTED = "stagnation_exhausted"
    SPEC_MEANING_GAP = "spec_meaning_gap"


class CapabilityId(str, Enum):
    SYSTEM_RULE = "system_rule"
    TOOL_EVIDENCE = "tool_evidence"
    RECOVERY = "recovery"
    REPLAN = "replan"
    SKILL_GRILL_ME = "skill:grill-me"
    HUMAN_APPROVAL = "human_approval"
    CONVERSATION_GRILL = "conversation_grill"
    GOAL_COMPLETION_HUMAN = "goal_completion_human"
    HELP = "help"


CONTINUATION_WINNERS = frozenset(
    {
        CapabilityId.TOOL_EVIDENCE.value,
        CapabilityId.RECOVERY.value,
        CapabilityId.REPLAN.value,
    }
)


@dataclass
class GapRouterInput:
    """Observed facts at execution end. No inferred Mission states."""

    request: str = ""
    stop_reason: str | None = None
    answer_gate: dict[str, Any] | None = None
    goal_incomplete: bool = False
    observation_complete: bool = False
    needs_human_grill: bool = False
    needs_goal_completion_human: bool = False
    has_confirmed_tool_gaps_approval: bool = False
    recovery_available: bool = False
    replan_available: bool = True
    tool_evidence_available: bool = True
    goal_completion_consumed: bool = False
    goal_read_target_status: str | None = None
    user_explicit_conditions: list[str] = field(default_factory=list)
    user_confirmed_supplements: list[dict[str, str]] = field(default_factory=list)
    gap_stagnation_count: int = 0
    stagnation_limit: int = 3
    artifact_kinds: set[str] = field(default_factory=set)
    orchestrator: Any | None = None

    @property
    def answer_gate_verified(self) -> bool:
        return bool((self.answer_gate or {}).get("verified"))

    @property
    def answer_gate_reason(self) -> str | None:
        reason = (self.answer_gate or {}).get("reason")
        return str(reason) if reason else None

    @property
    def stagnation_exhausted(self) -> bool:
        if self.gap_stagnation_count >= self.stagnation_limit:
            return True
        return str(self.stop_reason or "") in _STAGNATION_STOP_REASONS

    @property
    def facts_sufficient(self) -> bool:
        """True when observation work is complete but meaning may still be open."""
        if self.answer_gate_verified:
            return True
        if self.needs_goal_completion_human:
            return self.observation_complete
        gate_reason = self.answer_gate_reason
        if gate_reason == "completion_evidence_incomplete":
            return False
        if gate_reason in {
            "goal_read_target_unresolved",
            "goal_read_target_not_observed",
            "closed_unresolved_goal_target",
        }:
            return False
        return self.observation_complete


@dataclass
class CapabilityCandidate:
    id: str
    available: bool
    available_reasons: list[str] = field(default_factory=list)
    valuable: bool = False
    value_reasons: list[str] = field(default_factory=list)
    execute: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GapResolutionDecision:
    gap_kind: str
    gap_resolved: bool
    gap_resolved_reasons: list[str] = field(default_factory=list)
    facts_sufficient: bool = False
    candidates: list[CapabilityCandidate] = field(default_factory=list)
    winner: str | None = None
    boundary_grill_considered: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "gap_kind": self.gap_kind,
            "gap_resolved": self.gap_resolved,
            "gap_resolved_reasons": self.gap_resolved_reasons,
            "facts_sufficient": self.facts_sufficient,
            "candidates": [item.as_dict() for item in self.candidates],
            "winner": self.winner,
            "boundary_grill_considered": self.boundary_grill_considered,
        }


def build_router_input_from_orchestrator(
    orchestrator: Any,
    *,
    stop_reason: str | None = None,
    answer_gate: Mapping[str, Any] | None = None,
    loop_counters: Mapping[str, Any] | None = None,
    gap_stagnation_count: int = 0,
) -> GapRouterInput:
    runtime = getattr(orchestrator, "runtime", None)
    goals = getattr(runtime, "goals", {}) or {}
    g1 = goals.get("G1")
    goal_incomplete = g1 is None or getattr(g1, "status", None) != "complete"
    observation = (getattr(runtime, "tasks", None) or {}).get("T1")
    observation_complete = (
        observation is not None and getattr(observation, "status", None) == "complete"
    )
    confirmed_gaps = []
    tool_gaps = getattr(runtime, "tool_gaps", None) or {}
    if hasattr(tool_gaps, "values"):
        confirmed_gaps = [
            item
            for item in tool_gaps.values()
            if getattr(item, "status", None) == "confirmed"
            and getattr(item, "requires_human_approval", False)
        ]
    recovery_available = False
    recovery_hint = getattr(orchestrator, "recovery_hint", None)
    if callable(recovery_hint):
        recovery_available = bool(recovery_hint())
    replans = getattr(runtime, "replans", None) or []
    target = dict(getattr(orchestrator, "goal_read_target", None) or {})
    supplements = [
        dict(item)
        for item in (getattr(orchestrator, "goal_completion_supplements", None) or [])
        if isinstance(item, dict)
    ]
    supplements.extend(
        [
            {
                "text": str(item.get("text") or ""),
                "source": str(item.get("source") or "grill"),
                "decision_key": str(item.get("decision_key") or "") or None,
                "decision_id": str(item.get("decision_id") or "") or None,
                "status": str(item.get("status") or "confirmed"),
            }
            for item in (getattr(orchestrator, "confirmed_clarifications", None) or [])
            if isinstance(item, dict)
            and str(item.get("text") or "").strip()
            and str(item.get("status") or "confirmed") != "superseded"
        ]
    )
    counters = dict(loop_counters or {})
    return GapRouterInput(
        request=str(getattr(orchestrator, "request", "") or ""),
        stop_reason=str(stop_reason or "") or None,
        answer_gate=dict(answer_gate or {}),
        goal_incomplete=goal_incomplete,
        observation_complete=observation_complete,
        needs_human_grill=bool(
            getattr(orchestrator, "needs_human_grill", lambda: False)()
        ),
        needs_goal_completion_human=bool(needs_goal_completion_human(orchestrator)),
        has_confirmed_tool_gaps_approval=bool(confirmed_gaps),
        recovery_available=recovery_available,
        replan_available=True,
        tool_evidence_available=goal_incomplete,
        goal_completion_consumed=bool(
            getattr(orchestrator, "goal_completion_consumed", False)
        ),
        goal_read_target_status=str(target.get("status") or "") or None,
        user_explicit_conditions=list(
            getattr(orchestrator, "user_explicit_conditions", None) or []
        ),
        user_confirmed_supplements=supplements,
        gap_stagnation_count=int(gap_stagnation_count),
        stagnation_limit=int(counters.get("stagnation_limit") or 3),
        artifact_kinds=set(),
        orchestrator=orchestrator,
    )


def classify_gap_kind(inp: GapRouterInput) -> GapKind:
    gate_reason = inp.answer_gate_reason
    if gate_reason in {
        "awaiting_goal_completion_human",
        "spec_meaning_ambiguous",
    }:
        return GapKind.SPEC_MEANING_GAP
    if gate_reason == "awaiting_human_grill":
        return GapKind.TARGET_IDENTITY_GAP
    if inp.answer_gate_verified:
        return GapKind.NONE
    if inp.has_confirmed_tool_gaps_approval:
        return GapKind.CAPABILITY_GAP
    if inp.stagnation_exhausted:
        return GapKind.STAGNATION_EXHAUSTED
    if inp.needs_human_grill:
        return GapKind.TARGET_IDENTITY_GAP
    if gate_reason in {
        "goal_read_target_unresolved",
        "goal_read_target_not_observed",
        "closed_unresolved_goal_target",
    }:
        return GapKind.TARGET_IDENTITY_GAP
    if inp.needs_goal_completion_human:
        return GapKind.SPEC_MEANING_GAP
    if gate_reason == "completion_evidence_incomplete":
        return GapKind.FACT_GAP
    if inp.goal_incomplete:
        return GapKind.FACT_GAP
    return GapKind.NONE


def is_current_gap_resolved(
    inp: GapRouterInput,
    *,
    gap_kind: GapKind,
) -> tuple[bool, list[str]]:
    """True when a confirmed Human decision or Specification resolves this GAP.

    Initial Grill artifacts alone do not resolve a newly observed GAP.
    """
    if inp.goal_completion_consumed and gap_kind == GapKind.SPEC_MEANING_GAP:
        return True, ["goal_completion_human_decision_applied"]
    gate_reason = inp.answer_gate_reason
    if gate_reason in {
        "awaiting_goal_completion_human",
        "awaiting_human_grill",
    }:
        return False, []
    if inp.answer_gate_verified:
        return True, ["answer_gate_verified"]
    if inp.user_explicit_conditions and gap_kind == GapKind.SPEC_MEANING_GAP:
        # Explicit conditions fix completion meaning; they do not satisfy FACT evidence.
        return True, ["user_explicit_completion_conditions"]
    for row in inp.user_confirmed_supplements:
        source = str(row.get("source") or "")
        if source == "goal_completion" and str(row.get("text") or "").strip():
            return True, ["goal_completion_supplement_confirmed"]
        if (
            source == "boundary_grill"
            and str(row.get("text") or "").strip()
            and gap_kind == GapKind.SPEC_MEANING_GAP
        ):
            orchestrator = inp.orchestrator
            if orchestrator is not None:
                from ai_tool.chat_interface.boundary_grill import (
                    boundary_grill_open_dimensions,
                )

                if not boundary_grill_open_dimensions(orchestrator):
                    return True, ["boundary_grill_human_decision_applied"]
    if gap_kind == GapKind.TARGET_IDENTITY_GAP and inp.goal_read_target_status in {
        "SELECTED",
        "PROVISIONAL_SELECTED",
    }:
        return True, ["goal_read_target_selected"]
    orchestrator = inp.orchestrator
    if orchestrator is not None and existing_specs_uniquely_determine_goal_completion(
        orchestrator
    ):
        return True, ["system_rule_uniquely_determines_completion"]
    return False, []


def _candidate(
    capability_id: CapabilityId,
    *,
    available: bool,
    available_reasons: list[str],
    valuable: bool,
    value_reasons: list[str],
) -> CapabilityCandidate:
    return CapabilityCandidate(
        id=capability_id.value,
        available=available,
        available_reasons=available_reasons,
        valuable=valuable,
        value_reasons=value_reasons,
        execute=available and valuable,
    )


def _evaluate_boundary_grill_me(
    inp: GapRouterInput,
    *,
    gap_kind: GapKind,
    gap_resolved: bool,
) -> CapabilityCandidate:
    gap_context = GapContext(
        kind=gap_kind.value,
        facts_sufficient=inp.facts_sufficient,
        gap_resolved=gap_resolved,
    )
    artifacts = build_artifacts_from_router_input(inp)
    item = resolve_skill_applicability(
        "grill-me",
        request=inp.request,
        consumer="local_agent",
        artifacts=artifacts,
        composition_steps=["grill-me"],
        gap_context=gap_context,
    )
    available = item.usability != "BLOCKED"
    available_reasons = list(item.usability_reasons)
    valuable = should_execute(item) or (
        item.value == "USE" and available
    )
    value_reasons = list(item.value_reasons)
    if item.usability == "BLOCKED":
        valuable = False
    return _candidate(
        CapabilityId.SKILL_GRILL_ME,
        available=available,
        available_reasons=available_reasons,
        valuable=valuable,
        value_reasons=value_reasons,
    )


def _ordered_capability_ids(gap_kind: GapKind) -> list[CapabilityId]:
    if gap_kind == GapKind.FACT_GAP:
        return [
            CapabilityId.TOOL_EVIDENCE,
            CapabilityId.RECOVERY,
            CapabilityId.REPLAN,
            CapabilityId.HELP,
        ]
    if gap_kind == GapKind.TARGET_IDENTITY_GAP:
        return [CapabilityId.CONVERSATION_GRILL, CapabilityId.HELP]
    if gap_kind == GapKind.CAPABILITY_GAP:
        return [CapabilityId.HUMAN_APPROVAL, CapabilityId.HELP]
    if gap_kind == GapKind.STAGNATION_EXHAUSTED:
        return [CapabilityId.HELP]
    if gap_kind == GapKind.SPEC_MEANING_GAP:
        return [
            CapabilityId.SYSTEM_RULE,
            CapabilityId.GOAL_COMPLETION_HUMAN,
            CapabilityId.SKILL_GRILL_ME,
            CapabilityId.HELP,
        ]
    return []


def _evaluate_candidate(
    capability_id: CapabilityId,
    inp: GapRouterInput,
    *,
    gap_kind: GapKind,
    gap_resolved: bool,
) -> CapabilityCandidate:
    if capability_id == CapabilityId.SYSTEM_RULE:
        orchestrator = inp.orchestrator
        available = orchestrator is not None
        uniquely = (
            existing_specs_uniquely_determine_goal_completion(orchestrator)
            if available
            else False
        )
        return _candidate(
            capability_id,
            available=available,
            available_reasons=["goal_completion_gate_connected"]
            if available
            else ["no_orchestrator"],
            valuable=uniquely,
            value_reasons=["system_rule_resolves_gap"] if uniquely else ["not_connected_v0"],
        )
    if capability_id == CapabilityId.TOOL_EVIDENCE:
        return _candidate(
            capability_id,
            available=inp.tool_evidence_available,
            available_reasons=["open_tasks_remain"] if inp.tool_evidence_available else ["no_open_work"],
            valuable=gap_kind == GapKind.FACT_GAP and not gap_resolved,
            value_reasons=["fact_gap_needs_more_evidence"],
        )
    if capability_id == CapabilityId.RECOVERY:
        return _candidate(
            capability_id,
            available=inp.recovery_available,
            available_reasons=["recovery_hint_available"]
            if inp.recovery_available
            else ["no_stagnation_recovery_hint"],
            valuable=gap_kind == GapKind.FACT_GAP and not gap_resolved,
            value_reasons=["fact_gap_recovery_path"],
        )
    if capability_id == CapabilityId.REPLAN:
        return _candidate(
            capability_id,
            available=inp.replan_available,
            available_reasons=["replan_add_task_available"],
            valuable=gap_kind == GapKind.FACT_GAP and not gap_resolved,
            value_reasons=["fact_gap_alternative_task"],
        )
    if capability_id == CapabilityId.HUMAN_APPROVAL:
        return _candidate(
            capability_id,
            available=inp.has_confirmed_tool_gaps_approval,
            available_reasons=["confirmed_tool_gap_requires_approval"],
            valuable=gap_kind == GapKind.CAPABILITY_GAP,
            value_reasons=["capability_gap"],
        )
    if capability_id == CapabilityId.CONVERSATION_GRILL:
        return _candidate(
            capability_id,
            available=inp.needs_human_grill,
            available_reasons=["identity_unresolved_candidates_remain"],
            valuable=gap_kind == GapKind.TARGET_IDENTITY_GAP and not gap_resolved,
            value_reasons=["target_identity_gap"],
        )
    if capability_id == CapabilityId.GOAL_COMPLETION_HUMAN:
        return _candidate(
            capability_id,
            available=inp.needs_goal_completion_human,
            available_reasons=["goal_completion_gate_v0_case_connected"],
            valuable=gap_kind == GapKind.SPEC_MEANING_GAP and not gap_resolved,
            value_reasons=["spec_meaning_gap_v0_human_gate"],
        )
    if capability_id == CapabilityId.SKILL_GRILL_ME:
        return _evaluate_boundary_grill_me(
            inp,
            gap_kind=gap_kind,
            gap_resolved=gap_resolved,
        )
    if capability_id == CapabilityId.HELP:
        return _candidate(
            capability_id,
            available=True,
            available_reasons=["help_route_always_available"],
            valuable=gap_kind
            in {
                GapKind.STAGNATION_EXHAUSTED,
                GapKind.CAPABILITY_GAP,
                GapKind.FACT_GAP,
                GapKind.TARGET_IDENTITY_GAP,
                GapKind.SPEC_MEANING_GAP,
            },
            value_reasons=["escalation_or_exhausted_routes"],
        )
    return _candidate(
        capability_id,
        available=False,
        available_reasons=["unknown_capability"],
        valuable=False,
        value_reasons=["unknown_capability"],
    )


def route_gap_resolution(inp: GapRouterInput) -> GapResolutionDecision:
    gap_kind = classify_gap_kind(inp)
    gap_resolved, resolved_reasons = is_current_gap_resolved(inp, gap_kind=gap_kind)
    ordered = _ordered_capability_ids(gap_kind)
    candidates = [
        _evaluate_candidate(capability_id, inp, gap_kind=gap_kind, gap_resolved=gap_resolved)
        for capability_id in ordered
    ]
    winner = None
    for candidate in candidates:
        if candidate.execute:
            winner = candidate.id
            break
    boundary_grill_considered = any(
        item.id == CapabilityId.SKILL_GRILL_ME.value for item in candidates
    )
    return GapResolutionDecision(
        gap_kind=gap_kind.value,
        gap_resolved=gap_resolved,
        gap_resolved_reasons=resolved_reasons,
        facts_sufficient=inp.facts_sufficient,
        candidates=candidates,
        winner=winner,
        boundary_grill_considered=boundary_grill_considered,
    )


def route_gap_resolution_from_orchestrator(
    orchestrator: Any,
    *,
    stop_reason: str | None = None,
    answer_gate: Mapping[str, Any] | None = None,
    loop_counters: Mapping[str, Any] | None = None,
    gap_stagnation_count: int = 0,
) -> GapResolutionDecision:
    inp = build_router_input_from_orchestrator(
        orchestrator,
        stop_reason=stop_reason,
        answer_gate=answer_gate,
        loop_counters=loop_counters,
        gap_stagnation_count=gap_stagnation_count,
    )
    return route_gap_resolution(inp)


def human_priority_blocks_continuation(
    *,
    awaiting_goal_completion_human: bool = False,
    awaiting_human_grill: bool = False,
    awaiting_human_review: bool = False,
    stop_reason: str | None = None,
) -> bool:
    """Existing Human / Approval paths take precedence over continuation resume."""
    if awaiting_goal_completion_human or awaiting_human_grill or awaiting_human_review:
        return True
    return str(stop_reason or "") in {
        "GOAL_COMPLETION_HUMAN",
        "HUMAN_GRILL",
        "APPROVAL_REQUIRED",
    }


def _capability_candidate(
    decision: GapResolutionDecision,
    capability_id: CapabilityId,
) -> CapabilityCandidate | None:
    for item in decision.candidates:
        if item.id == capability_id.value:
            return item
    return None


def replan_available_for_regression(decision: GapResolutionDecision) -> bool:
    """True when existing Router would offer Replan as available + valuable."""
    candidate = _capability_candidate(decision, CapabilityId.REPLAN)
    return candidate is not None and candidate.available and candidate.valuable


@dataclass
class RegressionContinuationBridge:
    """Minimal reroute after cross-execution REGRESSION."""

    prior_winner: str | None
    reroute_winner: str | None
    help_escalation: bool
    block_continuation_resume: bool
    superseded_winner: str | None = None
    reroute_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "prior_winner": self.prior_winner,
            "reroute_winner": self.reroute_winner,
            "help_escalation": self.help_escalation,
            "block_continuation_resume": self.block_continuation_resume,
            "superseded_winner": self.superseded_winner,
            "reroute_reason": self.reroute_reason,
        }


def apply_regression_continuation_bridge(
    decision: GapResolutionDecision,
    *,
    prior_winner: str | None,
    human_priority_blocked: bool,
) -> tuple[GapResolutionDecision, RegressionContinuationBridge | None]:
    """Reroute continuation after REGRESSION without reusing the prior winner."""
    if human_priority_blocked:
        return decision, None
    if replan_available_for_regression(decision):
        decision.winner = CapabilityId.REPLAN.value
        return decision, RegressionContinuationBridge(
            prior_winner=prior_winner,
            reroute_winner=CapabilityId.REPLAN.value,
            help_escalation=False,
            block_continuation_resume=False,
            superseded_winner=prior_winner,
            reroute_reason="regression_replan_reroute",
        )
    decision.winner = CapabilityId.HELP.value
    return decision, RegressionContinuationBridge(
        prior_winner=prior_winner,
        reroute_winner=None,
        help_escalation=True,
        block_continuation_resume=True,
        superseded_winner=prior_winner,
        reroute_reason="regression_replan_unavailable",
    )


def should_persist_goal_continuation_resume(
    decision: GapResolutionDecision,
    *,
    human_priority_blocked: bool,
) -> bool:
    if human_priority_blocked:
        return False
    if decision.gap_resolved:
        return False
    if decision.gap_kind == GapKind.NONE.value:
        return False
    if not decision.winner:
        return False
    return decision.winner in CONTINUATION_WINNERS


def build_goal_continuation_resume(
    orchestrator: Any,
    decision: GapResolutionDecision,
    *,
    recorded: Mapping[str, Any] | None,
    correlation_id: str,
    gap_snapshot: Mapping[str, Any] | None = None,
    continuation_stagnation_count: int = 0,
    superseded_winner: str | None = None,
    regression_reroute: bool = False,
) -> dict[str, Any]:
    """Session-only resume pointer/material. Not Mission Memory canonical."""
    failures = getattr(getattr(orchestrator, "runtime", None), "failures", None) or []
    failure_tail = []
    for item in failures[-3:]:
        if hasattr(item, "__dataclass_fields__"):
            failure_tail.append(asdict(item))
        elif isinstance(item, Mapping):
            failure_tail.append(dict(item))
    mission_id = str(getattr(orchestrator, "mission_id", "") or "")
    execution_id = ""
    if recorded and recorded.get("execution_id"):
        execution_id = str(recorded["execution_id"])
    elif getattr(orchestrator, "execution_id", None):
        execution_id = str(orchestrator.execution_id)
    return {
        "kind": "goal_continuation_v0",
        "provisional": True,
        "not_mission_canonical": True,
        "mission_id": mission_id,
        "execution_id": execution_id,
        "correlation_id": str(correlation_id),
        "original_request": str(getattr(orchestrator, "request", "") or ""),
        "winner": decision.winner,
        "gap_kind": decision.gap_kind,
        "gap_resolution": decision.as_dict(),
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "failure_tail": failure_tail,
        "evidence_refs": list((recorded or {}).get("evidence_refs") or []),
        "prior_execution_id": execution_id or None,
        "gap_snapshot": dict(gap_snapshot or {}),
        "continuation_stagnation_count": int(continuation_stagnation_count),
        "superseded_winner": superseded_winner,
        "regression_reroute": bool(regression_reroute),
    }


def gap_resolution_routed_event_payload(
    decision: GapResolutionDecision,
    *,
    continuation_resume_persisted: bool,
    human_priority_blocked: bool,
    continuation_help_escalation: bool = False,
    regression_reroute: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "gap_kind": decision.gap_kind,
        "gap_resolved": decision.gap_resolved,
        "gap_resolved_reasons": decision.gap_resolved_reasons,
        "facts_sufficient": decision.facts_sufficient,
        "winner": decision.winner,
        "candidates": [item.as_dict() for item in decision.candidates],
        "boundary_grill_considered": decision.boundary_grill_considered,
        "continuation_resume_persisted": continuation_resume_persisted,
        "human_priority_blocked": human_priority_blocked,
        "continuation_help_escalation": continuation_help_escalation,
        "regression_reroute": dict(regression_reroute or {}),
    }


def observe_gap_resolution_at_execution_end(
    orchestrator: Any | None,
    *,
    stop_reason: str | None,
    answer_gate: Mapping[str, Any] | None,
    loop_counters: Mapping[str, Any] | None,
    correlation_id: str,
    recorded: Mapping[str, Any] | None,
    human_priority_blocked: bool,
    gap_stagnation_count: int = 0,
    gap_snapshot: Mapping[str, Any] | None = None,
    continuation_stagnation_count: int = 0,
    block_continuation_resume: bool = False,
    help_escalation: bool = False,
    decision: GapResolutionDecision | None = None,
    regression_reroute: Mapping[str, Any] | None = None,
    superseded_winner: str | None = None,
) -> tuple[GapResolutionDecision | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Classify and route at execution end. Observation only — no route execution."""
    if orchestrator is None:
        return None, None, None
    if decision is None:
        decision = route_gap_resolution_from_orchestrator(
            orchestrator,
            stop_reason=stop_reason,
            answer_gate=answer_gate,
            loop_counters=loop_counters,
            gap_stagnation_count=gap_stagnation_count,
        )
    if help_escalation:
        decision.winner = CapabilityId.HELP.value
    continuation_resume = None
    persist = should_persist_goal_continuation_resume(
        decision,
        human_priority_blocked=human_priority_blocked,
    )
    if block_continuation_resume or help_escalation:
        persist = False
    if persist:
        continuation_resume = build_goal_continuation_resume(
            orchestrator,
            decision,
            recorded=recorded,
            correlation_id=correlation_id,
            gap_snapshot=gap_snapshot,
            continuation_stagnation_count=continuation_stagnation_count,
            superseded_winner=superseded_winner,
            regression_reroute=bool(regression_reroute),
        )
    event_payload = gap_resolution_routed_event_payload(
        decision,
        continuation_resume_persisted=persist,
        human_priority_blocked=human_priority_blocked,
        continuation_help_escalation=help_escalation,
        regression_reroute=regression_reroute,
    )
    return decision, continuation_resume, event_payload
