"""State-cycle Detection v0 — shadow-only state transition cycle observation.

Detects semantic state revisits from state/action/observation separation.
Does not connect to stop_reason or legacy fuse counters.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from ai_tool.chat_interface.goal_continuation_progress import gap_signature
from ai_tool.chat_interface.progress_classification_v0 import (
    ProgressClassificationV0,
    ProgressStateSnapshot,
)


@dataclass(frozen=True)
class StateFingerprint:
    """Semantic Agent state without action or raw evidence-id cardinality."""

    gap: tuple[Any, ...]
    satisfied_conditions: tuple[str, ...]
    unsatisfied_conditions: tuple[str, ...]
    goal_statuses: tuple[tuple[str, str], ...]
    task_statuses: tuple[tuple[str, str], ...]
    completion_ratio: float | None
    requirements_passed: int | None
    requirements_total: int | None
    passed_condition_ids: tuple[str, ...]
    failed_condition_ids: tuple[str, ...]
    verified_evidence_ids: tuple[str, ...]
    failure_signature: str | None
    mutation_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TransitionFingerprint:
    """Action + observation for one Decision → Action → Observation step."""

    tool_name: str
    action_class: tuple[Any, ...]
    action_arguments: tuple[tuple[str, Any], ...]
    tool_status: str
    evidence_gain: bool
    relevance_audit: str | None
    observation_signature: tuple[Any, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StateCycleClassificationV0:
    unchanged_state: bool = False
    action_changed_without_state_progress: bool = False
    repeated_transition: bool = False
    state_cycle_candidate: bool = False
    unchanged_state_reasons: list[str] = field(default_factory=list)
    action_changed_reasons: list[str] = field(default_factory=list)
    repeated_transition_reasons: list[str] = field(default_factory=list)
    cycle_candidate_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _WitnessedTransition:
    state_before: StateFingerprint
    transition: TransitionFingerprint
    state_after: StateFingerprint


@dataclass
class StateCycleTracker:
    """Accumulates state-cycle evidence for one Chat turn (shadow only)."""

    version: str = "v0"
    _witnessed: list[_WitnessedTransition] = field(default_factory=list)
    _seen_states: list[StateFingerprint] = field(default_factory=list)
    _last_transition: TransitionFingerprint | None = None
    observations: list[dict[str, Any]] = field(default_factory=list)
    first_unchanged_state_tool_sequence: int | None = None
    first_repeated_transition_tool_sequence: int | None = None
    first_cycle_candidate_tool_sequence: int | None = None

    def observe_step(
        self,
        *,
        tool_sequence: int,
        prior_snapshot: ProgressStateSnapshot | None,
        current_snapshot: ProgressStateSnapshot,
        classification: ProgressClassificationV0,
        tool_name: str,
        tool_arguments: dict[str, Any],
        tool_status: str,
        evidence_gain: bool,
        relevance_audit: str | None,
        mutation_count: int,
    ) -> dict[str, Any]:
        prior_mutation = self._seen_states[-1].mutation_count if self._seen_states else 0
        state_before = (
            state_fingerprint_from_snapshot(prior_snapshot, mutation_count=prior_mutation)
            if prior_snapshot is not None
            else None
        )
        state_after = state_fingerprint_from_snapshot(
            current_snapshot,
            mutation_count=mutation_count,
        )
        transition = transition_fingerprint(
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            tool_status=tool_status,
            evidence_gain=evidence_gain,
            relevance_audit=relevance_audit,
            classification=classification,
        )
        cycle = classify_state_cycle_step(
            state_before=state_before,
            state_after=state_after,
            transition=transition,
            classification=classification,
            witnessed=self._witnessed,
            seen_states=self._seen_states,
            previous_transition=self._last_transition,
        )
        if state_before is not None:
            self._witnessed.append(
                _WitnessedTransition(
                    state_before=state_before,
                    transition=transition,
                    state_after=state_after,
                )
            )
        self._seen_states.append(state_after)
        self._last_transition = transition

        if cycle.unchanged_state and self.first_unchanged_state_tool_sequence is None:
            self.first_unchanged_state_tool_sequence = tool_sequence
        if cycle.repeated_transition and self.first_repeated_transition_tool_sequence is None:
            self.first_repeated_transition_tool_sequence = tool_sequence
        if cycle.state_cycle_candidate and self.first_cycle_candidate_tool_sequence is None:
            self.first_cycle_candidate_tool_sequence = tool_sequence

        row = {
            "tool_sequence": tool_sequence,
            "state_fingerprint": state_after.as_dict(),
            "transition": transition.as_dict(),
            "unchanged_state": cycle.unchanged_state,
            "action_changed_without_state_progress": cycle.action_changed_without_state_progress,
            "repeated_transition": cycle.repeated_transition,
            "state_cycle_candidate": cycle.state_cycle_candidate,
            "unchanged_state_reasons": cycle.unchanged_state_reasons,
            "action_changed_reasons": cycle.action_changed_reasons,
            "repeated_transition_reasons": cycle.repeated_transition_reasons,
            "cycle_candidate_reasons": cycle.cycle_candidate_reasons,
        }
        self.observations.append(row)
        return row

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "observation_only": True,
            "state_cycle_stop_connected": False,
            "first_unchanged_state_tool_sequence": self.first_unchanged_state_tool_sequence,
            "first_repeated_transition_tool_sequence": self.first_repeated_transition_tool_sequence,
            "first_cycle_candidate_tool_sequence": self.first_cycle_candidate_tool_sequence,
            "observations": list(self.observations),
        }


def state_fingerprint_from_snapshot(
    snapshot: ProgressStateSnapshot,
    *,
    mutation_count: int = 0,
) -> StateFingerprint:
    gap = snapshot.to_gap_snapshot()
    return StateFingerprint(
        gap=gap_signature(gap),
        satisfied_conditions=tuple(sorted(gap.satisfied_conditions)),
        unsatisfied_conditions=tuple(sorted(gap.unsatisfied_conditions)),
        goal_statuses=tuple(sorted(gap.goal_statuses.items())),
        task_statuses=tuple(sorted(gap.task_statuses.items())),
        completion_ratio=snapshot.completion_ratio,
        requirements_passed=snapshot.requirements_passed,
        requirements_total=snapshot.requirements_total,
        passed_condition_ids=tuple(sorted(snapshot.passed_condition_ids)),
        failed_condition_ids=tuple(sorted(snapshot.failed_condition_ids)),
        verified_evidence_ids=tuple(sorted(snapshot.verified_evidence_ids)),
        failure_signature=_norm_optional(snapshot.failure_signature),
        mutation_count=int(mutation_count or 0),
    )


def normalize_action_class(tool_name: str, tool_arguments: dict[str, Any]) -> tuple[Any, ...]:
    """Semantic action class without pagination cursors or key-order noise."""
    args = dict(tool_arguments or {})
    name = str(tool_name or "")
    if name == "read_file":
        return (name, "read", str(args.get("path") or ""))
    if name == "search_files":
        return (name, "search", str(args.get("query") or ""), str(args.get("path") or "."))
    if name == "list_files":
        return (name, "list", str(args.get("path") or "."))
    return (name, json.dumps(args, sort_keys=True, ensure_ascii=False, default=str))


def transition_fingerprint(
    *,
    tool_name: str,
    tool_arguments: dict[str, Any],
    tool_status: str,
    evidence_gain: bool,
    relevance_audit: str | None,
    classification: ProgressClassificationV0,
) -> TransitionFingerprint:
    args = dict(tool_arguments or {})
    action_class = normalize_action_class(tool_name, args)
    observation_signature = (
        str(tool_status or ""),
        bool(evidence_gain),
        str(relevance_audit or ""),
        bool(classification.observation_progress),
        bool(classification.newly_exposed_failure),
    )
    return TransitionFingerprint(
        tool_name=str(tool_name or ""),
        action_class=action_class,
        action_arguments=tuple(sorted((str(k), args[k]) for k in args)),
        tool_status=str(tool_status or ""),
        evidence_gain=bool(evidence_gain),
        relevance_audit=str(relevance_audit) if relevance_audit else None,
        observation_signature=observation_signature,
    )


def classify_state_cycle_step(
    *,
    state_before: StateFingerprint | None,
    state_after: StateFingerprint,
    transition: TransitionFingerprint,
    classification: ProgressClassificationV0,
    witnessed: list[_WitnessedTransition],
    seen_states: list[StateFingerprint],
    previous_transition: TransitionFingerprint | None = None,
) -> StateCycleClassificationV0:
    result = StateCycleClassificationV0()
    if state_before is None:
        return result

    result.unchanged_state = state_before == state_after
    if result.unchanged_state:
        result.unchanged_state_reasons.append("state_fingerprint_unchanged")

    last_transition = previous_transition
    if result.unchanged_state and last_transition is not None:
        if last_transition.action_class != transition.action_class:
            result.action_changed_without_state_progress = True
            result.action_changed_reasons.append("state_unchanged_action_class_changed")
        elif last_transition.action_arguments != transition.action_arguments:
            result.action_changed_without_state_progress = True
            result.action_changed_reasons.append("state_unchanged_action_arguments_changed")

    for item in witnessed:
        if (
            item.state_before == state_before
            and item.state_after == state_after
            and item.transition.action_class == transition.action_class
            and item.transition.observation_signature == transition.observation_signature
            and item.state_before == item.state_after
        ):
            result.repeated_transition = True
            result.repeated_transition_reasons.append(
                "same_state_action_observation_loop_redetected"
            )
            break

    if result.repeated_transition:
        result.state_cycle_candidate = True
        result.cycle_candidate_reasons.append("repeated_transition")
    elif result.unchanged_state and state_after in seen_states[:-1]:
        result.state_cycle_candidate = True
        result.cycle_candidate_reasons.append("semantic_state_revisited")

    return result


def _norm_optional(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None
