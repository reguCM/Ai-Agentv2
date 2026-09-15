"""Minimal Production bridge: Handoff verification → run_test_plan → Goal Acceptance.

Does not replace Runtime Task/Goal evaluation. Does not treat pytest PASS or
all-tasks-complete as Goal Acceptance PASS.
"""
from __future__ import annotations

import sys
from typing import Any, Mapping

from ai_tool.acceptance_meaning_audit import build_acceptance_meaning_audit
from ai_tool.evidence_requirement_trace import (
    EvidenceRequirementTraceError,
    trace_evidence_requirement_identity,
)
from ai_tool.goal_acceptance_eval import evaluate_goal_acceptance_from_facts
from tools.ai.task_runtime import AUTHORITATIVE_CERTAINTIES, GoalStatus, TaskStatus

HANDOFF_TASK_SOURCE = "goal_handoff"

TEST_RUN_CLOSED = "test_run_closed"
_OBSERVATION_MARKERS = (
    "list_files",
    "sandbox",
    "exists",
    "create_file succeeds",
    "read_file",
)
_PYTEST_MARKERS = ("pytest", "runnable", "starts", "起動")


def attach_handoff_verification_plan(
    orchestrator: Any,
    handoff_packet: Mapping[str, Any],
) -> None:
    plan = handoff_packet.get("test_plan")
    orchestrator.handoff_test_plan = dict(plan) if isinstance(plan, Mapping) else {}


def handoff_pytest_targets(orchestrator: Any) -> list[str]:
    plan = getattr(orchestrator, "handoff_test_plan", None) or {}
    return [str(item).strip() for item in (plan.get("pytest") or []) if str(item).strip()]


def _verification_texts_for_task(orchestrator: Any, task: Any) -> list[str]:
    texts = [str(item) for item in (getattr(task, "completion_conditions", None) or [])]
    task_id = str(getattr(task, "task_id", "") or "")
    source_id = str(getattr(task, "source_task_id", "") or "")
    mapped: list[str] = []
    for item in getattr(orchestrator, "handoff_task_acceptance_mapping", None) or []:
        runtime_id = str(item.get("runtime_task_id") or "")
        source = str(item.get("source_task_id") or "")
        if runtime_id != task_id and source != source_id:
            continue
        mapped.extend(str(token).strip() for token in (item.get("maps_to_acceptance") or []) if str(token).strip())
    projection = getattr(orchestrator, "handoff_acceptance_projection", None) or []
    for row in projection:
        acceptance_id = str(row.get("acceptance_id") or "")
        if acceptance_id in mapped:
            texts.append(str(row.get("verification") or ""))
    return texts


def task_requires_pytest_verification(orchestrator: Any, task: Any) -> bool:
    targets = handoff_pytest_targets(orchestrator)
    if not targets:
        return False
    blob = " ".join(_verification_texts_for_task(orchestrator, task)).casefold()
    if any(marker in blob for marker in _PYTEST_MARKERS):
        return True
    if any(target.casefold() in blob for target in targets):
        return True
    if blob and not any(marker in blob for marker in _OBSERVATION_MARKERS):
        return True
    return False


def task_row_requires_pytest_verification(
    row: Mapping[str, Any],
    handoff_packet: Mapping[str, Any],
) -> bool:
    plan = handoff_packet.get("test_plan") if isinstance(handoff_packet.get("test_plan"), Mapping) else {}
    targets = [str(item).strip() for item in (plan.get("pytest") or []) if str(item).strip()]
    if not targets:
        return False
    texts = [str(item) for item in (row.get("verification") or [])]
    texts.extend(str(item) for item in (row.get("acceptance") or []))
    mapped = {str(item).strip() for item in (row.get("maps_to_acceptance") or []) if str(item).strip()}
    for acc in handoff_packet.get("acceptance_criteria") or []:
        if not isinstance(acc, Mapping):
            continue
        if str(acc.get("id") or "") in mapped:
            texts.append(str(acc.get("verification") or ""))
    blob = " ".join(texts).casefold()
    if any(marker in blob for marker in _PYTEST_MARKERS):
        return True
    if any(target.casefold() in blob for target in targets):
        return True
    if blob and not any(marker in blob for marker in _OBSERVATION_MARKERS):
        return True
    return False


