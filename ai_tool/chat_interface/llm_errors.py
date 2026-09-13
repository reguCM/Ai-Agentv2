"""LLM / Ollama の失敗を、ユーザー向け文言に分ける。

エラーを Agent の回答として見せないための分類。
"""
from __future__ import annotations

from typing import Any


OLLAMA_DOWN_JA = "Ollamaに接続できません。\nOllamaが起動しているか確認してください。"
MODEL_MISSING_JA = "選択されたモデルがOllamaから見つかりません。"
LLM_ERROR_JA = "LLM処理中にエラーが発生しました。詳細は処理ログを確認してください。"
NO_MODELS_JA = "利用可能なLLMモデルがありません"
OLLAMA_UNREACHABLE_JA = "Ollamaに接続できません"


def classify_llm_error(exc: str | BaseException | None) -> dict[str, str]:
    text = str(exc or "")
    low = text.lower()
    if _is_timeout(low) and not _is_connection(low):
        return {"kind": "llm_error", "user_message": LLM_ERROR_JA, "detail": text}
    if _is_connection(low):
        return {"kind": "ollama_down", "user_message": OLLAMA_DOWN_JA, "detail": text}
    if _is_model_missing(low, text):
        return {"kind": "model_missing", "user_message": MODEL_MISSING_JA, "detail": text}
    return {"kind": "llm_error", "user_message": LLM_ERROR_JA, "detail": text}


def _is_timeout(low: str) -> bool:
    return any(token in low for token in ("timeout", "timed out", "llmtimeout"))


def _is_connection(low: str) -> bool:
    return any(
        token in low
        for token in (
            "connection refused",
            "connecterror",
            "connect error",
            "connectionerror",
            "10061",
            "failed to establish",
            "actively refused",
            "cannot connect",
            "connection abort",
            "winerror 10061",
            "no connection could be made",
            "name or service not known",
        )
    )


def _is_model_missing(low: str, original: str) -> bool:
    if "404" in original or "404" in low:
        return "model" in low or "not found" in low or "file does not exist" in low
    if "model" in low and "not found" in low:
        return True
    if "file does not exist" in low:
        return True
    return False


def error_payload(
    exc: str | BaseException | None,
    *,
    session_id: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    classified = classify_llm_error(exc)
    return {
        "ok": False,
        "is_error": True,
        "error_kind": classified["kind"],
        "error": classified["detail"],
        "user_error": classified["user_message"],
        "session_id": session_id,
        "model": model,
        "executor": "local_agent",
        "cursor_connected": False,
    }
