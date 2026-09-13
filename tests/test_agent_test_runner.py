import json

import pytest

from ai_tool.agent_test_runner import (
    aggregate_markdown,
    aggregate_records,
    evaluate_goal_acceptance,
    get_test_case,
    load_test_cases,
    record_run,
    run_batch,
    run_markdown,
)


def fake_turn(*, answer="plan", tool_status="success", final_status="complete"):
    return {
        "model": "gemma4:12b",
        "session_id": "session-1",
        "case_id": "case-1",
        "correlation_id": "correlation-1",
        "answer": answer,
        "final_llm_lifecycle": {
            "final_llm_request_started": True,
            "final_llm_response_received": True,
            "final_llm_response_length": len(answer),
            "final_llm_response_empty": not bool(answer),
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": "MODEL_RETURNED_EMPTY" if not answer else None,
        },
        "tools": [
            {
                "name": "read_file",
                "status": tool_status,
                "arguments": {"path": "docs/x"},
            }
        ],
        "events": [],
        "task_runtime": {
            "goals": [
                {
                    "goal_id": "G1",
                    "parent_goal_id": None,
                    "status": final_status,
                }
            ],
            "tasks": [
                {"task_id": "T1", "status": "complete", "progress_state": "progress"}
            ],
            "actions": [
                {
                    "action_id": "A1",
                    "tool_name": "read_file",
                    "arguments": {"path": "docs/x"},
                    "result_status": tool_status,
                    "relevance": "ACCEPT",
                }
            ],
            "evidence": [{"evidence_id": "E1", "summary": "contract"}],
            "failures": [],
            "replans": [],
            "tool_gaps": [],
            "events": [],
            "tool_expectation": {
                "generated": True,
                "required_capability": "workspace_file_read",
                "expected_tool": "read_file",
                "expected_arguments": {"path": "docs/x"},
                "level": "required",
                "actual_tool_called": "read_file",
                "expectation_matched": True,
            },
        },
    }


def make_record(**turn_changes):
    case = get_test_case("P216-GIT-PLAN")
    turn = fake_turn(**turn_changes)
    return record_run(
        case,
        turn,
        run_id="tr-1",
        started_at="2026-09-03T00:00:00Z",
        finished_at="2026-09-03T00:00:01Z",
        duration_ms=1000,
        git_metadata={"branch": "test", "commit_sha": "abc", "dirty": False},
    )


def acceptance_case():
    return {
        "test_case_id": "acceptance",
        "prompt": "observe time",
        "expected": {
            "expected_tool": "get_system_time",
            "tool_required": True,
            "evidence_required": True,
            "task_completion_required": True,
            "goal_completion_required": True,
            "final_answer_required": True,
        },
    }


def acceptance_record():
    return {
        "prompt": "observe time",
        "final_llm_lifecycle": {"final_llm_response_received": True},
        "tool": {"tool_sequence": ["get_system_time"]},
        "tool_executions": [{"name": "get_system_time", "status": "success"}],
        "evidence": {"evidence_count": 1},
        "goal": {"final_goal_status": "complete"},
        "completion_coverage": {"final_task_statuses": {"T1": "complete", "T2": "complete"}},
        "output": {"final_answer": "2026-09-05 JST"},
        "execution_diagnostics": {},
        "runtime_status_report": {},
    }


def test_goal_acceptance_all_required_facts_pass():
    assert evaluate_goal_acceptance(acceptance_case(), acceptance_record())["status"] == "PASS"


def test_goal_acceptance_incomplete_goal_fails_at_goal_completion():
    record = acceptance_record()
    record["goal"]["final_goal_status"] = "in_progress"
    result = evaluate_goal_acceptance(acceptance_case(), record)
    assert result["status"] == "FAIL"
    assert result["failure_stage"] == "GOAL_COMPLETION"


def test_goal_acceptance_empty_answer_fails_at_finalization():
    record = acceptance_record()
    record["output"]["final_answer"] = ""
    result = evaluate_goal_acceptance(acceptance_case(), record)
    assert result["status"] == "FAIL"
    assert result["failure_stage"] == "FINALIZATION"


