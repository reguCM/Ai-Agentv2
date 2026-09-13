"""Production Agent web tool loop mirror — same enrichment/boundary path as agent.py.

Importable (agent.py is not). Uses registry + agent_tool_gate + enrich_web_tool_result
+ WebSessionTracker + apply_web_answer_boundary identically to agent.py tool loop.
"""
from __future__ import annotations

import importlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    ollama_tools_for_llm,
    registry_index,
)
from ai_tool.agent_integration.production_bridge import append_experimental_agent_tools
from ai_tool.agent_integration.trial import normalize_arguments
from tools.system.agent_tool_gate import authorize_tool_execution, blocked_result, load_trust_store
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.execution_identity import PROJECT_AGENT, log_tool_call, log_tool_result
from tools.system.network.web_answer_boundary import apply_web_answer_boundary
from tools.system.network.web_evidence import enrich_web_tool_result
from tools.system.network.web_status import WebSessionTracker, user_visible_status_message
from tools.system.network.search_web import search_web as default_search_web
from ai_tool.experimental.read_url.reader import read_url_text as default_read_url_text

ChatFn = Callable[..., Any]
ToolFn = Callable[..., dict[str, Any]]


def _auto_confirm(_tool_name: str, _arguments: Any) -> str:
    return "y"


@dataclass
class ToolExecutionRecord:
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    web_status: dict[str, Any] | None = None
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentWebLoopResult:
    user_request: str
    path: str
    tool_executions: list[ToolExecutionRecord] = field(default_factory=list)
    raw_llm_answer: str | None = None
    final_answer: str | None = None
    boundary_applied: bool = False
    system_notice: str | None = None
    web_session_aggregate: dict[str, Any] | None = None
    rounds: int = 0
    error: str | None = None
    live: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_request": self.user_request,
            "path": self.path,
            "tool_executions": [t.to_dict() for t in self.tool_executions],
            "raw_llm_answer": self.raw_llm_answer,
            "final_answer": self.final_answer,
            "boundary_applied": self.boundary_applied,
            "system_notice": self.system_notice,
            "web_session_aggregate": self.web_session_aggregate,
            "rounds": self.rounds,
            "error": self.error,
            "live": self.live,
        }


def execute_registry_tool_with_gate(
    tool_name: str,
    arguments: Any,
    *,
    user_request: str,
    search_web_fn: ToolFn | None = None,
    read_url_text_fn: ToolFn | None = None,
    ask_confirm: Callable[[str, Any], str | None] | None = None,
    trust_path: Path | None = None,
) -> dict[str, Any]:
    """Mirror of agent.py execute_tool for registry web tools."""
    args = normalize_arguments(arguments)
    reg = registry_index()
    if tool_name not in reg:
        return {"ok": False, "error": f"unknown tool: {tool_name}"}

    store_path = trust_path
    auth = authorize_tool_execution(
        tool_name,
        args,
        ask_confirm=ask_confirm or _auto_confirm,
        store_path=store_path,
    )
    if not auth.get("allowed"):
        denied = blocked_result(tool_name, reason=str(auth.get("decision") or "deny"), arguments=args)
        log_tool_call(
            execution_actor=PROJECT_AGENT,
            tool_name=tool_name,
            arguments=args,
            extra={"agent_tool_gate": auth, "blocked": True, "mirror_loop": True},
        )
        return denied

    log_tool_call(
        execution_actor=PROJECT_AGENT,
        tool_name=tool_name,
        arguments=args,
        extra={"agent_tool_gate": auth, "mirror_loop": True},
    )

    if tool_name == "search_web":
        fn = search_web_fn or default_search_web
        result = fn(**args)
    elif tool_name == "read_url_text":
        fn = read_url_text_fn or default_read_url_text
        result = fn(**args)
    else:
        entry = reg[tool_name]
        module = importlib.import_module(str(entry["module"]))
        function = getattr(module, str(entry["function"]))
        result = function(**args)

    log_tool_result(
        execution_actor=PROJECT_AGENT,
        tool_name=tool_name,
        result=result,
        extra={"agent_tool_gate": auth, "mirror_loop": True},
    )
    return result if isinstance(result, dict) else {"result": result}


