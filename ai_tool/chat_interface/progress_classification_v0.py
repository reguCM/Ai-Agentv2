"""Progress Classification v0 — multi-axis state-delta assessment.

Compares a prior snapshot to a current snapshot using existing Runtime facts.
Does not replace fixed loop/continuation counters or stop_reason logic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ai_tool.chat_interface.goal_continuation_progress import (
    GapSnapshot,
    compare_gap_snapshots,
    gap_signature,
)
from tools.ai.task_runtime import ProgressState


@dataclass
class ProgressStateSnapshot:
    """Comparable state for progress classification (Runtime + lab eval)."""

    gap_kind: str = ""
    gap_resolved: bool = False
    answer_gate_verified: bool = False
    unsatisfied_conditions: list[str] = field(default_factory=list)
    satisfied_conditions: list[str] = field(default_factory=list)
    verified_evidence_ids: list[str] = field(default_factory=list)
    goal_statuses: dict[str, str] = field(default_factory=dict)
    task_statuses: dict[str, str] = field(default_factory=dict)
    completion_ratio: float | None = None
    requirements_passed: int | None = None
    requirements_total: int | None = None
    evidence_count: int = 0
    pytest_passed: int = 0
    pytest_failed: int = 0
    pytest_blocked: int = 0
    pytest_canonical_total: int = 0
    feature_units_passed: dict[str, bool] = field(default_factory=dict)
    feature_units_observable: dict[str, bool] = field(default_factory=dict)
    runnable_ok: bool = False
    playable: bool = False
    failure_signature: str | None = None
    passed_condition_ids: list[str] = field(default_factory=list)
    failed_condition_ids: list[str] = field(default_factory=list)

    def to_gap_snapshot(self) -> GapSnapshot:
        return GapSnapshot(
            gap_kind=self.gap_kind,
            gap_resolved=self.gap_resolved,
            answer_gate_verified=self.answer_gate_verified,
            unsatisfied_conditions=list(self.unsatisfied_conditions),
            satisfied_conditions=list(self.satisfied_conditions),
            verified_evidence_ids=list(self.verified_evidence_ids),
            goal_statuses=dict(self.goal_statuses),
            task_statuses=dict(self.task_statuses),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def empty(cls) -> ProgressStateSnapshot:
        return cls()

    @classmethod
    def from_gap_snapshot(cls, snapshot: GapSnapshot) -> ProgressStateSnapshot:
        return cls(
            gap_kind=snapshot.gap_kind,
            gap_resolved=snapshot.gap_resolved,
            answer_gate_verified=snapshot.answer_gate_verified,
            unsatisfied_conditions=list(snapshot.unsatisfied_conditions),
            satisfied_conditions=list(snapshot.satisfied_conditions),
            verified_evidence_ids=list(snapshot.verified_evidence_ids),
            goal_statuses=dict(snapshot.goal_statuses),
            task_statuses=dict(snapshot.task_statuses),
        )


@dataclass
class ProgressClassificationV0:
    goal_progress: bool = False
    observation_progress: bool = False
    regression: bool = False
    newly_exposed_failure: bool = False
    stagnation: bool = False
    goal_progress_reasons: list[str] = field(default_factory=list)
    observation_progress_reasons: list[str] = field(default_factory=list)
    regression_reasons: list[str] = field(default_factory=list)
    newly_exposed_failure_reasons: list[str] = field(default_factory=list)
    stagnation_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm_signature(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _observable_test_count(snapshot: ProgressStateSnapshot) -> int:
    return int(snapshot.pytest_passed) + int(snapshot.pytest_failed)


def _blocked_released(prior: ProgressStateSnapshot, current: ProgressStateSnapshot) -> bool:
    prior_obs = _observable_test_count(prior)
    current_obs = _observable_test_count(current)
    return (
        int(current.pytest_blocked) < int(prior.pytest_blocked)
        and current_obs > prior_obs
    )


def _completion_improved(prior: ProgressStateSnapshot, current: ProgressStateSnapshot) -> bool:
    if prior.completion_ratio is None or current.completion_ratio is None:
        if (
            prior.requirements_passed is not None
            and current.requirements_passed is not None
            and current.requirements_passed > prior.requirements_passed
        ):
            return True
        return False
    return current.completion_ratio > prior.completion_ratio


def _completion_regressed(prior: ProgressStateSnapshot, current: ProgressStateSnapshot) -> bool:
    if prior.completion_ratio is None or current.completion_ratio is None:
        if (
            prior.requirements_passed is not None
            and current.requirements_passed is not None
            and current.requirements_passed < prior.requirements_passed
        ):
            return True
        return False
    return current.completion_ratio < prior.completion_ratio


def _lost_passed_feature_units(
    prior: ProgressStateSnapshot,
    current: ProgressStateSnapshot,
) -> list[str]:
    lost: list[str] = []
    for unit_id, was_passed in prior.feature_units_passed.items():
        if was_passed and not current.feature_units_passed.get(unit_id, False):
            lost.append(unit_id)
    return lost


def _newly_observable_units(
    prior: ProgressStateSnapshot,
    current: ProgressStateSnapshot,
) -> list[str]:
    newly: list[str] = []
    for unit_id, now_observable in current.feature_units_observable.items():
        if now_observable and not prior.feature_units_observable.get(unit_id, False):
            newly.append(unit_id)
    return newly


def classify_progress_transition(
    prior: ProgressStateSnapshot | None,
    current: ProgressStateSnapshot,
) -> ProgressClassificationV0:
    """Classify prior→current using independent multi-axis flags."""
    if prior is None:
        prior = ProgressStateSnapshot.empty()

    result = ProgressClassificationV0()
    prior_gap = prior.to_gap_snapshot()
    current_gap = current.to_gap_snapshot()
    gap_verdict, gap_reasons = compare_gap_snapshots(prior_gap, current_gap)

    if gap_verdict == ProgressState.PROGRESS.value:
        result.goal_progress = True
        result.goal_progress_reasons.extend(gap_reasons)
    elif gap_verdict == ProgressState.REGRESSION.value:
        result.regression = True
        result.regression_reasons.extend(gap_reasons)

    if _completion_improved(prior, current):
        result.goal_progress = True
        result.goal_progress_reasons.append("completion_ratio_improved")
    if _completion_regressed(prior, current):
        result.regression = True
        result.regression_reasons.append("completion_ratio_regressed")

    newly_passed_conditions = sorted(
        set(current.passed_condition_ids) - set(prior.passed_condition_ids)
    )
    lost_passed_conditions = sorted(
        set(prior.passed_condition_ids) - set(current.passed_condition_ids)
    )
    if newly_passed_conditions:
        result.goal_progress = True
        result.goal_progress_reasons.append(
            f"conditions_passed:{','.join(newly_passed_conditions)}"
        )
    if lost_passed_conditions:
        result.regression = True
        result.regression_reasons.append(
            f"conditions_lost:{','.join(lost_passed_conditions)}"
        )

    new_verified = sorted(
        set(current.verified_evidence_ids) - set(prior.verified_evidence_ids)
    )
    if new_verified:
        result.observation_progress = True
        result.observation_progress_reasons.append(
            f"verified_evidence_added:{','.join(new_verified)}"
        )
    if current.evidence_count > prior.evidence_count:
        result.observation_progress = True
        result.observation_progress_reasons.append("evidence_count_increased")

    blocked_released = _blocked_released(prior, current)
    if blocked_released:
        result.observation_progress = True
        result.observation_progress_reasons.append("pytest_blocked_released")

    if current.pytest_passed > prior.pytest_passed:
        result.observation_progress = True
        result.observation_progress_reasons.append("pytest_passed_increased")

    if prior.runnable_ok and not current.runnable_ok:
        result.regression = True
        result.regression_reasons.append("runnable_ok_lost")
    if not prior.runnable_ok and current.runnable_ok:
        result.observation_progress = True
        result.observation_progress_reasons.append("runnable_ok_gained")

    lost_units = _lost_passed_feature_units(prior, current)
    if lost_units:
        result.regression = True
        result.regression_reasons.append(
            f"feature_units_lost:{','.join(sorted(lost_units))}"
        )

    if current.pytest_passed < prior.pytest_passed:
        result.regression = True
        result.regression_reasons.append("pytest_passed_decreased")

    prior_sig = _norm_signature(prior.failure_signature)
    current_sig = _norm_signature(current.failure_signature)
    failure_signature_changed = bool(
        current_sig and prior_sig != current_sig
    )
    newly_observable = _newly_observable_units(prior, current)

    if failure_signature_changed and not lost_units and not lost_passed_conditions:
        if blocked_released or newly_observable:
            result.newly_exposed_failure = True
            result.newly_exposed_failure_reasons.append("failure_signature_changed_after_blocker_release")
        elif prior_sig is None and current_sig:
            result.newly_exposed_failure = True
            result.newly_exposed_failure_reasons.append("failure_signature_first_observed")
        elif prior_sig and current_sig != prior_sig and not result.regression:
            result.newly_exposed_failure = True
            result.newly_exposed_failure_reasons.append("failure_signature_shift_without_regression")

    if (
        result.observation_progress
        and current.pytest_failed > prior.pytest_failed
        and current.pytest_passed > prior.pytest_passed
        and blocked_released
        and "pytest_passed_decreased" not in result.regression_reasons
    ):
        result.newly_exposed_failure = True
        if "failure_signature_changed_after_blocker_release" not in result.newly_exposed_failure_reasons:
            result.newly_exposed_failure_reasons.append(
                "failed_count_increased_after_more_tests_ran"
            )

    completion_flat = not _completion_improved(prior, current)
    gap_flat = gap_signature(prior_gap) == gap_signature(current_gap)
    if not result.goal_progress and completion_flat and not result.regression:
        result.stagnation = True
        result.stagnation_reasons.append("no_goal_completion_progress")
    if (
        not result.goal_progress
        and completion_flat
        and gap_flat
        and prior_sig == current_sig
        and prior.failed_condition_ids == current.failed_condition_ids
    ):
        result.stagnation = True
        if "failure_and_completion_unchanged" not in result.stagnation_reasons:
            result.stagnation_reasons.append("failure_and_completion_unchanged")

    return result


def classify_runtime_turn_end(
    *,
    prior_gap_snapshot: Mapping[str, Any] | GapSnapshot | None,
    current_gap_snapshot: Mapping[str, Any] | GapSnapshot,
    prior_evidence_count: int = 0,
    current_evidence_count: int = 0,
) -> ProgressClassificationV0:
    """Thin wrapper for Runtime gap snapshots at execution boundaries."""
    if isinstance(prior_gap_snapshot, GapSnapshot):
        prior = ProgressStateSnapshot.from_gap_snapshot(prior_gap_snapshot)
    else:
        prior = (
            ProgressStateSnapshot.from_gap_snapshot(
                GapSnapshot.from_mapping(prior_gap_snapshot)  # type: ignore[arg-type]
            )
            if prior_gap_snapshot
            else ProgressStateSnapshot.empty()
        )
    if isinstance(current_gap_snapshot, GapSnapshot):
        current = ProgressStateSnapshot.from_gap_snapshot(current_gap_snapshot)
    else:
        current = ProgressStateSnapshot.from_gap_snapshot(
            GapSnapshot.from_mapping(current_gap_snapshot)  # type: ignore[arg-type]
        )
    prior.evidence_count = int(prior_evidence_count)
    current.evidence_count = int(current_evidence_count)
    return classify_progress_transition(prior, current)
