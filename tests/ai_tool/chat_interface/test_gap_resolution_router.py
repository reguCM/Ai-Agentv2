"""Phase 0 tests for gap resolution router and boundary grill-me applicability."""
from __future__ import annotations

from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityId,
    GapKind,
    GapRouterInput,
    build_router_input_from_orchestrator,
    classify_gap_kind,
    is_current_gap_resolved,
    route_gap_resolution,
    route_gap_resolution_from_orchestrator,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.skill_applicability import (
    GapContext,
    SkillArtifacts,
    UsabilityVerdict,
    ValueVerdict,
    resolve_skill_applicability,
    should_execute,
)
from tests.ai_tool.chat_interface.test_h4_selection_core import _observe_root_listing

README_E2E_REQUEST = (
    "README.md がワークスペースにあるか確認して、ファイルの先頭1行を報告してください。"
)
ROOT_WITHOUT_NAMED_FILE = [{"name": "AGENTS.md", "path": "AGENTS.md", "type": "file"}]
TETRIS_REQUEST = "Dedicated Sandbox 内に tetris/main.py を作って"


def _readme_orchestrator() -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("gap-readme", README_E2E_REQUEST)
    orchestrator.initialize()
    _observe_root_listing(orchestrator, ROOT_WITHOUT_NAMED_FILE)
    return orchestrator


def _tetris_orchestrator() -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("gap-tetris", TETRIS_REQUEST)
    orchestrator.initialize()
    return orchestrator


def test_readme_case_classifies_spec_meaning_gap():
    orchestrator = _readme_orchestrator()
    _, gate = orchestrator.gate_answer("存在しません")
    inp = build_router_input_from_orchestrator(
        orchestrator,
        stop_reason="COMPLETED",
        answer_gate=gate,
    )
    assert classify_gap_kind(inp) == GapKind.SPEC_MEANING_GAP
    assert inp.facts_sufficient is True


def test_readme_case_routes_goal_completion_human_not_grill_me():
    orchestrator = _readme_orchestrator()
    _, gate = orchestrator.gate_answer("存在しません")
    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason="COMPLETED",
        answer_gate=gate,
    )
    assert decision.gap_kind == GapKind.SPEC_MEANING_GAP.value
    assert decision.winner == CapabilityId.GOAL_COMPLETION_HUMAN.value
    grill = next(
        item for item in decision.candidates if item.id == CapabilityId.SKILL_GRILL_ME.value
    )
    assert grill.available is True
    assert decision.winner != CapabilityId.SKILL_GRILL_ME.value


def test_tetris_incomplete_classifies_fact_gap_and_routes_replan():
    orchestrator = _tetris_orchestrator()
    answer = "まだ実装中です"
    _, gate = orchestrator.gate_answer(answer)
    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason="COMPLETED",
        answer_gate=gate,
    )
    assert decision.gap_kind == GapKind.FACT_GAP.value
    assert decision.winner in {
        CapabilityId.TOOL_EVIDENCE.value,
        CapabilityId.REPLAN.value,
        CapabilityId.RECOVERY.value,
    }
    assert CapabilityId.SKILL_GRILL_ME.value not in {
        item.id for item in decision.candidates
    }


def test_initial_grill_artifacts_do_not_resolve_current_fact_gap():
    orchestrator = _tetris_orchestrator()
    _, gate = orchestrator.gate_answer("未完了")
    inp = build_router_input_from_orchestrator(
        orchestrator,
        stop_reason="COMPLETED",
        answer_gate=gate,
    )
    inp.artifact_kinds = {"ambiguity_report", "prd", "tech_spec"}
    resolved, reasons = is_current_gap_resolved(inp, gap_kind=GapKind.FACT_GAP)
    assert resolved is False
    assert reasons == []


def test_boundary_grill_me_not_skipped_only_because_initial_grill_artifacts_exist():
    artifacts = SkillArtifacts({"ambiguity_report", "prd"})
    gap_context = GapContext(
        kind="spec_meaning_gap",
        facts_sufficient=True,
        gap_resolved=False,
    )
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
        artifacts=artifacts,
        composition_steps=["grill-me"],
        gap_context=gap_context,
    )
    assert "artifact_already_satisfied" not in item.value_reasons
    assert item.usability == UsabilityVerdict.USABLE.value
    assert item.value == ValueVerdict.USE.value


