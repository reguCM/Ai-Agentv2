"""LLM 仕様候補 Phase 1。自由文成功・上書き・COMPLETE を禁止する。"""
from __future__ import annotations

import json
from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.spec_proposal.propose import propose_specification, request_id_for
from ai_tool.spec_proposal.schema import normalize_claim_lists
from ai_tool.spec_proposal.store import list_by_request_id, load_jsonl


class _Msg:
    def __init__(self, content=""):
        self.content = content
        self.tool_calls = []


class _Resp:
    def __init__(self, message):
        self.message = message


def _chat(content: str):
    def fn(**_kwargs):
        return _Resp(_Msg(content=content))

    return fn


VALID = {
    "proposed_specification": "CPU温度を返す。Registry 登録はしない。",
    "objectives": ["温度を返す"],
    "inputs": [],
    "outputs": ["摂氏"],
    "behavior": ["既存観測経路を使う"],
    "constraints": ["ファイル作成禁止"],
    "completion_conditions": ["人間確認後に完成判定"],
    "confirmed": [{"text": "Toolを作る要求がある", "status": "CONFIRMED"}],
    "proposed": [{"text": "既存 cpu_status を参考にする", "status": "PROPOSED"}],
    "assumptions": [{"text": "センサーAPIは既存", "status": "ASSUMED"}],
    "unknowns": [{"text": "精度の要求値", "status": "UNKNOWN"}],
    "human_confirmation_required": [],
    "risks": ["センサー未確認"],
    "alternatives": ["既存Toolをそのまま使う"],
    "rationale": "既存経路を再実装しない",
    "confidence": "medium",
}


def test_normalize_rebuckets_mixed_status():
    out = normalize_claim_lists(
        {
            "proposed": [{"text": "仮でキャッシュする", "status": "ASSUMED"}],
            "assumptions": [{"text": "本当の提案", "status": "PROPOSED"}],
        }
    )
    assert out["assumptions"][0]["text"] == "仮でキャッシュする"
    assert out["proposed"][0]["text"] == "本当の提案"


def test_structured_proposal_is_saved_not_complete(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    out = propose_specification(
        "CPU温度を取得するToolを作って",
        chat_fn=_chat(json.dumps(VALID, ensure_ascii=False)),
        model="mock",
        source="api",
    )
    assert out["saved"] is True
    assert out["parse_status"] == "ok"
    assert out["overwrite"] is False
    assert out["confidence"] == "UNCONFIRMED"
    assert out["llm_reported_confidence"] == "medium"
    assert out["proposed_specification"].startswith("CPU温度")
    assert out["confirmed"][0]["status"] == "CONFIRMED"
    assert out["proposed"][0]["status"] == "PROPOSED"
    assert out["assumptions"][0]["status"] == "ASSUMED"
    assert out["unknowns"][0]["status"] == "UNKNOWN"
    assert out["human_confirmation_required"] == []
    assert out["validate_tool_spec"] == "NOT_CONNECTED"
    assert out["human_revision"] is None
    assert "auto_improvement" in out["phases_not_implemented"]
    assert out["origin"] == "llm_proposal"
    assert str(out["correlation_id"] or "").startswith("ac-")
    assert out["learning_method"] == "NOT_DETERMINED"
    policy = out["policy_eval"]
    assert policy["specification_status"] != "COMPLETE"
    assert policy["may_claim_specification_complete"] is False
    assert policy["test_status"] == "NOT_OBSERVED"
    assert policy["may_proceed_implementation"] is True
    rows = load_jsonl()
    assert len(rows) == 1
    assert rows[0]["proposal_id"] == out["proposal_id"]


def test_same_request_appends_version(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    first = propose_specification("同じ要求", chat_fn=_chat(json.dumps(VALID)), model="mock")
    second = propose_specification("同じ要求", chat_fn=_chat(json.dumps(VALID)), model="mock")
    assert first["request_id"] == second["request_id"] == request_id_for("同じ要求")
    assert first["version"] == 1
    assert second["version"] == 2
    assert first["proposal_id"] != second["proposal_id"]
    assert first["correlation_id"] != second["correlation_id"]
    rows = list_by_request_id(first["request_id"])
    assert len(rows) == 2


def test_parse_failed_is_not_success_spec(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    out = propose_specification(
        "CPU温度を取得するToolを作って",
        chat_fn=_chat("仕様案: cpu_temp。登録しません。"),
        model="mock",
    )
    assert out["parse_status"] == "PARSE_FAILED"
    assert out["proposed_specification"] == ""
    assert out["unknowns"]
    assert out["policy_eval"]["may_claim_specification_complete"] is False
    assert out["policy_eval"]["may_proceed_implementation"] is False
    assert out["policy_eval"]["specification_status"] == "NEED_HUMAN_DECISION"


def test_human_confirmation_blocks_implementation(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    payload = dict(VALID)
    payload["human_confirmation_required"] = [
        {"text": "データ形式を変えるか", "status": "HUMAN_CONFIRMATION_REQUIRED"}
    ]
    out = propose_specification("保存形式を決めて", chat_fn=_chat(json.dumps(payload)), model="mock")
    assert out["parse_status"] == "ok"
    assert out["policy_eval"]["may_proceed_implementation"] is False
    assert out["policy_eval"]["specification_status"] == "NEED_HUMAN_DECISION"
    assert out["human_confirmation_required"][0]["text"] == "データ形式を変えるか"


def test_chat_gpu_does_not_save_proposal(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-spec-gpu")
    result = run_chat_turn(session, "GPUの状態を教えて", chat_fn=_chat("GPUは未観測です。"))
    assert result["route"] == "chat"
    assert load_jsonl() == []


def test_chat_tool_creation_saves_structured(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-spec-tool")
    result = run_chat_turn(
        session,
        "CPU温度を取得するToolを作って",
        chat_fn=_chat(json.dumps(VALID, ensure_ascii=False)),
    )
    assert result["route"] == "tool_creation"
    assert result["registry_write"] is False
    assert result["awaiting_human_review"] is True
    assert result["proposal"]["parse_status"] == "ok"
    rows = load_jsonl()
    assert len(rows) == 1
    assert rows[0]["source"] == "chat_tool_creation"
    assert rows[0]["tool_materials"]["used"] is True
    cid = result["correlation_id"]
    assert cid.startswith("ac-")
    assert rows[0]["correlation_id"] == cid
    assert result["spec_proposal"]["correlation_id"] == cid
    assert session["turns"][-1]["correlation_id"] == cid
    assert {e.get("correlation_id") for e in result["events"]} == {cid}


def test_chat_development_saves_proposal(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-spec-dev")
    result = run_chat_turn(
        session,
        "この機能を実装して",
        chat_fn=_chat(json.dumps(VALID, ensure_ascii=False)),
    )
    assert result["route"] == "development"
    assert result["proposal"]["parse_status"] == "ok"
    row = load_jsonl()[0]
    assert row["source"] == "chat_development"
    assert row["correlation_id"] == result["correlation_id"]
    assert session["turns"][-1]["correlation_id"] == result["correlation_id"]
