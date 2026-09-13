"""P2-16.5 observable single-run recorder and bounded small batch runner."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Iterable, Mapping
import uuid

from ai_tool.run_human_summary import build_human_summary, human_summary_markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_REGISTRY = REPO_ROOT / "registry" / "agent_test_cases.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "runs" / "agent_tests"
ALLOWED_RUN_COUNTS = {1, 5, 10}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_test_cases(path: Path = CASE_REGISTRY) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError("test case registry must contain a cases array")
    return [dict(item) for item in cases if isinstance(item, dict)]


def get_test_case(test_case_id: str, path: Path = CASE_REGISTRY) -> dict[str, Any]:
    for item in load_test_cases(path):
        if item.get("test_case_id") == test_case_id:
            return item
    raise KeyError(f"unknown test case: {test_case_id}")


def _git_metadata(root: Path = REPO_ROOT) -> dict[str, Any]:
    safe = str(root).replace("\\", "/")

    def read(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-c", f"safe.directory={safe}", *args],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None

    status = read("status", "--porcelain")
    return {
        "branch": read("branch", "--show-current"),
        "commit_sha": read("rev-parse", "HEAD"),
        "dirty": None if status is None else bool(status),
    }


def _failure_signature(action: Mapping[str, Any]) -> str | None:
    if action.get("result_status") != "failure":
        return None
    arguments = json.dumps(action.get("arguments") or {}, sort_keys=True, ensure_ascii=False)
    return f"{action.get('tool_name')}:{arguments}"


def evaluate_goal_acceptance(
    test_case: Mapping[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate observed run facts without asking the LLM to grade itself."""
    expected = dict(test_case.get("expected") or {})
    expected_tool = str(expected.get("expected_tool") or "").strip() or None
    tool_required = bool(expected.get("tool_required") or expected_tool)
    evidence_required = bool(expected.get("evidence_required"))
    tasks_required = bool(expected.get("task_completion_required"))
    goal_required = bool(expected.get("goal_completion_required"))
    answer_required = bool(expected.get("final_answer_required", True))

    prompt = str(record.get("prompt") or "").strip()
    lifecycle = dict(record.get("final_llm_lifecycle") or {})
    tools = dict(record.get("tool") or {})
    tool_rows = list(record.get("tool_executions") or [])
    evidence = dict(record.get("evidence") or {})
    goal = dict(record.get("goal") or {})
    output = dict(record.get("output") or {})
    diagnostics = dict(record.get("execution_diagnostics") or {})
    status_report = dict(record.get("runtime_status_report") or {})

    selected_names = [str(item) for item in tools.get("tool_sequence") or []]
    matching_rows = [
        row for row in tool_rows
        if isinstance(row, Mapping) and (expected_tool is None or row.get("name") == expected_tool)
    ]
    required_tool_selected = (
        (expected_tool in selected_names if expected_tool else bool(selected_names))
        if tool_required else None
    )
    required_tool_executed = bool(matching_rows) if tool_required else None
    tool_result_returned = (
        any(row.get("status") in {"success", "partial", "failure"} for row in matching_rows)
        if tool_required else None
    )
    tool_succeeded = (
        any(row.get("status") == "success" for row in matching_rows)
        if tool_required else True
    )
    evidence_available = (
        int(evidence.get("evidence_count") or 0) > 0 if evidence_required else None
    )
    task_statuses = dict((record.get("completion_coverage") or {}).get("final_task_statuses") or {})
    required_tasks_complete = (
        bool(task_statuses) and all(value == "complete" for value in task_statuses.values())
        if tasks_required else None
    )
    final_goal_complete = (
        goal.get("final_goal_status") == "complete" if goal_required else None
    )
    final_answer_present = bool(str(output.get("final_answer") or "").strip())
    llm_response_received = bool(lifecycle.get("final_llm_response_received"))

    exception_text = " ".join(
        str(value or "")
        for value in (
            diagnostics.get("exception_type"),
            diagnostics.get("exception_message"),
            record.get("error"),
        )
    ).casefold()
    environment_blocked = (
        diagnostics.get("provider_reachable") is False
        or diagnostics.get("model_available") is False
        or diagnostics.get("communication_status") == "FAILED"
        or any(token in exception_text for token in ("ollama", "model_missing", "connection refused"))
    )
    runtime_blocked = status_report.get("status") == "BLOCKED"

    checks = [
        (not prompt, "INPUT", "Requirement / Intent", "user goal is not recorded"),
        (not llm_response_received, "LLM", "Model Behavior", "final LLM response was not observed"),
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


def record_run(
    test_case: Mapping[str, Any],
    turn: Mapping[str, Any],
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
    git_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    task_runtime = turn.get("task_runtime") or {}
    goals = list(task_runtime.get("goals") or [])
    tasks = list(task_runtime.get("tasks") or [])
    actions = list(task_runtime.get("actions") or [])
    evidence = list(task_runtime.get("evidence") or [])
    failures = list(task_runtime.get("failures") or [])
    events = list(task_runtime.get("events") or [])
    tools = list(turn.get("tools") or [])
    final_answer = str(turn.get("answer") or "")
    lifecycle = dict(turn.get("final_llm_lifecycle") or {})
    runtime_status_report = dict(turn.get("runtime_status_report") or {})
    agent_turn_timing = dict(turn.get("timing_breakdown") or {})
    tool_expectation = dict(task_runtime.get("tool_expectation") or {})
    local_reviews = list(task_runtime.get("local_reviews") or [])
    signatures = [item for item in (_failure_signature(row) for row in actions) if item]
    repeated_action_count = sum(count - 1 for count in Counter(signatures).values() if count > 1)
    rejected = sum(1 for row in actions if row.get("relevance") == "REJECT_ACTION_RESULT")
    final_goal = next((row for row in goals if not row.get("parent_goal_id")), None)
    unresolved = [row for row in tasks if row.get("status") != "complete"]
    completed = [row for row in tasks if row.get("status") == "complete"]
    completion_conditions = [
        {
            "task_id": row.get("task_id"),
            "condition": condition,
            "status": (row.get("condition_status") or {}).get(condition, "UNKNOWN"),
            "supporting_evidence": list(
                (row.get("condition_evidence") or {}).get(condition) or []
            ),
        }
        for row in tasks
        for condition in (row.get("completion_conditions") or [])
    ]
    statuses = Counter(str(row.get("status") or "failure") for row in tools)
    event_types = Counter(str(row.get("type") or "") for row in events)
    progress = Counter(str(row.get("progress_state") or "") for row in tasks)
    expected = test_case.get("expected") or {}
    tool_required = bool(expected.get("tool_required"))
    tool_usage = "PASS" if tools else ("FAIL" if tool_required else "NOT_REQUIRED")
    model_response_empty = bool(
        lifecycle.get("final_llm_response_empty")
        if lifecycle.get("final_llm_response_received")
        else not final_answer.strip()
    )
    empty_answer = "FAIL" if model_response_empty else "PASS"
    repeated_failure = "FAIL" if repeated_action_count else "PASS"
    inconsistent = bool(final_goal and final_goal.get("status") == "complete" and unresolved)
    if not goals or not tasks:
        completion_consistency = "REVIEW"
    else:
        completion_consistency = "FAIL" if inconsistent else "PASS"
    evaluations = {
        "tool_usage": tool_usage,
        "empty_answer": empty_answer,
        "repeated_failure": repeated_failure,
        "completion_consistency": completion_consistency,
        "tool_result_contract": "PASS" if all(row.get("status") in {"success", "partial", "failure"} for row in tools) else "REVIEW",
        "long_running": "INFO",
        "evidence_coverage": "REVIEW_REQUIRED",
        "goal_decomposition_quality": "REVIEW_REQUIRED",
        "technical_quality": "REVIEW_REQUIRED",
    }
    record = {
        "schema_version": 1,
        "test_mode": True,
        "test_case_id": test_case.get("test_case_id"),
        "run_id": run_id,
        "timestamp": finished_at,
        "model": turn.get("model"),
        "session_id": turn.get("session_id"),
        "case_id": turn.get("case_id"),
        "correlation_id": turn.get("correlation_id"),
        "turn_id": turn.get("correlation_id"),
        "prompt": test_case.get("prompt"),
        "git": dict(git_metadata or _git_metadata()),
        "status": "cancelled" if turn.get("cancelled") else ("failed" if turn.get("is_error") else "completed"),
        "goal": {
            "final_goal": final_goal,
            "goal_count": len(goals),
            "task_count": len(tasks),
            "completed_task_count": len(completed),
            "unresolved_task_count": len(unresolved),
            "final_goal_status": final_goal.get("status") if final_goal else None,
        },
        "completion_coverage": {
            "completion_conditions": completion_conditions,
            "unresolved_conditions": [
                row for row in completion_conditions if row["status"] != "SATISFIED"
            ],
            "final_task_statuses": {
                str(row.get("task_id")): row.get("status") for row in tasks
            },
        },
        "requirement_decomposition": dict(turn.get("requirement_decomposition") or {}),
        "concept_resolution": dict(
            task_runtime.get("concept_resolution")
            or turn.get("concept_resolution")
            or {}
        ),
        "capability_resolution": list(task_runtime.get("capability_resolution") or []),
        "claims": list(task_runtime.get("claims") or []),
        "effective_claims": list(task_runtime.get("effective_claims") or []),
        "answer_gate": dict(turn.get("answer_gate") or {}),
        "tool_expectation": tool_expectation,
        "local_review": {
            "review_count": len(local_reviews),
            "iterations": local_reviews,
            "final_review_status": (
                local_reviews[-1].get("final_review_status") if local_reviews else None
            ),
            "accepted_new_task_count": sum(
                len(row.get("accepted_new_tasks") or []) for row in local_reviews
            ),
            "rejected_new_task_count": sum(
                len(row.get("rejected_new_tasks") or []) for row in local_reviews
            ),
        },
        "tool": {
            "tool_call_count": len(tools),
            "tool_sequence": [row.get("name") for row in tools],
            "tool_success_count": statuses["success"],
            "tool_partial_count": statuses["partial"],
            "tool_failure_count": statuses["failure"],
            "repeated_action_count": repeated_action_count,
        },
        "tool_executions": tools,
        "evidence": {
            "evidence_count": len(evidence),
            "evidence_ids": [row.get("evidence_id") for row in evidence],
            "evidence_summary": [row.get("summary") for row in evidence],
            "rejected_evidence_count": rejected,
            "final_synthesis_evidence_ids": [row.get("evidence_id") for row in evidence],
        },
        "runtime": {
            "progress_count": progress["progress"],
            "stagnation_count": progress["stagnation"] + event_types["STAGNATION_DETECTED"],
            "regression_count": progress["regression"],
            "recovery_count": event_types["RECOVERY_REQUESTED"],
            "replan_count": len(task_runtime.get("replans") or []),
            "tool_gap_count": len(task_runtime.get("tool_gaps") or []),
        },
        "timing": {
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "long_running_occurred": duration_ms >= 30_000
            or any(
                row.get("status") == "LONG_RUNNING" for row in turn.get("events") or []
            ),
            "agent_turn": agent_turn_timing,
        },
        "output": {
            "final_answer_empty": not bool(final_answer.strip()),
            "model_response_empty": model_response_empty,
            "final_answer_length": len(final_answer),
            "final_answer": final_answer,
        },
        "final_llm_lifecycle": lifecycle,
        "runtime_status_report": runtime_status_report,
        "execution_diagnostics": dict(turn.get("execution_diagnostics") or {}),
        "evaluations": evaluations,
        "failure_codes": [row.get("failure_code") for row in failures],
    }
    record["human_summary"] = build_human_summary(
        record, task_runtime=task_runtime, turn=turn
    )
    record["goal_acceptance"] = evaluate_goal_acceptance(test_case, record)
    return record


def run_markdown(record: Mapping[str, Any]) -> str:
    tool = record["tool"]
    goal = record["goal"]
    runtime = record["runtime"]
    evidence = record["evidence"]
    evaluation = record["evaluations"]
    lifecycle = record.get("final_llm_lifecycle") or {}
    status_report = record.get("runtime_status_report") or {}
    coverage = record.get("completion_coverage") or {}
    condition_lines = "\n".join(
        f"- [{row.get('status')}] {row.get('condition')} "
        f"(Evidence: {', '.join(row.get('supporting_evidence') or []) or 'None'})"
        for row in coverage.get("completion_conditions") or []
    ) or "None"
    sequence = "\n→ ".join(str(item) for item in tool["tool_sequence"]) or "None"
    technical = f"""# Test Run Report

Test Case: {record['test_case_id']}
Run: {record['run_id']}
Model: {record.get('model')}
Status: {record['status']}

## Run Summary

Duration: {record['timing']['duration_ms']} ms
Long Running: {record['timing']['long_running_occurred']}

## Agent Output

{record['output']['final_answer']}

## Goal / Task Status

Final Goal: {goal['final_goal_status']}
Goals: {goal['goal_count']}
Tasks: {goal['task_count']}
Completed: {goal['completed_task_count']}
Unresolved: {goal['unresolved_task_count']}

Completion Conditions:
{condition_lines}

Unresolved Conditions: {len(coverage.get('unresolved_conditions') or [])}

## Tool Sequence

Calls: {tool['tool_call_count']}

Sequence:
{sequence}

Success: {tool['tool_success_count']}
Partial: {tool['tool_partial_count']}
Failure: {tool['tool_failure_count']}

## Evidence

Evidence Count: {evidence['evidence_count']}
Rejected: {evidence['rejected_evidence_count']}
Evidence IDs: {', '.join(str(item) for item in evidence['evidence_ids']) or 'None'}

## Completion / Progress

Progress: {runtime['progress_count']}
Stagnation: {runtime['stagnation_count']}
Recovery: {runtime['recovery_count']}
Replan: {runtime['replan_count']}
Stop Reason: {status_report.get('reason_code') or 'None'}

## Final LLM Lifecycle

Request Started: {lifecycle.get('final_llm_request_started')}
Request Started At: {lifecycle.get('final_llm_request_started_at')}
Response Received: {lifecycle.get('final_llm_response_received')}
Response Received At: {lifecycle.get('final_llm_response_received_at')}
Response Length: {lifecycle.get('final_llm_response_length')}
Response Accepted: {lifecycle.get('final_response_accepted')}
Response Discarded: {lifecycle.get('final_response_discarded')}
Late Response: {lifecycle.get('late_response_received')}
Turn Closed Before Response: {lifecycle.get('turn_closed_before_response')}
Empty Reason: {lifecycle.get('empty_reason')}

## Automatic Evaluation

Tool Usage: {evaluation['tool_usage']}
Empty Answer: {evaluation['empty_answer']}
Repeated Failure: {evaluation['repeated_failure']}
Completion Consistency: {evaluation['completion_consistency']}

## Review Required

Evidence Coverage: {evaluation['evidence_coverage']}
Goal Decomposition Quality: {evaluation['goal_decomposition_quality']}
Technical Quality: {evaluation['technical_quality']}
"""
    return human_summary_markdown(record.get("human_summary") or {}) + "\n---\n\n" + technical


def aggregate_records(
    test_case: Mapping[str, Any], records: Iterable[Mapping[str, Any]], *, batch_id: str
) -> dict[str, Any]:
    rows = list(records)
    count = len(rows)
    eval_keys = ("tool_usage", "empty_answer", "repeated_failure", "completion_consistency", "evidence_coverage")
    rates = {
        key: dict(Counter(str(row["evaluations"].get(key)) for row in rows))
        for key in eval_keys
    }
    problems = Counter()
    for row in rows:
        if row["evaluations"]["completion_consistency"] == "FAIL":
            problems["Completion inconsistency"] += 1
        if row["evidence"]["evidence_count"] == 0:
            problems["Insufficient evidence"] += 1
        if row["evaluations"]["repeated_failure"] == "FAIL":
            problems["Repeated action"] += 1
        if row["evaluations"]["empty_answer"] == "FAIL":
            problems["Empty answer"] += 1
    distribution = Counter(str(row["tool"]["tool_call_count"]) for row in rows)
    lifecycle_rows = [row.get("final_llm_lifecycle") or {} for row in rows]
    return {
        "schema_version": 1,
        "batch_id": batch_id,
        "test_case_id": test_case.get("test_case_id"),
        "model": rows[0].get("model") if rows else None,
        "total_runs": count,
        "completed_runs": sum(row["status"] == "completed" for row in rows),
        "failed_runs": sum(row["status"] != "completed" for row in rows),
        "empty_answer_count": sum(
            row["output"].get("model_response_empty", row["output"]["final_answer_empty"])
            for row in rows
        ),
        "tool_used_runs": sum(row["tool"]["tool_call_count"] > 0 for row in rows),
        "average_tool_calls": round(sum(row["tool"]["tool_call_count"] for row in rows) / count, 2) if count else 0,
        "average_evidence_count": round(sum(row["evidence"]["evidence_count"] for row in rows) / count, 2) if count else 0,
        "completion_consistency_failures": rates["completion_consistency"].get("FAIL", 0),
        "stagnation_runs": sum(row["runtime"]["stagnation_count"] > 0 for row in rows),
        "recovery_runs": sum(row["runtime"]["recovery_count"] > 0 for row in rows),
        "replan_runs": sum(row["runtime"]["replan_count"] > 0 for row in rows),
        "long_running_runs": sum(row["timing"]["long_running_occurred"] for row in rows),
        "final_llm_lifecycle": {
            "model_returned_empty_count": sum(row.get("empty_reason") == "MODEL_RETURNED_EMPTY" for row in lifecycle_rows),
            "response_not_received_count": sum(not row.get("final_llm_response_received") for row in lifecycle_rows),
            "turn_closed_early_count": sum(bool(row.get("turn_closed_before_response")) for row in lifecycle_rows),
            "late_response_count": sum(bool(row.get("late_response_received")) for row in lifecycle_rows),
            "response_discarded_count": sum(bool(row.get("final_response_discarded")) for row in lifecycle_rows),
        },
        "evaluation_counts": rates,
        "tool_call_count_distribution": dict(distribution),
        "frequent_problems": [
            {"problem": name, "runs": occurrences}
            for name, occurrences in problems.most_common()
        ],
        "run_ids": [row["run_id"] for row in rows],
    }


def aggregate_markdown(aggregate: Mapping[str, Any]) -> str:
    total = aggregate["total_runs"]
    evaluation = aggregate["evaluation_counts"]
    lifecycle = aggregate["final_llm_lifecycle"]
    problem_lines = "\n".join(
        f"{index}. {row['problem']}: {row['runs']} / {total}"
        for index, row in enumerate(aggregate["frequent_problems"], 1)
    ) or "None"
    return f"""# Batch Evaluation Report

Test Case: {aggregate['test_case_id']}
Model: {aggregate.get('model')}
Runs: {total}

## Batch Summary

Completed: {aggregate['completed_runs']} / {total}
Failed: {aggregate['failed_runs']} / {total}
Empty Answer: {aggregate['empty_answer_count']} / {total}
Tool Used: {aggregate['tool_used_runs']} / {total}
Long Running: {aggregate['long_running_runs']} / {total}
Average Tool Calls: {aggregate['average_tool_calls']}
Average Evidence: {aggregate['average_evidence_count']}

## PASS / FAIL Summary

Tool Usage PASS: {evaluation['tool_usage'].get('PASS', 0)} / {total}
Empty Answer PASS: {evaluation['empty_answer'].get('PASS', 0)} / {total}
Repeated Failure PASS: {evaluation['repeated_failure'].get('PASS', 0)} / {total}
Completion Consistency FAIL: {evaluation['completion_consistency'].get('FAIL', 0)} / {total}
Evidence Coverage REVIEW_REQUIRED: {evaluation['evidence_coverage'].get('REVIEW_REQUIRED', 0)} / {total}

## Tool Usage Summary

Tool Used: {aggregate['tool_used_runs']} / {total}
Average Calls: {aggregate['average_tool_calls']}
Distribution: {json.dumps(aggregate['tool_call_count_distribution'], ensure_ascii=False)}

## Completion Summary

Completed Runs: {aggregate['completed_runs']} / {total}
Completion Consistency FAIL: {aggregate['completion_consistency_failures']} / {total}

## Final LLM Lifecycle Summary

Model Returned Empty: {lifecycle['model_returned_empty_count']} / {total}
Response Not Received: {lifecycle['response_not_received_count']} / {total}
Turn Closed Early: {lifecycle['turn_closed_early_count']} / {total}
Late Response: {lifecycle['late_response_count']} / {total}
Response Discarded: {lifecycle['response_discarded_count']} / {total}

## Frequent Problems

{problem_lines}

## Runs Requiring Review

Evidence Coverage: {evaluation['evidence_coverage'].get('REVIEW_REQUIRED', 0)} / {total}
"""


ProgressFn = Callable[[dict[str, Any]], None]
ExecuteFn = Callable[[dict[str, Any], str], Mapping[str, Any]]


def run_batch(
    test_case: Mapping[str, Any],
    runs: int,
    execute: ExecuteFn,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    progress: ProgressFn | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    if runs not in ALLOWED_RUN_COUNTS:
        raise ValueError("runs must be one of 1, 5, or 10")
    batch = batch_id or f"tb-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    directory = output_root / str(test_case["test_case_id"]) / batch
    directory.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    git = _git_metadata()
    for index in range(1, runs + 1):
        run_id = f"tr-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{index:03d}-{uuid.uuid4().hex[:4]}"
        if progress:
            progress({"status": "running", "current": index, "total": runs, "run_id": run_id})
        started = datetime.now(timezone.utc)
        try:
            turn = dict(execute(dict(test_case), run_id))
        except Exception as exc:  # one run must not abort the batch
            turn = {
                "is_error": True,
                "error": f"{type(exc).__name__}: {exc}",
                "answer": "",
                "model": None,
                "execution_diagnostics": {
                    "provider_reachable": "UNKNOWN",
                    "provider_ready": "UNKNOWN",
                    "model_busy": "UNKNOWN",
                    "model_selection_started": False,
                    "model_selected": None,
                    "model_available": "UNKNOWN",
                    "preflight_started": False,
                    "preflight_failed": False,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
            }
        finished = datetime.now(timezone.utc)
        record = record_run(
            test_case,
            turn,
            run_id=run_id,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_ms=max(0, int((finished - started).total_seconds() * 1000)),
            git_metadata=git,
        )
        records.append(record)
        run_dir = directory / run_id
        run_dir.mkdir()
        (run_dir / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown = run_markdown(record)
        (run_dir / "report.md").write_text(markdown, encoding="utf-8")
        if progress:
            progress({"status": record["status"], "current": index, "total": runs, "run_id": run_id})
    aggregate = aggregate_records(test_case, records, batch_id=batch)
    aggregate_md = aggregate_markdown(aggregate)
    (directory / "aggregate.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "aggregate.md").write_text(aggregate_md, encoding="utf-8")
    return {
        "batch_id": batch,
        "output_directory": str(directory.relative_to(REPO_ROOT)).replace("\\", "/") if directory.is_relative_to(REPO_ROOT) else str(directory),
        "aggregate": aggregate,
        "aggregate_markdown": aggregate_md,
        "runs": [
            {
                "record": row,
                "human_summary_markdown": human_summary_markdown(row.get("human_summary") or {}),
                "markdown": run_markdown(row),
                "report_path": f"{run_id}/report.md",
            }
            for row, run_id in zip(records, aggregate["run_ids"])
        ],
    }


__all__ = [
    "ALLOWED_RUN_COUNTS",
    "aggregate_markdown",
    "aggregate_records",
    "evaluate_goal_acceptance",
    "get_test_case",
    "load_test_cases",
    "record_run",
    "run_batch",
    "run_markdown",
    "human_summary_markdown",
]
