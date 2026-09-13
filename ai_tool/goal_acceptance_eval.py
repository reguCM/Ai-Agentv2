"""Shared Goal Acceptance checks. Status names stay PASS / FAIL / BLOCKED / ENVIRONMENT_BLOCKED."""
from __future__ import annotations

from typing import Any, Mapping


def evaluate_goal_acceptance_from_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Mechanical checks against observed facts. Does not ask an LLM to grade itself."""
    expected_tool = facts.get("expected_tool")
    expected_tool = str(expected_tool).strip() or None if expected_tool is not None else None
    tool_required = bool(facts.get("tool_required") or expected_tool)
    evidence_required = bool(facts.get("evidence_required"))
    tasks_required = bool(facts.get("task_completion_required"))
    goal_required = bool(facts.get("goal_completion_required"))
    answer_required = bool(facts.get("final_answer_required", True))
    llm_required = bool(facts.get("llm_response_required", True))

    prompt = str(facts.get("prompt") or "").strip()
    selected_names = [str(item) for item in facts.get("tool_sequence") or []]
    tool_rows = [row for row in (facts.get("tool_executions") or []) if isinstance(row, Mapping)]
    matching_rows = [
        row for row in tool_rows if expected_tool is None or row.get("name") == expected_tool
    ]
    required_tool_selected = (
        (expected_tool in selected_names if expected_tool else bool(selected_names))
        if tool_required
        else None
    )
    required_tool_executed = bool(matching_rows) if tool_required else None
    tool_result_returned = (
        any(row.get("status") in {"success", "partial", "failure"} for row in matching_rows)
        if tool_required
        else None
    )
    tool_succeeded = (
        any(row.get("status") == "success" for row in matching_rows) if tool_required else True
    )
    evidence_count = int(facts.get("evidence_count") or 0)
    evidence_available = evidence_count > 0 if evidence_required else None
    task_statuses = dict(facts.get("final_task_statuses") or {})
    required_tasks_complete = (
        bool(task_statuses) and all(value == "complete" for value in task_statuses.values())
        if tasks_required
        else None
    )
    final_goal_complete = (
        facts.get("final_goal_status") == "complete" if goal_required else None
    )
    final_answer_present = bool(str(facts.get("final_answer") or "").strip())
    llm_response_received = bool(facts.get("llm_response_received"))

    exception_text = " ".join(
        str(value or "")
        for value in (
            facts.get("exception_type"),
            facts.get("exception_message"),
            facts.get("error"),
        )
    ).casefold()
    environment_blocked = (
        facts.get("provider_reachable") is False
        or facts.get("model_available") is False
        or facts.get("communication_status") == "FAILED"
        or any(token in exception_text for token in ("ollama", "model_missing", "connection refused"))
    )
    runtime_blocked = facts.get("runtime_status") == "BLOCKED"

    extra_failures = [
        (str(row[0]), str(row[1]), str(row[2]))
        for row in (facts.get("extra_failures") or [])
        if isinstance(row, (list, tuple)) and len(row) >= 3
    ]

    checks = [
        (not prompt, "INPUT", "Requirement / Intent", "user goal is not recorded"),
        (
            llm_required and not llm_response_received,
            "LLM",
            "Model Behavior",
            "final LLM response was not observed",
        ),
        (tool_required and not required_tool_selected, "TOOL_SELECTION", "Tool Selection", "required tool was not selected"),
        (tool_required and not required_tool_executed, "TOOL_EXECUTION", "Tool Execution", "required tool was not executed"),
        (tool_required and not tool_result_returned, "TOOL_RESULT_BRIDGE", "Tool Result Bridge", "tool result was not returned to the Agent run"),
        (tool_required and not tool_succeeded, "TOOL_EXECUTION", "Tool Execution", "required tool did not return success"),
        (evidence_required and not evidence_available, "EVIDENCE", "Evidence", "required evidence is unavailable"),
        (tasks_required and not required_tasks_complete, "TASK_COMPLETION", "Task State", "required tasks are incomplete or unobservable"),
        (goal_required and not final_goal_complete, "GOAL_COMPLETION", "Completion", "final goal is incomplete or unobservable"),
        (answer_required and not final_answer_present, "FINALIZATION", "Finalization", "final answer is empty"),
    ]
    failures = [(stage, category, reason) for failed, stage, category, reason in checks if failed]
    failures.extend(extra_failures)
    if environment_blocked:
        status = "ENVIRONMENT_BLOCKED"
        failure_stage, failure_category = "ENVIRONMENT", "Environment"
    elif runtime_blocked:
        status = "BLOCKED"
        failure_stage, failure_category = (
            failures[0][:2] if failures else ("UNKNOWN", "Environment")
        )
    elif failures:
        status = "FAIL"
        failure_stage, failure_category = failures[0][:2]
    else:
        status = "PASS"
        failure_stage = failure_category = None
    return {
        "status": status,
        "user_goal_recorded": bool(prompt),
        "llm_response_received": llm_response_received,
        "required_tool_selected": required_tool_selected,
        "required_tool_executed": required_tool_executed,
        "tool_result_returned": tool_result_returned,
        "evidence_available": evidence_available,
        "required_tasks_complete": required_tasks_complete,
        "final_goal_complete": final_goal_complete,
        "final_answer_present": final_answer_present,
        "failure_stage": failure_stage,
        "failure_category": failure_category,
        "reasons": [item[2] for item in failures],
    }


def facts_from_test_record(
    test_case: Mapping[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    expected = dict(test_case.get("expected") or {})
    lifecycle = dict(record.get("final_llm_lifecycle") or {})
    tools = dict(record.get("tool") or {})
    evidence = dict(record.get("evidence") or {})
    goal = dict(record.get("goal") or {})
    output = dict(record.get("output") or {})
    diagnostics = dict(record.get("execution_diagnostics") or {})
    status_report = dict(record.get("runtime_status_report") or {})
    return {
        "expected_tool": expected.get("expected_tool"),
        "tool_required": bool(expected.get("tool_required") or expected.get("expected_tool")),
        "evidence_required": bool(expected.get("evidence_required")),
        "task_completion_required": bool(expected.get("task_completion_required")),
        "goal_completion_required": bool(expected.get("goal_completion_required")),
        "final_answer_required": bool(expected.get("final_answer_required", True)),
        "prompt": record.get("prompt"),
        "tool_sequence": tools.get("tool_sequence") or [],
        "tool_executions": list(record.get("tool_executions") or []),
        "evidence_count": evidence.get("evidence_count") or 0,
        "final_task_statuses": dict(
            (record.get("completion_coverage") or {}).get("final_task_statuses") or {}
        ),
        "final_goal_status": goal.get("final_goal_status"),
        "final_answer": output.get("final_answer"),
        "llm_response_received": lifecycle.get("final_llm_response_received"),
        "exception_type": diagnostics.get("exception_type"),
        "exception_message": diagnostics.get("exception_message"),
        "error": record.get("error"),
        "provider_reachable": diagnostics.get("provider_reachable"),
        "model_available": diagnostics.get("model_available"),
        "communication_status": diagnostics.get("communication_status"),
        "runtime_status": status_report.get("status"),
    }


def evaluate_goal_acceptance(
    test_case: Mapping[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Test-runner overlay. Production Chat does not call this with a test_case."""
    return evaluate_goal_acceptance_from_facts(facts_from_test_record(test_case, record))


__all__ = [
    "evaluate_goal_acceptance",
    "evaluate_goal_acceptance_from_facts",
    "facts_from_test_record",
]
