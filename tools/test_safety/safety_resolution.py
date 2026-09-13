"""S7a — Automatic test safety resolution (explicit runner only; no pytest)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from test_safety.authorization import (
    AUTH_AUTHORIZED,
    AUTH_DENIED,
    DENY_GATE_BLOCKED,
    DENY_HUMAN_APPROVAL_REQUIRED,
    verify_authorization_for_execution,
)
from test_safety.plan_fingerprint import compute_plan_fingerprint
from test_safety.runner_wedge import (
    ConsumedAuthorizationRegistry,
    ExecutorFn,
    PostflightFn,
    execute_authorized_test_plan,
    prepare_evaluation_and_authorization,
)

RESOLVER_ID = "test_safety_resolution_s7a_v1"
MAX_AUTOMATIC_RESOLUTION_ATTEMPTS = 1

RESOLUTION_SKIPPED = "SKIPPED"
RESOLUTION_RESOLVED = "RESOLVED"
RESOLUTION_BLOCKED = "BLOCKED"
RESOLUTION_AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
RESOLUTION_ERROR = "ERROR"
RESOLUTION_UNRESOLVED = "UNRESOLVED"


@dataclass
class ResolutionRunState:
    """In-run state only (S6.1); not persisted across runs."""

    automatic_resolution_attempts: int = 0
    max_automatic_attempts: int = MAX_AUTOMATIC_RESOLUTION_ATTEMPTS
    resolution_attempted: bool = False


def authorization_is_valid(
    authorization_packet: Mapping[str, Any] | None,
    *,
    action_id: str,
    current_plan: Mapping[str, Any],
) -> bool:
    if not authorization_packet:
        return False
    verified = verify_authorization_for_execution(
        authorization_packet,
        action_id=action_id,
        current_plan=current_plan,
    )
    return verified.get("authorization") == AUTH_AUTHORIZED


def _map_denied_to_resolution(authorization: Mapping[str, Any], gate: Mapping[str, Any]) -> str:
    reasons = list(authorization.get("reasons") or [])
    if DENY_HUMAN_APPROVAL_REQUIRED in reasons or gate.get("human_approval_required"):
        return RESOLUTION_AWAITING_HUMAN_APPROVAL
    if DENY_GATE_BLOCKED in reasons or gate.get("gate_decision") == "BLOCKED":
        return RESOLUTION_BLOCKED
    if authorization.get("authorization") == AUTH_DENIED:
        return RESOLUTION_BLOCKED
    return RESOLUTION_ERROR


def resolve_test_safety(
    *,
    action_id: str,
    current_plan: Mapping[str, Any],
    authorization_packet: Mapping[str, Any] | None = None,
    state: ResolutionRunState | None = None,
    host_process_notes: list[str] | None = None,
    repo_root: Path | None = None,
    eval_schema_path: Path | None = None,
    gate_schema_path: Path | None = None,
) -> dict[str, Any]:
    """
    Detect missing/invalid authorization; run at most one automatic safety evaluation cycle.
    Does not execute pytest.
    """
    run_state = state or ResolutionRunState()
    issued_at = datetime.now(timezone.utc).isoformat()
    action_token = str(action_id or "").strip()
    fp_before = compute_plan_fingerprint(current_plan)

    present_before = authorization_is_valid(
        authorization_packet,
        action_id=action_token,
        current_plan=current_plan,
    )

    base: dict[str, Any] = {
        "schema_version": "1",
        "packet_type": "TEST_SAFETY_RESOLUTION_EVIDENCE",
        "resolver_id": RESOLVER_ID,
        "issued_at": issued_at,
        "action_id": action_token,
        "plan_fingerprint": fp_before,
        "authorization_present_before": present_before,
        "resolution_attempted": False,
        "resolution_attempt_count": run_state.automatic_resolution_attempts,
        "original_action_preserved": True,
        "general_runtime_connected": False,
    }

    if present_before:
        verified = verify_authorization_for_execution(
            authorization_packet or {},
            action_id=action_token,
            current_plan=current_plan,
        )
        base.update(
            {
                "resolution_result": RESOLUTION_SKIPPED,
                "resolution_skipped": True,
                "evaluation_ref": dict(verified.get("evaluation_ref") or {}),
                "gate_decision": verified.get("gate_decision"),
                "authorization_id": authorization_packet.get("authorization_id") if authorization_packet else None,
                "authorization_packet": dict(authorization_packet or {}),
                "evaluation_packet": None,
                "gate_packet": None,
            }
        )
        return base

    if run_state.automatic_resolution_attempts >= run_state.max_automatic_attempts:
        base.update(
            {
                "resolution_result": RESOLUTION_UNRESOLVED,
                "resolution_skipped": False,
                "resolution_attempted": False,
                "reason": "automatic_resolution_attempt_exhausted",
            }
        )
        return base

    run_state.automatic_resolution_attempts += 1
    run_state.resolution_attempted = True
    base["resolution_attempt_count"] = run_state.automatic_resolution_attempts
    base["resolution_attempted"] = True

    try:
        evaluation, gate, authorization = prepare_evaluation_and_authorization(
            current_plan,
            action_id=action_token,
            host_process_notes=host_process_notes,
            repo_root=repo_root,
            eval_schema_path=eval_schema_path,
            gate_schema_path=gate_schema_path,
        )
    except Exception as exc:  # noqa: BLE001
        base.update(
            {
                "resolution_result": RESOLUTION_ERROR,
                "error": f"{type(exc).__name__}: {exc}",
                "evaluation_packet": None,
                "gate_packet": None,
                "authorization_packet": None,
            }
        )
        return base

    fp_after = compute_plan_fingerprint(current_plan)
    base["original_action_preserved"] = (
        action_token == str(action_id).strip() and fp_before == fp_after
    )
    base["plan_fingerprint"] = fp_after

    if authorization.get("authorization") == AUTH_AUTHORIZED:
        base.update(
            {
                "resolution_result": RESOLUTION_RESOLVED,
                "resolution_skipped": False,
                "evaluation_ref": dict(authorization.get("evaluation_ref") or {}),
                "gate_decision": authorization.get("gate_decision"),
                "authorization_id": authorization.get("authorization_id"),
                "authorization_packet": dict(authorization),
                "evaluation_packet": evaluation,
                "gate_packet": gate,
            }
        )
        return base

    result = _map_denied_to_resolution(authorization, gate)
    base.update(
        {
            "resolution_result": result,
            "resolution_skipped": False,
            "evaluation_ref": dict(authorization.get("evaluation_ref") or {}),
            "gate_decision": gate.get("gate_decision"),
            "authorization_id": authorization.get("authorization_id"),
            "authorization_packet": dict(authorization),
            "evaluation_packet": evaluation,
            "gate_packet": gate,
            "reasons": list(authorization.get("reasons") or []),
        }
    )
    return base


def run_explicit_test_with_auto_resolution(
    *,
    action_id: str,
    current_plan: Mapping[str, Any],
    authorization_packet: Mapping[str, Any] | None = None,
    state: ResolutionRunState | None = None,
    host_process_notes: list[str] | None = None,
    repo_root: Path | None = None,
    eval_schema_path: Path | None = None,
    gate_schema_path: Path | None = None,
    executor: ExecutorFn | None = None,
    consumed_registry: ConsumedAuthorizationRegistry | None = None,
    postflight_fn: PostflightFn | None = None,
    baseline_git: Mapping[str, Any] | None = None,
    runner_plan_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Resolver → (optional) runner wedge. Single run-scoped resolution state.
    runner_plan_override is for negative tests only (tampered plan after resolution).
    """
    run_state = state or ResolutionRunState()
    resolution = resolve_test_safety(
        action_id=action_id,
        current_plan=current_plan,
        authorization_packet=authorization_packet,
        state=run_state,
        host_process_notes=host_process_notes,
        repo_root=repo_root,
        eval_schema_path=eval_schema_path,
        gate_schema_path=gate_schema_path,
    )

    outcome: dict[str, Any] = {
        "schema_version": "1",
        "packet_type": "TEST_SAFETY_EXPLICIT_RUN",
        "resolution": resolution,
        "executor_called": False,
        "test_failed": False,
        "runner_evidence": None,
    }

    if resolution.get("resolution_result") == RESOLUTION_SKIPPED:
        auth = dict(authorization_packet or resolution.get("authorization_packet") or {})
    elif resolution.get("resolution_result") == RESOLUTION_RESOLVED:
        auth = dict(resolution.get("authorization_packet") or {})
    else:
        outcome["resolution_stop_reason"] = resolution.get("resolution_result")
        return outcome

    plan_for_runner = dict(runner_plan_override or current_plan)
    runner_evidence = execute_authorized_test_plan(
        action_id=action_id,
        current_plan=plan_for_runner,
        authorization_packet=auth,
        executor=executor,
        consumed_registry=consumed_registry,
        repo_root=repo_root,
        postflight_fn=postflight_fn,
        baseline_git=baseline_git,
    )
    outcome["runner_evidence"] = runner_evidence
    outcome["executor_called"] = bool(runner_evidence.get("executor_called"))
    outcome["test_failed"] = bool(runner_evidence.get("test_failed"))
    outcome["run_closed"] = runner_evidence.get("run_closed")
    resolution["executor_called"] = outcome["executor_called"]
    return outcome
