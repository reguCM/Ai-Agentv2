"""人間修正・問題記録は追記。LLM 案は残す。正しさは付けない。"""
from __future__ import annotations

import json
from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.spec_proposal.follow import append_human_revision, append_problem_record
from ai_tool.spec_proposal.propose import propose_specification
from ai_tool.spec_proposal.store import get_by_proposal_id, list_by_parent_proposal_id, load_jsonl


class _Msg:
    def __init__(self, content=""):
        self.content = content


class _Resp:
    def __init__(self, message):
        self.message = message


def _chat(content: str):
    def fn(**_kwargs):
        return _Resp(_Msg(content=content))

    return fn


VALID = {
    "proposed_specification": "追記で保存する",
    "objectives": ["履歴"],
    "inputs": [],
    "outputs": [],
    "behavior": [],
    "constraints": [],
    "completion_conditions": [],
    "confirmed": [],
    "proposed": [{"text": "JSONL", "status": "PROPOSED"}],
    "assumptions": [{"text": "request_id は親を継承", "status": "ASSUMED"}],
    "unknowns": [],
    "human_confirmation_required": [],
    "risks": [],
    "alternatives": [],
    "rationale": "原本保持",
    "confidence": "low",
}


def test_human_revision_appends_without_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    llm = propose_specification("要求A", chat_fn=_chat(json.dumps(VALID)), model="mock")
    rev = append_human_revision(
        parent_proposal_id=llm["proposal_id"],
        revision_reason="既存DBを壊さない",
        body={"proposed_specification": "JSONLのまま追記する"},
    )
    assert rev["saved"] is True
    assert rev["origin"] == "human_revision"
    assert rev["llm_used"] is False
    assert rev["llm_judgment"] == "NOT_IMPLEMENTED"
    assert rev["learning_method"] == "NOT_DETERMINED"
    assert rev["parent_proposal_id"] == llm["proposal_id"]
    assert rev["request_id"] == llm["request_id"]
    assert rev["proposal_id"] != llm["proposal_id"]
    assert rev["correlation_id"] != llm["correlation_id"]
    assert str(rev["correlation_id"] or "").startswith("ac-")
    original = get_by_proposal_id(llm["proposal_id"])
    assert original["proposed_specification"] == llm["proposed_specification"]
    assert original["origin"] == "llm_proposal"
    assert len(load_jsonl()) == 2
    kids = list_by_parent_proposal_id(llm["proposal_id"])
    assert len(kids) == 1
    assert kids[0]["origin"] == "human_revision"


def test_revision_without_reason_is_unknown_not_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    llm = propose_specification("要求B", chat_fn=_chat(json.dumps(VALID)), model="mock")
    rev = append_human_revision(parent_proposal_id=llm["proposal_id"], revision_reason="  ")
    assert rev["saved"] is True
    assert rev["revision_reason_status"] == "UNKNOWN"


def test_missing_parent_does_not_save(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    out = append_human_revision(parent_proposal_id="sp-missing", revision_reason="x")
    assert out["saved"] is False
    assert load_jsonl() == []


def test_problem_record_does_not_judge_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    llm = propose_specification("要求C", chat_fn=_chat(json.dumps(VALID)), model="mock")
    prob = append_problem_record(
        parent_proposal_id=llm["proposal_id"],
        problem="DBスキーマ変更は影響が大きい",
        human_correction="JSONL追記にする",
        revision_reason="既存データへの影響",
    )
    assert prob["origin"] == "problem_record"
    assert prob["cause_status"] == "NOT_DETERMINED"
    assert prob["llm_judgment"] == "NOT_IMPLEMENTED"
    assert "correct" not in str(prob["llm_judgment"]).lower()
    assert get_by_proposal_id(llm["proposal_id"])["proposal_id"] == llm["proposal_id"]
    assert len(load_jsonl()) == 2
    assert prob["correlation_id"] != llm["correlation_id"]
    assert str(prob["correlation_id"] or "").startswith("ac-")


def test_empty_problem_not_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    llm = propose_specification("要求D", chat_fn=_chat(json.dumps(VALID)), model="mock")
    out = append_problem_record(parent_proposal_id=llm["proposal_id"], problem=" ")
    assert out["saved"] is False
    assert len(load_jsonl()) == 1


def test_chat_job_stores_proposal_id(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-obs-job")
    result = run_chat_turn(
        session,
        "CPU温度を取得するToolを作って",
        chat_fn=_chat(json.dumps(VALID, ensure_ascii=False)),
    )
    assert result["development_job"]["proposal_id"] == result["proposal"]["proposal_id"]
    rows = load_jsonl()
    assert rows[0]["session_id"] == "cs-obs-job"
    assert rows[0]["development_job_id"] == result["development_job"]["id"]
    assert session["turns"][-1]["proposal_id"] == result["proposal"]["proposal_id"]

    from ai_tool.chat_interface.activity import session_activity
    from ai_tool.chat_interface.dev_cases import session_jobs_as_notes
    from ai_tool.chat_interface.dev_timeline import build_timeline

    pid = result["proposal"]["proposal_id"]
    rid = result["proposal"]["request_id"]
    jid = result["development_job"]["id"]
    notes = session_jobs_as_notes(session)
    assert notes[0]["proposal_id"] == pid
    assert notes[0]["request_id"] == rid
    assert notes[0]["id"] == jid
    calls = [e for e in session_activity(session)["events"] if e["type"] == "LOCAL_AGENT_CALL"]
    assert calls[0]["proposal_id"] == pid
    assert calls[0]["request_id"] == rid
    assert calls[0]["development_job_id"] == jid
    timeline = build_timeline(session)
    assert timeline["jobs"][0]["proposal_id"] == pid
    assert timeline["jobs"][0]["request_id"] == rid
    job_events = [e for e in timeline["events"] if e.get("job_id") == jid]
    assert job_events
    assert all(e.get("proposal_id") == pid for e in job_events)
    assert all(e.get("request_id") == rid for e in job_events)
