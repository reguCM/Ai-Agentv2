"""Semantic stagnation warning — optional observation-period continue-on-warning wiring.

**Production default:** semantic fuse counters (STAGNATION / SAME_FAILURE / NO_EVIDENCE)
set ``stop_reason`` and end the Agent loop (``semantic_stagnation_warning_enabled: false``).

**Observation mode:** when ``semantic_stagnation_warning_enabled`` is true, fuse thresholds
emit warnings and execution continues (Warning+Continue).

**Unchanged by this module:** Progress Classification v0 and State-cycle Detection v0
remain shadow-only and are not connected to stop or routing.

**Spec note:** gap router ``STAGNATION_EXHAUSTED → HELP`` keys off ``stop_reason``.
Semantic fuses no longer populate ``stop_reason`` during warning mode, so that HELP
path does not fire at the former semantic-fuse stop point (HELP routing unchanged).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_tool.chat_interface.progress_classification_v0 import (
    ProgressClassificationV0,
    ProgressStateSnapshot,
)

SEMANTIC_FUSE_STOP_REASONS = frozenset(
    {
        "STAGNATION_LIMIT",
        "SAME_FAILURE_LIMIT",
        "NO_EVIDENCE_LIMIT",
    }
)

SEMANTIC_WARNING_USER_MESSAGE = (
    "同じ状態または類似した処理が継続しています。"
    "現在は停止せず実行を継続しています。"
)


def is_semantic_fuse_stop(reason: Any | None) -> bool:
    token = _stop_reason_token(reason)
    return token in SEMANTIC_FUSE_STOP_REASONS


def active_semantic_warnings(counters: Any) -> list[str]:
    """All semantic fuse thresholds currently met (not priority-truncated)."""
    active: list[str] = []
    same_failure_count = int(getattr(counters, "same_failure_count", 0) or 0)
    same_failure_limit = int(getattr(counters, "same_failure_limit", 0) or 0)
    stagnation_count = int(getattr(counters, "stagnation_count", 0) or 0)
    stagnation_limit = int(getattr(counters, "stagnation_limit", 0) or 0)
    no_evidence_count = int(getattr(counters, "no_evidence_count", 0) or 0)
    no_evidence_limit = int(getattr(counters, "no_evidence_limit", 0) or 0)
    if same_failure_limit and same_failure_count >= same_failure_limit:
        active.append("SAME_FAILURE_LIMIT")
    if stagnation_limit and stagnation_count >= stagnation_limit:
        active.append("STAGNATION_LIMIT")
    if no_evidence_limit and no_evidence_count >= no_evidence_limit:
        active.append("NO_EVIDENCE_LIMIT")
    return active



def resolve_actual_stop_reason(
    would_have_stopped_by: Any | None,
    *,
    semantic_warning_enabled: bool,
) -> Any | None:
    """Return actual loop stop reason; semantic fuses become warnings when enabled."""
    if would_have_stopped_by is None:
        return None
    if semantic_warning_enabled and is_semantic_fuse_stop(would_have_stopped_by):
        return None
    return would_have_stopped_by


def semantic_warning_enabled_from_pipeline(pipeline: dict[str, Any] | None) -> bool:
    """Production default: fuse stops apply unless warn-and-continue is explicitly enabled."""
    if pipeline is None:
        return False
    if "semantic_stagnation_warning_enabled" in pipeline:
        return bool(pipeline.get("semantic_stagnation_warning_enabled"))
    if pipeline.get("progress_shadow_semantic_bypass"):
        return True
    return False


def state_snapshot_key(snapshot: ProgressStateSnapshot | None) -> tuple[Any, ...]:
    if snapshot is None:
        return ()
    gap = snapshot.to_gap_snapshot()
    return (
        str(snapshot.gap_kind or ""),
        bool(snapshot.gap_resolved),
        bool(snapshot.answer_gate_verified),
        tuple(sorted(snapshot.satisfied_conditions)),
        tuple(sorted(snapshot.unsatisfied_conditions)),
        tuple(sorted(snapshot.verified_evidence_ids)),
        tuple(sorted(snapshot.goal_statuses.items())),
        tuple(sorted(snapshot.task_statuses.items())),
        snapshot.completion_ratio,
        snapshot.requirements_passed,
        snapshot.requirements_total,
        tuple(sorted(snapshot.passed_condition_ids)),
        tuple(sorted(snapshot.failed_condition_ids)),
        str(snapshot.failure_signature or ""),
    )


@dataclass
class SemanticStagnationWarningTracker:
    """Collects semantic-stagnation warning telemetry for one Chat turn."""

    enabled: bool = True
    warnings: list[dict[str, Any]] = field(default_factory=list)
    first_warning_reason: str | None = None
    first_warning_tool_sequence: int | None = None
    _displayed_reasons: set[str] = field(default_factory=set)
    _last_display_state_key: tuple[Any, ...] | None = None
    _post_warning_started: bool = False
    _post_warning_tool_count: int = 0
    _post_warning_goal_progress: bool = False
    _post_warning_observation_progress: bool = False
    _post_warning_newly_exposed_failure: bool = False
    _post_warning_action_changed: bool = False
    _last_action_signature: str | None = None
    final_stop_reason: str | None = None
    last_active_semantic_warnings: list[str] = field(default_factory=list)

    def note_active_fuses(self, active: list[str]) -> None:
        self.last_active_semantic_warnings = list(active)

    def observe_fuse_trigger(
        self,
        *,
        would_have_stopped_by: Any | None,
        tool_sequence: int,
        counters: Any,
        classification: ProgressClassificationV0,
        action_signature: str | None,
        failure_signature: str | None,
        state_key: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        reason = _stop_reason_token(would_have_stopped_by)
        if reason is None or reason not in SEMANTIC_FUSE_STOP_REASONS:
            return None

        if self.first_warning_reason is None:
            self.first_warning_reason = reason
            self.first_warning_tool_sequence = tool_sequence
        if not self._post_warning_started:
            self._post_warning_started = True
        if action_signature is not None:
            self._last_action_signature = action_signature

        active = active_semantic_warnings(counters)
        self.last_active_semantic_warnings = list(active)
        row = {
            "warning_reason": reason,
            "would_have_stopped_by": reason,
            "active_semantic_warnings": active,
            "first_warning_tool_sequence": self.first_warning_tool_sequence,
            "tool_sequence": tool_sequence,
            "loop_counters": {
                "stagnation_count": int(getattr(counters, "stagnation_count", 0) or 0),
                "same_failure_count": int(getattr(counters, "same_failure_count", 0) or 0),
                "no_evidence_count": int(getattr(counters, "no_evidence_count", 0) or 0),
                "total_tool_calls": int(getattr(counters, "total_tool_calls", 0) or 0),
            },
            "classifier": classification.as_dict(),
            "action_signature": action_signature,
            "failure_signature": failure_signature,
            "user_message": SEMANTIC_WARNING_USER_MESSAGE,
        }
        self.warnings.append(row)

        should_display = reason not in self._displayed_reasons
        if should_display:
            self._displayed_reasons.add(reason)
            self._last_display_state_key = state_key

        if should_display:
            return {**row, "display": True}
        return {**row, "display": False}

    def observe_post_warning_step(
        self,
        *,
        classification: ProgressClassificationV0,
        action_signature: str | None,
    ) -> None:
        if not self._post_warning_started:
            return
        self._post_warning_tool_count += 1
        if classification.goal_progress:
            self._post_warning_goal_progress = True
        if classification.observation_progress:
            self._post_warning_observation_progress = True
        if classification.newly_exposed_failure:
            self._post_warning_newly_exposed_failure = True
        if (
            action_signature is not None
            and self._last_action_signature is not None
            and action_signature != self._last_action_signature
        ):
            self._post_warning_action_changed = True
        if action_signature is not None:
            self._last_action_signature = action_signature

    def finalize(
        self,
        *,
        actual_stop_reason: Any | None,
        orchestrator: Any | None,
    ) -> None:
        self.final_stop_reason = _stop_reason_token(actual_stop_reason)
        if not self._post_warning_started or orchestrator is None:
            return
        if self.final_stop_reason == "COMPLETED":
            self._post_warning_goal_progress = True
            return
        runtime = orchestrator.runtime
        tasks = getattr(runtime, "tasks", None) or {}
        if tasks and all(
            str(getattr(task, "status", "") or "") == "complete" for task in tasks.values()
        ):
            self._post_warning_goal_progress = True

    def as_dict(self) -> dict[str, Any]:
        completed_after_warning = (
            self.final_stop_reason == "COMPLETED" or self._post_warning_goal_progress
        )
        return {
            "version": "v0",
            "semantic_warning_mode": bool(self.enabled),
            "production_semantic_fuse_stop_connected": not bool(self.enabled),
            "progress_classification_stop_connected": False,
            "state_cycle_stop_connected": False,
            "enabled": self.enabled,
            "user_message": SEMANTIC_WARNING_USER_MESSAGE if self.warnings else None,
            "last_active_semantic_warnings": list(self.last_active_semantic_warnings),
            "first_warning_reason": self.first_warning_reason,
            "first_warning_tool_sequence": self.first_warning_tool_sequence,
            "warning_count": len(self.warnings),
            "warnings": list(self.warnings),
            "post_warning_summary": (
                {
                    "tools_after_warning": self._post_warning_tool_count,
                    "goal_progress_after_warning": self._post_warning_goal_progress,
                    "observation_progress_after_warning": (
                        self._post_warning_observation_progress
                    ),
                    "newly_exposed_failure_after_warning": (
                        self._post_warning_newly_exposed_failure
                    ),
                    "action_changed_after_warning": self._post_warning_action_changed,
                    "completed_after_warning": completed_after_warning,
                    "final_stop_reason": self.final_stop_reason,
                }
                if self._post_warning_started
                else None
            ),
        }


def _stop_reason_token(value: Any | None) -> str | None:
    if value is None:
        return None
    token = getattr(value, "value", value)
    return str(token) if token else None
