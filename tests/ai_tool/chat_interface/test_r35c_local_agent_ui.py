"""R3.5-C Chat UI。mock のみ。実LLMは Local Agent 成功に数えない。"""
from __future__ import annotations

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import apply_session_model, empty_session
from ai_tool.chat_interface.events import pipeline_steps
from ai_tool.chat_interface.llm_errors import (
    LLM_ERROR_JA,
    MODEL_MISSING_JA,
    OLLAMA_DOWN_JA,
    classify_llm_error,
)
from ai_tool.chat_interface.ollama_env import resolve_default_model
from tests.ai_tool.chat_interface.test_r35b_chat_interface import _plain_chat


def test_classify_ollama_down():
    result = classify_llm_error("ConnectError: [WinError 10061] connection refused")
    assert result["kind"] == "ollama_down"
    assert "Ollamaに接続できません" in result["user_message"]


def test_classify_model_missing():
    result = classify_llm_error("ResponseError: model 'nope:1' not found (status code: 404)")
    assert result["kind"] == "model_missing"
    assert result["user_message"] == MODEL_MISSING_JA


def test_classify_llm_error_timeout():
    result = classify_llm_error("LLMTimeoutError: LLM応答が 90 秒以内に終わりませんでした")
    assert result["kind"] == "llm_error"
    assert result["user_message"] == LLM_ERROR_JA


def test_default_model_prefers_configured_if_listed():
    assert resolve_default_model(["qwen3:8b", "deepseek-coder-v2:16b"], "deepseek-coder-v2:16b") == "deepseek-coder-v2:16b"
    assert resolve_default_model(["qwen3:8b"], "missing:1") == "qwen3:8b"
    assert resolve_default_model([], "deepseek-coder-v2:16b") == "deepseek-coder-v2:16b"


def test_session_model_is_sent_to_chat(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    seen = {}
    inner = _plain_chat("次のモデルで応答します")

    def chat(**kwargs):
        seen["model"] = kwargs.get("model")
        return inner(**kwargs)

    session = empty_session("cs-test-r35c-model")
    session["model"] = "qwen3:8b"
    result = run_chat_turn(session, "こんにちは", chat_fn=chat, model="qwen3:8b")
    assert seen["model"] == "qwen3:8b"
    assert result["model"] == "qwen3:8b"
    user, assistant = session["messages"]
    assert user["role"] == "user"
    assert assistant["role"] == "assistant"
    assert user["timestamp"]
    assert user["session_id"] == "cs-test-r35c-model"
    assert user["model"] == "qwen3:8b"
    assert assistant["content"] == "次のモデルで応答します"


def test_llm_error_is_not_agent_answer(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")

    def boom(**_kwargs):
        raise ConnectionError("connection refused")

    session = empty_session("cs-test-r35c-err")
    result = run_chat_turn(session, "こんにちは", chat_fn=boom, model="qwen3:8b")
    assert result["is_error"] is True
    assert result["answer"] == ""
    assert result["user_error"] == OLLAMA_DOWN_JA
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "error"
    assert "Ollamaに接続できません" in session["messages"][1]["content"]


def test_apply_session_model_selects_existing_only(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    live = {
        "reachable": True,
        "models": ["deepseek-coder-v2:16b", "qwen3:8b"],
        "error": None,
        "user_message": None,
        "configured_model": "deepseek-coder-v2:16b",
        "default_model": "deepseek-coder-v2:16b",
    }
    monkeypatch.setattr("ai_tool.chat_interface.ollama_env.list_live_models", lambda: live)
    session = empty_session("cs-test-r35c-switch")
    session["model"] = "deepseek-coder-v2:16b"
    ok = apply_session_model(session, "qwen3:8b")
    assert ok["ok"] is True
    assert session["model"] == "qwen3:8b"
    assert any(e.get("type") == "model_change" for e in session["events"])
    assert session["messages"][-1]["role"] == "notice"
    missing = apply_session_model(session, "does-not-exist:1")
    assert missing["ok"] is False
    assert missing["error_kind"] == "model_missing"
    assert session["model"] == "qwen3:8b"


def test_apply_session_model_resolves_profile_id_before_provider_check(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "ai_tool.chat_interface.ollama_env.list_live_models",
        lambda: {
            "reachable": True,
            "models": ["qwen3:14b"],
            "error": None,
            "user_message": None,
        },
    )
    session = empty_session("cs-test-profile-id")

    result = apply_session_model(session, "qwen3_14b")

    assert result["ok"] is True
    assert session["model"] == "qwen3:14b"


def test_pipeline_does_not_claim_unrun_search():
    steps = pipeline_steps(model="qwen3:8b", tools=[], error=None, web_search=False)
    search = [s for s in steps if s["id"] == "search_capability"][0]
    assert search["executed"] is False
    assert "available" in search["label"].lower()
    labels = [s["label"] for s in steps]
    assert "ユーザー入力" in labels
    assert "Local Agent" in labels
    assert "LLM" in labels
    assert "回答" in labels
    assert not any(s["id"] == "tool" for s in steps)
