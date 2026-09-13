from __future__ import annotations

import json
from types import SimpleNamespace
from ai_tool.chat_interface.capability_resolution import next_capability_action, resolve_capability
from ai_tool.chat_interface.concept_resolution import load_workspace_index
from ai_tool.chat_interface.task_orchestration import (
    ChatTaskOrchestrator,
    build_tool_expectation,
)
from ai_tool.chat_interface.workspace_read_bridge import (
    READ_FILE_INITIAL_LINE_LIMIT,
    READ_FILE_LLM_CONTEXT_CHAR_BUDGET,
    prepare_tool_result_for_llm,
    read_file_llm_delivery,
    runtime_initial_read_arguments,
)
from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from tools.file.workspace.read_file import read_file


INDEX = load_workspace_index()
REGISTRY = load_registry_tools()


def _task(text: str, task_id: str = "T1"):
    return SimpleNamespace(
        task_id=task_id,
        title=text,
        instruction=text,
        completion_conditions=["relevant evidence observed"],
    )


def _tool(name: str, capability: str, visibility: str = "agent"):
    return {
        "name": name,
        "category": "file",
        "subcategory": "workspace",
        "capabilities": [capability],
        "visibility": visibility,
        "side_effect": "read-only",
        "module": f"tools.fake.{name}",
        "function": name,
        "input": {
            "path": {"type": "string", "required": True},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
    }


def test_next_capability_action_uses_bounded_initial_read():
    task = _task("PROJECT_SPEC.mdを読んで最初の目的を要約して")
    resolution = resolve_capability(
        task,
        capability="workspace_file_read",
        capability_index=INDEX,
        registry_tools=[_tool("read_file", "workspace_file_read")],
    )
    action = next_capability_action(
        resolution,
        task,
        INDEX["capabilities"]["workspace_file_read"],
    )
    assert action == {
        "tool": "read_file",
        "arguments": {
            "path": "PROJECT_SPEC.md",
            "offset": 1,
            "limit": READ_FILE_INITIAL_LINE_LIMIT,
        },
    }


def test_build_tool_expectation_includes_bounded_read():
    tools = [_tool("read_file", "workspace_file_read")]
    expectation = build_tool_expectation(
        "docs/notes.mdを読んで確認して",
        tools,
    )
    assert expectation.expected_tool == "read_file"
    assert expectation.expected_arguments == runtime_initial_read_arguments("docs/notes.md")


def test_case2_bounded_read_covers_project_purpose_without_full_file():
    result = read_file("PROJECT_SPEC.md", offset=1, limit=READ_FILE_INITIAL_LINE_LIMIT)
    assert result["ok"] is True
    assert result["has_more"] is True
    text = "\n".join(str(row.get("text") or "") for row in result["lines"])
    assert "Project Purpose" in text
    assert "local AI Agent" in text
    llm_payload = prepare_tool_result_for_llm("read_file", result)
    serialized = json.dumps(llm_payload, ensure_ascii=False)
    assert len(serialized) <= READ_FILE_LLM_CONTEXT_CHAR_BUDGET + 500
    assert llm_payload.get("has_more") is True


def test_read_file_continuation_scheduled_when_evidence_insufficient():
    orchestrator = ChatTaskOrchestrator("r", "read tail section")
    orchestrator.initialize()
    tools = [_tool("read_file", "workspace_file_read")]
    orchestrator.configure_tool_expectation(tools, registry_tools=tools)
    orchestrator.task.completion_conditions = [
        "Section 16. Design Status must be confirmed from the file"
    ]
    partial = {
        "ok": True,
        "status": "success",
        "path": "PROJECT_SPEC.md",
        "total_lines": 377,
        "offset": 1,
        "limit": READ_FILE_INITIAL_LINE_LIMIT,
        "returned_lines": READ_FILE_INITIAL_LINE_LIMIT,
        "lines": [{"line": 1, "text": "# AI Agent Project Specification"}],
        "has_more": True,
        "next_offset": READ_FILE_INITIAL_LINE_LIMIT + 1,
        "truncated": False,
    }
    orchestrator.observe_tool(
        "read_file",
        runtime_initial_read_arguments("PROJECT_SPEC.md"),
        partial,
        {"ok": True, "status": "success"},
        relevant_tools=["read_file"],
        raw_result=partial,
    )
    continuation = orchestrator.pending_observation_continuation()
    assert continuation is not None
    assert continuation["tool"] == "read_file"
    assert continuation["arguments"]["offset"] == READ_FILE_INITIAL_LINE_LIMIT + 1


def test_read_file_continuation_skipped_when_generic_evidence_sufficient():
    orchestrator = ChatTaskOrchestrator("r", "PROJECT_SPEC.mdを読んで最初の目的を要約して")
    orchestrator.initialize()
    tools = [_tool("read_file", "workspace_file_read")]
    orchestrator.configure_tool_expectation(tools, registry_tools=tools)
    bounded = read_file("PROJECT_SPEC.md", offset=1, limit=READ_FILE_INITIAL_LINE_LIMIT)
    orchestrator.observe_tool(
        "read_file",
        runtime_initial_read_arguments("PROJECT_SPEC.md"),
        bounded,
        {"ok": True, "status": "success"},
        relevant_tools=["read_file"],
        raw_result=bounded,
    )
    assert orchestrator.pending_observation_continuation() is None


def test_direct_read_file_tool_result_unchanged_when_small():
    result = read_file("PROJECT_SPEC.md", offset=1, limit=5)
    guarded = prepare_tool_result_for_llm("read_file", result)
    assert guarded == result


def test_context_guard_preserves_partial_continuation_metadata():
    full = read_file("PROJECT_SPEC.md")
    guarded = prepare_tool_result_for_llm("read_file", full)
    assert guarded is not full
    assert guarded["truncated"] is True
    assert guarded["has_more"] is True
    assert guarded["next_offset"] is not None
    assert any(
        str(item.get("code") or "") == "llm_context_guard"
        for item in guarded.get("warnings") or []
        if isinstance(item, dict)
    )
    serialized = json.dumps(guarded, ensure_ascii=False)
    assert len(serialized) <= READ_FILE_LLM_CONTEXT_CHAR_BUDGET + 200


def _synthetic_long_page(path: str = "big.md", *, offset: int = 1, limit: int = 50) -> dict:
    lines = [{"line": offset + index, "text": "x" * 200} for index in range(limit)]
    end_line = offset + limit - 1
    return {
        "ok": True,
        "status": "success",
        "path": path,
        "offset": offset,
        "limit": limit,
        "returned_lines": limit,
        "total_lines": 200,
        "has_more": True,
        "next_offset": end_line + 1,
        "truncated": False,
        "lines": lines,
        "warnings": [],
    }


def test_guard_next_offset_matches_last_presented_line_not_tool_page_end():
    fetched = _synthetic_long_page()
    assert fetched["returned_lines"] == 50
    assert fetched["next_offset"] == 51

    guarded = prepare_tool_result_for_llm("read_file", fetched)
    delivery = read_file_llm_delivery(fetched)

    presented_lines = [int(row["line"]) for row in guarded["lines"]]
    assert presented_lines
    assert presented_lines == list(
        range(presented_lines[0], presented_lines[-1] + 1)
    )
    assert guarded["next_offset"] == presented_lines[-1] + 1
    assert guarded["next_offset"] < fetched["next_offset"]
    assert delivery["next_offset"] == guarded["next_offset"]
    assert delivery["presented_line_end"] == presented_lines[-1]
    assert delivery["guard_applied"] is True
    assert delivery["has_more"] is True


def test_orchestrator_continuation_uses_guard_aligned_offset():
    orchestrator = ChatTaskOrchestrator("guard-gap", "big.md の後半を確認")
    orchestrator.initialize()
    tools = [_tool("read_file", "workspace_file_read")]
    orchestrator.configure_tool_expectation(tools, registry_tools=tools)
    orchestrator.task.completion_conditions = [
        "Section 16. Design Status must be confirmed from the file"
    ]
    fetched = _synthetic_long_page()
    delivery = read_file_llm_delivery(fetched)

    orchestrator.observe_tool(
        "read_file",
        runtime_initial_read_arguments("big.md"),
        fetched,
        {"ok": True, "status": "success"},
        relevant_tools=["read_file"],
        raw_result=fetched,
    )
    continuation = orchestrator.pending_observation_continuation()
    assert continuation is not None
    assert continuation["arguments"]["offset"] == delivery["next_offset"]
    assert continuation["arguments"]["offset"] != fetched["next_offset"]


def test_guard_inactive_preserves_original_next_offset():
    result = read_file("PROJECT_SPEC.md", offset=1, limit=5)
    delivery = read_file_llm_delivery(result)
    assert delivery["guard_applied"] is False
    assert delivery["next_offset"] == result["next_offset"]
    assert delivery["presented_line_count"] == result["returned_lines"]


def test_direct_read_file_without_runtime_bridge_keeps_explicit_limit():
    result = read_file("PROJECT_SPEC.md", offset=1, limit=3)
    assert result["ok"] is True
    assert result["returned_lines"] == 3
    assert result["limit"] == 3
    assert prepare_tool_result_for_llm("read_file", result) == result