def maybe_add_test_run_closed(conditions: list[str], *, required: bool) -> list[str]:
    if not required or TEST_RUN_CLOSED in conditions:
        return conditions
    return [*conditions, TEST_RUN_CLOSED]


def test_plan_arguments_from_handoff(orchestrator: Any) -> dict[str, Any] | None:
    targets = handoff_pytest_targets(orchestrator)
    if not targets:
        return None
    commands = [f"{sys.executable} -m pytest {target}" for target in targets]
    plan_id = str((getattr(orchestrator, "handoff_test_plan", None) or {}).get("plan_id") or "handoff-verification")
    return {
        "test_plan": {
            "plan_id": plan_id,
            "commands": commands,
            "declared_primary_risk_level": "LEVEL_1",
            "declared_dimensions": {
                "llm": "NONE",
                "gpu": "NONE",
                "network": "NONE",
                "subprocess": "CONTROLLED",
            },
        }
    }


def _latest_pytest_failure(orchestrator: Any) -> Any | None:
    failures = list(getattr(getattr(orchestrator, "runtime", None), "failures", None) or [])
    for item in reversed(failures):
        if str(getattr(item, "failure_code", "") or "") == "pytest_failed":
            return item
    return None


def _successful_mutation_after_failure(orchestrator: Any, failure: Any) -> bool:
    """True when a later create_file/edit_file success exists after pytest_failed.

    FailureRecord.action_id is often absent from the action log (the failed
    run_test_plan may only be recorded as FailureRecord). Compare created_at.
    """
    after = str(getattr(failure, "created_at", "") or "")
    failed_action_id = str(getattr(failure, "action_id", "") or "")
    for item in list(getattr(getattr(orchestrator, "runtime", None), "actions", None) or []):
        if str(getattr(item, "tool_name", "") or "") not in {"create_file", "edit_file"}:
            continue
        if str(getattr(item, "result_status", "") or "") != "success":
            continue
        if failed_action_id and str(getattr(item, "action_id", "") or "") == failed_action_id:
            continue
        created = str(getattr(item, "created_at", "") or "")
        if not after or created >= after:
            return True
    for item in list(getattr(getattr(orchestrator, "runtime", None), "mutations", None) or []):
        stamp = str(getattr(item, "timestamp", "") or "")
        if not after or stamp >= after:
            return True
    return False


def _latest_pytest_failure_action_id(orchestrator: Any) -> str | None:
    failure = _latest_pytest_failure(orchestrator)
    if failure is None:
        return None
    return str(getattr(failure, "action_id", "") or "") or None


def closed_test_evidence_present(orchestrator: Any) -> bool:
    evidence = getattr(getattr(orchestrator, "runtime", None), "evidence", None) or {}
    for item in evidence.values():
        if str(getattr(item, "tool_name", "") or "") != "run_test_plan":
            continue
        supported = list(getattr(item, "supported_completion_conditions", None) or [])
        if TEST_RUN_CLOSED in supported:
            return True
    return False


def pending_verification_action(orchestrator: Any) -> dict[str, Any] | None:
    """Inject run_test_plan only when the current Handoff task requires it."""
    task = getattr(orchestrator, "task", None)
    if task is None or str(getattr(task, "source", "") or "") != HANDOFF_TASK_SOURCE:
        return None
    if str(getattr(task, "status", "") or "") == TaskStatus.COMPLETE.value:
        return None
    if not task_requires_pytest_verification(orchestrator, task):
        return None
    if closed_test_evidence_present(orchestrator):
        return None
    failure = _latest_pytest_failure(orchestrator)
    if failure is not None and not _successful_mutation_after_failure(orchestrator, failure):
        return None
    arguments = test_plan_arguments_from_handoff(orchestrator)
    if arguments is None:
        return None
    return {"tool": "run_test_plan", "arguments": arguments}


