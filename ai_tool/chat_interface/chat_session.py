"""Chat Session の JSON 保存。新しい Session Core ではない。

会話履歴と Event を持つ。
Experimental の DevelopmentSessionState は optional で同梱するだけ。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.chat_interface.events import now_iso
from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
)
from ai_tool.experimental.development_assistance.research_record import ResearchStore

_REPO = Path(__file__).resolve().parents[2]
SESSIONS_DIR = _REPO / "runs" / "chat_ui" / "sessions"


def sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def new_session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"cs-{stamp}-{uuid.uuid4().hex[:6]}"


def make_message(
    role: str,
    content: str,
    *,
    session_id: str,
    model: str | None = None,
) -> dict[str, Any]:
    return {
        "role": role,
        "content": content,
        "timestamp": now_iso(),
        "session_id": session_id,
        "model": model or None,
    }


def empty_session(session_id: str | None = None) -> dict[str, Any]:
    sid = session_id or new_session_id()
    return {
        "session_id": sid,
        "started_at": now_iso(),
        "executor": "local_agent",
        "cursor_connected": False,
        "model": None,
        "messages": [],
        "turns": [],
        "events": [],
        "last_test_result": None,
        "research_record_id": None,
        "research_saved": False,
        "development_jobs": [],
        "active_case_id": None,
        "experimental_session": DevelopmentSessionState().as_session_dict(),
        "note": (
            "Chat UI Session。DevelopmentSessionState を再利用する。"
            "ResearchRecord は Agent 経路では自動保存しない。"
        ),
    }


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.json"


def load_session(session_id: str) -> dict[str, Any]:
    path = session_path(session_id)
    if not path.is_file():
        data = empty_session(session_id)
        save_session(data)
        return data
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = empty_session(session_id)
    data.setdefault("messages", [])
    data.setdefault("turns", [])
    data.setdefault("events", [])
    data.setdefault("cursor_connected", False)
    data.setdefault("executor", "local_agent")
    data.setdefault("model", None)
    data.setdefault("development_jobs", [])
    data.setdefault("active_case_id", None)
    return data


def append_session_message(
    session: dict[str, Any],
    role: str,
    content: str,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    item = make_message(
        role,
        content,
        session_id=str(session.get("session_id") or ""),
        model=model if model is not None else session.get("model"),
    )
    session.setdefault("messages", []).append(item)
    return item


def apply_session_model(session: dict[str, Any], model: str) -> dict[str, Any]:
    """現在の Chat Session で使うモデルを変える。Ollama 本体は触らない。"""
    from ai_tool.chat_interface.events import event
    from ai_tool.chat_interface.llm_errors import (
        MODEL_MISSING_JA,
        NO_MODELS_JA,
        OLLAMA_DOWN_JA,
    )
    from ai_tool.chat_interface.ollama_env import list_live_models
    from tools.system.model_registry import resolve_provider_model_name

    name = resolve_provider_model_name(model)
    live = list_live_models()
    if not live.get("reachable"):
        return {
            "ok": False,
            "is_error": True,
            "error_kind": "ollama_down",
            "user_error": OLLAMA_DOWN_JA,
            "error": live.get("error") or "Ollama unreachable",
            "session": session,
            "models": live,
        }
    available = list(live.get("models") or [])
    if not available:
        return {
            "ok": False,
            "is_error": True,
            "error_kind": "no_models",
            "user_error": NO_MODELS_JA,
            "error": live.get("error") or "no models",
            "session": session,
            "models": live,
        }
    if name not in available:
        return {
            "ok": False,
            "is_error": True,
            "error_kind": "model_missing",
            "user_error": MODEL_MISSING_JA,
            "error": f"model not in ollama list: {name}",
            "session": session,
            "models": live,
        }
    previous = session.get("model")
    session["model"] = name
    notice = f"モデルを {name} に変更しました"
    if previous and previous != name:
        notice = f"モデルを {previous} から {name} に変更しました"
    elif previous == name:
        notice = f"使用モデルは {name} のままです"
    session.setdefault("events", []).append(
        event(
            "model_change",
            previous=previous,
            model=name,
            message=notice,
        )
    )
    if previous != name:
        append_session_message(session, "notice", notice, model=name)
    save_session(session)
    return {
        "ok": True,
        "session": session,
        "previous": previous,
        "model": name,
        "notice": notice,
        "models": live,
    }


def save_session(data: dict[str, Any]) -> Path:
    path = session_path(str(data["session_id"]))
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def research_store_from_session(_data: dict[str, Any]) -> ResearchStore:
    """Agent は ResearchRecord を保存しない。空 store を返す（推測で埋めない）。"""
    return ResearchStore()


def development_state_from_session(data: dict[str, Any]) -> DevelopmentSessionState:
    raw = data.get("experimental_session") or {}
    state = DevelopmentSessionState()
    state.last_research_id = str(raw.get("last_research_id") or "")
    state.bound_label = str(raw.get("bound_label") or "")
    state.last_python = str(raw.get("last_python") or "")
    state.last_os = str(raw.get("last_os") or "")
    state.last_environment = str(raw.get("last_environment") or "")
    state.last_cuda = str(raw.get("last_cuda") or "")
    state.last_test = raw.get("last_test_result")
    state.awaiting_human_review = bool(raw.get("awaiting_human_review"))
    return state
