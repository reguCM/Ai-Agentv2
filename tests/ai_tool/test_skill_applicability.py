from __future__ import annotations

from ai_tool.skill_applicability import (
    GapContext,
    SkillArtifacts,
    SkillStepOutcome,
    UsabilityVerdict,
    ValueVerdict,
    resolve_composition_applicability,
    resolve_skill_applicability,
    should_execute,
    should_retry_skill_execution,
    skill_outcome_satisfied,
    count_execute_true,
    walk_composition_with_retry,
)


def test_grill_me_usable_and_valuable_for_vague_request() -> None:
    item = resolve_skill_applicability(
        "grill-me",
        request="テトリスを作って",
        consumer="local_agent",
        artifacts=SkillArtifacts(),
        composition_steps=["grill-only"],
    )
    assert item.usability == UsabilityVerdict.USABLE.value
    assert item.value == ValueVerdict.USE.value
    assert should_execute(item)


def test_grill_me_redundant_when_write_prd_runs_first() -> None:
    steps = ["write-prd", "grill-me", "tech-spec"]
    item = resolve_skill_applicability(
        "grill-me",
        request="テトリスを作って",
        consumer="local_agent",
        artifacts=SkillArtifacts(),
        composition_steps=steps,
    )
    assert item.usability == UsabilityVerdict.USABLE.value
    assert item.value == ValueVerdict.REDUNDANT.value
    assert item.value_reasons == ["invoked_by:write-prd"]
    assert not should_execute(item)


def test_graph_engineering_skipped_for_small_sandbox_scope() -> None:
    item = resolve_skill_applicability(
        "graph-engineering",
        request="Dedicated Sandbox 内に tetris/main.py を作って",
        consumer="local_agent",
        artifacts=SkillArtifacts({"prd"}),
        composition_steps=["grill-me", "write-prd", "graph-engineering", "tech-spec"],
    )
    assert item.usability == UsabilityVerdict.USABLE.value
    assert item.value == ValueVerdict.SKIP.value
    assert not should_execute(item)


def test_tech_spec_blocked_without_prd() -> None:
    item = resolve_skill_applicability(
        "tech-spec",
        request="テトリスを作って",
        consumer="local_agent",
        artifacts=SkillArtifacts(),
        composition_steps=["tech-spec"],
    )
    assert item.usability == UsabilityVerdict.BLOCKED.value
    assert "missing_inputs" in item.usability_reasons[0]
    assert item.value == ValueVerdict.DEFER.value
    assert not should_execute(item)


def test_session_start_skipped_for_fresh_work() -> None:
    item = resolve_skill_applicability(
        "session-start",
        request="テトリスを作って",
        consumer="local_agent",
        artifacts=SkillArtifacts(),
        composition_steps=["session-start"],
    )
    assert item.usability == UsabilityVerdict.USABLE.value
    assert item.value == ValueVerdict.SKIP.value
    assert not should_execute(item)


def test_session_start_valuable_on_resume_hint() -> None:
    item = resolve_skill_applicability(
        "session-start",
        request="作業を再開して session start を確認したい",
        consumer="local_agent",
        artifacts=SkillArtifacts(),
        composition_steps=["session-start"],
        resume_session=True,
    )
    assert item.usability == UsabilityVerdict.USABLE.value
    assert item.value == ValueVerdict.USE.value
    assert should_execute(item)


def test_tetris_composition_separates_usability_and_value() -> None:
    report = resolve_composition_applicability(
        request="テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        consumer="local_agent",
    )
    by_id = {item.skill_id: item for item in report.items}
    assert "grill-me" not in by_id
    assert by_id["write-prd"].value == ValueVerdict.USE.value
    assert by_id["goal-handoff"].value == ValueVerdict.USE.value
    assert report.executed_skill_ids() == [
        "write-prd",
        "tech-spec",
        "planning-and-task-breakdown",
        "goal-handoff",
    ]


def test_grill_me_use_when_explicit_before_write_prd() -> None:
    item = resolve_skill_applicability(
        "grill-me",
        request="テトリスを作って",
        consumer="local_agent",
        artifacts=SkillArtifacts(),
        composition_steps=["grill-me", "write-prd"],
    )
    assert item.value == ValueVerdict.USE.value
    assert should_execute(item)


def test_skill_outcome_satisfied_requires_gate_for_retryable_skills() -> None:
    assert skill_outcome_satisfied(
        "grill-me",
        SkillStepOutcome(status="partial", gate_passed=False),
    ) is False
    assert skill_outcome_satisfied(
        "write-prd",
        SkillStepOutcome(status="done", gate_passed=True),
    ) is True
    assert skill_outcome_satisfied(
        "goal-handoff",
        SkillStepOutcome(status="error"),
    ) is False


def test_grill_me_loops_until_gate_passed() -> None:
    calls = {"grill-me": 0}

    def executor(skill_id: str, attempt: int) -> SkillStepOutcome:
        if skill_id != "grill-me":
            return SkillStepOutcome(status="done", gate_passed=True)
        calls["grill-me"] += 1
        if calls["grill-me"] < 3:
            return SkillStepOutcome(status="partial", gate_passed=False)
        return SkillStepOutcome(status="done", gate_passed=True)

    report = walk_composition_with_retry(
        request="テトリスを作って",
        composition_id="grill-only",
        executor=executor,
        max_attempts_per_skill=5,
    )
    grill_run = report.step_runs[0]
    assert grill_run.skill_id == "grill-me"
    assert grill_run.attempt_count == 3
    assert calls["grill-me"] == 3
    for attempt in grill_run.attempts:
        assert count_execute_true(attempt.snapshot) == 1
        assert attempt.applicability.execute is True
        assert attempt.applicability.value == ValueVerdict.USE.value
    assert report.final_artifacts.has("ambiguity_report")


