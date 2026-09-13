from pathlib import Path

from ai_tool.agent_test_runner import record_run, run_markdown
from ai_tool.chat_interface.concept_resolution import (
    ConceptResolution,
    definition_conditions,
    definition_hint,
    detect_unknown_concept,
    filter_definition_first_conditions,
    load_workspace_index,
    next_definition_action,
    observe_definition_result,
    apply_concept_guidance_to_requirements,
)
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementCondition,
    RequirementDecomposition,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator


def _tools():
    return [
        {"name": "read_file", "visibility": "agent"},
        {"name": "search_files", "visibility": "agent"},
        {"name": "list_files", "visibility": "agent"},
    ]


def test_tool_gap_count_is_routed_by_concept_index():
    row = detect_unknown_concept("runtime.tool_gap_count の意味を確認する")
    assert row.index_hit is True
    assert row.concept == "runtime.tool_gap_count"
    assert row.look_first[0] == "ai_tool/agent_test_runner.py"


def test_index_look_first_is_selected_before_workspace_search():
    row = detect_unknown_concept("runtime.tool_gap_count を調べる")
    assert next_definition_action(row) == (
        "read_file",
        {"path": "ai_tool/agent_test_runner.py"},
    )


def test_unknown_identifier_falls_back_to_exact_search():
    row = detect_unknown_concept("project_private_counter を確認する")
    assert row.index_hit is False
    assert next_definition_action(row) == (
        "search_files",
        {"query": "project_private_counter", "path": "."},
    )


def test_causal_guess_is_deferred_until_definition_is_known():
    row = detect_unknown_concept("runtime.tool_gap_count を調べる")
    conditions = filter_definition_first_conditions(
        [
            "tool_gap_countの意味が確認できている",
            "tool_gap_countの計算ロジックにbugがある",
        ],
        row,
    )
    assert conditions == ["tool_gap_countの意味が確認できている"]
    assert row.deferred_conditions == ["tool_gap_countの計算ロジックにbugがある"]


def test_unknown_concept_does_not_create_a_tool_gap():
    row = detect_unknown_concept("runtime.tool_gap_count を確認する")
    orchestrator = ChatTaskOrchestrator(
        "turn",
        "runtime.tool_gap_count を確認する",
        completion_conditions=["tool_gap_countの意味が確認できている"],
        concept_resolution=row,
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(_tools())
    assert orchestrator.detect_required_tool_gap(_tools()) is None
    assert orchestrator.runtime.tool_gaps == {}
    assert orchestrator.tool_expectation.expected_tool == "read_file"


def test_definition_evidence_returns_to_original_task():
    row = detect_unknown_concept("runtime.tool_gap_count を確認する")
    orchestrator = ChatTaskOrchestrator(
        "turn",
        "runtime.tool_gap_count を確認する",
        completion_conditions=["tool_gap_countの意味が確認できている"],
        concept_resolution=row,
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(_tools())
    orchestrator.observe_tool(
        "read_file",
        {"path": "ai_tool/agent_test_runner.py"},
        {"status": "success"},
        {},
        relevant_tools=["read_file"],
        raw_result={"lines": [{"line": 1, "text": '"tool_gap_count": len(task_runtime.get("tool_gaps") or [])'}]},
    )
    assert orchestrator.current_task_id == "TC1"
    assert orchestrator.tool_expectation.expected_arguments == {"path": "tools/ai/task_runtime.py"}
    orchestrator.observe_tool(
        "read_file",
        {"path": "tools/ai/task_runtime.py"},
        {"status": "success"},
        {},
        relevant_tools=["read_file"],
        raw_result={"lines": [{"line": 1, "text": "self.tool_gaps[needle] = gap"}]},
    )
    assert row.resolution_status == "RESOLVED"
    assert row.returned_to_original_task is True
    assert len(row.evidence_ids) == 2
    assert orchestrator.runtime.tasks["T1"].evidence_ids
    assert orchestrator.runtime.tasks["T2"].evidence_ids
    assert orchestrator.current_task_id == "T2"
    assert "resolved_definition" in definition_hint(row)


def test_index_contains_only_existing_files():
    catalog = load_workspace_index()
    for group in ("categories", "concepts"):
        for item in catalog[group].values():
            assert all(Path(path).is_file() for path in item["look_first"])


def test_not_found_definition_is_structured_and_does_not_raise():
    row = ConceptResolution(
        detected=True,
        concept="missing_identifier",
        resolution_status="RESOLVING",
        search_terms=["missing_identifier"],
        fallback_tool="search_files",
    )
    excerpt = observe_definition_result(
        row,
        tool_name="search_files",
        arguments={"query": "missing_identifier", "path": "."},
        content="",
    )
    assert excerpt is None
    assert row.resolution_status == "NOT_FOUND"
    assert next_definition_action(row) is None


def test_definition_conditions_are_verifiable_outcomes_not_tool_actions():
    row = detect_unknown_concept("runtime.tool_gap_count を確認する")
    conditions = definition_conditions(row)
    assert conditions
    assert all("確認できている" in item for item in conditions)
    assert all(not item.startswith(("read_file", "search_files")) for item in conditions)


def test_guessed_requirement_paths_are_replaced_and_false_tool_gap_is_suppressed():
    row = detect_unknown_concept("runtime.tool_gap_count を確認する")
    requirement = RequirementDecomposition(
        [
            RequirementCondition(
                "C1",
                "tool_gap_countの更新条件が確認できている",
                source_hint="invented_counter.py",
            )
        ],
        "TOOL_GAP",
        ["C1:tool_gap:invented_counter.py"],
        "pathを指定してください",
    )
    result = apply_concept_guidance_to_requirements(requirement, row)
    assert result.status == "READY"
    assert result.conditions[0].source_hint == "ai_tool/agent_test_runner.py"
    assert "invented_counter.py" not in result.conditions[0].source_hint


def test_human_summary_contains_concept_resolution_result():
    concept = detect_unknown_concept("runtime.tool_gap_count を確認する")
    concept.files_checked = list(concept.look_first)
    concept.resolution_status = "RESOLVED"
    concept.resolved_definition = '"tool_gap_count": len(tool_gaps)'
    concept.returned_to_original_task = True
    turn = {
        "answer": "定義を確認しました",
        "tools": [],
        "events": [],
        "task_runtime": {
            "current_task_id": "T1",
            "goals": [{"goal_id": "G1", "title": "定義確認", "parent_goal_id": None, "status": "complete"}],
            "tasks": [{"task_id": "T1", "title": "定義確認", "status": "complete", "completion_conditions": ["定義済み"], "condition_status": {"定義済み": "SATISFIED"}, "condition_evidence": {"定義済み": ["E1"]}}],
            "actions": [],
            "evidence": [{"evidence_id": "E1", "summary": "len(tool_gaps)"}],
            "failures": [],
            "replans": [],
            "tool_gaps": [],
            "events": [],
            "concept_resolution": concept.as_dict(),
        },
        "final_llm_lifecycle": {"final_llm_response_received": True, "final_llm_response_empty": False},
    }
    record = record_run(
        {"test_case_id": "concept", "prompt": "定義確認", "expected": {}},
        turn,
        run_id="concept-1",
        started_at="a",
        finished_at="b",
        duration_ms=1,
        git_metadata={"available": False},
    )
    summary = record["human_summary"]["concept_resolution"]
    assert summary["concept"] == "runtime.tool_gap_count"
    report = run_markdown(record)
    assert "## 未知概念の確認" in report
    assert '分かった意味: "tool_gap_count": len(tool_gaps)' in report
