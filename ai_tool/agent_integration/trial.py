"""Experimental Tool execution trial — isolated Agent/LLM loop (Phase 4).

Exposes selected experimental catalog tools to an LLM tool schema overlay without
modifying registry/tools.json or agent.py production paths.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.agent_integration.experimental_exposure import (
    build_trial_ollama_tools,
    load_registry_tools,
)
from ai_tool.agent_integration.sources import load_experimental_entries
from ai_tool.agent_integration.trial_scenarios import TrialScenario
from ai_tool.core.audit import append_audit

ChatFn = Callable[..., Any]
SearchWebFn = Callable[..., dict[str, Any]]
FetchFn = Callable[..., tuple[int, dict[str, str], bytes, str | None]]


def normalize_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        if not arguments.strip():
            return {}
        return json.loads(arguments)
    return dict(arguments)


def _catalog_index(entries_dir: Path | None) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for entry in load_experimental_entries(entries_dir=entries_dir):
        name = str(entry.get("name") or "")
        if name:
            by_name[name] = entry
    return by_name


def _registry_index() -> dict[str, dict[str, Any]]:
    return {str(t["name"]): t for t in load_registry_tools()}


@dataclass
class TrialToolSelection:
    tool_name: str
    arguments: dict[str, Any]
    source: str
    experimental: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrialExecutionRecord:
    selection: TrialToolSelection
    result: dict[str, Any] | str | list[Any] | None
    ok: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["selection"] = self.selection.to_dict()
        return d


@dataclass
class TrialScenarioResult:
    scenario_id: str
    user_request: str
    expected_tool: str
    selected_tools: list[TrialToolSelection]
    executions: list[TrialExecutionRecord]
    routing_match: bool
    final_answer: str | None
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "user_request": self.user_request,
            "expected_tool": self.expected_tool,
            "selected_tools": [s.to_dict() for s in self.selected_tools],
            "executions": [e.to_dict() for e in self.executions],
            "routing_match": self.routing_match,
            "final_answer": self.final_answer,
            "message_count": len(self.messages),
        }


@dataclass
class ExperimentalTrialResult:
    ok: bool
    tools_exposed: list[str]
    experimental_tools: list[str]
    production_tools: list[str]
    scenario_results: list[TrialScenarioResult]
    registry_modified: bool
    production_agent_path_modified: bool
    execution_count: int
    audit_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tools_exposed": self.tools_exposed,
            "experimental_tools": self.experimental_tools,
            "production_tools": self.production_tools,
            "scenario_results": [s.to_dict() for s in self.scenario_results],
            "registry_modified": self.registry_modified,
            "production_agent_path_modified": self.production_agent_path_modified,
            "execution_count": self.execution_count,
            "audit_id": self.audit_id,
            "error": self.error,
        }


def trial_system_prompt(tools: list[dict[str, Any]]) -> str:
    names = ", ".join(t["function"]["name"] for t in tools)
    return f"""
あなたは隔離 trial 環境の AI Agent です。利用可能 Tool: {names}

search_web と read_url_text の使い分け:
- search_web: キーワードで Web 検索し、複数 hits (title/snippet/url) を返す。URL 不明の探索向け。
- read_url_text: [EXPERIMENTAL] 既知 URL の HTTP GET で本文を取得する。URL が明示されているときのみ。

