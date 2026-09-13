"""Local Agent の観測可能な処理履歴。新しい Core ではない。

Cursor ライブ監視ではない。存在しない経路は作らない。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ai_tool.chat_interface.events import now_iso
from ai_tool.chat_interface.activity_status import snapshot_activity


def _cursor_live() -> dict[str, Any]:
    return {
        "status": "NOT_OBSERVED",
        "label": "Cursor live status: NOT OBSERVED",
        "label_ja": "Cursor のライブ状態は観測していません",
        "note": "Git dirty や経過時間から実行中とは判断しません。",
    }


def new_correlation_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"ac-{stamp}-{uuid.uuid4().hex[:8]}"


def stamp_events(
    events: list[dict[str, Any]],
    *,
    correlation_id: str,
    model: str | None,
    session_id: str | None = None,
    case_id: str | None = None,
    requested_by: str = "user",
) -> list[dict[str, Any]]:
    """既存 Event に requested_by / executed_by / actor / source を足す。無いものは作らない。"""
    model_label = model or "NOT_OBSERVED"
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ev.setdefault("correlation_id", correlation_id)
        ev.setdefault("requested_by", requested_by)
        if session_id:
            ev.setdefault("session_id", session_id)
        if case_id:
            ev.setdefault("case_id", case_id)
        type_ = str(ev.get("type") or "")
        if type_ in {"llm", "llm_send", "llm_input", "llm_output"}:
            ev.setdefault("executed_by", "local_llm")
            ev.setdefault("actor", "local_llm")
            ev.setdefault("source", "ollama")
            ev.setdefault("model", model_label)
        elif type_ in {"tool_select", "tool_call", "tool_result", "compose", "web_search", "url_fetch", "tool"}:
            ev.setdefault("executed_by", "local_agent")
            ev.setdefault("actor", "local_agent")
            ev.setdefault("source", "session")
        elif type_ == "local_agent_call":
            ev.setdefault("executed_by", "local_agent")
            ev.setdefault("actor", "local_agent")
            ev.setdefault("source", "session")
            ev.setdefault("model", model_label)
        else:
            ev.setdefault("executed_by", "local_agent")
            ev.setdefault("actor", "local_agent")
            ev.setdefault("source", "session")
    return events


def _row(
    type_: str,
    *,
    actor: str,
    source: str,
    requested_by: str,
    executed_by: str,
    title: str,
    correlation_id: str,
    timestamp: str | None = None,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "stream": "local_agent",
        "kind": "activity",
        "type": type_,
        "actor": actor,
        "source": source,
        "requested_by": requested_by,
        "executed_by": executed_by,
        "confidence": "observed",
        "title": title,
        "correlation_id": correlation_id,
        "timestamp": timestamp or now_iso(),
        "model": model or "NOT_OBSERVED",
        "cursor_live": "NOT_OBSERVED",
    }
    if extra:
        row.update(extra)
    return row


def session_activity(session: dict[str, Any] | None) -> dict[str, Any]:
    """Chat UI Session で観測した Local Agent 処理。Cursor が呼んだ証明にはしない。"""
    if not session:
        return {
            "ok": True,
            "cursor_live": _cursor_live(),
            "cursor_to_local_agent": "NOT_CONNECTED",
            "research_write": "NOT_OBSERVED",
            "research_path": "NOT_CONNECTED",
            "matrix_write": "NOT_OBSERVED",
            "events": [],
            "note": "Session が無いため Local Agent 処理は観測していません。",
        }
    events: list[dict[str, Any]] = []
    sid = str(session.get("session_id") or "")
    for turn in session.get("turns") or []:
        if not isinstance(turn, dict):
            continue
        raw = [e for e in (turn.get("events") or []) if isinstance(e, dict)]
        cid = next((str(e.get("correlation_id")) for e in raw if e.get("correlation_id")), None) or "NOT_OBSERVED"
        ts = next((e.get("timestamp") for e in raw if e.get("timestamp")), None)
        model = str(turn.get("model") or "NOT_OBSERVED")
        tools = [t for t in (turn.get("tools") or []) if isinstance(t, dict)]
        case_id = str(turn.get("case_id") or "") or None
        start = len(events)
        events.append(
            _row(
                "LOCAL_AGENT_CALL",
                actor="local_agent",
                source="session",
                requested_by="user",
                executed_by="local_agent",
                title="Local Agent Call",
                correlation_id=cid,
                timestamp=ts,
                model=model,
                extra={
                    "session_id": sid,
                    "case_id": case_id,
                    "status": "error" if turn.get("is_error") else "ok",
                    "route": turn.get("route"),
                    "proposal_id": turn.get("proposal_id"),
                    "request_id": turn.get("request_id"),
                    "development_job_id": turn.get("development_job_id"),
                },
            )
        )
        events.append(
            _row(
                "LLM_CALL",
                actor="local_llm",
                source="ollama",
                requested_by="local_agent",
                executed_by="local_llm",
                title="LLM Call",
                correlation_id=cid,
                timestamp=ts,
                model=model,
                extra={"tool_selected": bool(tools), "status": "error" if turn.get("is_error") else "ok"},
            )
        )
        if not tools:
            events.append(
                _row(
                    "TOOL_CALL",
                    actor="local_agent",
                    source="session",
                    requested_by="user",
                    executed_by="local_agent",
                    title="Local Agent Tool Call: NONE",
                    correlation_id=cid,
                    timestamp=ts,
                    model=model,
                    extra={"status": "none", "name": None},
                )
            )
        search_index = 0
        for item in tools:
            name = str(item.get("name") or "")
            status = str(item.get("status") or "unknown")
            summary = item.get("summary")
            events.append(
                _row(
                    "TOOL_CALL",
                    actor="local_agent",
                    source="session",
                    requested_by="user",
                    executed_by="local_agent",
                    title=name or "tool",
                    correlation_id=cid,
                    timestamp=ts,
                    model=model,
                    extra={
                        "status": status,
                        "name": name,
                        "selected_by": "llm",
                        "layer": "real",
                    },
                )
            )
            section_keys = summary.get("composed_section_keys") if isinstance(summary, dict) else None
            if isinstance(section_keys, list) and section_keys:
                events.append(
                    _row(
                        "COMPOSE",
                        actor="local_agent",
                        source="session",
                        requested_by="user",
                        executed_by="local_agent",
                        title=name or "compose",
                        correlation_id=cid,
                        timestamp=ts,
                        model=model,
                        extra={
                            "status": "observed",
                            "name": name,
                            "sections": section_keys,
                            "independent_tool_calls": False,
                            "layer": "real",
                            "note": "Returned sections only. Child TOOL_CALL was not recorded.",
                        },
                    )
                )
            events.append(
                _row(
                    "TOOL_RESULT",
                    actor="local_agent",
                    source="session",
                    requested_by="user",
                    executed_by="local_agent",
                    title=name or "tool",
                    correlation_id=cid,
                    timestamp=ts,
                    model=model,
                    extra={
                        "status": status,
                        "name": name,
                        "summary": summary,
                        "layer": "real",
                    },
                )
            )
            if name == "search_web":
                search_index += 1
                query = summary.get("query") if isinstance(summary, dict) else None
                hit_count = summary.get("hit_count") if isinstance(summary, dict) else None
                extra = {
                    "status": status,
                    "query": query,
                    "hit_count": hit_count,
                    "search_index": search_index,
                    "layer": "real",
                    "name": name,
                }
                if isinstance(summary, dict):
                    if "backends_tried" in summary:
                        extra["backends_tried"] = summary.get("backends_tried")
                    if "web_status_overall" in summary:
                        extra["web_status_overall"] = summary.get("web_status_overall")
                    if summary.get("error"):
                        extra["error"] = summary.get("error")
                events.append(
                    _row(
                        "SEARCH",
                        actor="local_agent",
                        source="session",
                        requested_by="user",
                        executed_by="local_agent",
                        title="search_web",
                        correlation_id=cid,
                        timestamp=ts,
                        model=model,
                        extra=extra,
                    )
                )
            if name == "read_url_text":
                url = summary.get("url") if isinstance(summary, dict) else None
                events.append(
                    _row(
                        "URL_FETCH",
                        actor="local_agent",
                        source="session",
                        requested_by="user",
                        executed_by="local_agent",
                        title="read_url_text",
                        correlation_id=cid,
                        timestamp=ts,
                        model=model,
                        extra={"status": status, "url": url},
                    )
                )
        events.append(
            _row(
                "RESEARCH_PATH",
                actor="local_agent",
                source="session",
                requested_by="user",
                executed_by="local_agent",
                title="Chat → ResearchRecord",
                correlation_id=cid,
                timestamp=ts,
                model=model,
                extra={
                    "status": "NOT_CONNECTED",
                    "layer": "real",
                    "body": (
                        "ResearchRecord / run_standard_workflow は TDA experimental に存在する。"
                        "Chat はこのターンで呼び出していない。"
                    ),
                },
            )
        )
        events.append(
            _row(
                "RESEARCH_WRITE",
                actor="local_agent",
                source="session",
                requested_by="user",
                executed_by="local_agent",
                title="ResearchStore add / Matrix Write",
                correlation_id=cid,
                timestamp=ts,
                model=model,
                extra={
                    "status": "NOT_OBSERVED",
                    "layer": "real",
                    "body": (
                        "ResearchStore.add_from_run は Chat から呼ばれていない。"
                        "Chat はこのターンで Matrix へ書いていない。"
                        "Matrix は /api/matrix の別経路。"
                    ),
                },
            )
        )
        if case_id:
            for ev in events[start:]:
                if isinstance(ev, dict):
                    ev.setdefault("case_id", case_id)
    return {
        "ok": True,
        "kind": "activity",
        "cursor_live": _cursor_live(),
        "cursor_to_local_agent": "NOT_CONNECTED",
        "research_write": "NOT_OBSERVED",
        "research_path": "NOT_CONNECTED",
        "matrix_write": "NOT_OBSERVED",
        "session_id": sid,
        "active_turn": snapshot_activity(sid),
        "events": events,
        "note": (
            "Chat UI で観測した Local Agent / LLM / Tool です。"
            "Cursor が Local Agent を呼んだ経路は NOT CONNECTED。"
            "Chat → ResearchRecord は NOT CONNECTED。"
            "Matrix Write は NOT OBSERVED。"
            "Cursor ライブ状態は含みません。"
        ),
    }


def case_local_agent_bridge() -> dict[str, str]:
    """Cursor 案件と Local Agent を結ぶ経路は現時点で無い。推測しない。"""
    return {
        "cursor_to_local_agent": "NOT_CONNECTED",
        "local_agent_tool_call": "NONE",
        "research_write": "NOT_OBSERVED",
        "research_path": "NOT_CONNECTED",
        "matrix_write": "NOT_OBSERVED",
        "note": "この案件の成果物は Cursor 側の Run です。Chat UI の Local Agent 呼び出しとは結んでいません。",
    }
