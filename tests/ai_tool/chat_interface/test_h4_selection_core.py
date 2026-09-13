"""H4 Core regression: request → Index capability → Registry/Help Tool → bridge/sandbox."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.chat_interface.capability_resolution import (
    MultipleCapabilitiesError,
    confirmed_read_path_grounds,
    infer_required_capability,
    list_files_directory_path,
    required_capabilities,
    resolve_capabilities,
    resolve_capability,
)
from ai_tool.chat_interface.concept_resolution import load_workspace_index
from ai_tool.chat_interface.task_orchestration import (
    ChatTaskOrchestrator,
    confirm_interchangeable_paths,
    fold_search_candidate_set,
    match_clarification_to_candidate_paths,
    resolve_search_read_target,
    search_candidate_hint,
)
from ai_tool.chat_interface.workspace_read_bridge import runtime_initial_read_arguments
from ai_tool.help import h1_service


INDEX = load_workspace_index()
REGISTRY = load_registry_tools()


def _task(text: str, task_id: str = "T1"):
    return SimpleNamespace(task_id=task_id, title=text, instruction=text, completion_conditions=[])


def _caps(text: str) -> list[str]:
    return required_capabilities(
        _task(text), capability_index=INDEX, registry_tools=REGISTRY
    )


def _resolved(text: str):
    return resolve_capabilities(
        _task(text), capability_index=INDEX, registry_tools=REGISTRY
    )


def test_index_tools_are_agent_visible_registry_names():
    registry = {item["name"]: item for item in REGISTRY}
    for spec in INDEX["capabilities"].values():
        for name in spec.get("tools") or []:
            assert name in registry
            assert registry[name].get("visibility") == "agent"


def test_write_side_look_first_remaining_does_not_block_index_load():
    assert INDEX["schema_version"] == 2
    for name in (
        "workspace_file_write",
        "workspace_file_edit",
        "workspace_file_create",
        "command_execution",
        "test_execution",
    ):
        assert INDEX["capabilities"][name].get("look_first")


def test_justified_mutation_classifies_edit_or_create():
    edit_shared_object_only = [
        "ログファイルを編集して",
        "ファイルを編集して",
        "設定ファイルを書き換えて",
    ]
    create_cases = [
        "バックアップファイルを作って",
        "新しいファイルを作って",
        "新規ファイルを作る",
    ]
    for text in edit_shared_object_only:
        found = _caps(text)
        assert found == ["workspace_file_edit"], text
    # 「テキスト」は read_file 側 exclusive。「ファイルを書き換え」は edit exclusive。
    # Q6: 両側 exclusive なら両方残す（共有ファイルへの prefer ではない）。
    text_rewrite = _caps("テキストファイルを書き換えて")
    assert "workspace_file_edit" in text_rewrite
    assert "workspace_file_read" in text_rewrite
    for text in create_cases:
        found = _caps(text)
        assert "workspace_file_create" in found, text
        assert "workspace_file_edit" not in found, text
        assert "workspace_file_read" not in found, text


def test_write_side_not_selected_for_profile_bare_verb_and_audit_file():
    for text in (
        "ユーザープロファイルを編集",
        "プロファイル情報を更新",
        "設定を編集して",
        "文章を作って",
        "ファイルを確認して",
        "既存コードを修正する",
    ):
        found = _caps(text)
        assert "workspace_file_edit" not in found, text
        assert "workspace_file_create" not in found, text
        assert "workspace_file_write" not in found, text


def test_pathless_file_read_has_no_next_action():
    rows = _resolved("ファイルを読んで")
    assert [item.required_capability for item in rows] == ["workspace_file_read"]
    assert rows[0].selected_tool == "read_file"
    assert rows[0].status == "RESOLVED"
    assert rows[0].next_action is None


def test_registry_tools_json_read_bridges_that_path():
    rows = _resolved("registry/tools.json を読んで")
    assert [item.required_capability for item in rows] == ["workspace_file_read"]
    assert rows[0].next_action == {
        "tool": "read_file",
        "arguments": runtime_initial_read_arguments("registry/tools.json"),
    }


def test_shared_search_keyword_skips_unusable_web_search():
    found = _caps("検索して")
    assert found == ["workspace_file_search"]
    web = resolve_capability(
        _task("検索して"),
        capability="web_search",
        capability_index=INDEX,
        registry_tools=REGISTRY,
    )
    assert web.candidate_tools == ["search_web"]
    assert web.next_action is None


def test_unreachable_web_search_does_not_veto_file_search():
    file_tool = dict(next(item for item in REGISTRY if item["name"] == "search_files"))
    web_tool = dict(next(item for item in REGISTRY if item["name"] == "search_web"))
    web_tool["visibility"] = "pipeline"
    registry = [file_tool, web_tool]
    found = required_capabilities(
        _task("検索して"), capability_index=INDEX, registry_tools=registry
    )
    assert found == ["workspace_file_search"]
    rows = resolve_capabilities(
        _task("検索して"), capability_index=INDEX, registry_tools=registry
    )
    assert [item.required_capability for item in rows] == ["workspace_file_search"]
    assert rows[0].selected_tool == "search_files"
    assert "query" in rows[0].unresolved_arguments
    assert "query" not in rows[0].resolved_arguments
    assert rows[0].next_action is None


def test_file_search_does_not_add_web_search():
    found = _caps("ファイル検索")
    assert found == ["workspace_file_search"]
    assert "web_search" not in found
    assert "workspace_file_read" not in found


def test_explicit_uri_selects_url_fetch_not_workspace_path():
    found = _caps("https://example.com/docs")
    assert "url_fetch" in found
    assert "workspace_file_read" not in found


def test_generic_gpu_prefers_device_and_process_exclusive_is_process_only():
    generic = _caps("gpu の状態を確認する")
    assert generic == ["gpu_device_observation"]
    process = _caps("GPUプロセスを見て")
    assert process == ["gpu_process_observation"]
    device = _caps("GPUの温度を見て")
    assert device == ["gpu_device_observation"]
    both = _caps("GPUの温度とプロセスを見て")
    assert "gpu_device_observation" in both
    assert "gpu_process_observation" in both


def test_file_anchored_mutation_does_not_keep_prefer_read():
    found = _caps("ログファイルを編集して")
    assert found == ["workspace_file_edit"]


def test_cpu_observation_is_candidates_available_without_selected_tool():
    rows = _resolved("CPU を見て")
    assert len(rows) == 1
    assert rows[0].required_capability == "cpu_observation"
    assert rows[0].status == "CANDIDATES_AVAILABLE"
    assert rows[0].selected_tool is None
    assert set(rows[0].candidate_tools) == {"get_cpu_status", "cpu_status"}


def test_usage_rate_alone_does_not_pick_one_family():
    found = _caps("使用率")
    assert found, "shared keyword must not collapse to [] before tool reachability"
    assert len(found) >= 2
    assert found != ["gpu_device_observation"]
    assert found != ["cpu_observation"]


def test_web_generic_request_selects_web_search():
    assert _caps("web の情報を調べる") == ["web_search"]


def test_shared_file_prefers_workspace_file_read():
    assert _caps("ファイル") == ["workspace_file_read"]


def test_two_plus_candidates_are_not_ranked():
    result = resolve_capability(
        _task("ファイルの内容を読む"),
        capability="workspace_file_read",
        capability_index=INDEX,
        registry_tools=[
            {
                "name": "read_file",
                "capabilities": ["workspace_file_read"],
                "visibility": "agent",
                "module": "tools.file.workspace.read_file",
                "function": "read_file",
                "input": {"path": {"type": "string"}},
            },
            {
                "name": "read_text",
                "capabilities": ["workspace_file_read"],
                "visibility": "agent",
                "module": "tools.fake.read_text",
                "function": "read_text",
                "input": {},
            },
        ],
    )
    assert result.status == "CANDIDATES_AVAILABLE"
    assert result.selected_tool is None
    assert result.candidate_tools == ["read_file", "read_text"]


def test_empty_tools_capability_gap_does_not_execute_suggested():
    result = resolve_capability(
        _task("pytestを実行する"),
        capability="test_execution",
        capability_index=INDEX,
        registry_tools=REGISTRY,
    )
    assert result.status == "NO_MATCH"
    assert result.selected_tool is None
    assert result.suggested_minimal_tool == "run_tests"
    assert result.next_action is None


def test_singular_api_errors_when_two_capabilities():
    task = _task("GPUの温度とプロセスを見て")
    found = required_capabilities(task, capability_index=INDEX, registry_tools=REGISTRY)
    assert len(found) >= 2
    try:
        infer_required_capability(task, capability_index=INDEX, registry_tools=REGISTRY)
    except MultipleCapabilitiesError:
        return
    raise AssertionError("singular API folded multiple capabilities")


def test_list_is_not_the_unique_capability_for_file_object():
    found = _caps("ファイルを読んで")
    assert found != ["workspace_file_list"]
    rows = _resolved("ファイルを読んで")
    assert not any(item.selected_tool == "list_files" and item.next_action for item in rows)


def test_dual_mutation_resolutions_start_sandbox_without_required_name():
    orchestrator = ChatTaskOrchestrator(
        "h4-f10", "ログファイルを編集して新しいファイルを作って"
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    rows = orchestrator._task_resolutions()
    mutation = [
        item.selected_tool
        for item in rows
        if item.status == "RESOLVED"
        and item.selected_tool in {"edit_file", "create_file"}
    ]
    assert sorted(mutation) == ["create_file", "edit_file"]
    assert all(
        rows[index].selected_tool is None or len([rows[index].selected_tool]) == 1
        for index in range(len(rows))
    )
    assert orchestrator.requires_dedicated_sandbox() is True
    assert orchestrator.required_mutation_tool() is None


def test_pathless_read_does_not_inject_pending_action():
    orchestrator = ChatTaskOrchestrator("h4-f4", "ファイルを読んで")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    assert orchestrator.pending_capability_action() is None
    assert orchestrator.pending_definition_action() is None


def test_registry_path_read_injects_single_pending_action():
    orchestrator = ChatTaskOrchestrator("h4-f5", "registry/tools.json を読んで")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    assert orchestrator.pending_definition_action() is None
    assert orchestrator.pending_capability_action() == {
        "tool": "read_file",
        "arguments": runtime_initial_read_arguments("registry/tools.json"),
    }


def test_exclusion_table_does_not_change_help_match_query():
    source = inspect.getsource(h1_service._match_query)
    assert "match_exclusions" not in source
    assert "プロファイル" not in source
    result = h1_service.search("edit_file")
    names = {item.get("name") for item in result.get("tools") or []}
    assert "edit_file" in names


def test_audit_registry_look_first_selects_registry_read():
    assert _caps("pytest実行Capabilityが存在するかRegistryを調査してください") == [
        "registry_read"
    ]


def test_search_files_keeps_query_unresolved_without_inventing_value():
    rows = _resolved("検索して")
    search = next(
        item for item in rows if item.required_capability == "workspace_file_search"
    )
    assert search.selected_tool == "search_files"
    assert search.resolved_arguments.get("path") == "."
    assert "query" in search.unresolved_arguments
    assert "query" not in search.resolved_arguments
    assert search.next_action is None


def test_grid_search_goal_resolves_literal_query():
    text = "gridを検索して、その内容を要約してほしい。"
    found = _caps(text)
    assert found == ["workspace_file_search"]
    rows = _resolved(text)
    search = next(
        item for item in rows if item.required_capability == "workspace_file_search"
    )
    assert search.selected_tool == "search_files"
    assert search.resolved_arguments.get("query") == "grid"
    assert "query" not in search.unresolved_arguments
    assert search.next_action == {
        "tool": "search_files",
        "arguments": {"query": "grid", "path": "."},
    }


def test_goal_state_labels_do_not_use_orchestrator_title_as_query():
    task = SimpleNamespace(
        task_id="T1",
        title="Observe the facts required by the request",
        instruction=(
            "Goal:\n"
            "gridを検索して、その内容を要約してほしい。\n\n"
            "Current State:\n"
            "まだ何も調査していない。\n"
        ),
        completion_conditions=[],
    )
    rows = resolve_capabilities(
        task, capability_index=INDEX, registry_tools=REGISTRY
    )
    search = next(
        item for item in rows if item.required_capability == "workspace_file_search"
    )
    assert search.resolved_arguments.get("query") == "grid"
    assert search.next_action["arguments"]["query"] == "grid"


def test_unresolved_section_quotes_do_not_become_query():
    task = SimpleNamespace(
        task_id="T1",
        title="Observe the facts required by the request",
        instruction=(
            "Goal:\n検索してほしい。\n\n"
            "Current State:\nまだ何も調査していない。\n\n"
            "現在の未解決点:\n例: \"ID\", \"名前\"\n"
        ),
        completion_conditions=[],
    )
    rows = resolve_capabilities(
        task, capability_index=INDEX, registry_tools=REGISTRY
    )
    search = next(
        item for item in rows if item.required_capability == "workspace_file_search"
    )
    assert "query" in search.unresolved_arguments
    assert search.next_action is None


def test_incomplete_search_does_not_inject_pending_action():
    orchestrator = ChatTaskOrchestrator("h4-search-params", "検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    assert orchestrator.pending_capability_action() is None
    caps = [
        item.required_capability
        for item in orchestrator._task_resolutions()
        if item.required_capability
    ]
    assert caps == ["workspace_file_search"]
    assert orchestrator.tool_expectation.generated is False


def test_literal_search_object_injects_pending_search_files():
    request = (
        "Goal:\n"
        "gridを検索して、その内容を要約してほしい。\n\n"
        "Current State:\n"
        "まだ何も調査していない。\n"
    )
    orchestrator = ChatTaskOrchestrator("h4-search-query", request)
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    assert orchestrator.pending_capability_action() == {
        "tool": "search_files",
        "arguments": {"query": "grid", "path": "."},
    }


def test_scan_limit_continues_search_and_does_not_first_hit_read():
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator("h4-search-continue", request)
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    first = orchestrator.pending_capability_action()
    assert first == {"tool": "search_files", "arguments": {"query": "grid", "path": "."}}
    raw = {
        "ok": True,
        "status": "partial",
        "query": "grid",
        "matches": [
            {"path": "ai_tool/example.py", "line": 1, "text": "grid"},
        ],
        "has_more": True,
        "next_cursor": "ai_tool/example.py",
        "last_scanned_path": "ai_tool/example.py",
        "files_scanned": 200,
        "warnings": [
            {
                "code": "scan_limit_reached",
                "message": "走査ファイル数が上限に達したため打ち切りました",
            }
        ],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "partial", "error": None, "warnings": raw["warnings"]},
        {"query": "grid", "hit_count": 1},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    assert orchestrator.search_observations[-1]["status"] == "INCOMPLETE_OBSERVATION"
    assert orchestrator.search_observations[-1]["confirmed_absent"] is False
    candidate = orchestrator.search_candidate_sets[("grid", ".")]
    assert candidate["substring_cardinality"] == "INCOMPLETE_SCAN"
    assert candidate["unique_path_count"] == 1
    assert candidate["unresolved_for_read"] is True
    assert candidate["read_target_selected"] is None
    assert candidate["read_target_reason"] == "SCAN_INCOMPLETE"
    assert orchestrator.pending_capability_action() == {
        "tool": "search_files",
        "arguments": {"query": "grid", "path": ".", "after": "ai_tool/example.py"},
    }
    assert orchestrator.pending_capability_action() is None


def test_completed_empty_search_is_not_found_not_incomplete():
    orchestrator = ChatTaskOrchestrator("h4-search-complete-empty", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    orchestrator.pending_capability_action()
    raw = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 3,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 0},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    assert orchestrator.search_observations[-1]["status"] == "NOT_FOUND_YET"
    assert orchestrator.search_observations[-1]["confirmed_absent"] is True
    candidate = orchestrator.search_candidate_sets[("grid", ".")]
    assert candidate["substring_cardinality"] == "NO_SUBSTRING_HITS"
    assert candidate["unique_path_count"] == 0
    assert candidate["scan_complete"] is True
    assert candidate["unresolved_for_read"] is True
    assert candidate["read_target_reason"] == "NO_SUBSTRING_HITS"
    assert orchestrator.pending_capability_action() is None
    assert "Search Candidate Set" in orchestrator.hint()
    assert orchestrator.snapshot()["search_candidate_sets"][0]["unique_path_count"] == 0


def test_fold_search_candidate_set_is_cardinality_not_selection():
    incomplete = fold_search_candidate_set(
        query="grid",
        search_path=".",
        match_paths=["a.py", "a.py", "b.py"],
        scan_complete=False,
        page_count=1,
    )
    assert incomplete["substring_cardinality"] == "INCOMPLETE_SCAN"
    assert incomplete["unique_path_count"] == 2
    assert incomplete["read_target_selected"] is None
    assert incomplete["unresolved_for_read"] is True

    multiple = fold_search_candidate_set(
        query="grid",
        search_path=".",
        match_paths=["research/a.py", "tests/b.py", "research/a.py"],
        scan_complete=True,
        page_count=2,
    )
    assert multiple["substring_cardinality"] == "MULTIPLE_SUBSTRING_PATHS"
    assert multiple["unique_path_count"] == 2
    assert multiple["match_row_count"] == 3
    assert multiple["matches_per_first_path_segment"] == {"research": 2, "tests": 1}
    assert multiple["returned_paths_in_order"] == ["research/a.py", "tests/b.py"]
    assert multiple["unresolved_for_read"] is True

    single = fold_search_candidate_set(
        query="grid",
        search_path=".",
        match_paths=["docs/CURRENT_DEVELOPMENT_STATE.md"],
        scan_complete=True,
        page_count=1,
    )
    assert single["substring_cardinality"] == "SINGLE_SUBSTRING_PATH"
    assert single["unresolved_for_read"] is True
    assert single["read_target_selected"] is None
    assert single["read_target_status"] is None


def test_completed_search_with_multiple_paths_does_not_first_hit_read():
    orchestrator = ChatTaskOrchestrator("h4-search-candidates", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [
            {"path": "AGENTS.md", "line": 1, "text": "grid"},
            {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 4,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    candidate = orchestrator.search_candidate_sets[("grid", ".")]
    assert candidate["substring_cardinality"] == "MULTIPLE_SUBSTRING_PATHS"
    assert candidate["unique_path_count"] == 2
    assert candidate["scan_complete"] is True
    assert candidate["unresolved_for_read"] is True
    assert candidate["read_target_selected"] is None
    assert candidate["read_target_reason"] == "NO_CONFIRMED_PATH_GROUND"
    assert orchestrator.pending_capability_action() is None
    hint = orchestrator.hint()
    assert "MULTIPLE_SUBSTRING_PATHS" in hint
    assert "1件を選んでreadしないでください" in hint
    snap = orchestrator.snapshot()["search_candidate_sets"][0]
    assert snap["returned_paths_in_order"] == [
        "AGENTS.md",
        "docs/CURRENT_DEVELOPMENT_STATE.md",
    ]


def test_search_candidate_set_accumulates_across_pages_then_stays_unresolved():
    orchestrator = ChatTaskOrchestrator("h4-search-fold-pages", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    first = {
        "ok": True,
        "status": "partial",
        "query": "grid",
        "matches": [{"path": "AGENTS.md", "line": 1, "text": "grid"}],
        "has_more": True,
        "next_cursor": "AGENTS.md",
        "files_scanned": 200,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "partial", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 1},
        relevant_tools=["search_files"],
        raw_result=first,
    )
    assert orchestrator.search_candidate_sets[("grid", ".")]["substring_cardinality"] == (
        "INCOMPLETE_SCAN"
    )
    assert orchestrator.pending_capability_action()["arguments"]["after"] == "AGENTS.md"
    second = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [
            {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"}
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 10,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": ".", "after": "AGENTS.md"},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 1},
        relevant_tools=["search_files"],
        raw_result=second,
    )
    candidate = orchestrator.search_candidate_sets[("grid", ".")]
    assert candidate["page_count"] == 2
    assert candidate["unique_path_count"] == 2
    assert candidate["substring_cardinality"] == "MULTIPLE_SUBSTRING_PATHS"
    assert candidate["matches_per_first_path_segment"]["docs"] == 1
    assert candidate["read_target_reason"] == "NO_CONFIRMED_PATH_GROUND"
    assert orchestrator.pending_capability_action() is None


def test_single_substring_path_is_not_a_read_target():
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator("h4-search-single", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [{"path": path, "line": 1, "text": "grid"}],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 2,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 1},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    candidate = orchestrator.search_candidate_sets[("grid", ".")]
    assert candidate["substring_cardinality"] == "SINGLE_SUBSTRING_PATH"
    assert candidate["read_target_selected"] is None
    assert candidate["read_target_reason"] == "NO_CONFIRMED_PATH_GROUND"
    assert candidate["unresolved_for_read"] is True
    assert orchestrator.pending_capability_action() is None


def test_confirmed_path_in_candidates_selects_that_path_not_return_order():
    selected = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-search-confirmed",
        f"{selected} を検索して確認して",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "success",
        "query": "CURRENT_DEVELOPMENT_STATE.md",
        "matches": [
            {"path": "AGENTS.md", "line": 1, "text": "grid"},
            {"path": selected, "line": 2, "text": "grid"},
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 4,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "CURRENT_DEVELOPMENT_STATE.md", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "CURRENT_DEVELOPMENT_STATE.md", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    candidate = orchestrator.search_candidate_sets[("CURRENT_DEVELOPMENT_STATE.md", ".")]
    assert candidate["read_target_status"] == "SELECTED"
    assert candidate["read_target_reason"] == "CONFIRMED_UNIQUE_PATH_IN_CANDIDATES"
    assert candidate["read_target_selected"] == selected
    assert candidate["unresolved_for_read"] is False
    assert orchestrator.pending_capability_action() == {
        "tool": "read_file",
        "arguments": {"path": selected},
    }


def test_confirmed_path_absent_from_candidates_does_not_select_another_hit():
    orchestrator = ChatTaskOrchestrator(
        "h4-search-missing-ground",
        "docs/CURRENT_DEVELOPMENT_STATE.md を検索して確認して",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "success",
        "query": "CURRENT_DEVELOPMENT_STATE.md",
        "matches": [{"path": "AGENTS.md", "line": 1, "text": "grid"}],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 2,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "CURRENT_DEVELOPMENT_STATE.md", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "CURRENT_DEVELOPMENT_STATE.md", "hit_count": 1},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    candidate = orchestrator.search_candidate_sets[("CURRENT_DEVELOPMENT_STATE.md", ".")]
    assert candidate["unique_path_count"] == 1
    assert candidate["read_target_reason"] == "CONFIRMED_PATH_NOT_IN_CANDIDATES"
    assert candidate["read_target_selected"] is None
    assert orchestrator.current_task_id == "T1"
    assert orchestrator.runtime.tasks["T1"].status == "in_progress"
    pending = orchestrator.pending_capability_action()
    if pending is not None:
        assert pending.get("arguments", {}).get("path") != "AGENTS.md"


def test_two_confirmed_paths_in_candidates_stay_unresolved():
    folded = fold_search_candidate_set(
        query="grid",
        search_path=".",
        match_paths=["AGENTS.md", "docs/CURRENT_DEVELOPMENT_STATE.md"],
        scan_complete=True,
        page_count=1,
    )
    resolved = resolve_search_read_target(
        folded,
        ["AGENTS.md", "docs/CURRENT_DEVELOPMENT_STATE.md"],
    )
    assert resolved["read_target_status"] == "UNRESOLVED"
    assert resolved["read_target_reason"] == "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES"
    assert resolved["read_target_selected"] is None
    assert resolved["matched_confirmed_paths"] == [
        "AGENTS.md",
        "docs/CURRENT_DEVELOPMENT_STATE.md",
    ]


def test_look_first_default_without_mention_is_not_a_path_ground():
    grounds = confirmed_read_path_grounds(
        "gridを検索して、その内容を要約してほしい。",
        capability_index=INDEX,
        registry_tools=REGISTRY,
    )
    assert "registry/tools.json" not in grounds
    assert grounds == []


def test_search_candidate_hint_truncates_paths_without_ranking():
    paths = [f"docs/file_{index:02d}.md" for index in range(41)]
    folded = fold_search_candidate_set(
        query="grid",
        search_path=".",
        match_paths=paths,
        scan_complete=True,
        page_count=1,
    )
    text = search_candidate_hint(folded)
    assert "hint_paths_truncated" in text
    assert "file_40.md" not in text
    assert folded["returned_paths_in_order"][-1] == "docs/file_40.md"
    assert folded["unique_path_count"] == 41


def _assert_human_grill(
    answer: str,
    gate: dict,
    orchestrator: ChatTaskOrchestrator,
) -> None:
    assert "検索候補が複数残っています" in answer
    assert "次に調査すべき対象を合理的に決められません" in answer or "次に調べる対象を決められません" in answer
    assert "返信で指定してください" in answer
    assert "1件選びません" in answer
    assert "uniqueness_class" not in answer
    assert not answer.startswith("【未確認】")
    assert gate["reason"] == "awaiting_human_grill"
    assert gate["verified"] is True
    assert gate["certainty"] == "OBSERVED"
    grill = gate["conversation_grill"]
    assert grill["phase"] == "conversation_grill"
    assert grill["status"] == "AWAITING_HUMAN"
    assert grill["reason"] == "CONFIRMED_INFO_INSUFFICIENT_FOR_NEXT_TARGET"
    assert grill["selected"] is None
    assert grill["candidates_preserved"] is True
    snap = orchestrator.snapshot()
    assert snap["awaiting_human_grill"] is True
    assert snap["conversation_grill"]["status"] == "AWAITING_HUMAN"
    assert snap["goal_read_target"]["selected"] is None
    assert snap["goal_close"] is None
    assert orchestrator.needs_human_grill() is True


def _observe_unresolved_grid_hits(orchestrator: ChatTaskOrchestrator) -> None:
    raw = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [
            {"path": "AGENTS.md", "line": 1, "text": "grid"},
            {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 4,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw,
    )


def _observe_single_unresolved_grid_hit(orchestrator: ChatTaskOrchestrator) -> None:
    raw = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [{"path": "AGENTS.md", "line": 1, "text": "grid"}],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 4,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 1},
        relevant_tools=["search_files"],
        raw_result=raw,
    )


def test_semantic_need_with_new_search_object_reexecutes_system_search():
    orchestrator = ChatTaskOrchestrator("h4-followup-search", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_single_unresolved_grid_hit(orchestrator)
    follow = orchestrator.accept_semantic_followup("researchを検索して")
    assert follow["status"] == "EXECUTABLE"
    assert follow["human_confirmation_eligible"] is False
    assert follow["action"] == {
        "tool": "search_files",
        "arguments": {"query": "research", "path": "."},
    }
    assert orchestrator.snapshot()["human_confirmation_eligible"] is False


def test_repeat_of_completed_search_is_not_additional_investigation():
    orchestrator = ChatTaskOrchestrator("h4-followup-dup", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_single_unresolved_grid_hit(orchestrator)
    follow = orchestrator.accept_semantic_followup("gridを検索して")
    assert follow["status"] == "NOT_EXECUTABLE"
    assert follow["reason"] == "SEARCH_ALREADY_COMPLETE"
    assert follow["action"] is None
    assert follow["human_confirmation_eligible"] is False
    assert follow["conversion"]["blocked_action_reasons"] == ["SEARCH_ALREADY_COMPLETE"]
    assert orchestrator.pending_capability_action() is None
    assert orchestrator.should_retry_semantic_followup(follow) is True
    assert "SEARCH_ALREADY_COMPLETE" in orchestrator.followup_retry_hint(follow)


def test_vague_need_is_not_system_executable_and_does_not_pick_a_hit():
    orchestrator = ChatTaskOrchestrator("h4-followup-vague", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_single_unresolved_grid_hit(orchestrator)
    follow = orchestrator.accept_semantic_followup("どれが本題のgridか決める")
    assert follow["status"] == "NOT_EXECUTABLE"
    assert follow["reason"] == "NO_REQUIRED_CAPABILITY"
    assert follow["human_confirmation_eligible"] is False
    assert follow["conversion"]["required_capabilities"] == []
    assert follow["conversion"]["recovery_classifies_followup_conversion"] is False
    assert orchestrator.pending_capability_action() is None
    candidate = orchestrator.search_candidate_sets[("grid", ".")]
    assert candidate["read_target_selected"] is None


def test_search_need_without_query_is_arguments_unresolved_not_human():
    orchestrator = ChatTaskOrchestrator("h4-followup-query", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_single_unresolved_grid_hit(orchestrator)
    follow = orchestrator.accept_semantic_followup("検索して")
    assert follow["status"] == "NOT_EXECUTABLE"
    assert follow["reason"] == "ARGUMENTS_UNRESOLVED"
    assert "query" in follow["conversion"]["unresolved_arguments"]
    assert follow["human_confirmation_eligible"] is False
    assert "workspace_file_search" in follow["conversion"]["required_capabilities"]
    assert orchestrator.should_retry_semantic_followup(follow) is True
    retry = orchestrator.followup_retry_hint(follow)
    assert "ARGUMENTS_UNRESOLVED" in retry
    assert "直ちにHuman確認へは落としません" in retry
    again = orchestrator.accept_semantic_followup("検索して")
    assert orchestrator.should_retry_semantic_followup(again) is False


def test_cpu_need_is_candidates_available_not_human():
    orchestrator = ChatTaskOrchestrator("h4-followup-cpu", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_single_unresolved_grid_hit(orchestrator)
    follow = orchestrator.accept_semantic_followup("CPU を見て")
    assert follow["status"] == "NOT_EXECUTABLE"
    assert follow["reason"] == "CANDIDATES_AVAILABLE"
    assert "CANDIDATES_AVAILABLE" in follow["conversion"]["resolution_statuses"]
    assert follow["conversion"]["selected_tools"] == []
    assert follow["human_confirmation_eligible"] is False


def test_goal_search_match_text_is_not_observation_ground():
    selected = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-goal-search-text",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [
            {"path": "AGENTS.md", "line": 1, "text": "grid"},
            {"path": selected, "line": 2, "text": f"canonical note: {selected}"},
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 4,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    candidate = orchestrator.search_candidate_sets[("grid", ".")]
    assert candidate["observation_role"] == "goal_request"
    assert orchestrator.goal_read_target["observation_path_grounds"] == []
    assert orchestrator.goal_read_target["selected"] is None
    assert orchestrator.goal_read_target["reason"] == "NO_CONFIRMED_PATH_GROUND"
    assert orchestrator.pending_capability_action() is None


def test_named_path_in_need_is_agent_investigation_not_first_hit():
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator("h4-followup-read", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    follow = orchestrator.accept_semantic_followup(f"{path} を確認して")
    assert follow["status"] == "NOT_APPLICABLE"
    assert follow["reason"] == "HUMAN_GRILL_REQUIRED"
    assert follow["action"] is None
    assert orchestrator.needs_human_grill() is True
    assert orchestrator.goal_read_target["selected"] is None
    answer, gate = orchestrator.gate_answer("これはgridの要約です。")
    _assert_human_grill(answer, gate, orchestrator)
    assert "これはgridの要約です。" in answer


def test_agent_named_file_search_does_not_confirm_goal_target():
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-followup-named-search",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    follow = orchestrator.accept_semantic_followup(f"{path} を検索して")
    assert follow["status"] == "NOT_APPLICABLE"
    assert follow["reason"] == "HUMAN_GRILL_REQUIRED"
    assert follow["action"] is None
    answer, gate = orchestrator.gate_answer("CURRENT_DEVELOPMENT_STATE.md の要約です。")
    _assert_human_grill(answer, gate, orchestrator)


def test_followup_observation_can_confirm_goal_path_without_adopting_agent_query():
    selected = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-followup-feeds-goal",
        f"{selected} を検索して要約して",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw_grid = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [
            {"path": "AGENTS.md", "line": 1, "text": "grid"},
            {"path": "docs/GRILL_V0.md", "line": 2, "text": "grid"},
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 4,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw_grid,
    )
    assert orchestrator.goal_read_target["status"] == "UNRESOLVED"
    assert orchestrator.goal_read_target["reason"] == "CONFIRMED_PATH_NOT_IN_CANDIDATES"
    assert orchestrator.goal_read_target["selected"] is None
    assert orchestrator.current_task_id == "T1"
    assert orchestrator.runtime.tasks["T1"].status == "in_progress"
    follow = orchestrator.accept_semantic_followup("researchを検索して")
    assert follow["status"] == "EXECUTABLE"
    assert follow["proposed_investigation_target"] == {
        "tool": "search_files",
        "arguments": {"query": "research", "path": "."},
    }
    assert selected not in follow["proposed_path_grounds"]
    raw_research = {
        "ok": True,
        "status": "success",
        "query": "research",
        "matches": [
            {"path": "research/grill_observation_v0/README.md", "line": 1, "text": "grid"},
            {"path": selected, "line": 2, "text": "grid"},
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 6,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "research", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "research", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw_research,
    )
    research = orchestrator.search_candidate_sets[("research", ".")]
    grid = orchestrator.search_candidate_sets[("grid", ".")]
    assert research["observation_role"] == "followup_investigation"
    assert grid["observation_role"] == "goal_request"
    assert grid["read_target_selected"] is None
    assert orchestrator.goal_read_target["status"] == "SELECTED"
    assert orchestrator.goal_read_target["selected"] == selected
    assert orchestrator.goal_read_target["reason"] == "CONFIRMED_UNIQUE_PATH_IN_CANDIDATES"
    assert orchestrator.pending_capability_action() == {
        "tool": "read_file",
        "arguments": {"path": selected},
    }
    orchestrator.observe_tool(
        "read_file",
        {"path": selected},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {},
        relevant_tools=["read_file"],
        raw_result={"lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}]},
    )
    answer, gate = orchestrator.gate_answer("確認したファイルの内容です。")
    assert gate["verified"] is True
    assert not answer.startswith("【未確認】")
    assert orchestrator.snapshot()["goal_read_target"]["selected"] == selected
    assert orchestrator.snapshot()["followup_investigations"][0][
        "proposed_investigation_target"
    ]["arguments"]["query"] == "research"


def test_selected_goal_without_read_does_not_verify_summary():
    selected = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-goal-unread",
        f"{selected} を検索して確認して",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "success",
        "query": "CURRENT_DEVELOPMENT_STATE.md",
        "matches": [
            {"path": "AGENTS.md", "line": 1, "text": "grid"},
            {"path": selected, "line": 2, "text": "grid"},
        ],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 4,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "CURRENT_DEVELOPMENT_STATE.md", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "CURRENT_DEVELOPMENT_STATE.md", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    assert orchestrator.goal_read_target["selected"] == selected
    pending = orchestrator.pending_capability_action()
    assert pending == {
        "tool": "read_file",
        "arguments": runtime_initial_read_arguments(selected),
    }
    answer, gate = orchestrator.gate_answer("まだ読んでいない要約です。")
    assert answer.startswith("【未確認】")
    assert gate["reason"] == "goal_read_target_not_observed"
    assert gate["verified"] is False


def test_observation_path_forms_ignore_look_first_mentions():
    grounds = confirmed_read_path_grounds(
        "research の案内に grid とある",
        capability_index=INDEX,
        registry_tools=REGISTRY,
        include_look_first=False,
    )
    assert grounds == []
    assert "registry/tools.json" not in confirmed_read_path_grounds(
        "tools.json に書いてある",
        capability_index=INDEX,
        registry_tools=REGISTRY,
        include_look_first=False,
    )


def test_followup_hit_path_is_not_an_observation_ground():
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-obs-hit-path",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    follow = orchestrator.accept_semantic_followup("researchを検索して")
    assert follow["status"] == "NOT_APPLICABLE"
    assert follow["reason"] == "HUMAN_GRILL_REQUIRED"
    assert orchestrator.goal_read_target["observation_path_grounds"] == []
    assert orchestrator.goal_read_target["selected"] is None
    assert orchestrator.needs_human_grill() is True


def test_followup_match_text_path_can_confirm_goal_without_request_ground():
    selected = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-obs-match-text",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    assert orchestrator.goal_read_target["request_path_grounds"] == []
    follow = orchestrator.accept_semantic_followup("researchを検索して")
    assert follow["status"] == "NOT_APPLICABLE"
    assert follow["reason"] == "HUMAN_GRILL_REQUIRED"
    assert orchestrator.goal_read_target["selected"] is None
    assert orchestrator.needs_human_grill() is True
    answer, gate = orchestrator.gate_answer("これはgridの要約です。")
    _assert_human_grill(answer, gate, orchestrator)


def test_two_observation_paths_in_goal_candidates_stay_unresolved():
    orchestrator = ChatTaskOrchestrator(
        "h4-obs-two-paths",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    follow = orchestrator.accept_semantic_followup("researchを検索して")
    assert follow["status"] == "NOT_APPLICABLE"
    assert follow["reason"] == "HUMAN_GRILL_REQUIRED"
    assert orchestrator.goal_read_target["status"] == "UNRESOLVED"
    assert orchestrator.goal_read_target["selected"] is None
    assert orchestrator.needs_human_grill() is True


def test_investigation_read_does_not_confirm_the_proposed_file():
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-obs-proposed-read",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    follow = orchestrator.accept_semantic_followup(f"{path} を確認して")
    assert follow["status"] == "NOT_APPLICABLE"
    assert follow["reason"] == "HUMAN_GRILL_REQUIRED"
    assert orchestrator.goal_read_target["selected"] is None
    answer, gate = orchestrator.gate_answer("提案ファイルの要約です。")
    _assert_human_grill(answer, gate, orchestrator)


def test_investigation_need_does_not_bypass_human_grill():
    orchestrator = ChatTaskOrchestrator(
        "h4-obs-read-other",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    follow = orchestrator.accept_semantic_followup("AGENTS.md を確認して")
    assert follow["status"] == "NOT_APPLICABLE"
    assert follow["reason"] == "HUMAN_GRILL_REQUIRED"
    assert orchestrator.goal_read_target["selected"] is None
    assert orchestrator.needs_human_grill() is True


def test_unresolved_complete_scan_closes_without_selecting():
    orchestrator = ChatTaskOrchestrator(
        "h4-close-unresolved",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    assert orchestrator.goal_read_target["status"] == "UNRESOLVED"
    assert orchestrator.goal_read_target["reason"] == "NO_CONFIRMED_PATH_GROUND"
    assert orchestrator.snapshot()["goal_close"] is None
    evidence_ids = list(orchestrator.runtime.evidence)
    answer, gate = orchestrator.gate_answer("これはgridの要約です。")
    _assert_human_grill(answer, gate, orchestrator)
    assert "これはgridの要約です。" in answer
    assert list(orchestrator.runtime.evidence) == evidence_ids
    assert ("grid", ".") in orchestrator.search_candidate_sets
    assert orchestrator.search_candidate_sets[("grid", ".")]["unique_path_count"] == 2


def test_scan_incomplete_does_not_close_unresolved_goal():
    orchestrator = ChatTaskOrchestrator("h4-close-incomplete", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "partial",
        "query": "grid",
        "matches": [{"path": "ai_tool/example.py", "line": 1, "text": "grid"}],
        "has_more": True,
        "next_cursor": "ai_tool/example.py",
        "last_scanned_path": "ai_tool/example.py",
        "files_scanned": 200,
        "warnings": [
            {
                "code": "scan_limit_reached",
                "message": "走査ファイル数が上限に達したため打ち切りました",
            }
        ],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "partial", "error": None, "warnings": raw["warnings"]},
        {"query": "grid", "hit_count": 1},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    assert orchestrator.goal_read_target["reason"] == "SCAN_INCOMPLETE"
    assert orchestrator.goal_read_target["uniqueness_class"] == "INCOMPLETE_OBSERVATION"
    answer, gate = orchestrator.gate_answer("途中結果の要約です。")
    assert answer.startswith("【未確認】")
    assert gate["verified"] is False
    assert gate["reason"] == "goal_read_target_unresolved"
    assert orchestrator.snapshot()["goal_close"] is None
    assert orchestrator.search_candidate_sets[("grid", ".")].get("scan_complete") is False
    assert orchestrator.needs_human_grill() is False


def test_incomplete_scan_with_multiple_hits_still_continues_same_search():
    orchestrator = ChatTaskOrchestrator("h4-grill-incomplete-multi", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "partial",
        "query": "grid",
        "matches": [
            {"path": "AGENTS.md", "line": 1, "text": "grid"},
            {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
        ],
        "has_more": True,
        "next_cursor": "docs/CURRENT_DEVELOPMENT_STATE.md",
        "last_scanned_path": "docs/CURRENT_DEVELOPMENT_STATE.md",
        "files_scanned": 200,
        "warnings": [
            {
                "code": "scan_limit_reached",
                "message": "走査ファイル数が上限に達したため打ち切りました",
            }
        ],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "partial", "error": None, "warnings": raw["warnings"]},
        {"query": "grid", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    assert orchestrator.goal_read_target["uniqueness_class"] == "INCOMPLETE_OBSERVATION"
    assert orchestrator.needs_human_grill() is False
    assert orchestrator.pending_capability_action() == {
        "tool": "search_files",
        "arguments": {
            "query": "grid",
            "path": ".",
            "after": "docs/CURRENT_DEVELOPMENT_STATE.md",
        },
    }


def test_empty_complete_search_is_not_closed_unresolved():
    orchestrator = ChatTaskOrchestrator("h4-close-empty", "gridを検索して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    raw = {
        "ok": True,
        "status": "success",
        "query": "grid",
        "matches": [],
        "has_more": False,
        "next_cursor": None,
        "files_scanned": 3,
        "warnings": [],
        "error": None,
    }
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 0},
        relevant_tools=["search_files"],
        raw_result=raw,
    )
    answer, gate = orchestrator.gate_answer("見つかりませんでした。")
    assert orchestrator.goal_read_target["uniqueness_class"] == "EMPTY_OBSERVATION"
    assert answer.startswith("【未確認】")
    assert gate["reason"] == "goal_read_target_unresolved"
    assert orchestrator.snapshot()["goal_close"] is None


def test_confirm_interchangeable_paths_requires_complete_subset():
    identity = ["AGENTS.md", "docs/CURRENT_DEVELOPMENT_STATE.md"]
    assert confirm_interchangeable_paths(identity, []) == []
    assert confirm_interchangeable_paths(
        identity,
        [{"AGENTS.md", "README.md"}],
    ) == []
    assert confirm_interchangeable_paths(
        identity,
        [{"AGENTS.md", "docs/CURRENT_DEVELOPMENT_STATE.md", "docs/extra.md"}],
    ) == ["AGENTS.md", "docs/CURRENT_DEVELOPMENT_STATE.md"]
    assert confirm_interchangeable_paths(["AGENTS.md"], [{"AGENTS.md", "README.md"}]) == []


def test_grid_hits_are_identity_unresolved_not_user_variable():
    orchestrator = ChatTaskOrchestrator(
        "h4-grid-not-variable",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    target = orchestrator.goal_read_target
    assert target["status"] == "UNRESOLVED"
    assert target["uniqueness_class"] == "IDENTITY_UNRESOLVED"
    assert target["user_variable"]["interchangeability_status"] == "UNCONFIRMED"
    assert target["user_variable"]["provisional_selected"] is None
    assert target["selected"] is None
    assert orchestrator.pending_capability_action() is None
    assert orchestrator.needs_human_grill() is True


def test_partial_equivalent_set_does_not_make_grid_hits_user_variable():
    orchestrator = ChatTaskOrchestrator(
        "h4-partial-equivalent",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    orchestrator.interchangeable_path_sets = [
        frozenset({"AGENTS.md", "README.md"}),
    ]
    _observe_unresolved_grid_hits(orchestrator)
    assert orchestrator.goal_read_target["uniqueness_class"] == "IDENTITY_UNRESOLVED"
    assert orchestrator.goal_read_target["status"] == "UNRESOLVED"
    assert orchestrator.goal_read_target["selected"] is None


def test_confirmed_equivalent_set_is_provisionally_selected():
    first = "AGENTS.md"
    second = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-user-variable",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    orchestrator.interchangeable_path_sets = [frozenset({first, second})]
    _observe_unresolved_grid_hits(orchestrator)
    target = orchestrator.goal_read_target
    assert target["status"] == "PROVISIONAL_SELECTED"
    assert target["uniqueness_class"] == "USER_VARIABLE"
    assert target["selected"] == first
    assert target["user_variable"]["interchangeability_status"] == "CONFIRMED"
    assert target["user_variable"]["provisional_selected"] == first
    assert target["user_variable"]["candidates"] == [first, second]
    assert target["user_variable"]["selection_rule"] == "lexicographic_path"
    assert target["user_variable"]["replaceable_by"] == [
        "user_preference",
        "project_convention",
    ]
    assert orchestrator.pending_capability_action() == {
        "tool": "read_file",
        "arguments": {"path": first},
    }
    assert orchestrator.snapshot()["goal_close"] is None
    answer, gate = orchestrator.gate_answer("暫定ファイルの要約です。")
    assert answer.startswith("【未確認】")
    assert gate["reason"] == "goal_read_target_not_observed"


def test_provisional_user_variable_read_is_observed_and_replaceable():
    first = "AGENTS.md"
    second = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "h4-user-variable-read",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    orchestrator.interchangeable_path_sets = [frozenset({first, second})]
    _observe_unresolved_grid_hits(orchestrator)
    pending = orchestrator.pending_capability_action()
    assert pending == {
        "tool": "read_file",
        "arguments": runtime_initial_read_arguments(first),
    }
    orchestrator.observe_tool(
        "read_file",
        {"path": first},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {},
        relevant_tools=["read_file"],
        raw_result={"lines": [{"line": 1, "text": "# Agents"}]},
    )
    assert orchestrator.goal_read_target["status"] == "PROVISIONAL_SELECTED"
    assert orchestrator.goal_read_target["selected"] == first
    answer, gate = orchestrator.gate_answer("暫定選択したファイルの内容です。")
    assert answer.startswith("【結果】Goal対象は交換可能なユーザー可変要素です。")
    assert "差し替え可能" in answer
    assert not answer.startswith("【未確認】")
    assert gate["reason"] == "provisional_user_variable_target"
    assert gate["verified"] is True
    assert gate["certainty"] == "OBSERVED"
    assert gate["user_variable"]["provisional_selected"] == first
    assert orchestrator.snapshot()["goal_close"] is None


def test_grill_clarification_selects_unique_candidate_without_repeating_search():
    orchestrator = ChatTaskOrchestrator(
        "grill-clarify-select",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    assert orchestrator.needs_human_grill() is True
    observations_before = list(orchestrator.search_observations)
    applied = orchestrator.apply_human_grill_answer(
        "docs/CURRENT_DEVELOPMENT_STATE.md を対象にして"
    )
    assert applied["status"] == "CLARIFICATION_APPLIED"
    assert applied["completed_search_repeated"] is False
    assert applied["needs_human_grill"] is False
    assert orchestrator.goal_read_target["status"] == "SELECTED"
    assert (
        orchestrator.goal_read_target["selected"]
        == "docs/CURRENT_DEVELOPMENT_STATE.md"
    )
    assert orchestrator.goal_read_target["ground_source"] == "human_grill"
    assert orchestrator.search_observations == observations_before
    pending = orchestrator.pending_selected_read_action()
    assert pending == {
        "tool": "read_file",
        "arguments": {"path": "docs/CURRENT_DEVELOPMENT_STATE.md"},
    }
    assert orchestrator.pending_capability_action() is None


def test_grill_clarification_without_identity_asks_again():
    orchestrator = ChatTaskOrchestrator(
        "grill-clarify-again",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    applied = orchestrator.apply_human_grill_answer("まだどれか分かりません")
    assert applied["needs_human_grill"] is True
    assert applied["extracted_path_grounds"] == []
    assert orchestrator.goal_read_target["selected"] is None
    assert orchestrator.confirmed_clarifications[-1]["role"] == "confirmed_clarification"
    answer, gate = orchestrator.gate_answer("")
    _assert_human_grill(answer, gate, orchestrator)
    assert orchestrator.pending_selected_read_action() is None


def test_conversation_grill_state_restore_reevaluates_same_goal():
    first = ChatTaskOrchestrator(
        "grill-state-1",
        "gridを検索して、その内容を要約してほしい。",
    )
    first.initialize()
    first.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(first)
    packet = first.conversation_grill_state()
    restored = ChatTaskOrchestrator.restore_from_grill_resume("grill-state-2", packet)
    restored.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    assert restored.request == first.request
    assert restored.search_candidate_sets[("grid", ".")]["unique_path_count"] == 2
    assert restored.needs_human_grill() is True
    restored.apply_human_grill_answer("AGENTS.md")
    assert restored.goal_read_target["selected"] == "AGENTS.md"
    assert restored.goal_read_target["ground_source"] == "human_grill"
    assert restored.needs_human_grill() is False


def test_latest_grill_clarification_is_the_current_identity():
    orchestrator = ChatTaskOrchestrator(
        "grill-latest",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    orchestrator.apply_human_grill_answer("まだ決められない")
    assert orchestrator.needs_human_grill() is True
    orchestrator.apply_human_grill_answer("AGENTS.md でお願いします")
    assert orchestrator.needs_human_grill() is False
    assert orchestrator.goal_read_target["selected"] == "AGENTS.md"
    assert len(orchestrator.confirmed_clarifications) == 2


def test_match_clarification_ignores_tokens_that_hit_every_candidate():
    paths = ["AGENTS.md", "docs/CURRENT_DEVELOPMENT_STATE.md"]
    assert match_clarification_to_candidate_paths("まだどれか分かりません", paths) == []
    assert match_clarification_to_candidate_paths(
        "CURRENT を対象にして",
        paths,
    ) == ["docs/CURRENT_DEVELOPMENT_STATE.md"]
    assert match_clarification_to_candidate_paths("AGENTS の方", paths) == ["AGENTS.md"]
    assert match_clarification_to_candidate_paths(
        "grid",
        paths,
        observed_match_texts={
            "AGENTS.md": ["grid"],
            "docs/CURRENT_DEVELOPMENT_STATE.md": ["grid"],
        },
        ignore_tokens=["grid"],
    ) == []


def test_grill_clarification_without_filename_can_select_unique_candidate():
    orchestrator = ChatTaskOrchestrator(
        "grill-clarify-token",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    applied = orchestrator.apply_human_grill_answer("CURRENT の文書を対象にして")
    assert applied["needs_human_grill"] is False
    assert applied["extracted_path_grounds"] == [
        "docs/CURRENT_DEVELOPMENT_STATE.md"
    ]
    assert (
        orchestrator.goal_read_target["selected"]
        == "docs/CURRENT_DEVELOPMENT_STATE.md"
    )
    assert orchestrator.goal_read_target["ground_source"] == "human_grill"


def test_grill_clarification_observed_text_can_select_unique_candidate():
    orchestrator = ChatTaskOrchestrator(
        "grill-clarify-text",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    orchestrator.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result={
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {
                    "path": "docs/GRILL_V0.md",
                    "line": 2,
                    "text": "Human Grill の原則と出口",
                },
            ],
            "has_more": False,
            "next_cursor": None,
            "files_scanned": 4,
            "warnings": [],
            "error": None,
        },
    )
    applied = orchestrator.apply_human_grill_answer("原則の文書です")
    assert applied["needs_human_grill"] is False
    assert applied["extracted_path_grounds"] == ["docs/GRILL_V0.md"]
    assert orchestrator.goal_read_target["selected"] == "docs/GRILL_V0.md"


def test_grill_clarification_ambiguous_token_asks_again():
    orchestrator = ChatTaskOrchestrator(
        "grill-clarify-ambiguous",
        "gridを検索して、その内容を要約してほしい。",
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_unresolved_grid_hits(orchestrator)
    applied = orchestrator.apply_human_grill_answer("CURRENT と AGENTS のどちらでも")
    assert applied["needs_human_grill"] is True
    assert set(applied["extracted_path_grounds"]) == {
        "AGENTS.md",
        "docs/CURRENT_DEVELOPMENT_STATE.md",
    }
    assert orchestrator.goal_read_target["selected"] is None


def test_list_files_directory_path_does_not_use_filename_as_root():
    assert list_files_directory_path("README.md") == "."
    assert list_files_directory_path("docs/README.md") == "docs"
    assert list_files_directory_path(".agents") == ".agents"
    assert list_files_directory_path(".") == "."


def test_list_files_next_action_uses_parent_directory_not_filename():
    result = resolve_capability(
        _task("README.md があるか確認するため一覧する"),
        capability="workspace_file_list",
        capability_index=INDEX,
        registry_tools=REGISTRY,
    )
    assert result.selected_tool == "list_files"
    assert result.next_action == {"tool": "list_files", "arguments": {"path": "."}}
    nested = resolve_capability(
        _task("docs/README.md があるディレクトリを一覧する"),
        capability="workspace_file_list",
        capability_index=INDEX,
        registry_tools=REGISTRY,
    )
    assert nested.next_action == {"tool": "list_files", "arguments": {"path": "docs"}}


def test_pending_capability_action_does_not_repeat_failed_read_path():
    orchestrator = ChatTaskOrchestrator("mm-missing-readme", "README.md を読んで")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    assert orchestrator.pending_capability_action() == {
        "tool": "read_file",
        "arguments": runtime_initial_read_arguments("README.md"),
    }
    orchestrator.observe_tool(
        "read_file",
        {"path": "README.md"},
        {
            "ok": False,
            "status": "failure",
            "error": {"code": "path_not_found", "message": "x"},
            "warnings": [],
        },
        {"ok": False, "status": "failure", "error": {"code": "path_not_found"}},
        relevant_tools=["read_file"],
    )
    assert orchestrator.pending_capability_action() is None


def test_complete_listing_omits_missing_file_from_bridge():
    orchestrator = ChatTaskOrchestrator("mm-list-absent", "README.md を読んで")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    orchestrator.observe_tool(
        "list_files",
        {"path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"ok": True, "status": "success"},
        relevant_tools=["list_files", "read_file"],
        raw_result={
            "ok": True,
            "status": "success",
            "base": ".",
            "truncated": False,
            "has_more": False,
            "entries": [
                {"name": "AGENTS.md", "path": "AGENTS.md", "type": "file"},
            ],
        },
    )
    assert orchestrator.path_absent_from_complete_listing(
        "read_file", {"path": "README.md"}
    )
    assert orchestrator.path_absent_from_complete_listing(
        "list_files", {"path": "README.md"}
    )
    assert orchestrator.pending_capability_action() is None


def _observe_root_listing(orchestrator, entries):
    orchestrator.observe_tool(
        "list_files",
        {"path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"ok": True, "status": "success"},
        relevant_tools=["list_files", "read_file"],
        raw_result={
            "ok": True,
            "status": "success",
            "base": ".",
            "truncated": False,
            "has_more": False,
            "entries": entries,
        },
    )


def test_named_path_omitted_from_listing_supports_existing_observation_condition():
    request = "README.md がワークスペースにあるか確認して、ファイルの先頭1行を報告してください。"
    orchestrator = ChatTaskOrchestrator("mm-absent-obs", request)
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_root_listing(
        orchestrator,
        [{"name": "AGENTS.md", "path": "AGENTS.md", "type": "file"}],
    )
    t1 = orchestrator.runtime.tasks["T1"]
    assert t1.completion_conditions == ["relevant evidence observed"]
    assert "README.md does not exist" not in t1.completion_conditions
    assert t1.status == "complete"
    assert orchestrator.current_task_id == "T2"
    assert orchestrator.runtime.goals["G1"].status != "complete"
    evidence = list(orchestrator.runtime.evidence.values())
    assert evidence
    assert "README.md" in (evidence[-1].relevant_content or evidence[-1].summary)
    answer, gate = orchestrator.gate_answer("README.md はワークスペースに存在しません。")
    assert gate["verified"] is True
    assert gate["reason"] == "awaiting_goal_completion_human"
    packet = gate["goal_completion_human"]
    assert packet["reason"] == (
        "EXISTING_SPECS_DO_NOT_UNIQUELY_DETERMINE_GOAL_COMPLETION"
    )
    assert [item["id"] for item in packet["goal_meaning_options"]] == [
        "absence_confirmed_completes_goal",
        "content_report_required",
    ]
    assert "achieved" not in answer
    assert "ended_incomplete" not in answer
    assert not answer.startswith("【未確認】")
    orchestrator.finish("README.md はワークスペースに存在しません。")
    assert orchestrator.runtime.tasks["T2"].status == "complete"
    assert orchestrator.runtime.goals["G1"].status == "complete"
    assert orchestrator.runtime.goals["G1"].completion_conditions == ["all tasks complete"]
    assert orchestrator.needs_goal_completion_human() is True


def test_listing_does_not_complete_observation_when_named_file_is_present():
    orchestrator = ChatTaskOrchestrator("mm-present-obs", "README.md の先頭1行を報告して")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_root_listing(
        orchestrator,
        [{"name": "README.md", "path": "README.md", "type": "file"}],
    )
    t1 = orchestrator.runtime.tasks["T1"]
    assert t1.completion_conditions == ["relevant evidence observed"]
    assert t1.status != "complete"


def test_listing_does_not_complete_observation_without_named_path():
    orchestrator = ChatTaskOrchestrator("mm-audit-obs", "repository audit")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    _observe_root_listing(
        orchestrator,
        [{"name": "AGENTS.md", "path": "AGENTS.md", "type": "file"}],
    )
    assert orchestrator.runtime.tasks["T1"].status != "complete"
