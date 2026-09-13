"""S5b — Explicit authorized test runner wedge (TEST_EXECUTION only)."""
from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, MutableSet, Sequence

from test_safety.authorization import (
    AUTH_AUTHORIZED,
    AUTH_DENIED,
    bind_test_safety_authorization,
    verify_authorization_for_execution,
)
from test_safety.git_snapshot import git_worktree_snapshot
from test_safety.postflight import (
    POSTFLIGHT_PASS,
    PostflightFn,
    evaluate_run_closure,
    run_required_postflight,
)
from test_safety.shadow_gate import evaluate_shadow_gate
from test_safety.validator import evaluate_test_plan

RUNNER_ID = "test_safety_runner_wedge_s5c_v1"

OUTCOME_SAFETY_DENIED = "SAFETY_AUTHORIZATION_FAILURE"
OUTCOME_ALREADY_CONSUMED = "EXECUTION_ALREADY_CONSUMED"
OUTCOME_EXECUTED = "EXECUTED"

DENY_EXECUTION_ALREADY_CONSUMED = "EXECUTION_ALREADY_CONSUMED"

ExecutorFn = Callable[[Sequence[str]], dict[str, Any]]


def _argv_from_commands(commands: Sequence[str]) -> list[str]:
    rows = [str(c).strip() for c in commands if str(c).strip()]
    if not rows:
        return []
    if len(rows) == 1 and " " in rows[0]:
        return shlex.split(rows[0], posix=sys.platform != "win32")
    return rows


@dataclass
class ConsumedAuthorizationRegistry:
    """Tracks consumed authorization_binding_key values for exactly-once spawn."""

    _keys: MutableSet[str] = field(default_factory=set)

    def consume(self, binding_key: str) -> bool:
        token = str(binding_key or "").strip()
        if not token or token in self._keys:
            return False
        self._keys.add(token)
        return True

    def was_consumed(self, binding_key: str) -> bool:
        return str(binding_key or "").strip() in self._keys


def default_pytest_executor(commands: Sequence[str]) -> dict[str, Any]:
    """Run declared shell commands (typically pytest). Not called by Gate/Binder."""
    if not commands:
        return {"ok": False, "error": "no_commands", "returncode": 1}
    cmd = _argv_from_commands(commands)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            shell=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
            "command": cmd,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "returncode": 1,
            "command": cmd,
        }


