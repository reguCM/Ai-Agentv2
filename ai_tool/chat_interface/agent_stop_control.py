"""Terminal stop control helpers for Production Chat Agent loop.

Hard / pause stops must not trigger additional LLM calls (final synthesis, help, etc.).
"""
from __future__ import annotations

from typing import Any

_INCOMPLETE_GOAL_STOP_REASONS = frozenset(
    {
        "GOAL_INCOMPLETE_OPEN_WORK",
        "GOAL_INCOMPLETE_BLOCKED",
        "GOAL_INCOMPLETE_CONTINUATION",
        "GOAL_INCOMPLETE_REPLAN",
    }
)

_RESUMABLE_PAUSE_STOP_REASONS = frozenset(
    {
        "HUMAN_GRILL",
        "GOAL_COMPLETION_HUMAN",
        "APPROVAL_REQUIRED",
    }
)

_HARD_TERMINAL_STOP_REASONS = frozenset(
    {
        "USER_CANCELLED",
        "TIMEOUT",
        "PIPELINE_BUDGET_EXCEEDED",
        "RUNTIME_ERROR",
        "LLM_EMPTY_RESPONSE",
        "LLM_RESPONSE_ERROR",
        "HARD_CAPABILITY_GAP",
        "STAGNATION_LIMIT",
        "SAME_FAILURE_LIMIT",
        "NO_EVIDENCE_LIMIT",
        "GOAL_CONTINUATION_REGRESSION",
        "TASK_CHANGE_PROPAGATION_NON_CONVERGED",
        "PREMISE_REVALIDATION_EXECUTION_BLOCKED",
    }
) | _INCOMPLETE_GOAL_STOP_REASONS

# Narrower than ``_HARD_TERMINAL_STOP_REASONS``: semantic fuses and hard infra stops
# bypass post-loop routers. Orchestration blocks (capability gap, goal-incomplete,
# propagation / premise guards) keep the normal execution-end path.
_SYSTEM_FAST_EXIT_STOP_REASONS = frozenset(
    {
        "USER_CANCELLED",
        "TIMEOUT",
        "PIPELINE_BUDGET_EXCEEDED",
        "RUNTIME_ERROR",
        "LLM_EMPTY_RESPONSE",
        "LLM_RESPONSE_ERROR",
        "STAGNATION_LIMIT",
        "SAME_FAILURE_LIMIT",
        "NO_EVIDENCE_LIMIT",
    }
)

_NO_AGENT_LLM_AFTER_STOP = _HARD_TERMINAL_STOP_REASONS | _RESUMABLE_PAUSE_STOP_REASONS


def stop_reason_token(stop_reason: Any) -> str:
    if stop_reason is None:
        return ""
    value = getattr(stop_reason, "value", stop_reason)
    return str(value or "")


def is_resumable_pause_stop(stop_reason: Any) -> bool:
    return stop_reason_token(stop_reason) in _RESUMABLE_PAUSE_STOP_REASONS


def is_hard_terminal_stop(stop_reason: Any) -> bool:
    token = stop_reason_token(stop_reason)
    return token in _HARD_TERMINAL_STOP_REASONS


def should_skip_agent_llm_after_stop(stop_reason: Any) -> bool:
    """True when stop is decided and no further agent LLM calls are allowed."""
    token = stop_reason_token(stop_reason)
    if not token or token == "COMPLETED":
        return False
    return token in _NO_AGENT_LLM_AFTER_STOP


def should_system_fast_exit_after_stop(stop_reason: Any) -> bool:
    """True when execution must bypass post-stop routers and return immediately."""
    return stop_reason_token(stop_reason) in _SYSTEM_FAST_EXIT_STOP_REASONS


def pause_exit_answer(
    orchestrator: Any,
    stop_reason: Any,
    *,
    existing_answer: str = "",
    runtime_status_report: dict[str, Any] | None = None,
) -> str:
    """Read-only pause message without gate/router side effects."""
    if str(existing_answer or "").strip():
        return str(existing_answer)
    token = stop_reason_token(stop_reason)
    if orchestrator is not None and token == "HUMAN_GRILL":
        if orchestrator.needs_human_grill():
            from ai_tool.chat_interface.task_orchestration import format_conversation_grill

            return format_conversation_grill(orchestrator.conversation_grill_record())
    if orchestrator is not None and token == "GOAL_COMPLETION_HUMAN":
        if orchestrator.needs_goal_completion_human():
            from ai_tool.chat_interface.goal_completion_gate import format_goal_completion_human

            return format_goal_completion_human(
                orchestrator.goal_completion_human_record()
            )
    return system_exit_answer(
        runtime_status_report,
        stop_reason=stop_reason,
        existing_answer=existing_answer,
    )


def finalize_exit_answer(
    stop_reason: Any,
    *,
    existing_answer: str = "",
    runtime_status_report: dict[str, Any] | None = None,
    orchestrator: Any = None,
) -> str:
    if is_resumable_pause_stop(stop_reason):
        return pause_exit_answer(
            orchestrator,
            stop_reason,
            existing_answer=existing_answer,
            runtime_status_report=runtime_status_report,
        )
    if should_skip_agent_llm_after_stop(stop_reason):
        return system_exit_answer(
            runtime_status_report,
            stop_reason=stop_reason,
            existing_answer=existing_answer,
        )
    return str(existing_answer or "")


def system_exit_answer(
    runtime_status_report: dict[str, Any] | None,
    *,
    stop_reason: Any,
    existing_answer: str = "",
) -> str:
    """Mechanical exit message without LLM synthesis."""
    if str(existing_answer or "").strip():
        return str(existing_answer)
    if runtime_status_report is not None:
        markdown = str(runtime_status_report.get("markdown") or "").strip()
        if markdown:
            return markdown
    token = stop_reason_token(stop_reason) or "UNKNOWN"
    resumable = is_resumable_pause_stop(stop_reason)
    state = "paused" if resumable else "stopped"
    return (
        f"Execution {state}.\n"
        f"Reason: {token}\n"
        "Mission state has been persisted where applicable."
    )