def test_boundary_grill_me_skips_when_gap_resolved_by_human_decision():
    artifacts = SkillArtifacts({"ambiguity_report"})
    gap_context = GapContext(
        kind="spec_meaning_gap",
        facts_sufficient=True,
        gap_resolved=True,
    )
    item = resolve_skill_applicability(
        "grill-me",
        request=README_E2E_REQUEST,
        consumer="local_agent",
        artifacts=artifacts,
        composition_steps=["grill-me"],
        gap_context=gap_context,
    )
    assert item.value == ValueVerdict.SKIP.value
    assert "gap_resolved_by_confirmed_spec_or_human_decision" in item.value_reasons
    assert not should_execute(item)


def test_explicit_conditions_resolve_spec_meaning_gap_not_fact_gap():
    inp = GapRouterInput(
        request="probe",
        answer_gate={"verified": False, "reason": "completion_evidence_incomplete"},
        goal_incomplete=True,
        user_explicit_conditions=[
            "local_state/part_a.txt の先頭1行を read_file で読み取り、内容を報告する",
            "local_state/part_b.txt の先頭1行を read_file で読み取り、内容を報告する",
        ],
    )
    spec_resolved, spec_reasons = is_current_gap_resolved(
        inp,
        gap_kind=GapKind.SPEC_MEANING_GAP,
    )
    fact_resolved, fact_reasons = is_current_gap_resolved(
        inp,
        gap_kind=GapKind.FACT_GAP,
    )
    assert spec_resolved is True
    assert "user_explicit_completion_conditions" in spec_reasons
    assert fact_resolved is False
    assert fact_reasons == []


def test_partial_explicit_fact_gap_stays_open_and_routes_continuation():
    condition_a = (
        "local_state/_goal_continuation_live_probe/part_a.txt の先頭1行を "
        "read_file で読み取り、内容を報告する"
    )
    condition_b = (
        "local_state/_goal_continuation_live_probe/part_b.txt の先頭1行を "
        "read_file で読み取り、内容を報告する"
    )
    request = (
        "partial explicit probe。次を完了してください。\n"
        f"1. {condition_a}\n"
        f"2. {condition_b}"
    )
    orchestrator = ChatTaskOrchestrator(
        "partial-explicit",
        request,
        completion_conditions=[condition_a, condition_b],
    )
    orchestrator.user_explicit_conditions = [condition_a, condition_b]
    orchestrator.initialize()
    from tools.ai.task_runtime import EvidenceRecord, InformationCertainty

    orchestrator.runtime.add_evidence(
        EvidenceRecord(
            evidence_id="E1",
            source_type="tool_result",
            source="tool://read_file",
            summary="GC-LIVE-PART-A-LINE1",
            created_by_action="A1",
            tool_name="read_file",
            target="local_state/_goal_continuation_live_probe/part_a.txt",
            certainty=InformationCertainty.OBSERVED.value,
            verified=True,
            task_ids=["T1"],
        ),
        ["T1"],
    )
    orchestrator.runtime.support_completion_conditions("T1", "E1", [condition_a])
    _, gate = orchestrator.gate_answer("part_a only")
    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason="COMPLETED",
        answer_gate=gate,
    )
    assert decision.gap_kind == GapKind.FACT_GAP.value
    assert decision.gap_resolved is False
    assert decision.winner in {
        CapabilityId.TOOL_EVIDENCE.value,
        CapabilityId.RECOVERY.value,
        CapabilityId.REPLAN.value,
    }


def test_goal_completion_consumed_resolves_current_gap():
    orchestrator = _readme_orchestrator()
    orchestrator.goal_completion_consumed = True
    inp = build_router_input_from_orchestrator(
        orchestrator,
        stop_reason="GOAL_COMPLETION_JUDGED",
        answer_gate={"verified": False, "reason": "awaiting_goal_completion_human"},
    )
    resolved, reasons = is_current_gap_resolved(inp, gap_kind=GapKind.SPEC_MEANING_GAP)
    assert resolved is True
    assert "goal_completion_human_decision_applied" in reasons


def test_stagnation_exhausted_routes_help():
    inp = GapRouterInput(
        request="audit",
        stop_reason="STAGNATION_LIMIT",
        answer_gate={"verified": False, "reason": "completion_evidence_incomplete"},
        goal_incomplete=True,
    )
    decision = route_gap_resolution(inp)
    assert decision.gap_kind == GapKind.STAGNATION_EXHAUSTED.value
    assert decision.winner == CapabilityId.HELP.value


def test_capability_gap_routes_human_approval():
    inp = GapRouterInput(
        request="edit repo",
        stop_reason="APPROVAL_REQUIRED",
        answer_gate={"verified": False},
        has_confirmed_tool_gaps_approval=True,
    )
    decision = route_gap_resolution(inp)
    assert decision.gap_kind == GapKind.CAPABILITY_GAP.value
    assert decision.winner == CapabilityId.HUMAN_APPROVAL.value
