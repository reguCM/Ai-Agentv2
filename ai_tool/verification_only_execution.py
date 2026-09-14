"""Execute one identity-bound Verification action without reopening a Task."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from ai_tool.production_verification_acceptance import (
    test_plan_arguments_from_handoff,
    task_requires_pytest_verification,
)
from tools.ai.task_runtime import TaskStatus


def _tokens(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return list(dict.fromkeys(str(item or "").strip() for item in value if str(item or "").strip()))


def execute_verification_only_reentry(
    orchestrator: Any,
    reentry: Mapping[str, Any] | None,
    *,
    execute_action: Callable[[Any, str, Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one declared Verification action while preserving completed Task state.

    This is intentionally not retry, reopen, or recovery. The caller owns
    Acceptance re-evaluation after an action succeeds.
    """
    context = reentry if isinstance(reentry, Mapping) else {}
    if str(context.get("status") or "") != "VERIFICATION_REENTRY_CONTEXT_READY":
        return {"status": "VERIFICATION_REENTRY_UNRESOLVED", "reason": "reentry_not_ready"}
    runtime = getattr(orchestrator, "runtime", None)
    sandbox = getattr(runtime, "sandbox_session", None)
    if runtime is None or sandbox is None or str(getattr(sandbox, "status", "") or "") != "ACTIVE":
        return {"status": "VERIFICATION_REENTRY_UNRESOLVED", "reason": "active_sandbox_required"}
    entries = context.get("verification_reentry")
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], Mapping):
        return {"status": "VERIFICATION_REENTRY_UNRESOLVED", "reason": "single_reentry_target_required"}
    entry = entries[0]
    task_ids = _tokens(entry.get("runtime_task_ids"))
    source_ids = _tokens(entry.get("source_task_ids"))
    if len(task_ids) != 1 or len(source_ids) != 1:
        return {"status": "VERIFICATION_REENTRY_UNRESOLVED", "reason": "single_runtime_task_required"}
    task = (getattr(runtime, "tasks", None) or {}).get(task_ids[0])
    if (
        task is None
        or str(getattr(task, "source_task_id", "") or "") != source_ids[0]
        or str(getattr(task, "status", "") or "") != TaskStatus.COMPLETE.value
    ):
        return {"status": "VERIFICATION_REENTRY_UNRESOLVED", "reason": "completed_target_task_identity_mismatch"}
    if not task_requires_pytest_verification(orchestrator, task):
        return {"status": "VERIFICATION_REENTRY_UNRESOLVED", "reason": "verification_action_unavailable"}
    arguments = test_plan_arguments_from_handoff(orchestrator)
    if arguments is None:
        return {"status": "VERIFICATION_REENTRY_UNRESOLVED", "reason": "verification_plan_unavailable"}
    before_status = str(getattr(task, "status", "") or "")
    before_action_ids = [str(getattr(item, "action_id", "") or "") for item in runtime.actions]
    before_evidence_ids = list((getattr(runtime, "evidence", None) or {}).keys())
    runner = execute_action or (
        lambda current, task_id, args: current.execute_test_plan_action(
            args,
            relevant_tools=["run_test_plan"],
            verification_only_task_id=task_id,
        )
    )
    result = dict(runner(orchestrator, task_ids[0], arguments) or {})
    if str(getattr(task, "status", "") or "") != before_status:
        raise RuntimeError("verification_only_task_state_changed")
    action_ids = [str(getattr(item, "action_id", "") or "") for item in runtime.actions]
    evidence_ids = list((getattr(runtime, "evidence", None) or {}).keys())
    new_actions = [item for item in action_ids if item not in before_action_ids]
    new_evidence = [item for item in evidence_ids if item not in before_evidence_ids]
    if str(result.get("status") or "") not in {"success", "partial"}:
        return {
            "status": "VERIFICATION_EXECUTION_FAILED",
            "runtime_task_id": task_ids[0],
            "result": result,
            "new_action_ids": new_actions,
            "new_evidence_ids": new_evidence,
        }
    if not new_actions or not new_evidence:
        return {
            "status": "VERIFICATION_EXECUTION_UNRESOLVED",
            "reason": "verification_result_not_recorded",
            "runtime_task_id": task_ids[0],
        }
    return {
        "status": "VERIFICATION_EXECUTED",
        "runtime_task_id": task_ids[0],
        "source_task_id": source_ids[0],
        "result": result,
        "new_action_ids": new_actions,
        "new_evidence_ids": new_evidence,
    }


__all__ = ["execute_verification_only_reentry"]