ルール:
1. ユーザー要求に従い、適切な Tool を 1 つ選んで引数を schema に従って生成する。
2. 存在しない引数を捏造しない。
3. ファイル作成・Registry 変更はしない。
""".strip()


def authorize_trial_execution(tool_name: str, *, experimental: bool) -> dict[str, Any]:
    """Trial gate record — experimental network tools require explicit trial context."""
    if experimental:
        return {
            "allowed": True,
            "policy": "trial_experimental",
            "decision": "allow_trial_only",
            "human_required_in_production": True,
            "note": "read_url_text is not in production registry; trial isolation only",
        }
    return {
        "allowed": True,
        "policy": "trial_production_subset",
        "decision": "allow_trial_subset",
        "human_required_in_production": False,
    }


def execute_trial_tool(
    tool_name: str,
    arguments: Any,
    *,
    catalog_by_name: dict[str, dict[str, Any]],
    registry_by_name: dict[str, dict[str, Any]] | None = None,
    fetch_fn: FetchFn | None = None,
    search_web_fn: SearchWebFn | None = None,
) -> TrialExecutionRecord:
    registry_by_name = registry_by_name or _registry_index()
    args = normalize_arguments(arguments)

    if tool_name in catalog_by_name:
        entry = catalog_by_name[tool_name]
        auth = authorize_trial_execution(tool_name, experimental=True)
        if not auth.get("allowed"):
            return TrialExecutionRecord(
                selection=TrialToolSelection(tool_name, args, "catalog", True),
                result={"error": "trial_not_authorized"},
                ok=False,
                error="trial_not_authorized",
            )
        ps = dict(entry.get("provider_specific") or {})
        module_name = str(ps.get("implementation_module") or "")
        function_name = str(ps.get("implementation_function") or "")
        module = importlib.import_module(module_name)
        function = getattr(module, function_name)
        call_args = dict(args)
        if fetch_fn is not None and tool_name == "read_url_text":
            call_args["fetch_fn"] = fetch_fn
        result = function(**call_args)
        ok = bool(result.get("ok")) if isinstance(result, dict) else True
        return TrialExecutionRecord(
            selection=TrialToolSelection(tool_name, args, "catalog", True),
            result=result,
            ok=ok,
            error=None if ok else str((result or {}).get("error") if isinstance(result, dict) else ""),
        )

    if tool_name in registry_by_name:
        entry = registry_by_name[tool_name]
        auth = authorize_trial_execution(tool_name, experimental=False)
        if not auth.get("allowed"):
            return TrialExecutionRecord(
                selection=TrialToolSelection(tool_name, args, "registry", False),
                result={"error": "trial_not_authorized"},
                ok=False,
                error="trial_not_authorized",
            )
        if tool_name == "search_web" and search_web_fn is not None:
            result = search_web_fn(**args)
        else:
            module = importlib.import_module(str(entry["module"]))
            function = getattr(module, str(entry["function"]))
            result = function(**args)
        ok = not (isinstance(result, dict) and result.get("error"))
        return TrialExecutionRecord(
            selection=TrialToolSelection(tool_name, args, "registry", False),
            result=result,
            ok=ok,
            error=str(result.get("error")) if isinstance(result, dict) and result.get("error") else None,
        )

    return TrialExecutionRecord(
        selection=TrialToolSelection(tool_name, args, "unknown", False),
        result={"error": f"unknown trial tool: {tool_name}"},
        ok=False,
        error=f"unknown trial tool: {tool_name}",
    )


def _mock_fetch_for_url(url: str) -> FetchFn:
    def fetch(
        requested_url: str,
        *,
        timeout_seconds: float,
        max_bytes: int,
        max_redirects: int,
    ) -> tuple[int, dict[str, str], bytes, str | None]:
        body = (
            f"# Release Notes\n\nTrial fixture body for {requested_url}\n"
            "Line 2: feature alpha\nLine 3: feature beta\n"
        ).encode("utf-8")
        return 200, {"content-type": "text/plain; charset=utf-8"}, body[:max_bytes], requested_url

    return fetch  # noqa: ARG001 — url captured for scenario context


def _mock_search_web(**kwargs: Any) -> dict[str, Any]:
    query = str(kwargs.get("query") or "")
    limit = kwargs.get("limit")
    hits = [
        {
            "title": f"Trial hit 1 for {query}",
            "snippet": "Mock snippet about Python 3.13 features.",
            "url": "https://example.com/python313-1",
            "backend": "trial_mock",
        },
        {
            "title": f"Trial hit 2 for {query}",
            "snippet": "Another mock snippet.",
            "url": "https://example.com/python313-2",
            "backend": "trial_mock",
        },
        {
            "title": f"Trial hit 3 for {query}",
            "snippet": "Third mock snippet.",
            "url": "https://example.com/python313-3",
            "backend": "trial_mock",
        },
    ]
    if limit is not None:
        hits = hits[: int(limit)]
    return {"query": query, "hits": hits, "backends_tried": ["trial_mock"], "error": None}


class _MockToolCall:
    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.function = type("Fn", (), {"name": name, "arguments": json.dumps(arguments)})()


class _MockMessage:
    def __init__(
        self,
        *,
        content: str | None = None,
        tool_calls: list[_MockToolCall] | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class _MockChatResponse:
    def __init__(self, message: _MockMessage) -> None:
        self.message = message


def make_mock_chat_fn(scenario: TrialScenario) -> ChatFn:
    """Deterministic mock LLM that selects tools per scenario definition."""
    calls = list(scenario.mock_tool_calls)
    step = {"i": 0}

    def chat(**kwargs: Any) -> _MockChatResponse:
        if step["i"] < len(calls):
            spec = calls[step["i"]]
            step["i"] += 1
            tc = _MockToolCall(str(spec["name"]), dict(spec.get("arguments") or {}))
            return _MockChatResponse(_MockMessage(content=None, tool_calls=[tc]))
        return _MockChatResponse(_MockMessage(content=scenario.mock_final_answer, tool_calls=[]))

    return chat


def run_trial_scenario(
    scenario: TrialScenario,
    *,
    tools: list[dict[str, Any]],
    chat_fn: ChatFn | None = None,
    catalog_entries_dir: Path | None = None,
    max_rounds: int = 3,
    fetch_fn: FetchFn | None = None,
    search_web_fn: SearchWebFn | None = None,
) -> TrialScenarioResult:
    chat = chat_fn or make_mock_chat_fn(scenario)
    catalog_by_name = _catalog_index(catalog_entries_dir)
    registry_by_name = _registry_index()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": trial_system_prompt(tools)},
        {"role": "user", "content": scenario.user_request},
    ]

    selected: list[TrialToolSelection] = []
    executions: list[TrialExecutionRecord] = []
    final_answer: str | None = None

    ollama_tools = [{k: v for k, v in t.items() if k != "_trial_meta"} for t in tools]

    for _ in range(max_rounds):
        response = chat(model="trial-mock", messages=messages, tools=ollama_tools)
        messages.append(
            {
                "role": "assistant",
                "content": response.message.content,
                "tool_calls": [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in (response.message.tool_calls or [])
                ],
            }
        )

        if not response.message.tool_calls:
            final_answer = response.message.content
            break

        for tool_call in response.message.tool_calls:
            tool_name = tool_call.function.name
            arguments = tool_call.function.arguments
            exec_record = execute_trial_tool(
                tool_name,
                arguments,
                catalog_by_name=catalog_by_name,
                registry_by_name=registry_by_name,
                fetch_fn=fetch_fn or _mock_fetch_for_url(""),
                search_web_fn=search_web_fn or _mock_search_web,
            )
            selected.append(exec_record.selection)
            executions.append(exec_record)
            content = exec_record.result
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            messages.append({"role": "tool", "tool_name": tool_name, "content": content})

    first_tool = selected[0].tool_name if selected else None
    routing_match = (
        scenario.expected_tool == "either"
        or first_tool == scenario.expected_tool
    )

    return TrialScenarioResult(
        scenario_id=scenario.scenario_id,
        user_request=scenario.user_request,
        expected_tool=scenario.expected_tool,
        selected_tools=selected,
        executions=executions,
        routing_match=routing_match,
        final_answer=final_answer,
        messages=messages,
    )


def run_experimental_trial(
    scenarios: list[TrialScenario] | None = None,
    *,
    experimental_tool_ids: list[str] | None = None,
    production_tool_names: list[str] | None = None,
    catalog_entries_dir: Path | None = None,
    chat_fn: ChatFn | None = None,
    audit: bool = True,
    audit_log: Path | None = None,
) -> ExperimentalTrialResult:
    """Run isolated experimental tool trial — registry and agent.py unchanged."""
    from ai_tool.agent_integration.trial_scenarios import DEFAULT_TRIAL_SCENARIOS

    scenario_list = scenarios or DEFAULT_TRIAL_SCENARIOS
    tools = build_trial_ollama_tools(
        experimental_tool_ids=experimental_tool_ids or ["local:read_url_text"],
        production_tool_names=production_tool_names or ["search_web"],
        entries_dir=catalog_entries_dir,
    )

    exposed = [t["function"]["name"] for t in tools]
    experimental = [
        t["function"]["name"] for t in tools if (t.get("_trial_meta") or {}).get("experimental")
    ]
    production = [
        t["function"]["name"] for t in tools if not (t.get("_trial_meta") or {}).get("experimental")
    ]

    # Production discovery reflects registry; formally adopted tools may be agent_available.
    adapter = AgentToolDiscoveryAdapter(catalog_entries_dir=catalog_entries_dir)
    _ = adapter.get_tool_descriptor("local:read_url_text")

    results: list[TrialScenarioResult] = []
    execution_count = 0
    for scenario in scenario_list:
        sr = run_trial_scenario(
            scenario,
            tools=tools,
            chat_fn=chat_fn,
            catalog_entries_dir=catalog_entries_dir,
        )
        results.append(sr)
        execution_count += len(sr.executions)

    all_routing_ok = all(r.routing_match for r in results)
    all_exec_ok = all(e.ok for r in results for e in r.executions)

    audit_id = None
    if audit:
        audit_id = append_audit(
            {
                "event": "experimental_tool_execution_trial",
                "tools_exposed": exposed,
                "experimental_tools": experimental,
                "execution_count": execution_count,
                "scenario_ids": [s.scenario_id for s in results],
                "routing_all_match": all_routing_ok,
            },
            log_path=audit_log,
        )

    return ExperimentalTrialResult(
        ok=all_routing_ok and all_exec_ok and execution_count > 0,
        tools_exposed=exposed,
        experimental_tools=experimental,
        production_tools=production,
        scenario_results=results,
        registry_modified=False,
        production_agent_path_modified=False,
        execution_count=execution_count,
        audit_id=audit_id,
    )
