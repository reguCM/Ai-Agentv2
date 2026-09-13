"""Shadow-only Progress Classification v0 wiring for production Chat Runtime.

Observes state deltas alongside LoopCounters. Semantic fuse stops may be converted
to warnings via ``semantic_stagnation_warning`` (observation period).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ai_tool.chat_interface.goal_continuation_progress import capture_gap_snapshot
from ai_tool.chat_interface.progress_classification_v0 import (
    ProgressClassificationV0,
    ProgressStateSnapshot,
    classify_progress_transition,
)
from ai_tool.chat_interface.semantic_stagnation_warning import (
    is_semantic_fuse_stop,
    resolve_actual_stop_reason,
)
from ai_tool.chat_interface.state_cycle_detection_v0 import StateCycleTracker

__all__ = [
    "ProgressShadowTracker",
    "is_semantic_fuse_stop",
    "resolve_actual_stop_reason",
    "snapshot_from_orchestrator",
    "SEMANTIC_FUSE_STOP_REASONS",
]

from ai_tool.chat_interface.semantic_stagnation_warning import (  # noqa: E402
    SEMANTIC_FUSE_STOP_REASONS,
)


def snapshot_from_orchestrator(orchestrator: Any) -> ProgressStateSnapshot:
    """Build a comparable snapshot from the live Chat Task Runtime."""
    gap = capture_gap_snapshot(
        orchestrator,
        gap_kind="",
        gap_resolved=False,
        answer_gate=None,
    )
    snap = ProgressStateSnapshot.from_gap_snapshot(gap)
    runtime = orchestrator.runtime
    tasks = getattr(runtime, "tasks", None) or {}

    total_conditions = 0
    satisfied_count = 0
    passed_ids: list[str] = []
    failed_ids: list[str] = []
    for task in tasks.values():
        total_conditions += len(task.completion_conditions)
        satisfied_count += len(task.satisfied_conditions)
        for condition in task.completion_conditions:
            status = str(task.condition_status.get(condition) or "UNKNOWN")
            if status == "SATISFIED" and condition not in passed_ids:
                passed_ids.append(condition)
            elif status == "FAILED" and condition not in failed_ids:
                failed_ids.append(condition)

    if total_conditions:
        snap.completion_ratio = round(satisfied_count / total_conditions, 4)
        snap.requirements_passed = satisfied_count
        snap.requirements_total = total_conditions

    snap.evidence_count = len(getattr(runtime, "evidence", None) or {})
    snap.passed_condition_ids = sorted(passed_ids)
    snap.failed_condition_ids = sorted(failed_ids)

    current_task_id = str(getattr(orchestrator, "current_task_id", "") or "")
    failures = [
        item
        for item in (getattr(runtime, "failures", None) or [])
        if str(getattr(item, "task_id", "") or "") == current_task_id
    ]
    if failures:
        last = failures[-1]
        snap.failure_signature = (
            f"{last.failure_code}:"
            f"{json.dumps(last.arguments, sort_keys=True, ensure_ascii=False)}"
        )
    return snap


@dataclass
class ProgressShadowTracker:
    """Accumulates per-tool shadow observations for one Chat turn."""

    semantic_bypass_enabled: bool = False
    version: str = "v0"
    _prior: ProgressStateSnapshot | None = None
    observations: list[dict[str, Any]] = field(default_factory=list)
    first_bypassed_stop_reason: str | None = None
    first_bypassed_tool_sequence: int | None = None
    bypass_count: int = 0
    actual_stop_reason: str | None = None
    _baseline_at_first_bypass: ProgressStateSnapshot | None = None
    _post_bypass_goal_progress: bool = False
    _post_bypass_observation_progress: bool = False
    _post_bypass_newly_exposed_failure: bool = False
    _post_bypass_all_stagnation: bool = True
    _post_bypass_started: bool = False
    _post_bypass_transitions: list[dict[str, Any]] = field(default_factory=list)
    _state_cycle_tracker: StateCycleTracker = field(default_factory=StateCycleTracker)

    def note_semantic_bypass(
        self,
        *,
        would_have_stopped_by: Any | None,
        bypass_applied: bool,
        tool_sequence: int,
    ) -> None:
        if not bypass_applied or would_have_stopped_by is None:
            return
        token = _stop_reason_token(would_have_stopped_by)
        if token is None:
            return
        self.bypass_count += 1
        if self.first_bypassed_stop_reason is None:
            self.first_bypassed_stop_reason = token
            self.first_bypassed_tool_sequence = tool_sequence

    def observe_after_tool(
        self,
        *,
        orchestrator: Any,
        counters: Any,
        tool_name: str,
        tool_arguments: dict[str, Any],
        tool_status: str,
        would_have_stopped_by: Any | None,
        current_stop_reason: Any | None,
        semantic_bypass_applied: bool = False,
        evidence_gain: bool = False,
        relevance_audit: str | None = None,
    ) -> dict[str, Any]:
        current = snapshot_from_orchestrator(orchestrator)
        classification = classify_progress_transition(self._prior, current)
        mutation_count = len(getattr(orchestrator.runtime, "mutations", None) or [])
        state_cycle_row = self._state_cycle_tracker.observe_step(
            tool_sequence=int(getattr(counters, "total_tool_calls", 0) or 0),
            prior_snapshot=self._prior,
            current_snapshot=current,
            classification=classification,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            tool_status=tool_status,
            evidence_gain=evidence_gain,
            relevance_audit=relevance_audit,
            mutation_count=mutation_count,
        )
        if semantic_bypass_applied and self._baseline_at_first_bypass is None:
            self._baseline_at_first_bypass = (
                self._prior if self._prior is not None else ProgressStateSnapshot.empty()
            )
            self._post_bypass_started = True
        elif self._post_bypass_started:
            self._accumulate_post_bypass(
                classification,
                tool_sequence=int(getattr(counters, "total_tool_calls", 0) or 0),
            )
        row = _shadow_row(
            tool_sequence=int(getattr(counters, "total_tool_calls", 0) or 0),
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            tool_status=tool_status,
            classification=classification,
            counters=counters,
            would_have_stopped_by=would_have_stopped_by,
            current_stop_reason=current_stop_reason,
            semantic_bypass_applied=semantic_bypass_applied,
            state_cycle=state_cycle_row,
        )
        self.observations.append(row)
        self._prior = current
        return row

    def finalize(self, *, actual_stop_reason: Any | None, orchestrator: Any | None) -> None:
        self.actual_stop_reason = _stop_reason_token(actual_stop_reason)
        if not self._post_bypass_started or orchestrator is None:
            return
        completed = self.actual_stop_reason == "COMPLETED"
        if not completed:
            runtime = orchestrator.runtime
            tasks = getattr(runtime, "tasks", None) or {}
            completed = all(
                str(getattr(task, "status", "") or "") == "complete"
                for task in tasks.values()
            )
        if completed:
            self._post_bypass_goal_progress = True

    def finalize_and_as_dict(
        self,
        *,
        actual_stop_reason: Any | None,
        orchestrator: Any | None,
    ) -> dict[str, Any]:
        self.finalize(actual_stop_reason=actual_stop_reason, orchestrator=orchestrator)
        return self.as_dict()

    def _accumulate_post_bypass(
        self,
        classification: ProgressClassificationV0,
        *,
        tool_sequence: int,
    ) -> None:
        if classification.goal_progress:
            self._post_bypass_goal_progress = True
        if classification.observation_progress:
            self._post_bypass_observation_progress = True
        if classification.newly_exposed_failure:
            self._post_bypass_newly_exposed_failure = True
        if not classification.stagnation:
            self._post_bypass_all_stagnation = False
        self._post_bypass_transitions.append(
            {
                "tool_sequence": tool_sequence,
                "goal_progress": classification.goal_progress,
                "observation_progress": classification.observation_progress,
                "newly_exposed_failure": classification.newly_exposed_failure,
                "stagnation": classification.stagnation,
            }
        )

    def as_dict(self) -> dict[str, Any]:
        post_bypass = None
        if self._post_bypass_started:
            post_bypass = {
                "goal_progress_after_bypass": self._post_bypass_goal_progress,
                "observation_progress_after_bypass": self._post_bypass_observation_progress,
                "newly_exposed_failure_after_bypass": self._post_bypass_newly_exposed_failure,
                "completed_after_bypass": self.actual_stop_reason == "COMPLETED"
                or self._post_bypass_goal_progress,
                "stagnation_throughout_after_bypass": self._post_bypass_all_stagnation,
                "transitions_after_bypass": list(self._post_bypass_transitions),
            }
        return {
            "version": self.version,
            "observation_only": True,
            "progress_classification_stop_connected": False,
            "semantic_warning_mode": self.semantic_bypass_enabled,
            "semantic_bypass_enabled": self.semantic_bypass_enabled,
            "first_bypassed_stop_reason": self.first_bypassed_stop_reason,
            "first_bypassed_tool_sequence": self.first_bypassed_tool_sequence,
            "bypass_count": self.bypass_count,
            "actual_stop_reason": self.actual_stop_reason,
            "post_bypass_summary": post_bypass,
            "state_cycle_detection": self._state_cycle_tracker.as_dict(),
            "observations": list(self.observations),
        }


def _stop_reason_token(value: Any | None) -> str | None:
    if value is None:
        return None
    token = getattr(value, "value", value)
    return str(token) if token else None


def _shadow_row(
    *,
    tool_sequence: int,
    tool_name: str,
    tool_arguments: dict[str, Any],
    tool_status: str,
    classification: ProgressClassificationV0,
    counters: Any,
    would_have_stopped_by: Any | None,
    current_stop_reason: Any | None,
    semantic_bypass_applied: bool = False,
    state_cycle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = classification.as_dict()
    return {
        "tool_sequence": tool_sequence,
        "attempt": tool_sequence,
        "tool_name": tool_name,
        "tool_arguments": dict(tool_arguments),
        "tool_status": tool_status,
        "goal_progress": payload["goal_progress"],
        "observation_progress": payload["observation_progress"],
        "regression": payload["regression"],
        "newly_exposed_failure": payload["newly_exposed_failure"],
        "stagnation": payload["stagnation"],
        "goal_progress_reasons": payload["goal_progress_reasons"],
        "observation_progress_reasons": payload["observation_progress_reasons"],
        "regression_reasons": payload["regression_reasons"],
        "newly_exposed_failure_reasons": payload["newly_exposed_failure_reasons"],
        "stagnation_reasons": payload["stagnation_reasons"],
        "loop_counters": {
            "stagnation_count": int(getattr(counters, "stagnation_count", 0) or 0),
            "same_failure_count": int(getattr(counters, "same_failure_count", 0) or 0),
            "no_evidence_count": int(getattr(counters, "no_evidence_count", 0) or 0),
            "total_tool_calls": int(getattr(counters, "total_tool_calls", 0) or 0),
        },
        "would_have_stopped_by": _stop_reason_token(would_have_stopped_by),
        "current_stop_reason": _stop_reason_token(current_stop_reason),
        "semantic_bypass_applied": bool(semantic_bypass_applied),
        "state_cycle_detection": dict(state_cycle or {}),
    }
