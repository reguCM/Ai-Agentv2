from ai_tool.chat_interface.concept_resolution import (
    apply_concept_guidance_to_requirements,
    detect_unknown_concept,
)
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementCondition,
    RequirementDecomposition,
    validate_conditions,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.run_human_summary import build_human_summary, human_summary_markdown
from tools.ai.task_runtime import (
    AgentTaskRuntime,
    ClaimRecord,
    EvidenceRecord,
    GoalNode,
    InformationCertainty,
    TaskRecord,
)


def _runtime() -> AgentTaskRuntime:
    runtime = AgentTaskRuntime("certainty-test")
    runtime.add_goal(GoalNode("G1", "goal"))
    runtime.add_task(TaskRecord("T1", "G1", "task", "inspect", ["field confirmed"]))
    return runtime


def test_unverified_source_hint_does_not_establish_tool_gap():
    result = validate_conditions(
        [RequirementCondition("C1", "field confirmed", source_hint="invented.py")],
        available_tools=[],
    )
    assert result.status == "READY"
    assert not any(":tool_gap:" in item for item in result.validator_errors)


def test_verified_concept_index_path_overrides_llm_source_hint():
    resolution = detect_unknown_concept("runtime.tool_gap_countとは何ですか")
    requirement = RequirementDecomposition(
        [RequirementCondition("C1", "tool_gap_countの意味が確認できている", source_hint="guess.py")],
        "READY",
    )
    apply_concept_guidance_to_requirements(requirement, resolution)
    condition = requirement.conditions[0]
    assert condition.source_hint == resolution.look_first[0]
    assert condition.source_hint_certainty == "CONFIRMED"


def test_hypothesis_evidence_cannot_satisfy_completion():
    runtime = _runtime()
    runtime.add_evidence(
        EvidenceRecord(
            "E1", "local_review", "review://1", "maybe", "A1",
            certainty=InformationCertainty.HYPOTHESIS.value,
            verified=False,
        ),
        ["T1"],
    )
    runtime.support_completion_conditions("T1", "E1", ["field confirmed"])
    assert runtime.tasks["T1"].condition_status["field confirmed"] == "UNKNOWN"


def test_claim_without_evidence_is_not_confirmed():
    runtime = _runtime()
    claim = runtime.add_claim(
        ClaimRecord("CL1", "unsupported statement", "CONFIRMED", "local_llm", verified=True)
    )
    assert claim.verified is False


def test_observed_evidence_promotes_condition_to_confirmed_claim():
    runtime = _runtime()
    runtime.add_evidence(EvidenceRecord("E1", "file", "docs/x", "fact", "A1"), ["T1"])
    runtime.support_completion_conditions("T1", "E1", ["field confirmed"])
    assert runtime.tasks["T1"].condition_status["field confirmed"] == "SATISFIED"
    assert any(item.claim == "field confirmed" and item.verified for item in runtime.claims)


def test_local_review_fact_is_confirmed_only_when_observed_evidence_supports_it():
    orchestrator = ChatTaskOrchestrator("r1", "inspect repository")
    orchestrator.initialize()
    orchestrator.runtime.add_evidence(
        EvidenceRecord("E1", "file", "docs/x", "read_file is registered", "A1"),
        ["T1"],
    )
    orchestrator.record_local_review(
        {
            "structured_review": {
                "facts": ["read_file is registered", "another unsupported fact"],
                "problems": [],
            }
        }
    )
    claims = {item.claim: item for item in orchestrator.runtime.claims}
    assert claims["read_file is registered"].certainty == "CONFIRMED"
    assert claims["read_file is registered"].verified is True
    assert claims["another unsupported fact"].certainty == "UNVERIFIED"
    assert claims["another unsupported fact"].verified is False


def test_confirmed_claim_wins_over_same_hypothesis():
    runtime = _runtime()
    runtime.add_claim(ClaimRecord("CL1", "same claim", "HYPOTHESIS", "review"))
    runtime.add_evidence(EvidenceRecord("E1", "file", "docs/x", "fact", "A1"), ["T1"])
    runtime.add_claim(
        ClaimRecord("CL2", "same claim", "CONFIRMED", "file", ["E1"], verified=True)
    )
    effective = runtime.effective_claims()
    assert len(effective) == 1
    assert effective[0].certainty == "CONFIRMED"
    assert effective[0].verified is True


def test_unknown_concept_definition_task_precedes_original_task():
    resolution = detect_unknown_concept("runtime.tool_gap_countの原因を調べる")
    orchestrator = ChatTaskOrchestrator("r1", "runtime.tool_gap_countの原因を調べる", concept_resolution=resolution)
    orchestrator.initialize()
    assert orchestrator.current_task_id == "TC1"
    assert orchestrator.runtime.tasks["T1"].depends_on == ["TC1"]


def test_answer_gate_marks_unsupported_answer_unverified():
    orchestrator = ChatTaskOrchestrator("r1", "inspect repository")
    orchestrator.initialize()
    answer, gate = orchestrator.gate_answer("tool_gap_countは未登録Tool数です。")
    assert answer.startswith("【未確認】")
    assert gate["certainty"] == "UNVERIFIED"
    assert gate["verified"] is False


def test_human_summary_separates_confirmed_hypothesis_and_unverified():
    task_runtime = {
        "goals": [{"goal_id": "G1", "title": "goal", "parent_goal_id": None}],
        "tasks": [],
        "evidence": [],
        "replans": [],
        "local_reviews": [],
    }
    record = {
        "prompt": "prompt",
        "completion_coverage": {"completion_conditions": []},
        "claims": [
            {"claim": "confirmed", "certainty": "CONFIRMED", "source": "file", "evidence_ids": ["E1"], "verified": True},
            {"claim": "hypothesis", "certainty": "HYPOTHESIS", "source": "review", "evidence_ids": [], "verified": False},
            {"claim": "unknown", "certainty": "UNVERIFIED", "source": "llm", "evidence_ids": [], "verified": False},
        ],
        "runtime": {}, "tool": {}, "output": {}, "goal": {}, "evaluations": {},
    }
    summary = build_human_summary(record, task_runtime=task_runtime, turn={"tools": []})
    assert any(item["statement"] == "confirmed" for item in summary["learned"]["confirmed"])
    assert "hypothesis" in summary["learned"]["hypotheses"]
    assert any(item["statement"] == "unknown" for item in summary["learned"]["unverified"])
    markdown = human_summary_markdown(summary)
    assert "確定したこと" in markdown
    assert "仮説" in markdown
    assert "未確認" in markdown
