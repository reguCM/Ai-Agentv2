from types import SimpleNamespace

from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.chat_interface.activity_status import begin_turn
from ai_tool.chat_interface.agent_turn import _chat_turn, run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.concept_resolution import detect_unknown_concept
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import AgentTaskRuntime


def _response(content="", calls=None):
    return SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls or []))


def _tool_call(name, arguments):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


def test_user_file_name_is_not_an_unknown_runtime_concept():
    result = detect_unknown_concept(
        "workspace内に hello_test.txt という新しいテキストファイルを作成してください。"
    )
    assert result.detected is False


def test_successful_known_path_read_records_observation_and_supports_matching_fact():
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    orchestrator = ChatTaskOrchestrator(
        "read-known-path",
        f"{path} を確認し、P2-18 Safe Mutation Toolsを要約する",
        completion_conditions=[
            f"{path} が読み取り可能であることが確認されている",
            "P2-18 Safe Mutation Toolsに関する記述が確認されている",
            "内容が日本語で要約されている",
        ],
    )
    orchestrator.initialize()
    orchestrator.observe_tool(
        "read_file",
        {"path": path},
        {"status": "success"},
        {},
        relevant_tools=["read_file"],
        raw_result={"lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}]},
    )

    task = orchestrator.runtime.tasks["T1"]
    assert len(orchestrator.runtime.evidence) == 1
    assert task.condition_status[task.completion_conditions[0]] == "SATISFIED"
    assert task.condition_status[task.completion_conditions[1]] == "SATISFIED"
    assert task.condition_status[task.completion_conditions[2]] == "UNKNOWN"
    assert task.status == "in_progress"


def test_partial_search_hit_becomes_evidence_and_schedules_safe_read():
    orchestrator = ChatTaskOrchestrator(
        "search-read",
        "Safe Mutation Toolsを検索し、該当文書を確認する",
        completion_conditions=["Safe Mutation Toolsの定義が確認されている"],
    )
    orchestrator.initialize()
    orchestrator.observe_tool(
        "search_files",
        {"query": "Safe Mutation Tools", "path": "."},
        {"status": "partial"},
        {},
        relevant_tools=["search_files", "read_file"],
        raw_result={
            "status": "partial",
            "matches": [{
                "path": "docs/CURRENT_DEVELOPMENT_STATE.md",
                "line": 1,
                "text": "P2-18 Safe Mutation Tools",
            }],
        },
    )

    assert len(orchestrator.runtime.evidence) == 1
    assert orchestrator.search_observations[-1]["status"] == "OBSERVED_CANDIDATES"
    assert orchestrator.search_observations[-1]["confirmed_absent"] is False
    candidate = orchestrator.search_candidate_sets[("Safe Mutation Tools", ".")]
    assert candidate["unique_path_count"] == 1
    assert candidate["substring_cardinality"] == "SINGLE_SUBSTRING_PATH"
    assert candidate["read_target_selected"] is None
    assert candidate["read_target_reason"] == "NO_CONFIRMED_PATH_GROUND"
    assert orchestrator.pending_capability_action() is None


def test_empty_complete_search_records_not_found_candidate_set():
    orchestrator = ChatTaskOrchestrator("search-empty", "Safe Mutation Toolsを検索する")
    orchestrator.initialize()
    orchestrator.observe_tool(
        "search_files",
        {"query": "Safe Mutation Tools", "path": "."},
        {"status": "success"},
        {},
        relevant_tools=["search_files"],
        raw_result={"status": "success", "matches": [], "match_count": 0},
    )
    page = orchestrator.search_observations[-1]
    assert page["query"] == "Safe Mutation Tools"
    assert page["status"] == "NOT_FOUND_YET"
    assert page["match_count"] == 0
    assert page["confirmed_absent"] is True
    candidate = orchestrator.search_candidate_sets[("Safe Mutation Tools", ".")]
    assert candidate["substring_cardinality"] == "NO_SUBSTRING_HITS"
    assert candidate["unique_path_count"] == 0
    assert candidate["unresolved_for_read"] is True
    assert candidate["read_target_reason"] == "NO_SUBSTRING_HITS"
    assert orchestrator.pending_capability_action() is None


def test_replan_task_does_not_inherit_an_unrelated_condition():
    orchestrator = ChatTaskOrchestrator(
        "replan-scope",
        "hello_test.txtを作成する",
        completion_conditions=["hello_test.txtが作成されている"],
    )
    orchestrator.initialize()
    added = orchestrator.add_review_task(
        {
            "description": "Dedicated Sandbox Sessionを確立する",
            "reason": "mutation prerequisite",
            "supports_conditions": ["hello_testの定義・更新箇所が確認できている"],
        }
    )
    assert added.completion_conditions == ["Dedicated Sandbox Sessionを確立する"]


def test_mutation_request_starts_runtime_owned_sandbox_before_tool(monkeypatch, tmp_path):
    correlation_id = "p2181-mutation"
    session = {"session_id": "p2181", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = (
        "workspace内に hello_test.txt という新しいテキストファイルを作成してください。"
        "内容は Hello Local Agent の1行だけにしてください。"
    )
    orchestrator = ChatTaskOrchestrator(
        correlation_id,
        request,
        completion_conditions=["hello_test.txtがSandbox内に作成されている"],
    )
    orchestrator.initialize()
    observed = {}
    sandbox = SimpleNamespace(
        session_id="S-runtime-owned",
        sandbox_root=str(tmp_path / "sandbox"),
        branch="agent-sandbox/S-runtime-owned",
        base_head="abc",
        current_head="abc",
        status="ACTIVE",
        production_applied=False,
        git_base="HEAD:abc",
        workspace_base="working-tree-sha256:test",
        session_kind="DEDICATED",
    )

    def start_sandbox(self, source, parent):
        observed["source"] = source
        observed["parent"] = parent
        self.sandbox_session = sandbox
        return sandbox

    def execute(name, arguments, **kwargs):
        observed["tool"] = name
        observed["arguments"] = arguments
        observed["sandbox"] = kwargs.get("sandbox_session")
        return {"ok": True, "status": "success", "error": None, "warnings": []}

    monkeypatch.setattr(AgentTaskRuntime, "start_dedicated_sandbox", start_sandbox)
    monkeypatch.setattr(
        AgentTaskRuntime,
        "sandbox_identity",
        lambda self: vars(self.sandbox_session) if self.sandbox_session else None,
    )
    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    responses = iter([
        _response(calls=[_tool_call("create_file", {
            "path": "hello_test.txt", "content": "Hello Local Agent\n",
        })]),
        _response("Sandbox内で作成処理を実行しました。"),
    ])

    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert observed["tool"] == "create_file"
    assert observed["sandbox"] is sandbox
    assert orchestrator.runtime.sandbox_session is sandbox
    assert result["tools"][0]["status"] == "success"
    assert result["task_runtime"]["goals"][0]["status"] != "complete"


def test_chat_turn_injects_concept_definition_action_before_llm(monkeypatch, tmp_path):
    correlation_id = "concept-def-bridge"
    session = {"session_id": "concept-def-bridge-session", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "runtime.tool_gap_count を確認する"
    row = detect_unknown_concept(request)
    orchestrator = ChatTaskOrchestrator(
        correlation_id,
        request,
        completion_conditions=["tool_gap_countの意味が確認できている"],
        concept_resolution=row,
    )
    orchestrator.initialize()
    tools_run = []

    def execute(name, arguments, **_kwargs):
        tools_run.append((name, dict(arguments or {})))
        return {
            "ok": True,
            "status": "success",
            "lines": [{"line": 1, "text": '"tool_gap_count": len(tool_gaps)'}],
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )

    def chat_fn(**_kwargs):
        assert tools_run, "Index look_first must run before the first LLM call"
        return _response("tool_gap_count の定義を確認しました。")

    result = _chat_turn(
        request,
        session,
        chat_fn=chat_fn,
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert tools_run[0] == ("read_file", {"path": "ai_tool/agent_test_runner.py"})
    assert ("read_file", {"path": "tools/ai/task_runtime.py"}) in tools_run
    bridges = [
        item
        for item in result["events"]
        if item.get("type") == "capability_action_bridge"
    ]
    assert [item.get("selected_by") for item in bridges] == [
        "concept_definition_first",
        "concept_definition_first",
    ]
    assert not any(
        item.get("selected_by") == "runtime_capability_resolution" for item in bridges
    )
    assert orchestrator.pending_definition_action() is None


def test_chat_turn_consumes_observation_continuation_before_llm(monkeypatch, tmp_path):
    correlation_id = "obs-cont-before-llm"
    session = {"session_id": "obs-cont-before-llm-session", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    tools_run = []
    llm_when = []

    def execute(name, arguments, **_kwargs):
        payload = dict(arguments or {})
        tools_run.append((name, payload))
        if payload.get("after"):
            return {
                "ok": True,
                "status": "success",
                "query": "grid",
                "matches": [{"path": "AGENTS.md", "line": 1, "text": "grid"}],
                "has_more": False,
                "next_cursor": None,
                "error": None,
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "partial",
            "query": "grid",
            "matches": [{"path": "ai_tool/example.py", "line": 1, "text": "grid"}],
            "has_more": True,
            "next_cursor": "ai_tool/example.py",
            "files_scanned": 200,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )

    def chat_fn(**_kwargs):
        llm_when.append(len(tools_run))
        if len(llm_when) == 1:
            return _response()
        return _response("検索候補が複数あります。")

    result = _chat_turn(
        request,
        session,
        chat_fn=chat_fn,
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert tools_run[0][0] == "search_files"
    assert tools_run[1] == (
        "search_files",
        {"query": "grid", "path": ".", "after": "ai_tool/example.py"},
    )
    assert llm_when[0] == 0
    assert 1 not in llm_when
    assert 2 in llm_when or orchestrator.needs_human_grill()
    selected_by = [
        item.get("selected_by")
        for item in result["events"]
        if item.get("type") == "capability_action_bridge"
    ]
    assert "task_observation_continuation" in selected_by
    assert selected_by.index("task_observation_continuation") > selected_by.index(
        "runtime_capability_resolution"
    )
    assert orchestrator.current_task_id == "T1"


def test_known_path_read_e2e_keeps_unresolved_summary_condition(monkeypatch, tmp_path):
    correlation_id = "p2181-read"
    session = {"session_id": "p2181-read-session", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    request = f"{path} を実際に読み、P2-18 Safe Mutation Toolsを要約してください。"
    orchestrator = ChatTaskOrchestrator(
        correlation_id,
        request,
        completion_conditions=[
            f"{path} が読み取り可能であることが確認されている",
            "P2-18 Safe Mutation Toolsに関する記述が確認されている",
            "内容が日本語で要約されている",
        ],
    )
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {
            "ok": True,
            "status": "success",
            "lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}],
            "error": None,
            "warnings": [],
        },
    )
    responses = iter([
        _response(calls=[_tool_call("read_file", {"path": path})]),
        _response("P2-18の概要です。"),
    ])

    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    task = next(item for item in result["task_runtime"]["tasks"] if item["task_id"] == "T1")
    assert len(result["task_runtime"]["evidence"]) == 1
    assert list(task["condition_status"].values()).count("SATISFIED") == 2
    assert task["condition_status"]["内容が日本語で要約されている"] == "UNKNOWN"
    assert task["status"] == "in_progress"
    assert result["answer"]


def test_search_hit_e2e_bridges_to_read_without_confirming_absence(monkeypatch, tmp_path):
    correlation_id = "p2181-search-read"
    session = {"session_id": "p2181-search-session", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "Safe Mutation Toolsを検索し、該当する定義を確認してください。"
    orchestrator = ChatTaskOrchestrator(
        correlation_id,
        request,
        completion_conditions=["Safe Mutation Toolsの定義が確認されている"],
    )
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        if name == "search_files":
            return {
                "ok": True,
                "status": "partial",
                "matches": [{
                    "path": "docs/CURRENT_DEVELOPMENT_STATE.md",
                    "line": 1,
                    "text": "# P2-18 Safe Mutation Tools",
                }],
                "error": None,
                "warnings": [{"code": "match_limit_reached"}],
            }
        return {
            "ok": True,
            "status": "success",
            "lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}],
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "Safe Mutation Tools", "path": "."})]),
        _response("候補を観測しました。"),
        _response("候補を観測しました。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert [item[0] for item in executed] == ["search_files"]
    assert len(result["task_runtime"]["evidence"]) >= 1
    assert result["task_runtime"]["search_observations"][0]["status"] == "OBSERVED_CANDIDATES"
    assert result["task_runtime"]["search_observations"][0]["confirmed_absent"] is False
    sets = result["task_runtime"]["search_candidate_sets"]
    assert sets[0]["unique_path_count"] == 1
    assert sets[0]["read_target_selected"] is None
    assert sets[0]["read_target_reason"] == "NO_CONFIRMED_PATH_GROUND"


def test_confirmed_path_in_search_hits_bridges_to_that_read(monkeypatch, tmp_path):
    correlation_id = "p2181-search-confirmed-read"
    session = {"session_id": "p2181-search-confirmed", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    request = f"{path} を検索して確認してください。"
    orchestrator = ChatTaskOrchestrator(
        correlation_id,
        request,
        completion_conditions=["Safe Mutation Toolsの定義が確認されている"],
    )
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        if name == "search_files":
            return {
                "ok": True,
                "status": "success",
                "matches": [
                    {"path": "AGENTS.md", "line": 1, "text": "grid"},
                    {"path": path, "line": 2, "text": "# P2-18 Safe Mutation Tools"},
                ],
                "has_more": False,
                "next_cursor": None,
                "error": None,
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "success",
            "lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}],
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "CURRENT_DEVELOPMENT_STATE.md", "path": "."})]),
        _response("確認しました。"),
        _response("定義を確認しました。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert [item[0] for item in executed] == ["search_files", "read_file"]
    assert executed[1][1] == {"path": path}
    sets = result["task_runtime"]["search_candidate_sets"]
    assert sets[0]["read_target_selected"] == path
    assert sets[0]["read_target_reason"] == "CONFIRMED_UNIQUE_PATH_IN_CANDIDATES"


def test_multiple_search_hits_are_observed_without_injected_read(monkeypatch, tmp_path):
    correlation_id = "p2181-search-candidates"
    session = {"session_id": "p2181-search-candidates", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        return {
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {
                    "path": "docs/CURRENT_DEVELOPMENT_STATE.md",
                    "line": 2,
                    "text": "grid",
                },
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
        _response("候補が複数あります。"),
        _response("候補が複数あります。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert [item[0] for item in executed] == ["search_files"]
    sets = result["task_runtime"]["search_candidate_sets"]
    assert len(sets) == 1
    assert sets[0]["unique_path_count"] == 2
    assert sets[0]["substring_cardinality"] == "MULTIPLE_SUBSTRING_PATHS"
    assert sets[0]["unresolved_for_read"] is True
    assert sets[0]["read_target_selected"] is None
    assert sets[0]["read_target_reason"] == "NO_CONFIRMED_PATH_GROUND"
    followups = result["task_runtime"]["followup_investigations"]
    assert followups == []
    assert result["awaiting_human_grill"] is True
    assert result["answer_gate"]["reason"] == "awaiting_human_grill"
    assert "返信で指定してください" in result["answer"]
    assert not result.get("awaiting_human_review")
    assert "Search Candidate Set" in orchestrator.hint()


def test_semantic_followup_need_reexecutes_new_system_search(monkeypatch, tmp_path):
    correlation_id = "p2181-search-followup"
    session = {"session_id": "p2181-search-followup", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        query = str(arguments.get("query") or "")
        if query == "research":
            return {
                "ok": True,
                "status": "success",
                "query": "research",
                "matches": [
                    {"path": "research/grill_observation_v0/README.md", "line": 1, "text": "grid"},
                ],
                "has_more": False,
                "next_cursor": None,
                "error": None,
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {
                    "path": "docs/CURRENT_DEVELOPMENT_STATE.md",
                    "line": 2,
                    "text": "grid",
                },
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
        _response("researchを検索して"),
        _response("追加調査の結果を見ます。"),
        _response("追加調査の結果を見ます。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert executed[0] == ("search_files", {"query": "grid", "path": "."})
    assert "read_file" not in [item[0] for item in executed]
    assert result["awaiting_human_grill"] is True
    assert result["answer_gate"]["reason"] == "awaiting_human_grill"
    assert result["task_runtime"]["goal_read_target"]["selected"] is None
    assert result["task_runtime"]["goal_read_target"]["status"] == "UNRESOLVED"
    assert "返信で指定してください" in result["answer"]
    assert result["conversation_grill"]["reason"] == "CONFIRMED_INFO_INSUFFICIENT_FOR_NEXT_TARGET"


def test_unresolved_query_reason_is_returned_then_new_search_runs(monkeypatch, tmp_path):
    correlation_id = "p2181-followup-retry"
    session = {"session_id": "p2181-followup-retry", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        query = str(arguments.get("query") or "")
        if query == "research":
            return {
                "ok": True,
                "status": "success",
                "query": "research",
                "matches": [
                    {"path": "research/grill_observation_v0/README.md", "line": 1, "text": "grid"},
                ],
                "has_more": False,
                "next_cursor": None,
                "error": None,
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
        _response("検索して"),
        _response("researchを検索して"),
        _response("追加調査の結果を見ます。"),
        _response("追加調査の結果を見ます。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert executed == [
        ("search_files", {"query": "grid", "path": "."}),
    ]
    assert result["task_runtime"]["goal_read_target"]["selected"] is None
    assert result["awaiting_human_grill"] is True
    assert result["answer_gate"]["reason"] == "awaiting_human_grill"
    assert "返信で指定してください" in result["answer"]


def test_followup_observation_can_bridge_confirmed_goal_read(monkeypatch, tmp_path):
    correlation_id = "p2181-followup-goal-read"
    session = {"session_id": "p2181-followup-goal-read", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    request = f"{path} を検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        query = str(arguments.get("query") or "")
        if name == "read_file":
            return {
                "ok": True,
                "status": "success",
                "lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}],
                "error": None,
                "warnings": [],
            }
        if query == "research":
            return {
                "ok": True,
                "status": "success",
                "query": "research",
                "matches": [
                    {"path": "research/grill_observation_v0/README.md", "line": 1, "text": "grid"},
                    {"path": path, "line": 2, "text": "grid"},
                ],
                "has_more": False,
                "next_cursor": None,
                "error": None,
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "success",
            "query": query or "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {"path": "docs/GRILL_V0.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
        _response("researchを検索して"),
        _response("確認しました。"),
        _response("内容を要約します。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert executed[0] == ("search_files", {"query": "grid", "path": "."})
    assert orchestrator.runtime.tasks["T1"].status == "in_progress"
    assert orchestrator.current_task_id == "T1"
    assert orchestrator.current_goal_id == "G1.1"
    assert orchestrator.runtime.tasks["T2"].status == "pending"
    # Follow-up Goal confirm + read is covered without _chat_turn H4 in
    # test_followup_observation_can_confirm_goal_path_without_adopting_agent_query.


def test_agent_named_file_followup_does_not_verify_grid_summary(monkeypatch, tmp_path):
    correlation_id = "p2181-agent-named-file"
    session = {"session_id": "p2181-agent-named-file", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        if name == "read_file":
            return {
                "ok": True,
                "status": "success",
                "lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}],
                "error": None,
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {"path": path, "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
        _response(f"{path} を確認して"),
        _response("要約します。"),
        _response("要約します。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert executed == [
        ("search_files", {"query": "grid", "path": "."}),
    ]
    assert result["task_runtime"]["goal_read_target"]["selected"] is None
    assert result["awaiting_human_grill"] is True
    assert result["answer_gate"]["reason"] == "awaiting_human_grill"
    assert "返信で指定してください" in result["answer"]
    assert result["task_runtime"]["search_candidate_sets"]


def test_followup_match_text_can_confirm_goal_without_request_path(monkeypatch, tmp_path):
    correlation_id = "p2181-obs-match-text"
    session = {"session_id": "p2181-obs-match-text", "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        query = str(arguments.get("query") or "")
        if name == "read_file":
            return {
                "ok": True,
                "status": "success",
                "lines": [{"line": 1, "text": "# P2-18 Safe Mutation Tools"}],
                "error": None,
                "warnings": [],
            }
        if query == "research":
            return {
                "ok": True,
                "status": "success",
                "query": "research",
                "matches": [
                    {
                        "path": "research/grill_observation_v0/README.md",
                        "line": 1,
                        "text": f"canonical note: {path}",
                    },
                ],
                "has_more": False,
                "next_cursor": None,
                "error": None,
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {"path": path, "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([
        _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
        _response("researchを検索して"),
        _response("確認しました。"),
        _response("内容を要約します。"),
    ])
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )

    assert executed == [
        ("search_files", {"query": "grid", "path": "."}),
    ]
    assert result["task_runtime"]["goal_read_target"]["selected"] is None
    assert result["awaiting_human_grill"] is True
    assert result["answer_gate"]["reason"] == "awaiting_human_grill"
    assert "返信で指定してください" in result["answer"]


def test_conversation_grill_vague_clarification_does_not_rerun_search(monkeypatch, tmp_path):
    correlation_id = "p2181-grill-vague"
    session = {"session_id": correlation_id, "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "gridを検索して、その内容を要約してほしい。"
    first = ChatTaskOrchestrator(correlation_id, request)
    first.initialize()
    registry = load_registry_tools()
    first.configure_tool_expectation(registry, registry_tools=registry)
    first.observe_tool(
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
                {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        },
    )
    restored = ChatTaskOrchestrator.restore_from_grill_resume(
        f"{correlation_id}-2",
        first.conversation_grill_state(),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        raise AssertionError("completed search/investigation must not rerun")

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)

    def boom(**_kwargs):
        raise AssertionError("conversation Grill loop must not call the agent LLM")

    result = _chat_turn(
        "まだどれか分かりません",
        session,
        chat_fn=boom,
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=restored,
        grill_answer="まだどれか分かりません",
    )
    assert executed == []
    assert result["awaiting_human_grill"] is True
    assert result["answer_gate"]["reason"] == "awaiting_human_grill"
    assert "返信で指定してください" in result["answer"]
    assert restored.request == request
    assert any(
        item.get("name") == "conversation_grill_clarification"
        or item.get("type") == "conversation_grill_clarification"
        or item.get("event") == "conversation_grill_clarification"
        for item in result["events"]
    )


def test_conversation_grill_path_clarification_reads_without_new_search(monkeypatch, tmp_path):
    correlation_id = "p2181-grill-path"
    session = {"session_id": correlation_id, "messages": []}
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "gridを検索して、その内容を要約してほしい。"
    first = ChatTaskOrchestrator(correlation_id, request)
    first.initialize()
    registry = load_registry_tools()
    first.configure_tool_expectation(registry, registry_tools=registry)
    first.observe_tool(
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
                {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        },
    )
    restored = ChatTaskOrchestrator.restore_from_grill_resume(
        f"{correlation_id}-2",
        first.conversation_grill_state(),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    executed = []
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        assert name != "search_files"
        return {
            "ok": True,
            "status": "success",
            "lines": [{"line": 1, "text": "# Current Development State"}],
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter([_response("指定された文書の内容です。")])
    result = _chat_turn(
        path,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=restored,
        grill_answer=path,
    )
    assert executed == [("read_file", {"path": path})]
    assert result["awaiting_human_grill"] is False
    assert result["task_runtime"]["goal_read_target"]["selected"] == path
    assert result["task_runtime"]["goal_read_target"]["ground_source"] == "human_grill"
    assert not result["answer"].startswith("【未確認】")


def test_run_chat_turn_path_only_is_clarification_not_new_goal(monkeypatch, tmp_path):
    request = "gridを検索して、その内容を要約してほしい。"
    first = ChatTaskOrchestrator("grill-session-1", request)
    first.initialize()
    registry = load_registry_tools()
    first.configure_tool_expectation(registry, registry_tools=registry)
    first.observe_tool(
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
                {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        },
    )
    session = empty_session("grill-clarification-session")
    session["awaiting_human_grill"] = True
    session["conversation_grill_state"] = first.conversation_grill_state()
    executed = []
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"

    def execute(name, arguments, **_kwargs):
        executed.append((name, dict(arguments)))
        assert name != "search_files"
        return {
            "ok": True,
            "status": "success",
            "lines": [{"line": 1, "text": "# Current Development State"}],
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr("ai_tool.chat_interface.agent_turn.save_session", lambda _data: None)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Grill clarification must not start a new Goal")
        ),
    )
    responses = iter([_response("指定された文書の内容です。")])
    result = run_chat_turn(
        session,
        path,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
    )
    assert executed == [("read_file", {"path": path})]
    assert result["awaiting_human_grill"] is False
    assert result["task_runtime"]["goal_read_target"]["selected"] == path
    assert result["task_runtime"]["goals"][0]["title"] == request