def test_goal_acceptance_ollama_unavailable_is_environment_blocked():
    record = acceptance_record()
    record["execution_diagnostics"] = {
        "provider_reachable": False,
        "exception_type": "ConnectionError",
        "exception_message": "Ollama connection refused",
    }
    result = evaluate_goal_acceptance(acceptance_case(), record)
    assert result["status"] == "ENVIRONMENT_BLOCKED"


def test_goal_acceptance_requirement_communication_failure_is_environment_blocked():
    record = acceptance_record()
    record["execution_diagnostics"] = {
        "communication_status": "FAILED",
        "failure_phase": "requirement_decomposition",
        "exception_type": "ResponseError",
        "exception_message": "model not found",
    }

    result = evaluate_goal_acceptance(acceptance_case(), record)

    assert result["status"] == "ENVIRONMENT_BLOCKED"
    assert result["failure_stage"] == "ENVIRONMENT"
    assert result["failure_stage"] == "ENVIRONMENT"


def test_01_registered_case_is_available():
    assert [row["test_case_id"] for row in load_test_cases()] == [
        "E2E-1A",
        "P216-GIT-PLAN",
    ]


def test_02_single_run_identification_and_git_metadata():
    record = make_record()
    assert record["run_id"] == "tr-1"
    assert record["git"]["commit_sha"] == "abc"
    assert record["turn_id"] == "correlation-1"


def test_03_tool_sequence_and_contract_counts():
    record = make_record(tool_status="partial")
    assert record["tool"]["tool_sequence"] == ["read_file"]
    assert record["tool"]["tool_partial_count"] == 1


def test_04_evidence_count_and_synthesis_ids():
    record = make_record()
    assert record["evidence"]["evidence_count"] == 1
    assert record["evidence"]["final_synthesis_evidence_ids"] == ["E1"]


def test_tool_expectation_is_preserved_by_recorder():
    expectation = make_record()["tool_expectation"]
    assert expectation["expected_tool"] == "read_file"
    assert expectation["expected_arguments"] == {"path": "docs/x"}
    assert expectation["actual_tool_called"] == "read_file"
    assert expectation["expectation_matched"] is True


def test_agent_turn_timing_is_preserved_by_recorder():
    turn = fake_turn()
    turn["timing_breakdown"] = {
        "requirement_decomposition_ms": 10,
        "agent_initial_llm_ms": 20,
        "tool_execution_ms": 1,
        "agent_post_tool_llm_ms": 30,
        "final_synthesis_llm_ms": 0,
        "total_turn_ms": 61,
        "llm_calls": [],
    }
    record = record_run(
        get_test_case("P216-GIT-PLAN"),
        turn,
        run_id="tr-timing",
        started_at="a",
        finished_at="b",
        duration_ms=61,
    )
    assert record["timing"]["agent_turn"] == turn["timing_breakdown"]


def test_05_empty_answer_is_failed_mechanically():
    record = make_record(answer="")
    assert record["output"]["final_answer_empty"]
    assert record["evaluations"]["empty_answer"] == "FAIL"


def test_06_repeated_failure_is_detected():
    turn = fake_turn(tool_status="failure")
    turn["task_runtime"]["actions"].append(dict(turn["task_runtime"]["actions"][0], action_id="A2"))
    record = record_run(
        get_test_case("P216-GIT-PLAN"), turn, run_id="tr-r", started_at="a", finished_at="b", duration_ms=1
    )
    assert record["tool"]["repeated_action_count"] == 1
    assert record["evaluations"]["repeated_failure"] == "FAIL"


def test_07_completion_inconsistency_is_failed():
    turn = fake_turn()
    turn["task_runtime"]["tasks"].append({"task_id": "T2", "status": "pending"})
    record = record_run(
        get_test_case("P216-GIT-PLAN"), turn, run_id="tr-c", started_at="a", finished_at="b", duration_ms=1
    )
    assert record["evaluations"]["completion_consistency"] == "FAIL"


def test_08_markdown_contains_result_sections_and_answer():
    report = run_markdown(make_record())
    assert "# Test Run Report" in report
    assert "## Automatic Evaluation" in report
    assert "plan" in report


def test_09_batch_five_runs_are_independent_and_saved(tmp_path):
    seen = []

    def execute(_case, run_id):
        seen.append(run_id)
        return fake_turn()

    result = run_batch(
        get_test_case("P216-GIT-PLAN"), 5, execute, output_root=tmp_path, batch_id="b5"
    )
    assert len(set(seen)) == 5
    assert result["aggregate"]["total_runs"] == 5
    assert len(list((tmp_path / "P216-GIT-PLAN" / "b5").glob("tr-*/result.json"))) == 5


