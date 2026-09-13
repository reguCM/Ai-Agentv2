from ai_tool.chat_interface.events import mission_ui_summary, runtime_ui_summary


def test_runtime_ui_summary_extracts_task_goal_status():
    summary = runtime_ui_summary(
        {
            "current_task_id": "T2",
            "current_goal_id": "G1.2",
            "tasks": [
                {
                    "task_id": "T1",
                    "title": "Observe",
                    "status": "complete",
                    "satisfied_conditions": ["relevant evidence observed"],
                },
                {
                    "task_id": "T2",
                    "title": "Synthesize",
                    "status": "complete",
                    "satisfied_conditions": ["answer produced"],
                },
            ],
            "goals": [
                {"goal_id": "G1", "title": "Root", "status": "complete"},
            ],
            "awaiting_goal_completion_human": True,
            "evidence": [{"evidence_id": "E1"}],
        }
    )
    assert summary is not None
    assert summary["tasks"][0]["status"] == "complete"
    assert summary["goals"][0]["status"] == "complete"
    assert summary["awaiting_goal_completion_human"] is True
    assert summary["evidence_count"] == 1


def test_mission_ui_summary_keeps_judgment_fields():
    summary = mission_ui_summary(
        {
            "ok": True,
            "mission_id": "m1",
            "execution_id": "x1",
            "execution_end_state_judgment": "judged",
            "execution_end_state": "achieved",
            "goal_achievement_performed": True,
            "goal_achievement_result": "achieved",
            "stop_reason": "GOAL_COMPLETION_JUDGED",
            "evidence_refs": ["pe1"],
        }
    )
    assert summary == {
        "ok": True,
        "mission_id": "m1",
        "execution_id": "x1",
        "execution_end_state_judgment": "judged",
        "execution_end_state": "achieved",
        "goal_achievement_performed": True,
        "goal_achievement_result": "achieved",
        "stop_reason": "GOAL_COMPLETION_JUDGED",
        "evidence_refs": ["pe1"],
    }
