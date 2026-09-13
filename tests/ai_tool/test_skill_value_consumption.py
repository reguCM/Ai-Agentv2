from __future__ import annotations

from ai_tool.skill_applicability import (
    SkillStepOutcome,
    ValueVerdict,
    count_execute_true,
    judgment_target_steps,
    run_skill_value_consumption_loop,
)
from ai_tool.skill_applicability import composition_steps


def test_judgment_targets_exclude_grill_me_only() -> None:
    steps = composition_steps("tetris-sandbox-e2e")
    targets = judgment_target_steps(steps)
    assert "grill-me" not in targets
    assert targets[0] == "write-prd"


def test_value_loop_from_blank_excludes_grill_me_and_runs_downstream() -> None:
    calls: dict[str, int] = {}

    def executor(skill_id: str) -> SkillStepOutcome:
        calls[skill_id] = calls.get(skill_id, 0) + 1
        if skill_id == "write-prd":
            return SkillStepOutcome(status="done", gate_passed=True)
        return SkillStepOutcome(status="done", gate_passed=True)

    report = run_skill_value_consumption_loop(
        request="テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        executor=executor,
    )

    assert "grill-me" not in calls
    assert report.all_executed_skill_ids() == [
        "write-prd",
        "tech-spec",
        "planning-and-task-breakdown",
        "goal-handoff",
    ]
    assert report.final_artifacts.has("prd")
    assert report.final_artifacts.has("goal_handoff_packet")
    first_round = report.rounds[0]
    assert all(row.skill_id != "grill-me" for row in first_round.snapshot)
    write_row = next(row for row in first_round.snapshot if row.skill_id == "write-prd")
    assert write_row.execute is True
    assert write_row.value == ValueVerdict.USE.value


def test_value_loop_repeats_until_write_prd_gate_passes() -> None:
    calls = {"write-prd": 0}

    def executor(skill_id: str) -> SkillStepOutcome:
        if skill_id == "write-prd":
            calls["write-prd"] += 1
            if calls["write-prd"] < 2:
                return SkillStepOutcome(status="partial", gate_passed=False)
            return SkillStepOutcome(status="done", gate_passed=True)
        return SkillStepOutcome(status="done", gate_passed=True)

    report = run_skill_value_consumption_loop(
        request="テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        executor=executor,
    )

    assert calls["write-prd"] == 2
    assert report.rounds[0].executed_skill_ids == ["write-prd"]
    round1_write = next(
        row for row in report.rounds[1].snapshot if row.skill_id == "write-prd"
    )
    assert round1_write.execute is True
    assert report.rounds[1].executed_skill_ids[0] == "write-prd"
    assert report.final_artifacts.has("prd")


def test_value_loop_stops_when_no_value_remains() -> None:
    def executor(skill_id: str) -> SkillStepOutcome:
        return SkillStepOutcome(status="done", gate_passed=True)

    report = run_skill_value_consumption_loop(
        request="テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        executor=executor,
    )

    assert report.round_count >= 2
    last_round = report.rounds[-1]
    assert last_round.executed_skill_ids == []
    assert all(not row.execute for row in last_round.snapshot)


def test_value_loop_can_execute_multiple_use_skills_in_one_round() -> None:
    round_one_execute_counts: list[int] = []

    def executor(skill_id: str) -> SkillStepOutcome:
        return SkillStepOutcome(status="done", gate_passed=True)

    report = run_skill_value_consumption_loop(
        request="テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        executor=executor,
    )

    for round_row in report.rounds:
        round_one_execute_counts.append(count_execute_true(round_row.snapshot))

    assert max(round_one_execute_counts) >= 2
    first_round = report.rounds[0]
    assert "write-prd" in first_round.executed_skill_ids
    assert count_execute_true(first_round.snapshot) >= 1
