import json
from types import SimpleNamespace

from ai_tool.chat_interface.local_review import (
    ReviewTaskCandidate,
    StructuredReview,
    build_review_input,
    call_local_reviewer,
    parse_review,
    validate_review,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementCondition,
    RequirementDecomposition,
)
from ai_tool.agent_test_runner import record_run


def _runtime(conditions=("field A confirmed",)):
    item = ChatTaskOrchestrator("turn", "inspect a file", completion_conditions=conditions)
    item.initialize()
    return item


def _review(**changes):
    values = {"review_status": "CONTINUE"}
    values.update(changes)
    return StructuredReview(**values)


def test_complete_is_accepted_when_all_conditions_are_satisfied():
    runtime = _runtime()
    task = runtime.task
    task.condition_status["field A confirmed"] = "SATISFIED"
    task.satisfied_conditions.append("field A confirmed")
    result = validate_review(_review(review_status="COMPLETE"), runtime)
    assert result["review_status"] == "COMPLETE"
    assert result["coverage_complete"] is True


def test_missing_evidence_creates_a_grounded_evidence_task():
    runtime = _runtime()
    review = _review(
        missing_evidence=["field A has no source"],
        new_tasks=[
            ReviewTaskCandidate(
                "read the source for field A",
                "obtain the missing evidence",
                ["field A confirmed"],
                "field A has no source",
            )
        ],
    )
    result = validate_review(review, runtime)
    assert [row["description"] for row in result["accepted_new_tasks"]] == [
        "read the source for field A"
    ]


def test_conflict_creates_a_grounded_verification_task():
    runtime = _runtime()
    review = _review(
        conflicts=["two sources disagree"],
        new_tasks=[
            ReviewTaskCandidate(
                "verify the conflicting values",
                "resolve the observed conflict",
                [],
                "two sources disagree",
            )
        ],
    )
    assert validate_review(review, runtime)["accepted_new_tasks"]


def test_ungrounded_additional_research_is_rejected():
    runtime = _runtime()
    review = _review(
        new_tasks=[ReviewTaskCandidate("research more", "might be useful", [], "")]
    )
    result = validate_review(review, runtime)
    assert result["accepted_new_tasks"] == []
    assert result["rejected_new_tasks"][0]["reason"] == "ungrounded_task"


def test_duplicate_task_is_rejected():
    runtime = _runtime()
    review = _review(
        missing_evidence=["need source"],
        new_tasks=[
            ReviewTaskCandidate(
                "Observe the facts required by the request",
                "need source",
                ["field A confirmed"],
                "need source",
            )
        ],
    )
    assert validate_review(review, runtime)["rejected_new_tasks"][0]["reason"] == "duplicate_task"


def test_reviewer_complete_cannot_override_unknown_coverage():
    runtime = _runtime()
    result = validate_review(_review(review_status="COMPLETE"), runtime)
    assert result["review_status"] == "CONTINUE"
    assert result["rejected_new_tasks"][-1] == {
        "claim": "COMPLETE",
        "reason": "coverage_incomplete",
    }


def test_malformed_reviewer_task_is_rejected_by_runtime():
    runtime = _runtime()
    review = _review(
        new_tasks=[ReviewTaskCandidate("invent a feature", "", ["not a condition"], "")]
    )
    result = validate_review(review, runtime)
    assert result["accepted_new_tasks"] == []
    assert result["rejected_new_tasks"][0]["reason"] == "missing_required_fields"


def test_reviewer_invented_problem_cannot_ground_an_unrelated_task():
    runtime = _runtime()
    result = validate_review(
        _review(
            problems=["maybe rewrite everything"],
            new_tasks=[
                ReviewTaskCandidate(
                    "rewrite everything",
                    "reviewer prefers it",
                    [],
                    "maybe rewrite everything",
                )
            ],
        ),
        runtime,
    )
    assert result["accepted_new_tasks"] == []
    assert result["rejected_new_tasks"][0]["reason"] == "ungrounded_task"


def test_invalid_or_empty_reviewer_output_does_not_raise():
    assert parse_review("").parse_error
    assert parse_review("not json").review_status == "CONTINUE"

    response = SimpleNamespace(message=SimpleNamespace(content=""))
    result = call_local_reviewer(
        lambda **_kwargs: response,
        model="local",
        review_input=build_review_input(_runtime(), "candidate answer"),
    )
    assert result.review_status == "CONTINUE"
    assert result.parse_error


def test_escalation_only_builds_a_packet_and_never_calls_an_external_service():
    runtime = _runtime()
    result = validate_review(
        _review(
            review_status="ESCALATE",
            conflicts=["cannot resolve local conflict"],
            recommended_next_action="ask a human",
        ),
        runtime,
    )
    assert result["escalation_packet"]["automatic_escalation"] is False


def test_ungrounded_escalation_is_downgraded_to_continue():
    result = validate_review(_review(review_status="ESCALATE"), _runtime())
    assert result["review_status"] == "CONTINUE"
    assert result["escalation_packet"] is None


def test_review_input_is_compact_and_contains_runtime_authority():
    payload = build_review_input(_runtime(), "candidate")
    assert payload["current_task"]["task_id"] == "T1"
    assert payload["unresolved_conditions"] == ["field A confirmed"]
    assert payload["completion_conditions"][0]["status"] == "UNKNOWN"


def test_validated_task_is_registered_with_iteration_record():
    runtime = _runtime()
    result = validate_review(
        _review(
            missing_evidence=["need source"],
            new_tasks=[
                ReviewTaskCandidate(
                    "obtain source",
                    "needed for completion",
                    ["field A confirmed"],
                    "need source",
                )
            ],
        ),
        runtime,
    )
    added = runtime.add_review_task(result["accepted_new_tasks"][0])
    runtime.record_local_review(
        {
            "review_iteration": 1,
            "final_review_status": "CONTINUE",
            "accepted_new_tasks": result["accepted_new_tasks"],
            "rejected_new_tasks": [],
        }
    )
    assert runtime.current_task_id == added.task_id
    assert runtime.snapshot()["local_reviews"][0]["review_iteration"] == 1


