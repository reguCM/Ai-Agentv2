"""横断キー case_id。Session / correlation / Job / Proposal / Run の別名ではない。

所属は case_id フィールドと Case レコード上の明示リストだけを使う。
同じ Session・Timeline・時刻・path では所属としない。

Session.active_case_id による後続 turn の継承は暫定。本来の開始・完全停止判定ではない。
active_case_id の存在を同一要求の完全な証明とみなさない。
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.chat_interface.chat_session import SESSIONS_DIR, load_session, session_path
from ai_tool.chat_interface.events import now_iso


def cases_dir() -> Path:
    """Session と同じ親。テストは SESSIONS_DIR または AI_AGENT_EXECUTION_CASES_DIR を差し替える。"""
    raw = (os.environ.get("AI_AGENT_EXECUTION_CASES_DIR") or "").strip()
    path = Path(raw) if raw else Path(SESSIONS_DIR).parent / "execution_cases"
    path.mkdir(parents=True, exist_ok=True)
    return path


SAFE_CASE = re.compile(r"^cx-[A-Za-z0-9._-]+$")
LINK_KINDS = (
    "correlation_id",
    "job_id",
    "proposal_id",
    "run_id",
    "matrix_record_id",
    "git_ref",
    "test_ref",
    "investigation_ref",
    "report_ref",
)

_KIND_TO_LIST = {
    "correlation_id": "correlation_ids",
    "job_id": "job_ids",
    "proposal_id": "proposal_ids",
    "run_id": "run_ids",
    "matrix_record_id": "matrix_record_ids",
    "git_ref": "git_refs",
    "test_ref": "test_refs",
    "investigation_ref": "investigation_refs",
    "report_ref": "report_refs",
}


def case_path(case_id: str) -> Path:
    return cases_dir() / f"{case_id}.json"


def new_case_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"cx-{stamp}-{uuid.uuid4().hex[:8]}"


def empty_case(
    *,
    case_id: str | None = None,
    originating_request: str = "",
    session_id: str | None = None,
) -> dict[str, Any]:
    cid = case_id or new_case_id()
    ts = now_iso()
    return {
        "case_id": cid,
        "created_at": ts,
        "updated_at": ts,
        "status": "open",
        "status_note": (
            "Provisional. complete_stop の自動判定は NOT_IMPLEMENTED。"
            "turn 終了 / awaiting_human_review / LLM timeout / 個別 Event エラーでは終了しない。"
        ),
        "originating_request": originating_request,
        "session_id": session_id,
        "correlation_ids": [],
        "job_ids": [],
        "proposal_ids": [],
        "run_ids": [],
        "matrix_record_ids": [],
        "git_refs": [],
        "test_refs": [],
        "investigation_refs": [],
        "report_refs": [],
        "turns": [],
        "membership": (
            "Records belong to this Case only when they store this case_id "
            "or are listed in the arrays above. Session/Timeline/time/path are not proof."
        ),
        "attach_rule": (
            "Provisional: if Session has no open active Case, create one; "
            "otherwise later Chat turns inherit it. classify_request is not a start event. "
            "Unrelated chat in the same Session may be included. Do not treat this as the real start rule."
        ),
        "not_a_rename_of": [
            "session_id",
            "correlation_id",
            "job_id",
            "proposal_id",
            "run_id",
        ],
        "note": "Cross-cutting parent key. Not a Chat turn, Job, Proposal, or harness Run.",
    }


def save_case(data: dict[str, Any]) -> Path:
    data["updated_at"] = now_iso()
    path = case_path(str(data["case_id"]))
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def load_case(case_id: str) -> dict[str, Any] | None:
    if not case_id or not SAFE_CASE.match(case_id):
        return None
    path = case_path(case_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _unique_append(values: list[Any], item: Any) -> None:
    text = str(item or "").strip()
    if not text or text in values:
        return
    values.append(text)


def link_member(case_id: str, kind: str, member_id: str) -> dict[str, Any]:
    """明示所属だけを書く。時刻・path から推定しない。"""
    case = load_case(case_id)
    if not case:
        return {"ok": False, "error": "指定された Case はありません", "error_kind": "not_found"}
    if kind not in _KIND_TO_LIST:
        return {"ok": False, "error": "未知の所属種別です", "error_kind": "invalid_kind"}
    member = str(member_id or "").strip()
    if not member:
        return {"ok": False, "error": "所属先 ID が空です", "error_kind": "invalid_id"}
    _unique_append(case.setdefault(_KIND_TO_LIST[kind], []), member)
    save_case(case)
    return {"ok": True, "case": case, "kind": kind, "member_id": member}


def record_turn(case_id: str, turn: dict[str, Any]) -> dict[str, Any] | None:
    case = load_case(case_id)
    if not case:
        return None
    cid = str(turn.get("correlation_id") or "").strip()
    if cid:
        _unique_append(case.setdefault("correlation_ids", []), cid)
    jid = str(turn.get("development_job_id") or turn.get("job_id") or "").strip()
    if jid:
        _unique_append(case.setdefault("job_ids", []), jid)
    pid = str(turn.get("proposal_id") or "").strip()
    if pid:
        _unique_append(case.setdefault("proposal_ids", []), pid)
    tools = []
    for item in turn.get("tools") or []:
        if isinstance(item, dict):
            tools.append(
                {
                    "name": item.get("name"),
                    "status": item.get("status"),
                }
            )
    case.setdefault("turns", []).append(
        {
            "correlation_id": cid or None,
            "user": turn.get("user"),
            "route": turn.get("route"),
            "is_error": bool(turn.get("is_error")),
            "error_kind": turn.get("error_kind"),
            "development_job_id": jid or None,
            "proposal_id": pid or None,
            "web_search": bool(turn.get("web_search")),
            "tools": tools,
        }
    )
    save_case(case)
    return case


def open_case(*, originating_request: str, session_id: str | None = None) -> dict[str, Any]:
    case = empty_case(originating_request=originating_request, session_id=session_id)
    save_case(case)
    return case


def attach_or_open_case(session: dict[str, Any], originating_request: str) -> dict[str, Any]:
    """暫定: Session.active_case_id を継承する。本来の開始判定ではない。分類では開始しない。"""
    sid = str(session.get("session_id") or "") or None
    active = str(session.get("active_case_id") or "").strip()
    if active:
        existing = load_case(active)
        if existing and existing.get("status") == "open":
            if sid and not existing.get("session_id"):
                existing["session_id"] = sid
                save_case(existing)
            session["active_case_id"] = existing["case_id"]
            return existing
    case = open_case(originating_request=originating_request, session_id=sid)
    session["active_case_id"] = case["case_id"]
    return case


def resolve_case_for_request(
    *,
    originating_request: str,
    session: dict[str, Any] | None = None,
    session_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    if case_id:
        found = load_case(case_id)
        if found:
            if session is not None:
                session["active_case_id"] = found["case_id"]
            return found
    if session is not None:
        return attach_or_open_case(session, originating_request)
    sid = str(session_id or "").strip()
    if sid and session_path(sid).is_file():
        loaded = load_session(sid)
        case = attach_or_open_case(loaded, originating_request)
        from ai_tool.chat_interface.chat_session import save_session

        save_session(loaded)
        return case
    return open_case(originating_request=originating_request, session_id=sid or None)


def list_case_summaries() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    root = cases_dir()
    for path in sorted(root.glob("cx-*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not data.get("case_id"):
            continue
        rows.append(
            {
                "case_id": data.get("case_id"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "status": data.get("status"),
                "session_id": data.get("session_id"),
                "originating_request": str(data.get("originating_request") or "")[:80],
                "correlation_count": len(data.get("correlation_ids") or []),
                "job_count": len(data.get("job_ids") or []),
                "proposal_count": len(data.get("proposal_ids") or []),
                "run_count": len(data.get("run_ids") or []),
            }
        )
    return {
        "ok": True,
        "cases": rows,
        "note": "Execution Case 一覧。/api/dev/cases の Run 案件とは別物。",
    }


def _records_with_case_id(rows: list[dict[str, Any]], case_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if isinstance(row, dict) and str(row.get("case_id") or "") == case_id]


def get_case_bundle(case_id: str) -> dict[str, Any]:
    """明示所属だけを集める。Git/Test 横断結果は混ぜない。"""
    if not case_id or not SAFE_CASE.match(case_id):
        return {"ok": False, "error": "不正な Case ID です", "error_kind": "invalid_id"}
    case = load_case(case_id)
    if not case:
        return {"ok": False, "error": "指定された Case はありません", "error_kind": "not_found"}

    sid = str(case.get("session_id") or "")
    session = load_session(sid) if sid and session_path(sid).is_file() else None
    turns = _records_with_case_id(list((session or {}).get("turns") or []), case_id)
    events: list[dict[str, Any]] = []
    for turn in turns:
        for ev in turn.get("events") or []:
            if isinstance(ev, dict) and str(ev.get("case_id") or "") == case_id:
                events.append(ev)

    jobs = [
        job
        for job in list((session or {}).get("development_jobs") or [])
        if isinstance(job, dict)
        and (
            str(job.get("case_id") or "") == case_id
            or str(job.get("id") or "") in (case.get("job_ids") or [])
        )
    ]

    from ai_tool.spec_proposal.store import load_jsonl

    proposals = [
        row
        for row in load_jsonl()
        if isinstance(row, dict)
        and (
            str(row.get("case_id") or "") == case_id
            or str(row.get("proposal_id") or "") in (case.get("proposal_ids") or [])
        )
    ]

    return {
        "ok": True,
        "case": case,
        "case_id": case_id,
        "originating_request": case.get("originating_request"),
        "status": case.get("status"),
        "session_id": case.get("session_id"),
        "correlation_ids": list(case.get("correlation_ids") or []),
        "turns": turns,
        "events": events,
        "jobs": jobs,
        "proposals": proposals,
        "runs": list(case.get("run_ids") or []),
        "matrix_record_ids": list(case.get("matrix_record_ids") or []),
        "git_refs": list(case.get("git_refs") or []),
        "test_refs": list(case.get("test_refs") or []),
        "investigation_refs": list(case.get("investigation_refs") or []),
        "report_refs": list(case.get("report_refs") or []),
        "extension_points": {
            "run": "NOT_CONNECTED until an explicit run_id is linked",
            "test": "NOT_CONNECTED until an explicit test_ref is linked; repo-wide pytest XML is not membership",
            "git": "NOT_CONNECTED until an explicit git_ref is linked; git snapshot is not membership",
            "matrix": "NOT_CONNECTED until an explicit matrix_record_id is linked",
            "complete_stop": "NOT_IMPLEMENTED as automatic detection",
            "investigation": "NOT_IMPLEMENTED as a child model; investigation_refs is the hook",
            "cursor_handoff": "GET this bundle is the entry; Cursor live path is NOT_CONNECTED",
        },
        "note": (
            "Membership is case_id on records plus the Case link arrays. "
            "Timeline juxtaposition is not used."
        ),
    }