def test_grill_me_stops_retrying_at_max_attempts() -> None:
    def executor(skill_id: str, attempt: int) -> SkillStepOutcome:
        return SkillStepOutcome(status="partial", gate_passed=False)

    report = walk_composition_with_retry(
        request="テトリスを作って",
        composition_id="grill-only",
        executor=executor,
        max_attempts_per_skill=2,
    )
    grill_run = report.step_runs[0]
    assert grill_run.attempt_count == 2
    assert grill_run.final_status == "partial"
    assert not report.final_artifacts.has("ambiguity_report")
    assert should_retry_skill_execution(
        "grill-me",
        next_attempt=2,
        outcome=SkillStepOutcome(status="partial", gate_passed=False),
        max_attempts=2,
    ) is False


def test_write_prd_loops_until_internal_grill_gate_passes() -> None:
    calls = {"write-prd": 0}

    def executor(skill_id: str, attempt: int) -> SkillStepOutcome:
        if skill_id == "write-prd":
            calls["write-prd"] += 1
            if calls["write-prd"] < 2:
                return SkillStepOutcome(
                    status="partial",
                    gate_passed=False,
                    notes=["internal_grill_gate_open"],
                )
            return SkillStepOutcome(status="done", gate_passed=True)
        return SkillStepOutcome(status="done", gate_passed=True)

    report = walk_composition_with_retry(
        request="テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        executor=executor,
        max_attempts_per_skill=3,
    )
    write_run = next(run for run in report.step_runs if run.skill_id == "write-prd")
    assert write_run.attempt_count == 2
    assert calls["write-prd"] == 2
    for attempt in write_run.attempts:
        assert count_execute_true(attempt.snapshot) == 1
        assert attempt.applicability.skill_id == "write-prd"
        assert attempt.applicability.execute is True
        assert all(row.skill_id != "grill-me" for row in attempt.snapshot)
        tech_row = next(row for row in attempt.snapshot if row.skill_id == "tech-spec")
        assert tech_row.execute is False
        assert tech_row.value == ValueVerdict.DEFER.value
    assert report.final_artifacts.has("prd")


def test_walk_snapshot_only_topmost_step_is_use_during_write_prd_loop() -> None:
    def executor(skill_id: str, attempt: int) -> SkillStepOutcome:
        if skill_id == "write-prd":
            return SkillStepOutcome(status="partial", gate_passed=False)
        return SkillStepOutcome(status="done", gate_passed=True)

    report = walk_composition_with_retry(
        request="テトリスを作って",
        composition_id="tetris-sandbox-e2e",
        executor=executor,
        max_attempts_per_skill=1,
    )
    first_write = report.step_runs[0].attempts[0]
    by_id = {row.skill_id: row for row in first_write.snapshot}
    assert count_execute_true(first_write.snapshot) == 1
    assert by_id["write-prd"].execute is True
    assert "grill-me" not in by_id
    assert by_id["tech-spec"].value == ValueVerdict.DEFER.value


def test_boundary_grill_me_ignores_initial_grill_artifact_when_gap_unresolved() -> None:
    fork_request = (
        "README.md を読んで成果物を作成してください。\n"
        "完了条件は次の2通りがともに妥当ですが、どちらを採用するか未決です。\n"
        "A: 先頭3行をそのまま引用する\n"
        "B: 1段落の要約文を生成する"
    )
    item = resolve_skill_applicability(
        "grill-me",
        request=fork_request,
        consumer="local_agent",
        artifacts=SkillArtifacts({"ambiguity_report", "prd", "tech_spec"}),
        composition_steps=["grill-me"],
        gap_context=GapContext(
            kind="spec_meaning_gap",
            facts_sufficient=True,
            gap_resolved=False,
        ),
    )
    assert "artifact_already_satisfied" not in item.value_reasons
    assert item.usability == UsabilityVerdict.USABLE.value
    assert item.value == ValueVerdict.USE.value


def test_boundary_grill_me_skips_without_material_spec_fork() -> None:
    item = resolve_skill_applicability(
        "grill-me",
        request="README.md を読んで要約してください。",
        consumer="local_agent",
        artifacts=SkillArtifacts({"ambiguity_report"}),
        composition_steps=["grill-me"],
        gap_context=GapContext(
            kind="spec_meaning_gap",
            facts_sufficient=True,
            gap_resolved=False,
        ),
    )
    assert item.value == ValueVerdict.SKIP.value
    assert "no_material_spec_fork" in item.value_reasons


def test_boundary_grill_me_skips_for_fact_gap_kind() -> None:
    item = resolve_skill_applicability(
        "grill-me",
        request="テトリスを作って",
        consumer="local_agent",
        artifacts=SkillArtifacts({"ambiguity_report"}),
        composition_steps=["grill-me"],
        gap_context=GapContext(
            kind="fact_gap",
            facts_sufficient=False,
            gap_resolved=False,
        ),
    )
    assert item.value == ValueVerdict.SKIP.value
    assert "gap_kind_not_spec_meaning:fact_gap" in item.value_reasons
