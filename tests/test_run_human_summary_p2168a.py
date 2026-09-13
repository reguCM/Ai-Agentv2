from copy import deepcopy

from ai_tool.agent_test_runner import record_run, run_markdown


def _turn(*, complete=True, evidence=True, review=False, added_task=False, answer="回答"):
    condition_status = "SATISFIED" if complete else "UNKNOWN"
    task_status = "complete" if complete else "in_progress"
    reviews = []
    if review:
        accepted = []
        if added_task:
            accepted.append(
                {
                    "description": "不足Evidenceを確認する",
                    "reason": "根拠が不足している",
                    "supports_conditions": ["仕様が確認できている"],
                    "source_problem": "根拠不足",
                }
            )
        reviews.append(
            {
                "review_iteration": 1,
                "final_review_status": "CONTINUE",
                "accepted_new_tasks": accepted,
                "rejected_new_tasks": [],
                "structured_review": {
                    "review_status": "CONTINUE",
                    "facts": ["Reviewerは仕様候補を検出した"],
                    "problems": ["仕様解釈が誤っている可能性"],
                    "missing_evidence": ["根拠不足"],
                    "conflicts": [],
                    "recommended_next_action": "不足Evidenceを確認する",
                },
            }
        )
    tasks = [
        {
            "task_id": "T1",
            "goal_id": "G1",
            "title": "仕様を確認する",
            "instruction": "正本仕様を確認する",
            "status": task_status,
            "completion_conditions": ["仕様が確認できている"],
            "condition_status": {"仕様が確認できている": condition_status},
            "condition_evidence": {"仕様が確認できている": ["E1"] if evidence else []},
            "depends_on": [],
            "progress_state": "progress" if evidence else None,
        }
    ]
    if added_task:
        tasks.append(
            {
                "task_id": "T2",
                "goal_id": "G1",
                "title": "不足Evidenceを確認する",
                "instruction": "不足Evidenceを確認する",
                "status": "pending",
                "completion_conditions": ["仕様が確認できている"],
                "condition_status": {"仕様が確認できている": "UNKNOWN"},
                "condition_evidence": {"仕様が確認できている": []},
                "depends_on": ["T1"],
            }
        )
    return {
        "answer": answer,
        "model": "local",
        "tools": [
            {
                "name": "read_file",
                "arguments": {"path": "docs/spec.md"},
                "status": "success",
            }
        ],
        "events": [],
        "task_runtime": {
            "current_task_id": tasks[-1]["task_id"],
            "goals": [
                {
                    "goal_id": "G1",
                    "title": "正本仕様を根拠付きで説明する",
                    "parent_goal_id": None,
                    "status": "complete" if complete and not added_task else "in_progress",
                }
            ],
            "tasks": tasks,
            "actions": [],
            "evidence": (
                [{"evidence_id": "E1", "summary": "正本に仕様が記載されている"}]
                if evidence
                else []
            ),
            "failures": [],
            "replans": [],
            "tool_gaps": [],
            "events": [],
            "local_reviews": reviews,
            "tool_expectation": {
                "generated": True,
                "expected_tool": "read_file",
                "expected_arguments": {"path": "docs/spec.md"},
            },
        },
        "requirement_decomposition": {"status": "READY"},
        "final_llm_lifecycle": {
            "final_llm_response_received": True,
            "final_llm_response_empty": not bool(answer),
        },
    }


def _record(turn):
    return record_run(
        {"test_case_id": "summary", "prompt": "正本仕様を確認する", "expected": {}},
        turn,
        run_id="run-summary",
        started_at="a",
        finished_at="b",
        duration_ms=1,
        git_metadata={"available": False},
    )


def test_complete_run_has_good_final_evaluation():
    summary = _record(_turn())["human_summary"]
    assert summary["evaluation"]["final_result"]["rating"] == "良好"


def test_incomplete_run_is_not_presented_as_complete():
    summary = _record(_turn(complete=False))["human_summary"]
    assert summary["evaluation"]["final_result"]["rating"] == "未完了"


def test_zero_evidence_is_explicit():
    summary = _record(_turn(complete=False, evidence=False))["human_summary"]
    assert summary["unresolved"]["evidence_absent"] is True
    assert summary["evaluation"]["execution"]["rating"] == "要確認"


def test_local_review_is_visible_in_approach_and_execution():
    summary = _record(_turn(complete=False, review=True))["human_summary"]
    assert any("Local Reviewを1回" in row for row in summary["approach"])
    assert any(row["type"] == "local_review" for row in summary["execution"])


def test_review_added_task_is_marked_in_decomposition():
    summary = _record(
        _turn(complete=False, review=True, added_task=True)
    )["human_summary"]
    assert summary["decomposition"][-1]["added_by_local_review"] is True


def test_unresolved_condition_and_next_action_are_preserved():
    summary = _record(_turn(complete=False))["human_summary"]
    assert summary["unresolved"]["conditions"][0]["condition"] == "仕様が確認できている"
    assert any(row["source"] == "completion_coverage" for row in summary["next_actions"])


def test_empty_response_fallback_still_produces_nonempty_summary():
    summary = _record(_turn(complete=False, answer=""))["human_summary"]
    assert summary["purpose"]["summary"]
    assert summary["evaluation"]["final_result"]["rating"] == "未完了"


def test_reviewer_hypothesis_is_not_mixed_with_confirmed_facts():
    summary = _record(_turn(complete=False, review=True))["human_summary"]
    assert "仕様解釈が誤っている可能性" in summary["learned"]["hypotheses"]
    confirmed = [row["statement"] for row in summary["learned"]["confirmed"]]
    assert "仕様解釈が誤っている可能性" not in confirmed
    assert "Reviewerは仕様候補を検出した" in summary["learned"]["review_observations_unconfirmed"]


def test_raw_record_fields_are_not_replaced_by_human_summary():
    turn = _turn()
    original_tools = deepcopy(turn["tools"])
    record = _record(turn)
    assert record["tool"]["tool_sequence"] == ["read_file"]
    assert turn["tools"] == original_tools
    assert "human_summary" in record


def test_markdown_starts_with_japanese_summary_and_keeps_technical_details():
    report = run_markdown(_record(_turn()))
    for heading in (
        "## 今回の目的",
        "## 今回の進め方",
        "## 作業の分け方",
        "## 実際に行ったこと",
        "## 分かったこと",
        "## 分からなかったこと",
        "## 今回の評価",
        "## 次にやること",
        "## Run Summary",
        "## Tool Sequence",
    ):
        assert heading in report
    assert report.index("## 今回の目的") < report.index("## Run Summary")


def test_ui_shows_japanese_summary_before_collapsed_detail_log():
    script = open("ai_tool/chat_interface/static/app.js", encoding="utf-8").read()
    assert "human_summary_markdown" in script
    assert "日本語要約をコピー" in script
    assert '<details class="test-run-report"><summary>詳細ログ</summary>' in script
    assert script.index("test-run-human-summary") < script.index("<details class=\"test-run-report\"")


def test_execution_keeps_tool_arguments_and_unfinished_task_is_visible():
    record = _record(_turn(complete=False))
    summary = record["human_summary"]
    assert summary["execution"][0]["arguments"] == {"path": "docs/spec.md"}
    report = run_markdown(record)
    assert '引数: {"path": "docs/spec.md"}' in report
    assert "未完了Task: T1 仕様を確認する" in report
