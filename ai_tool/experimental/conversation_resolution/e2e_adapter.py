"""E2E adapter: Production mirror web loop → Evidence → Conversation Resolution.

Does NOT modify Production Search/Fetch/Agent/Registry/Prompt.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Literal

from ai_tool.agent_integration.eval_production_parity_bridge import (
    EvalPathMetadata,
    run_canonical_web_eval,
)
from ai_tool.agent_integration.production_agent_web_loop import AgentWebLoopResult
from ai_tool.experimental.conversation_resolution.resolver import (
    handle_follow_up,
    initialize_conversation,
    parse_follow_up_intent,
    resolve_initial_turn,
)
from ai_tool.experimental.evidence_context.packager import EvidenceSource
from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from tools.system.network.web_evidence import enrich_web_tool_result

FailureLayer = Literal[
    "WEB_FAILURE",
    "EVIDENCE_FAILURE",
    "CANDIDATE_FAILURE",
    "LLM_FAILURE",
    "USER_RESOLUTION_FAILURE",
    "NONE",
]

ToolFn = Callable[..., dict[str, Any]]
ChatFn = Callable[..., Any]

_URL_RE = re.compile(r"https?://[^\s\)\]\"\'<>、。）]+")


def make_canonical_tool_chat(
    mock_tool_calls: list[dict[str, Any]],
    *,
    final_answer: str = "Web調査の結果を確認しました。",
) -> ChatFn:
    """Deterministic agent-loop LLM that issues tool calls then stops."""
    calls = list(mock_tool_calls)
    step = {"i": 0}

    class _ToolCall:
        def __init__(self, name: str, arguments: dict[str, Any]) -> None:
            self.function = type("Fn", (), {"name": name, "arguments": json.dumps(arguments)})()

    class _Message:
        def __init__(self, *, content: str | None = None, tool_calls: list[_ToolCall] | None = None) -> None:
            self.content = content
            self.tool_calls = tool_calls or []

    class _Response:
        def __init__(self, message: _Message) -> None:
            self.message = message

    def chat(**kwargs: Any) -> _Response:
        if step["i"] < len(calls):
            spec = calls[step["i"]]
            step["i"] += 1
            tc = _ToolCall(str(spec["name"]), dict(spec.get("arguments") or {}))
            return _Response(_Message(content=None, tool_calls=[tc]))
        return _Response(_Message(content=final_answer, tool_calls=[]))

    return chat


def make_multi_fixture_read_url_fn(url_html: dict[str, str]) -> ToolFn:
    """Map URL → HTML fixture for canonical eval read_url_text."""
    normalized: dict[str, dict[str, Any]] = {}
    for url, html in url_html.items():
        normalized[url] = normalize_html_to_evidence(html)

    def fn(**kwargs: Any) -> dict[str, Any]:
        u = str(kwargs.get("url") or "")
        ev = normalized.get(u)
        if ev is None:
            return enrich_web_tool_result(
                "read_url_text",
                {"ok": False, "url": u, "error": f"fixture not configured for {u}"},
            )
        return enrich_web_tool_result(
            "read_url_text",
            {
                "ok": True,
                "url": u,
                "main_text": ev.get("main_text") or "",
                "quality": ev.get("quality") or {},
            },
        )

    return fn


def make_fixture_search_fn(hits: list[dict[str, Any]]) -> ToolFn:
    def fn(**kwargs: Any) -> dict[str, Any]:
        q = str(kwargs.get("query") or "")
        return enrich_web_tool_result(
            "search_web",
            {"query": q, "hits": hits, "backends_tried": ["fixture"]},
        )

    return fn


def evidence_sources_from_loop(loop: AgentWebLoopResult) -> list[EvidenceSource]:
    """Extract all successful read_url_text executions as EvidenceSource list."""
    sources: list[EvidenceSource] = []
    seen_urls: set[str] = set()
    for ex in loop.tool_executions:
        if ex.tool_name != "read_url_text":
            continue
        result = ex.result if isinstance(ex.result, dict) else {}
        if result.get("ok") is False or ex.blocked:
            continue
        url = str(result.get("url") or ex.arguments.get("url") or "")
        if not url or url in seen_urls:
            continue
        main_text = str(result.get("main_text") or "")
        if not main_text.strip():
            continue
        quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
        ws = ex.web_status or {}
        backend = str(ws.get("backend") or quality.get("backend") or "web")
        title = str(result.get("title") or quality.get("title") or url)
        sources.append(
            EvidenceSource(
                url=url,
                title=title,
                main_text=main_text,
                quality=quality,
                backend=backend,
            )
        )
        seen_urls.add(url)
    return sources


def classify_web_failure(loop: AgentWebLoopResult, sources: list[EvidenceSource]) -> FailureLayer | None:
    if loop.error:
        return "WEB_FAILURE"
    fetch_execs = [ex for ex in loop.tool_executions if ex.tool_name == "read_url_text"]
    if not fetch_execs:
        if any(ex.tool_name == "search_web" for ex in loop.tool_executions):
            return "WEB_FAILURE"
        return "WEB_FAILURE"
    if not sources:
        all_failed = all(
            (isinstance(ex.result, dict) and ex.result.get("ok") is False) or ex.blocked
            for ex in fetch_execs
        )
        if all_failed:
            return "WEB_FAILURE"
        return "EVIDENCE_FAILURE"
    return None


def classify_evidence_failure(sources: list[EvidenceSource]) -> FailureLayer | None:
    if not sources:
        return "EVIDENCE_FAILURE"
    usable = [
        s
        for s in sources
        if len(s.main_text.strip()) >= 15
        or (s.quality or {}).get("fact_ready")
        or (s.quality or {}).get("extraction_success")
    ]
    if not usable:
        return "EVIDENCE_FAILURE"
    return None


def extract_urls_from_text(text: str) -> list[str]:
    return _URL_RE.findall(text or "")


def check_url_integrity(
    *,
    known_urls: set[str],
    texts: list[str],
    allow_fixture: bool = True,
) -> tuple[bool, list[str]]:
    unknown: list[str] = []
    for text in texts:
        for url in extract_urls_from_text(text):
            if url in known_urls:
                continue
            if allow_fixture and ("fixture" in url or url.startswith("https://fixture")):
                continue
            unknown.append(url)
    return len(unknown) == 0, unknown


def run_canonical_evidence_collection(
    user_request: str,
    *,
    mock_tool_calls: list[dict[str, Any]],
    search_web_fn: ToolFn | None = None,
    read_url_text_fn: ToolFn | None = None,
    final_answer: str = "Web調査の結果を確認しました。",
    live: bool = False,
    model: str = "e2e-mock",
) -> tuple[AgentWebLoopResult, EvalPathMetadata, list[EvidenceSource], FailureLayer | None]:
    chat = make_canonical_tool_chat(mock_tool_calls, final_answer=final_answer)
    loop, meta = run_canonical_web_eval(
        user_request,
        chat_fn=chat,
        model=model,
        search_web_fn=search_web_fn,
        read_url_text_fn=read_url_text_fn,
        live=live,
        scored=True,
    )
    if loop.error:
        return loop, meta, [], "WEB_FAILURE"

    fetch_execs = [ex for ex in loop.tool_executions if ex.tool_name == "read_url_text"]
    if not fetch_execs and not any(ex.tool_name == "search_web" for ex in loop.tool_executions):
        return loop, meta, [], "WEB_FAILURE"

    sources = evidence_sources_from_loop(loop)
    if fetch_execs:
        all_failed = all(
            (isinstance(ex.result, dict) and ex.result.get("ok") is False) or ex.blocked
            for ex in fetch_execs
        )
        if all_failed:
            return loop, meta, sources, "WEB_FAILURE"

    if not sources:
        return loop, meta, sources, "EVIDENCE_FAILURE"
    ev_fail = classify_evidence_failure(sources)
    if ev_fail:
        return loop, meta, sources, ev_fail
    return loop, meta, sources, None


def run_resolution_pipeline(
    sources: list[EvidenceSource],
    *,
    user_request: str,
    topic: str,
    expected_facts: list[Any] | None,
    follow_ups: list[tuple[str, str, str]],
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    state, envelope = initialize_conversation(
        sources,
        user_request=user_request,
        topic=topic,
        expected_facts=expected_facts,
    )
    initial = resolve_initial_turn(
        state,
        envelope,
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )

    follow_results: list[dict[str, Any]] = []
    failures: list[str] = []
    for message, expected_intent, check in follow_ups:
        parsed = parse_follow_up_intent(message)
        if parsed != expected_intent:
            failures.append(f"intent {message!r} expected {expected_intent} got {parsed}")
        fu = handle_follow_up(
            state,
            envelope,
            message,
            chat_fn=chat_fn,
            model=model,
            llm_enabled=llm_enabled,
        )
        follow_results.append({"message": message, "result": fu})

        if check == "selection_persist" and not fu.get("selected_candidate_id"):
            failures.append("selection not persisted")
        if check == "selection_b" and fu.get("selected_candidate_id") != "CB":
            failures.append("B not selected")
        if check == "source_url":
            body = str(fu.get("body") or "")
            if "http" not in body and not (initial.get("presentation") or {}).get("source_links"):
                failures.append("source URL not navigable")
        if check == "dual_source" and "出典" not in str(fu.get("body") or ""):
            failures.append("dual source not shown")
        if check == "state_persist_turn2" and not state.selected_candidate_id:
            failures.append("selection lost on turn 2")

    known_urls = {c.url for c in state.candidates}
    all_texts = [str(initial.get("llm_body") or "")]
    all_texts.extend(str(fu["result"].get("body") or "") for fu in follow_results)
    url_ok, unknown_urls = check_url_integrity(known_urls=known_urls, texts=all_texts)
    if not url_ok:
        failures.append(f"url integrity: unknown urls {unknown_urls}")

    failure_layer: FailureLayer = "NONE"
    if not state.candidates:
        failure_layer = "CANDIDATE_FAILURE"
        failures.append("no candidates built")
    elif any("selection" in f for f in failures):
        failure_layer = "USER_RESOLUTION_FAILURE"

    return {
        "state": {
            "presentation_mode": state.presentation_mode,
            "relation": state.relation,
            "selected_candidate_id": state.selected_candidate_id,
            "candidate_count": len(state.candidates),
            "candidate_ids": [c.candidate_id for c in state.candidates],
        },
        "envelope_summary": {
            "candidate_count": len(envelope.get("candidates") or []),
            "relation": envelope.get("relation"),
            "difference_note": envelope.get("difference_note"),
        },
        "initial_turn": initial,
        "follow_ups": follow_results,
        "url_integrity": url_ok,
        "unknown_urls": unknown_urls,
        "failures": failures,
        "failure_layer": failure_layer,
        "pass": len(failures) == 0,
    }