def agent_web_system_prompt() -> str:
    """Agent web rules aligned with agent.py SYSTEM_PROMPT web section."""
    return """
あなたは PROJECT_AGENT です。Web調査には search_web と read_url_text を使います。

Web調査の手順（Search → Fetch → Evidence）:
1. URLが分からない → search_web
2. 特定 URL の本文 → read_url_text
3. main_text と quality.fact_ready を確認する
4. hits / main_text に無い数値・URLを補完しない
5. search_web が空、または grounding.do_not_claim_web_verified_facts のとき、Web確認済み体裁の数値を述べない
6. tool result の web_status.overall が SUCCESS 以外のとき、Web確認済みの具体的事実として回答しない
7. 検索でも確認できない場合は「確認できなかった」と書く

ルール:
- Tool schema に従った引数のみ
- 不明は未確認と書く
""".strip()


def run_production_agent_web_loop(
    user_request: str,
    *,
    chat_fn: ChatFn,
    model: str,
    search_web_fn: ToolFn | None = None,
    read_url_text_fn: ToolFn | None = None,
    trust_path: Path | None = None,
    max_rounds: int | None = None,
    path_label: str = "production_mirror",
    live: bool = False,
    system_prompt: str | None = None,
) -> AgentWebLoopResult:
    pipeline = get_pipeline()
    max_r = int(max_rounds or pipeline.get("max_tool_rounds") or 5)

    base_tools = build_production_agent_tools()
    tools = append_experimental_agent_tools(base_tools)
    llm_tools = ollama_tools_for_llm(tools)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt or agent_web_system_prompt()},
        {"role": "user", "content": user_request},
    ]

    web_session = WebSessionTracker()
    executions: list[ToolExecutionRecord] = []
    raw_answer: str | None = None
    rounds = 0

    try:
        for _ in range(max_r):
            rounds += 1
            response = chat_fn(model=model, messages=messages, tools=llm_tools)
            messages.append(response.message)

            if not response.message.tool_calls:
                raw_answer = str(getattr(response.message, "content", None) or "")
                break

            for tool_call in response.message.tool_calls:
                tool_name = tool_call.function.name
                arguments = tool_call.function.arguments
                result = execute_registry_tool_with_gate(
                    tool_name,
                    arguments,
                    user_request=user_request,
                    search_web_fn=search_web_fn,
                    read_url_text_fn=read_url_text_fn,
                    trust_path=trust_path,
                )
                result = enrich_web_tool_result(tool_name, result)
                web_session.record(tool_name, result)
                ws = result.get("web_status") if isinstance(result, dict) else None
                executions.append(
                    ToolExecutionRecord(
                        tool_name=tool_name,
                        arguments=normalize_arguments(arguments),
                        result=result if isinstance(result, dict) else {"raw": result},
                        web_status=ws if isinstance(ws, dict) else None,
                        blocked=bool(isinstance(result, dict) and result.get("blocked_by_agent_tool_gate")),
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": json.dumps(result, ensure_ascii=False, indent=2)
                        if isinstance(result, dict)
                        else str(result),
                    }
                )
        else:
            raw_answer = str(getattr(messages[-1], "content", None) or "")

        boundary = apply_web_answer_boundary(raw_answer or "", web_session)
        agg = web_session.aggregate()
        notice = boundary.get("system_notice") or user_visible_status_message(agg)

        return AgentWebLoopResult(
            user_request=user_request,
            path=path_label,
            tool_executions=executions,
            raw_llm_answer=raw_answer,
            final_answer=boundary.get("answer"),
            boundary_applied=bool(boundary.get("boundary_applied")),
            system_notice=notice,
            web_session_aggregate=agg,
            rounds=rounds,
            live=live,
        )
    except Exception as exc:  # noqa: BLE001
        return AgentWebLoopResult(
            user_request=user_request,
            path=path_label,
            tool_executions=executions,
            raw_llm_answer=raw_answer,
            error=f"{type(exc).__name__}: {exc}",
            web_session_aggregate=web_session.aggregate(),
            rounds=rounds,
            live=live,
        )


def make_e2e_trust_file(target: Path) -> Path:
    """Non-interactive trust for search_web + read_url_text (eval only)."""
    store = load_trust_store()
    store["auto_allow"] = sorted(set(store.get("auto_allow") or []) | {"search_web", "read_url_text"})
    store["note"] = "Web Status Live E2E eval only — not production default"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def default_live_model() -> str:
    return str(get_llm_profile("qwen3_8b").get("model") or get_llm_profile().get("model") or "")