def prepare_evaluation_and_authorization(
    plan: Mapping[str, Any],
    *,
    action_id: str,
    host_process_notes: list[str] | None = None,
    repo_root: Path | None = None,
    eval_schema_path: Path | None = None,
    gate_schema_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Validator → Shadow Gate → bind (no execution)."""
    evaluation = evaluate_test_plan(
        dict(plan),
        repo_root=repo_root,
        host_process_notes=host_process_notes,
    )
    gate = evaluate_shadow_gate(evaluation, schema_path=eval_schema_path)
    authorization = bind_test_safety_authorization(
        action_id=action_id,
        current_plan=plan,
        evaluation_packet=evaluation,
        gate_packet=gate,
        eval_schema_path=eval_schema_path,
        gate_schema_path=gate_schema_path,
    )
    return evaluation, gate, authorization


def execute_authorized_test_plan(
    *,
    action_id: str,
    current_plan: Mapping[str, Any],
    authorization_packet: Mapping[str, Any],
    executor: ExecutorFn | None = None,
    consumed_registry: ConsumedAuthorizationRegistry | None = None,
    repo_root: Path | None = None,
    postflight_fn: PostflightFn | None = None,
    baseline_git: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Authoritative execution boundary: verify authorization, then call executor at most once per binding key.
    """
    issued_at = datetime.now(timezone.utc).isoformat()
    run = executor or default_pytest_executor
    registry = consumed_registry or ConsumedAuthorizationRegistry()

    verification = verify_authorization_for_execution(
        authorization_packet,
        action_id=action_id,
        current_plan=current_plan,
    )
    base_evidence = _evidence_skeleton(
        action_id=action_id,
        current_plan=current_plan,
        authorization_packet=authorization_packet,
        verification=verification,
        issued_at=issued_at,
    )

    required_postflight = dict(
        verification.get("required_postflight")
        or authorization_packet.get("required_postflight")
        or {"postflight_git_check_required": False}
    )

    if verification.get("authorization") != AUTH_AUTHORIZED:
        base_evidence.update(
            {
                "outcome": OUTCOME_SAFETY_DENIED,
                "execution_verification": "DENIED",
                "executor_called": False,
                "execution_result": None,
                "postflight_result": None,
                "test_failed": False,
                "run_closed": False,
                "closure_reason": "SAFETY_AUTHORIZATION_NOT_EXECUTED",
            }
        )
        return base_evidence

    binding_key = str(verification.get("authorization_binding_key") or "")
    if registry.was_consumed(binding_key):
        denied = dict(verification)
        denied["authorization"] = AUTH_DENIED
        denied["reason"] = DENY_EXECUTION_ALREADY_CONSUMED
        denied["reasons"] = [DENY_EXECUTION_ALREADY_CONSUMED]
        base_evidence["authorization_verification"] = denied
        base_evidence.update(
            {
                "outcome": OUTCOME_ALREADY_CONSUMED,
                "execution_verification": "DENIED",
                "executor_called": False,
                "execution_result": None,
                "postflight_result": None,
                "test_failed": False,
                "run_closed": False,
                "closure_reason": "EXECUTION_ALREADY_CONSUMED",
            }
        )
        return base_evidence

    if not registry.consume(binding_key):
        base_evidence.update(
            {
                "outcome": OUTCOME_ALREADY_CONSUMED,
                "execution_verification": "DENIED",
                "executor_called": False,
                "execution_result": None,
                "postflight_result": None,
                "test_failed": False,
                "run_closed": False,
                "closure_reason": "EXECUTION_ALREADY_CONSUMED",
            }
        )
        return base_evidence

    baseline = baseline_git
    if baseline is None and repo_root is not None and required_postflight.get("postflight_git_check_required"):
        baseline = git_worktree_snapshot(repo_root)

    commands = [str(c) for c in (current_plan.get("commands") or []) if str(c).strip()]
    execution_result = run(commands)

    write_scope = [str(x) for x in (current_plan.get("declared_write_scope") or [])]
    postflight_result = run_required_postflight(
        required_postflight,
        repo_root=repo_root,
        baseline_git=baseline,
        declared_write_scope=write_scope,
        postflight_fn=postflight_fn,
    )

    run_closed, closure_reason = evaluate_run_closure(
        executor_called=True,
        safety_outcome=OUTCOME_EXECUTED,
        execution_result=execution_result,
        required_postflight=required_postflight,
        postflight_result=postflight_result,
    )

    base_evidence.update(
        {
            "outcome": OUTCOME_EXECUTED,
            "execution_verification": "VALID",
            "executor_called": True,
            "execution_result": execution_result,
            "postflight_result": postflight_result,
            "test_failed": execution_result.get("ok") is False,
            "run_closed": run_closed,
            "postflight_completed": (
                postflight_result is not None
                and str(postflight_result.get("postflight_status")) == POSTFLIGHT_PASS
            ),
            "closure_reason": closure_reason,
            "execution_consumed": True,
        }
    )
    return base_evidence


def _evidence_skeleton(
    *,
    action_id: str,
    current_plan: Mapping[str, Any],
    authorization_packet: Mapping[str, Any],
    verification: Mapping[str, Any],
    issued_at: str,
) -> dict[str, Any]:
    from test_safety.plan_fingerprint import compute_plan_fingerprint

    try:
        fp = compute_plan_fingerprint(current_plan)
    except ValueError:
        fp = ""

    return {
        "schema_version": "1",
        "packet_type": "TEST_SAFETY_RUNNER_EVIDENCE",
        "runner_id": RUNNER_ID,
        "issued_at": issued_at,
        "action_id": str(action_id),
        "plan_fingerprint": fp,
        "evaluation_ref": dict(verification.get("evaluation_ref") or authorization_packet.get("evaluation_ref") or {}),
        "authorization_id": authorization_packet.get("authorization_id"),
        "authorization": verification.get("authorization"),
        "authorization_binding_key": verification.get("authorization_binding_key"),
        "authorization_packet": dict(authorization_packet),
        "authorization_verification": dict(verification),
        "required_postflight": dict(
            verification.get("required_postflight")
            or authorization_packet.get("required_postflight")
            or {"postflight_git_check_required": False}
        ),
        "execution_connected": True,
        "general_runtime_connected": False,
    }
