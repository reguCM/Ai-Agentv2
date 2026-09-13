"""
実行主体（Actor Identity）の最小記録。

Judge / PLAN_GATE / 能力判定とは独立。
「誰が実行したか」だけを記録し、結果の良し悪しは判定しない。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- 正式名称（報告・ログでこれを使う） ---
PROJECT_AGENT = "PROJECT_AGENT"
PROJECT_AGENT_LLM = "PROJECT_AGENT_LLM"
RESEARCH_PIPELINE = "RESEARCH_PIPELINE"
LOCAL_JUDGE = "LOCAL_JUDGE"
GLOBAL_JUDGE = "GLOBAL_JUDGE"
PLAN_GATE = "PLAN_GATE"
CURSOR_CONTROLLER = "CURSOR_CONTROLLER"
CURSOR_EXPLORER = "CURSOR_EXPLORER"
CURSOR_SHELL = "CURSOR_SHELL"
CURSOR_VALIDATION = "CURSOR_VALIDATION"
HUMAN = "HUMAN"
UNKNOWN = "UNKNOWN"

_DEFAULT_RELATIVE_LOG = Path("logs") / "execution_identity.jsonl"
_DIGEST_MAX_CHARS = 500


def ollama_endpoint() -> str:
    return (os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")


def log_path() -> Path:
    raw = (os.environ.get("AI_AGENT_EXECUTION_LOG") or "").strip()
    if raw:
        return Path(raw)
    # リポジトリ root（本ファイル: tools/system/execution_identity.py）
    root = Path(__file__).resolve().parents[2]
    return root / _DEFAULT_RELATIVE_LOG


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest_result(result: Any, *, max_chars: int = _DIGEST_MAX_CHARS) -> dict:
    """巨大結果を複製せず、判別用ダイジェストだけ返す。"""
    try:
        if isinstance(result, (dict, list)):
            text = json.dumps(result, ensure_ascii=False, default=str)
        else:
            text = str(result)
    except Exception as exc:
        return {
            "type": type(result).__name__,
            "error": f"digest_failed:{type(exc).__name__}",
        }

    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
    preview = text if len(text) <= max_chars else text[:max_chars] + "…"
    return {
        "type": type(result).__name__,
        "sha256_16": digest,
        "chars": len(text),
        "preview": preview,
    }


def record_event(event: dict) -> dict:
    """
    JSONL 1行を追記し、同じ内容を stdout にも1行出す。
    失敗しても呼び出し元の本処理は止めない。
    """
    payload = dict(event)
    payload.setdefault("ts", _now_iso())
    path = log_path()
    line = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        print(
            f"[EXECUTION_IDENTITY] write_failed path={path} error={exc}",
            file=sys.stderr,
        )
    actor = payload.get("execution_actor", UNKNOWN)
    ev = payload.get("event", "event")
    print(f"[EXECUTION_IDENTITY] event={ev} EXECUTION_ACTOR={actor}")
    return payload


def log_run_start(
    *,
    execution_actor: str,
    entrypoint: str,
    llm: str | None = None,
    extra: dict | None = None,
) -> dict:
    payload = {
        "event": "run_start",
        "execution_actor": execution_actor,
        "entrypoint": entrypoint,
        "llm": llm,
        "ollama_endpoint": ollama_endpoint(),
        "pid": os.getpid(),
        "python": sys.executable,
    }
    if extra:
        payload.update(extra)
    return record_event(payload)


def log_tool_call(
    *,
    execution_actor: str,
    tool_name: str,
    arguments: Any = None,
    extra: dict | None = None,
) -> dict:
    payload = {
        "event": "tool_call",
        "execution_actor": execution_actor,
        "tool_name": tool_name,
        "arguments": arguments if arguments is not None else {},
    }
    if extra:
        payload.update(extra)
    return record_event(payload)


def log_tool_result(
    *,
    execution_actor: str,
    tool_name: str,
    result: Any = None,
    error: str | None = None,
    extra: dict | None = None,
) -> dict:
    payload = {
        "event": "tool_result",
        "execution_actor": execution_actor,
        "tool_name": tool_name,
        "result_digest": digest_result(result) if error is None else None,
        "error": error,
    }
    if extra:
        payload.update(extra)
    return record_event(payload)
