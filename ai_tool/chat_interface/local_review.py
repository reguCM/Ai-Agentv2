"""Bounded local review of an Agent Task result.

The reviewer proposes facts and follow-up tasks.  It is never authoritative:
the runtime validates completion coverage and task grounding before accepting
any proposal.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping


REVIEW_STATUSES = {"COMPLETE", "CONTINUE", "ESCALATE"}


@dataclass
class ReviewTaskCandidate:
    description: str
    reason: str
    supports_conditions: list[str] = field(default_factory=list)
    source_problem: str = ""


@dataclass
class StructuredReview:
    review_status: str = "CONTINUE"
    facts: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    new_tasks: list[ReviewTaskCandidate] = field(default_factory=list)
    recommended_next_action: str = ""
    confidence: float | None = None
    parse_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def parse_review(value: Any) -> StructuredReview:
    """Parse untrusted reviewer output without raising into the Agent Loop."""
    try:
        if not isinstance(value, Mapping):
            text = str(value or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            value = json.loads(text)
        if not isinstance(value, Mapping):
            raise ValueError("review must be a JSON object")
        status = str(value.get("review_status") or "CONTINUE").upper()
        if status not in REVIEW_STATUSES:
            raise ValueError(f"invalid review_status: {status}")
        candidates: list[ReviewTaskCandidate] = []
        for item in value.get("new_tasks") or []:
            if not isinstance(item, Mapping):
                continue
            candidates.append(
                ReviewTaskCandidate(
                    description=str(item.get("description") or "").strip(),
                    reason=str(item.get("reason") or "").strip(),
                    supports_conditions=_strings(item.get("supports_conditions")),
                    source_problem=str(item.get("source_problem") or "").strip(),
                )
            )
        confidence = value.get("confidence")
        if confidence is not None:
            confidence = max(0.0, min(1.0, float(confidence)))
        return StructuredReview(
            review_status=status,
            facts=_strings(value.get("facts")),
            problems=_strings(value.get("problems")),
            missing_evidence=_strings(value.get("missing_evidence")),
            conflicts=_strings(value.get("conflicts")),
            new_tasks=candidates,
            recommended_next_action=str(value.get("recommended_next_action") or "").strip(),
            confidence=confidence,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return StructuredReview(parse_error=f"{type(exc).__name__}: {exc}")


def build_review_input(orchestrator: Any, task_result: str) -> dict[str, Any]:
    runtime = orchestrator.runtime
    task = orchestrator.task
    roots = [goal for goal in runtime.goals.values() if goal.parent_goal_id is None]
    evidence = [runtime.evidence[item] for item in task.evidence_ids]
    unresolved = [
        condition
        for condition in task.completion_conditions
        if task.condition_status.get(condition) != "SATISFIED"
    ]
    return {
        "final_goal": roots[0].title if roots else None,
        "current_goal": runtime.goals[task.goal_id].title,
        "current_task": {
            "task_id": task.task_id,
            "title": task.title,
            "instruction": task.instruction,
            "status": task.status,
        },
        "completion_conditions": [
            {
                "description": condition,
                "status": task.condition_status.get(condition, "UNKNOWN"),
                "supporting_evidence": list(task.condition_evidence.get(condition) or []),
            }
            for condition in task.completion_conditions
        ],
        "task_result": str(task_result or "")[:6000],
        "relevant_evidence": [
            {
                "evidence_id": item.evidence_id,
                "summary": item.summary,
                "supported_completion_conditions": item.supported_completion_conditions,
            }
            for item in evidence
        ],
        "known_failures": [
            {
                "failure_id": item.failure_id,
                "failure_code": item.failure_code,
                "tool_name": item.tool_name,
            }
            for item in runtime.failures
            if item.task_id == task.task_id
        ],
        "unresolved_conditions": unresolved,
    }


def review_prompt(review_input: Mapping[str, Any]) -> list[dict[str, str]]:
    schema = {
        "review_status": "COMPLETE | CONTINUE | ESCALATE",
        "facts": ["observed fact"],
        "problems": ["grounded problem"],
        "missing_evidence": ["missing evidence"],
        "conflicts": ["conflict"],
        "new_tasks": [
            {
                "description": "bounded follow-up task",
                "reason": "why it is necessary",
                "supports_conditions": ["exact unresolved condition"],
                "source_problem": "exact problem/missing evidence/conflict",
            }
        ],
        "recommended_next_action": "next action",
        "confidence": 0.0,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are LocalReviewAssistant. Review only the supplied Task result. "
                "Return one JSON object and no prose. Do not declare completion when a "
                "required condition is unresolved. Every new task must cite an exact "
                "unresolved condition or an exact listed problem, missing evidence, "
                "conflict, or known failure. Schema:\n"
                + json.dumps(schema, ensure_ascii=False)
            ),
        },
        {
            "role": "user",
            "content": json.dumps(dict(review_input), ensure_ascii=False),
        },
    ]


def call_local_reviewer(
    chat_fn: Callable[..., Any], *, model: str, review_input: Mapping[str, Any]
) -> StructuredReview:
    try:
        response = chat_fn(model=model, messages=review_prompt(review_input), tools=[])
        message = getattr(response, "message", None)
        return parse_review(getattr(message, "content", None))
    except Exception as exc:  # review failure must not fail the Agent Turn
        return StructuredReview(parse_error=f"{type(exc).__name__}: {exc}")


def validate_review(
    review: StructuredReview,
    orchestrator: Any,
    *,
    max_new_tasks: int = 2,
) -> dict[str, Any]:
    """Validate reviewer claims against authoritative runtime state."""
    runtime = orchestrator.runtime
    task = orchestrator.task
    unresolved = [
        condition
        for condition in task.completion_conditions
        if task.condition_status.get(condition) != "SATISFIED"
    ]
    known_failures = [
        item.failure_code for item in runtime.failures if item.task_id == task.task_id
    ]
    existing = {
        " ".join(f"{item.title} {item.instruction}".casefold().split())
        for item in runtime.tasks.values()
    }
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in review.new_tasks:
        reason = None
        normalized = " ".join(candidate.description.casefold().split())
        condition_match = any(item in unresolved for item in candidate.supports_conditions)
        known_failure_match = candidate.source_problem in known_failures
        conflict_match = candidate.source_problem in review.conflicts
        missing_evidence_match = (
            candidate.source_problem in review.missing_evidence and condition_match
        )
        # A reviewer-proposed generic problem is not authority by itself.  New
        # work must trace to runtime coverage/failure state, or to an explicit
        # conflict that requires verification.
        problem_match = bool(candidate.source_problem) and (
            known_failure_match or conflict_match or missing_evidence_match
        )
        duplicate = any(
            normalized and (normalized == item or normalized in item or item in normalized)
            for item in existing
        )
        if not candidate.description or not candidate.reason:
            reason = "missing_required_fields"
        elif duplicate:
            reason = "duplicate_task"
        elif not condition_match and not problem_match:
            reason = "ungrounded_task"
        elif len(accepted) >= max_new_tasks:
            reason = "new_task_limit"
        row = asdict(candidate)
        if reason:
            rejected.append({"task": row, "reason": reason})
        else:
            accepted.append(row)
            existing.add(normalized)

    coverage_complete = bool(task.completion_conditions) and not unresolved
    status = review.review_status
    if status == "COMPLETE" and not coverage_complete:
        status = "CONTINUE"
        rejected.append({"claim": "COMPLETE", "reason": "coverage_incomplete"})
    escalation_packet = None
    task_is_stagnating = task.progress_state == "stagnation"
    has_tool_gap = any(item.task_id == task.task_id for item in runtime.tool_gaps.values())
    human_decision = any(
        token in " ".join(review.problems).casefold()
        for token in ("human", "judgment", "decision", "approval")
    )
    escalation_grounded = bool(
        review.conflicts
        or known_failures
        or task_is_stagnating
        or has_tool_gap
        or human_decision
    )
    if status == "ESCALATE" and not escalation_grounded:
        status = "CONTINUE"
        rejected.append({"claim": "ESCALATE", "reason": "escalation_not_grounded"})
    if status == "ESCALATE":
        escalation_packet = {
            "automatic_escalation": False,
            "current_task": task.title,
            "unresolved_conditions": unresolved,
            "problems": review.problems,
            "conflicts": review.conflicts,
            "known_failures": known_failures,
            "recommended_next_action": review.recommended_next_action,
        }
    return {
        "review_status": status,
        "coverage_complete": coverage_complete,
        "unresolved_conditions_before": unresolved,
        "unresolved_conditions_after": list(unresolved),
        "accepted_new_tasks": accepted,
        "rejected_new_tasks": rejected,
        "escalation_packet": escalation_packet,
        "parse_error": review.parse_error,
    }


__all__ = [
    "ReviewTaskCandidate",
    "StructuredReview",
    "build_review_input",
    "call_local_reviewer",
    "parse_review",
    "review_prompt",
    "validate_review",
]