def test_review_follow_up_evidence_satisfies_source_condition_and_returns_to_synthesis():
    runtime = _runtime(("status values confirmed",))
    added = runtime.add_review_task(
        {
            "description": "verify status values",
            "reason": "coverage is unresolved",
            "supports_conditions": ["status values confirmed"],
            "source_problem": "status values need a source",
        }
    )
    runtime.observe_tool(
        "read_file",
        {"path": "docs/spec.md"},
        {"status": "success"},
        {"path": "docs/spec.md"},
        relevant_tools=["read_file"],
        raw_result={"content": "status permits success, partial, and failure"},
    )
    assert runtime.runtime.tasks[added.task_id].status == "complete"
    assert runtime.runtime.tasks["T1"].status == "complete"
    assert runtime.runtime.tasks["T1"].condition_evidence["status values confirmed"]
    assert runtime.current_task_id == "T2"


def _prepare_turn(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition(
            [RequirementCondition("C1", "field A confirmed")], "READY"
        ),
    )


def test_agent_loop_records_review_but_does_not_accept_false_complete(
    monkeypatch, tmp_path
):
    _prepare_turn(monkeypatch, tmp_path)
    main = lambda **_kwargs: SimpleNamespace(
        message=SimpleNamespace(content="candidate answer", tool_calls=[])
    )
    reviewer = lambda **_kwargs: SimpleNamespace(
        message=SimpleNamespace(
            content=json.dumps(
                {
                    "review_status": "COMPLETE",
                    "facts": [],
                    "problems": [],
                    "missing_evidence": [],
                    "conflicts": [],
                    "new_tasks": [],
                    "recommended_next_action": "finish",
                    "confidence": 0.9,
                }
            ),
            tool_calls=[],
        )
    )
    result = run_chat_turn(
        empty_session("review-integration"),
        "inspect repository file and report facts",
        chat_fn=main,
        review_chat_fn=reviewer,
        local_review_enabled=True,
        model="local",
    )
    review = result["task_runtime"]["local_reviews"][0]
    assert review["final_review_status"] == "CONTINUE"
    assert review["rejected_new_tasks"][-1]["reason"] == "coverage_incomplete"
    assert result["answer"].startswith("【未確認】")
    assert result["answer"].endswith("candidate answer")
    assert result["answer_gate"]["verified"] is False


def test_agent_loop_registers_grounded_review_task_and_continues(
    monkeypatch, tmp_path
):
    _prepare_turn(monkeypatch, tmp_path)
    main_rows = iter(
        [
            SimpleNamespace(message=SimpleNamespace(content="first", tool_calls=[])),
            SimpleNamespace(message=SimpleNamespace(content="second", tool_calls=[])),
        ]
    )
    review_rows = iter(
        [
            {
                "review_status": "CONTINUE",
                "facts": [],
                "problems": [],
                "missing_evidence": ["field A has no source"],
                "conflicts": [],
                "new_tasks": [
                    {
                        "description": "obtain the source for field A",
                        "reason": "required evidence is absent",
                        "supports_conditions": ["field A confirmed"],
                        "source_problem": "field A has no source",
                    }
                ],
                "recommended_next_action": "read the source",
                "confidence": 0.8,
            },
            {
                "review_status": "CONTINUE",
                "facts": [],
                "problems": [],
                "missing_evidence": [],
                "conflicts": [],
                "new_tasks": [],
                "recommended_next_action": "report status",
                "confidence": 0.5,
            },
        ]
    )
    result = run_chat_turn(
        empty_session("review-follow-up"),
        "inspect repository file and report facts",
        chat_fn=lambda **_kwargs: next(main_rows),
        review_chat_fn=lambda **_kwargs: SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(next(review_rows)), tool_calls=[])
        ),
        local_review_enabled=True,
        model="local",
    )
    snapshot = result["task_runtime"]
    assert len(snapshot["local_reviews"]) == 2
    assert len(snapshot["tasks"]) == 3
    assert snapshot["tasks"][-1]["title"] == "obtain the source for field A"
    assert result["answer"].startswith("【未確認】")
    assert result["answer"].endswith("second")
    assert result["answer_gate"]["verified"] is False
    assert result["timing_breakdown"]["local_review_llm_ms"] >= 0


def test_recorder_preserves_local_review_iterations():
    turn = {
        "answer": "status",
        "task_runtime": {
            "goals": [],
            "tasks": [],
            "actions": [],
            "evidence": [],
            "failures": [],
            "events": [],
            "local_reviews": [
                {
                    "review_iteration": 1,
                    "review_input_summary": {"evidence_count": 0},
                    "structured_review": {"review_status": "CONTINUE"},
                    "accepted_new_tasks": [],
                    "rejected_new_tasks": [{"reason": "ungrounded_task"}],
                    "unresolved_conditions_before": ["A"],
                    "unresolved_conditions_after": ["A"],
                    "final_review_status": "CONTINUE",
                }
            ],
        },
    }
    record = record_run(
        {"test_case_id": "review", "prompt": "review", "expected": {}},
        turn,
        run_id="run-1",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        duration_ms=1000,
        git_metadata={"available": False},
    )
    assert record["local_review"]["review_count"] == 1
    assert record["local_review"]["rejected_new_task_count"] == 1
    assert record["local_review"]["iterations"][0]["unresolved_conditions_after"] == ["A"]