def advance_runnable_handoff_task(orchestrator: Any) -> str | None:
    from ai_tool.task_execution_guard import task_execution_blocked

    runtime = getattr(orchestrator, "runtime", None)
    tasks = getattr(runtime, "tasks", None) or {}
    current = tasks.get(getattr(orchestrator, "current_task_id", None))
    if current is None or str(getattr(current, "source", "") or "") != HANDOFF_TASK_SOURCE:
        return None
    if str(getattr(current, "status", "") or "") != TaskStatus.COMPLETE.value:
        return None
    for task in tasks.values():
        if str(getattr(task, "source", "") or "") != HANDOFF_TASK_SOURCE:
            continue
        if str(getattr(task, "status", "") or "") in {
            TaskStatus.COMPLETE.value,
            TaskStatus.CANCELLED.value,
        }:
            continue
        if task_execution_blocked(task):
            continue
        deps = list(getattr(task, "depends_on", None) or [])
        if all(
            dep in tasks and str(getattr(tasks[dep], "status", "") or "") == TaskStatus.COMPLETE.value
            for dep in deps
        ):
            orchestrator.current_task_id = task.task_id
            orchestrator.current_goal_id = task.goal_id
            if str(getattr(task, "status", "") or "") == TaskStatus.PENDING.value:
                task.status = TaskStatus.IN_PROGRESS.value
            return task.task_id
    return None


def assess_handoff_acceptance_readiness(orchestrator: Any) -> dict[str, Any]:
    """Report whether Goal Acceptance may start, without running Acceptance."""
    runtime = getattr(orchestrator, "runtime", None)
    tasks = getattr(runtime, "tasks", None) or {}
    required_tasks = [
        task
        for task in tasks.values()
        if str(getattr(task, "source", "") or "") == HANDOFF_TASK_SOURCE
    ]
    incomplete_task_ids = [
        str(task.task_id)
        for task in required_tasks
        if str(getattr(task, "status", "") or "") != TaskStatus.COMPLETE.value
    ]

    missing_evidence: list[dict[str, str]] = []
    evidence = getattr(runtime, "evidence", None) or {}
    for task in required_tasks:
        for condition in list(getattr(task, "completion_conditions", None) or []):
            refs = list((getattr(task, "condition_evidence", None) or {}).get(condition) or [])
            authoritative = any(
                evidence_id in evidence
                and bool(getattr(evidence[evidence_id], "verified", False))
                and str(getattr(evidence[evidence_id], "certainty", "") or "")
                in AUTHORITATIVE_CERTAINTIES
                and condition
                in list(
                    getattr(
                        evidence[evidence_id], "supported_completion_conditions", None
                    )
                    or []
                )
                for evidence_id in refs
            )
            if not authoritative:
                missing_evidence.append(
                    {"task_id": str(task.task_id), "condition": str(condition)}
                )

    unresolved_failure_ids: list[str] = []
    actions = list(getattr(runtime, "actions", None) or [])
    for failure in list(getattr(runtime, "failures", None) or []):
        failure_time = str(getattr(failure, "created_at", "") or "")
        failure_action_id = str(getattr(failure, "action_id", "") or "")
        failure_tool = str(getattr(failure, "tool_name", "") or "")
        resolved = any(
            str(getattr(action, "task_id", "") or "")
            == str(getattr(failure, "task_id", "") or "")
            and (not failure_tool or str(getattr(action, "tool_name", "") or "") == failure_tool)
            and str(getattr(action, "action_id", "") or "") != failure_action_id
            and str(getattr(action, "result_status", "") or "") == "success"
            and (
                not failure_time
                or str(getattr(action, "created_at", "") or "") >= failure_time
            )
            for action in actions
        )
        if not resolved:
            unresolved_failure_ids.append(str(getattr(failure, "failure_id", "") or ""))

    acceptance_ready = bool(required_tasks) and not (
        incomplete_task_ids or unresolved_failure_ids or missing_evidence
    )
    return {
        "acceptance_ready": acceptance_ready,
        "required_task_ids": [str(task.task_id) for task in required_tasks],
        "incomplete_task_ids": incomplete_task_ids,
        "unresolved_failure_ids": unresolved_failure_ids,
        "missing_evidence": missing_evidence,
    }