def test_10_one_failed_run_does_not_stop_batch(tmp_path):
    calls = {"count": 0}

    def execute(_case, _run_id):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("one run failed")
        return fake_turn()

    result = run_batch(
        get_test_case("P216-GIT-PLAN"), 5, execute, output_root=tmp_path, batch_id="continue"
    )
    assert calls["count"] == 5
    assert result["aggregate"]["failed_runs"] == 1


def test_11_aggregate_json_is_machine_readable(tmp_path):
    result = run_batch(
        get_test_case("P216-GIT-PLAN"), 1, lambda *_: fake_turn(), output_root=tmp_path, batch_id="json"
    )
    path = tmp_path / "P216-GIT-PLAN" / "json" / "aggregate.json"
    assert json.loads(path.read_text(encoding="utf-8"))["batch_id"] == result["batch_id"]


def test_12_aggregate_markdown_has_pass_rates():
    case = get_test_case("P216-GIT-PLAN")
    aggregate = aggregate_records(case, [make_record(), make_record(answer="")], batch_id="b")
    report = aggregate_markdown(aggregate)
    assert "Empty Answer PASS: 1 / 2" in report
    assert "Evidence Coverage REVIEW_REQUIRED: 2 / 2" in report


def test_13_frequent_problem_ranking():
    case = get_test_case("P216-GIT-PLAN")
    rows = [make_record(answer=""), make_record(answer="")]
    aggregate = aggregate_records(case, rows, batch_id="b")
    assert aggregate["frequent_problems"][0] == {"problem": "Empty answer", "runs": 2}


def test_14_only_bounded_ui_run_counts_are_accepted(tmp_path):
    with pytest.raises(ValueError, match="1, 5, or 10"):
        run_batch(get_test_case("P216-GIT-PLAN"), 100, lambda *_: fake_turn(), output_root=tmp_path)


def test_15_progress_reports_each_run_without_chat_history_coupling(tmp_path):
    events = []
    run_batch(
        get_test_case("P216-GIT-PLAN"),
        1,
        lambda *_: fake_turn(),
        output_root=tmp_path,
        progress=events.append,
        batch_id="progress",
    )
    assert [row["status"] for row in events] == ["running", "completed"]


def test_16_review_required_is_not_fabricated_as_pass():
    evaluations = make_record()["evaluations"]
    assert evaluations["technical_quality"] == "REVIEW_REQUIRED"
    assert evaluations["goal_decomposition_quality"] == "REVIEW_REQUIRED"


def test_17_duration_marks_long_running_without_ui_polling():
    case = get_test_case("P216-GIT-PLAN")
    record = record_run(
        case,
        fake_turn(),
        run_id="tr-long",
        started_at="a",
        finished_at="b",
        duration_ms=30_001,
    )
    assert record["timing"]["long_running_occurred"]


def test_18_run_markdown_contains_required_ui_sections():
    report = run_markdown(make_record())
    for heading in (
        "## Run Summary",
        "## Agent Output",
        "## Goal / Task Status",
        "## Tool Sequence",
        "## Evidence",
        "## Completion / Progress",
        "## Final LLM Lifecycle",
        "## Automatic Evaluation",
        "## Review Required",
    ):
        assert heading in report


def test_19_aggregate_contains_final_lifecycle_counts():
    aggregate = aggregate_records(
        get_test_case("P216-GIT-PLAN"), [make_record(answer="")], batch_id="b"
    )
    assert aggregate["final_llm_lifecycle"]["model_returned_empty_count"] == 1


def test_20_aggregate_markdown_contains_required_ui_sections():
    aggregate = aggregate_records(
        get_test_case("P216-GIT-PLAN"), [make_record()], batch_id="b"
    )
    report = aggregate_markdown(aggregate)
    for heading in (
        "## Batch Summary",
        "## PASS / FAIL Summary",
        "## Tool Usage Summary",
        "## Completion Summary",
        "## Final LLM Lifecycle Summary",
        "## Frequent Problems",
        "## Runs Requiring Review",
    ):
        assert heading in report
