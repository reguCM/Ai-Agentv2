"""Context 拡張 Gate（increase_context は最後の手段、P2-13）。"""
from __future__ import annotations

from typing import Any

from tools.system.context_monitor.recovery import (
    RecoverySession,
    gpu_observation_allows_execution,
    load_recovery_policy,
    next_context_step,
    validate_candidate_context,
)


def evaluate_context_expansion_gate(
    *,
    execution: dict[str, Any],
    cycle_state: dict[str, Any] | None = None,
    context_expansion_decision: dict[str, Any] | None = None,
    normal_recommendations: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
    session: RecoverySession | None = None,
    human_approved: bool = False,
    check_approval: bool = True,
) -> dict[str, Any]:
    """
    increase_context 実行可否を判定。通常 Recovery 候補と同列に扱わない。
    条件未成立時は BLOCKED。
    """
    policy = policy or load_recovery_policy()
    session = session or RecoverySession(policy=policy)
    cycle = cycle_state or {}
    normal_recommendations = normal_recommendations or []
    blocked_reasons: list[str] = []

    if cycle.get("context_expansion_used"):
        blocked_reasons.append("context_expansion_already_used_this_cycle")

    if not cycle.get("normal_recovery_attempted"):
        blocked_reasons.append("normal_recovery_not_attempted")

    task_unresolved = cycle.get("task_unresolved", False)
    recovery_failed = cycle.get("recovery_failed", False)
    if not task_unresolved and not recovery_failed:
        blocked_reasons.append("task_not_unresolved_and_recovery_not_failed")

    tried = set(cycle.get("tried_strategies") or [])
    viable_untried = [
        r
        for r in normal_recommendations
        if r.get("candidate_strategy") not in tried
        and r.get("execution_allowed")
        and r.get("candidate_strategy") != "increase_context"
    ]
    if viable_untried:
        blocked_reasons.append("viable_normal_candidates_remain")

    configured = execution.get("configured_context")
    current = execution.get("runtime_context") or execution.get("context_size") or configured
    model = str(execution.get("model") or "")
    profile_id = execution.get("profile_id")

    candidate_ctx = None
    if context_expansion_decision:
        candidate_ctx = context_expansion_decision.get("candidate_context")
    if candidate_ctx is None and current is not None:
        candidate_ctx = next_context_step(int(current), policy)

    validation = (
        validate_candidate_context(
            int(candidate_ctx),
            current=int(current),
            model=model,
            profile_id=profile_id,
            policy=policy,
        )
        if candidate_ctx is not None and current is not None
        else {"valid": False, "reasons": ["no candidate context"]}
    )
    if not validation.get("valid"):
        blocked_reasons.extend(validation.get("reasons") or ["context_expansion_not_technically_valid"])

    gpu_state = execution.get("gpu_state") or (context_expansion_decision or {}).get("gpu_state")
    gpu_check = gpu_observation_allows_execution(gpu_state, policy)
    if not gpu_check.get("execution_allowed"):
        blocked_reasons.append("gpu_observation_unavailable")

    if candidate_ctx is not None and not session.can_change_context(int(candidate_ctx)):
        blocked_reasons.append("context_change_limit_reached")

    if check_approval and not human_approved:
        blocked_reasons.append("human_approval_required")

    status = "ALLOWED" if not blocked_reasons else "BLOCKED"
    return {
        "gate_status": status,
        "blocked_reasons": blocked_reasons,
        "candidate_context": candidate_ctx,
        "validation": validation,
        "gpu_execution_check": gpu_check,
        "note": "increase_context is last-resort; not ranked with normal candidates",
    }