def pytest_failed_repair_hint(orchestrator: Any) -> str | None:
    if _latest_pytest_failure_action_id(orchestrator) is None:
        return None
    if closed_test_evidence_present(orchestrator):
        return None
    return (
        "Verification failed. Repair the failing artifact, then re-run the same Handoff test_plan. "
        "Do not mark the Goal accepted."
    )


def _mapped_tasks_complete(orchestrator: Any, acceptance_id: str) -> bool | None:
    tasks = getattr(getattr(orchestrator, "runtime", None), "tasks", None) or {}
    trace_fn = getattr(orchestrator, "handoff_acceptance_runtime_trace", None)
    trace = list(trace_fn()) if callable(trace_fn) else []
    mapped_ids = [
        str(item.get("runtime_task_id") or "")
        for row in trace
        if str(row.get("acceptance_id") or "") == acceptance_id
        for item in (row.get("mapped_runtime_tasks") or [])
        if isinstance(item, Mapping)
    ]
    mapped_ids = [item for item in mapped_ids if item]
    if not mapped_ids:
        return None
    return all(
        task_id in tasks and str(getattr(tasks[task_id], "status", "") or "") == TaskStatus.COMPLETE.value
        for task_id in mapped_ids
    )


def handoff_acceptance_extra_failures(orchestrator: Any) -> list[tuple[str, str, str]]:
    failures: list[tuple[str, str, str]] = []
    projection = list(getattr(orchestrator, "handoff_acceptance_projection", None) or [])
    pytest_needed = bool(handoff_pytest_targets(orchestrator)) and any(
        task_requires_pytest_verification(orchestrator, task)
        for task in (getattr(getattr(orchestrator, "runtime", None), "tasks", None) or {}).values()
    )
    if pytest_needed and not closed_test_evidence_present(orchestrator):
        failures.append(
            ("EVIDENCE", "Evidence", "required verification Evidence from run_test_plan is missing")
        )
    for row in projection:
        acceptance_id = str(row.get("acceptance_id") or "")
        mapped = _mapped_tasks_complete(orchestrator, acceptance_id)
        if mapped is False:
            failures.append(
                (
                    "TASK_COMPLETION",
                    "Task State",
                    f"acceptance {acceptance_id} mapped tasks are incomplete",
                )
            )
    return failures


def _criterion_expected_requirement_ids(
    handoff_packet: Mapping[str, Any], acceptance_id: str
) -> list[str]:
    """Read Requirement references declared for one existing Acceptance id."""
    result: list[str] = []
    for row in handoff_packet.get("requirement_bindings") or []:
        if not isinstance(row, Mapping):
            continue
        if acceptance_id not in [
            str(item).strip() for item in (row.get("acceptance_ids") or []) if str(item).strip()
        ]:
            continue
        requirement_id = str(row.get("requirement_id") or "").strip()
        if requirement_id and requirement_id not in result:
            result.append(requirement_id)
    return result


def _criterion_evidence_ids(orchestrator: Any, criterion: Mapping[str, Any]) -> list[str]:
    """Read Evidence actually attached to mapped Runtime Task conditions."""
    tasks = getattr(getattr(orchestrator, "runtime", None), "tasks", None) or {}
    result: list[str] = []
    for mapped in criterion.get("mapped_runtime_tasks") or []:
        if not isinstance(mapped, Mapping):
            continue
        task = tasks.get(str(mapped.get("runtime_task_id") or ""))
        if task is None:
            continue
        for evidence_ids in (getattr(task, "condition_evidence", None) or {}).values():
            for evidence_id in evidence_ids or []:
                token = str(evidence_id or "").strip()
                if token and token not in result:
                    result.append(token)
    return result


def build_handoff_acceptance_evidence_requirement_trace(
    orchestrator: Any,
    *,
    handoff_packet: Mapping[str, Any],
    mission: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Enrich criterion explanation only; never influence Acceptance judgment."""
    trace_fn = getattr(orchestrator, "handoff_acceptance_runtime_trace", None)
    criteria = list(trace_fn()) if callable(trace_fn) else []
    enriched: list[dict[str, Any]] = []
    for criterion in criteria:
        row = dict(criterion)
        acceptance_id = str(row.get("acceptance_id") or "").strip()
        expected_requirement_ids = _criterion_expected_requirement_ids(handoff_packet, acceptance_id)
        evidence_rows: list[dict[str, Any]] = []
        derived_requirement_ids: list[str] = []
        alignments: list[str] = []
        for evidence_id in _criterion_evidence_ids(orchestrator, row):
            try:
                evidence_trace = trace_evidence_requirement_identity(
                    evidence_id,
                    runtime=getattr(orchestrator, "runtime", None),
                    handoff_packet=handoff_packet,
                    mission=mission,
                )
            except EvidenceRequirementTraceError as exc:
                evidence_rows.append(
                    {"evidence_id": evidence_id, "alignment": "UNTRACEABLE", "error": str(exc)}
                )
                alignments.append("UNTRACEABLE")
                continue
            reverse_acceptance_ids = list(evidence_trace.get("acceptance_ids") or [])
            evidence_requirement_ids = list(evidence_trace.get("requirement_ids") or [])
            for requirement_id in evidence_requirement_ids:
                if requirement_id not in derived_requirement_ids:
                    derived_requirement_ids.append(requirement_id)
            if acceptance_id not in reverse_acceptance_ids:
                alignment = "MISMATCH"
            elif set(evidence_requirement_ids) == set(expected_requirement_ids):
                alignment = "MATCH"
            elif set(evidence_requirement_ids) & set(expected_requirement_ids):
                alignment = "PARTIAL"
            else:
                alignment = "MISMATCH"
            evidence_rows.append(
                {"evidence_id": evidence_id, "alignment": alignment, "trace": evidence_trace}
            )
            alignments.append(alignment)

        if not expected_requirement_ids or not evidence_rows or "UNTRACEABLE" in alignments:
            coverage = "UNTRACEABLE"
        elif set(derived_requirement_ids) == set(expected_requirement_ids):
            coverage = "MATCH"
        elif set(derived_requirement_ids) & set(expected_requirement_ids):
            coverage = "PARTIAL"
        else:
            coverage = "MISMATCH"
        row["evidence_requirement_trace"] = {
            "expected_requirement_ids": expected_requirement_ids,
            "evidence": evidence_rows,
            "coverage": coverage,
        }
        enriched.append(row)
    return enriched


def evaluate_handoff_goal_acceptance(
    orchestrator: Any,
    *,
    final_answer: str = "",
    llm_response_received: bool | None = None,
    handoff_packet: Mapping[str, Any] | None = None,
    mission: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Runtime Goal Acceptance. Does not require Runtime G1 complete (avoids deadlock)."""
    runtime = getattr(orchestrator, "runtime", None)
    tasks = getattr(runtime, "tasks", None) or {}
    evidence = getattr(runtime, "evidence", None) or {}
    actions = list(getattr(runtime, "actions", None) or [])
    extra = handoff_acceptance_extra_failures(orchestrator)
    facts = {
        "prompt": getattr(orchestrator, "request", ""),
        "tool_required": False,
        "evidence_required": True,
        "task_completion_required": False,
        "goal_completion_required": False,
        "final_answer_required": True,
        "llm_response_required": llm_response_received is not None,
        "llm_response_received": bool(llm_response_received),
        "evidence_count": len(evidence),
        "final_task_statuses": {
            task_id: str(getattr(task, "status", "") or "") for task_id, task in tasks.items()
        },
        "final_answer": final_answer,
        "tool_executions": [
            {"name": getattr(item, "tool_name", ""), "status": getattr(item, "result_status", "")}
            for item in actions
        ],
        "extra_failures": extra,
    }
    result = evaluate_goal_acceptance_from_facts(facts)
    if isinstance(handoff_packet, Mapping) and isinstance(mission, Mapping):
        result["criterion_trace"] = build_handoff_acceptance_evidence_requirement_trace(
            orchestrator, handoff_packet=handoff_packet, mission=mission
        )
    else:
        trace_fn = getattr(orchestrator, "handoff_acceptance_runtime_trace", None)
        result["criterion_trace"] = list(trace_fn()) if callable(trace_fn) else []
    if isinstance(handoff_packet, Mapping) and isinstance(mission, Mapping):
        # Derived audit only. It must not participate in Acceptance judgment.
        result["meaning_trace_audit"] = build_acceptance_meaning_audit(result)
    result["verification_closed"] = closed_test_evidence_present(orchestrator)
    return result


def apply_acceptance_pass_to_runtime_goal(
    orchestrator: Any,
    acceptance: Mapping[str, Any],
    *,
    completion_eligibility: Mapping[str, Any] | None = None,
) -> bool:
    if str(acceptance.get("status") or "") != "PASS":
        return False
    if completion_eligibility is not None and not bool(
        completion_eligibility.get("completion_eligible")
    ):
        return False
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return False
    goal = runtime.goals.get("G1")
    if goal is None:
        return False
    runtime.evaluate_goal("G1", list(goal.completion_conditions))
    return str(getattr(goal, "status", "") or "") == GoalStatus.COMPLETE.value


def resolve_mission_achievement(
    orchestrator: Any,
    *,
    final_answer: str = "",
    llm_response_received: bool | None = None,
) -> dict[str, Any] | None:
    """Single Mission writer helper. None means leave persist defaults (not performed)."""
    tasks = getattr(getattr(orchestrator, "runtime", None), "tasks", None) or {}
    if not any(str(getattr(task, "source", "") or "") == HANDOFF_TASK_SOURCE for task in tasks.values()):
        return None
    acceptance = evaluate_handoff_goal_acceptance(
        orchestrator,
        final_answer=final_answer,
        llm_response_received=llm_response_received,
    )
    if acceptance.get("status") != "PASS":
        return {"acceptance": acceptance}
    apply_acceptance_pass_to_runtime_goal(orchestrator, acceptance)
    return {
        "acceptance": acceptance,
        "goal_achievement_performed": True,
        "execution_end_state": "achieved",
        "goal_achievement_result": "PASS",
    }


__all__ = [
    "TEST_RUN_CLOSED",
    "advance_runnable_handoff_task",
    "assess_handoff_acceptance_readiness",
    "build_handoff_acceptance_evidence_requirement_trace",
    "apply_acceptance_pass_to_runtime_goal",
    "attach_handoff_verification_plan",
    "closed_test_evidence_present",
    "evaluate_handoff_goal_acceptance",
    "maybe_add_test_run_closed",
    "pending_verification_action",
    "pytest_failed_repair_hint",
    "resolve_mission_achievement",
    "task_requires_pytest_verification",
    "task_row_requires_pytest_verification",
    "test_plan_arguments_from_handoff",
]
