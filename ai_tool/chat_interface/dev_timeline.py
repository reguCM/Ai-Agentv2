"""Development Timeline。成果物と Job を時系列にする。Cursor ライブは推測しない。"""
from __future__ import annotations

from typing import Any

from ai_tool.chat_interface.dev_readonly import (
    get_run,
    git_snapshot,
    list_runs,
    mechanical_tests,
)
from ai_tool.chat_interface.activity import session_activity
from ai_tool.chat_interface.development_job import get_job, list_jobs
from ai_tool.chat_interface.events import now_iso
from ai_tool.chat_interface.execution_case import load_case


def cursor_live_status() -> dict[str, Any]:
    return {
        "status": "NOT_OBSERVED",
        "label": "Cursor live status: NOT OBSERVED",
        "label_ja": "Cursor のライブ状態は観測していません",
        "note": "Git dirty や経過時間から実行中とは判断しません。",
    }


def _item(
    type_: str,
    *,
    layer: str,
    source: str,
    timestamp: str | None,
    title: str,
    body: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "stream": "development",
        "kind": "development",
        "type": type_,
        "layer": layer,
        "source": source,
        "timestamp": timestamp or now_iso(),
        "title": title,
    }
    if body:
        row["body"] = body
    if extra:
        row.update(extra)
    return row


def _status_from_text(value: Any) -> str:
    text = str(value or "").strip()
    upper = text.upper()
    if any(w in upper for w in ("FAIL", "ERROR")):
        return "FAIL"
    if any(w in upper for w in ("PASS", "OK", "SUCCESS")):
        return "PASS"
    if not text:
        return "UNKNOWN"
    return "UNKNOWN"


def extract_cursor_test_items(summary: dict[str, Any] | None, observations: dict[str, Any] | None) -> list[dict[str, Any]]:
    """observations/summary の tests を Cursor 報告として列挙する。pytest 実測ではない。"""
    blob: dict[str, Any] | None = None
    if isinstance(observations, dict) and isinstance(observations.get("tests"), dict):
        blob = observations["tests"]
    elif isinstance(summary, dict) and isinstance(summary.get("tests"), dict):
        blob = summary["tests"]
    if not blob:
        return []
    items: list[dict[str, Any]] = []
    for key, raw in blob.items():
        if isinstance(raw, dict):
            status = raw.get("status") or raw.get("judgment") or raw.get("result") or ""
        else:
            status = raw
        observed: dict[str, Any] = {}
        if isinstance(raw, dict):
            for field, value in raw.items():
                observed[str(field)] = value
        extra = [k for k in observed if k not in {"status", "judgment", "result"}]
        items.append(
            {
                "id": str(key),
                "status": _status_from_text(status),
                "raw": status if not isinstance(status, dict) else str(status),
                "source": "cursor_report",
                "actor": "cursor",
                "layer": "cursor_report",
                "observed": observed,
                "detail": None if extra else "未取得",
            }
        )
    return items


def _events_from_run(run_meta: dict[str, Any]) -> list[dict[str, Any]]:
    run_id = str(run_meta.get("run_id") or "")
    ts = run_meta.get("summary_mtime")
    detail = get_run(run_id)
    if not detail.get("ok"):
        return []
    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
    obs = detail.get("observations") if isinstance(detail.get("observations"), dict) else {}
    events = [
        _item(
            "RUN",
            layer="real",
            source="run",
            timestamp=ts,
            title=f"Run {run_id}",
            body=str(summary.get("judgment") or "UNKNOWN"),
            extra={
                "run_id": run_id,
                "session_id": summary.get("session_id") or run_meta.get("session_id"),
                "judgment": summary.get("judgment"),
                "judgment_ja": summary.get("judgment_ja"),
            },
        )
    ]
    claim = detail.get("cursor_test_report")
    if isinstance(claim, dict) and claim.get("text"):
        events.append(
            _item(
                "CURSOR_REPORT",
                layer="cursor_report",
                source="cursor_report",
                timestamp=ts,
                title="Cursor報告（テスト）",
                body=str(claim.get("text")),
                extra={
                    "run_id": run_id,
                    "counts_as_pytest": False,
                    "machine_status": "NOT_AVAILABLE"
                    if not (detail.get("mechanical_tests") or {}).get("available")
                    else "AVAILABLE",
                },
            )
        )
    items = extract_cursor_test_items(summary, obs)
    if items:
        events.append(
            _item(
                "TEST_LIST",
                layer="cursor_report",
                source="cursor_report",
                timestamp=ts,
                title=f"Cursor報告テスト一覧（{len(items)} 件）",
                extra={
                    "run_id": run_id,
                    "items": items,
                    "source_label": "Cursor Report",
                    "counts_as_pytest": False,
                },
            )
        )
    mech = detail.get("mechanical_tests") or {}
    events.append(
        _item(
            "TEST",
            layer="real",
            source="pytest_xml" if mech.get("available") else "missing",
            timestamp=ts,
            title="機械的テスト",
            body="NOT AVAILABLE" if not mech.get("available") else str(mech.get("user_message")),
            extra={
                "run_id": run_id,
                "status": "PASS" if mech.get("available") else "NOT_AVAILABLE",
                "machine": mech,
            },
        )
    )
    return events


def _events_from_git(snap: dict[str, Any]) -> list[dict[str, Any]]:
    if not snap.get("ok"):
        return [
            _item(
                "GIT",
                layer="real",
                source="git",
                timestamp=now_iso(),
                title="Git を読めません",
                body=str(snap.get("error") or ""),
            )
        ]
    counts = snap.get("counts") or {}
    files = snap.get("files") or []
    named = [f.get("path") for f in files if f.get("state") != "untracked"][:40]
    events = [
        _item(
            "GIT",
            layer="real",
            source="git",
            timestamp=now_iso(),
            title="作業ツリー（git status）",
            body=(
                f"modified: {counts.get('modified', 0)} "
                f"added: {counts.get('added', 0)} "
                f"deleted: {counts.get('deleted', 0)} "
                f"untracked: {counts.get('untracked', 0)}"
            ),
            extra={
                "counts": counts,
                "files": named,
                "branch": snap.get("branch"),
                "head": snap.get("head"),
                "diff_stat": snap.get("diff_stat"),
            },
        )
    ]
    for commit in snap.get("commits") or []:
        events.append(
            _item(
                "GIT_COMMIT",
                layer="real",
                source="git",
                timestamp=commit.get("date"),
                title=f"Commit {str(commit.get('hash') or '')[:8]}",
                body=str(commit.get("subject") or ""),
                extra={"commit": commit.get("hash"), "branch": snap.get("branch")},
            )
        )
    return events


def build_timeline(
    session: dict[str, Any] | None = None,
    *,
    job_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    jobs = list_jobs(session)
    if job_id:
        one = get_job(session, job_id)
        jobs = [one] if one else []
    if case_id:
        jobs = [j for j in jobs if j and str(j.get("case_id") or "") == case_id]
    case = load_case(case_id) if case_id else None
    allowed_runs = set(case.get("run_ids") or []) if case else None
    for job in jobs:
        for ev in job.get("events") or []:
            if isinstance(ev, dict):
                row = dict(ev)
                row.setdefault("job_id", job.get("id"))
                if job.get("proposal_id"):
                    row.setdefault("proposal_id", job.get("proposal_id"))
                if job.get("request_id"):
                    row.setdefault("request_id", job.get("request_id"))
                if job.get("case_id"):
                    row.setdefault("case_id", job.get("case_id"))
                events.append(row)

    for run_meta in (list_runs().get("runs") or [])[:12]:
        run_id = str(run_meta.get("run_id") or "")
        if case_id:
            if not allowed_runs or run_id not in allowed_runs:
                continue
        elif job_id:
            sid = (jobs[0] or {}).get("session_id") if jobs else None
            if not sid or run_meta.get("session_id") != sid:
                continue
        events.extend(_events_from_run(run_meta))

    if not case_id:
        git = git_snapshot()
        events.extend(_events_from_git(git))
        mech = mechanical_tests()
        events.append(
            _item(
                "TEST",
                layer="real",
                source=str(mech.get("source") or "missing"),
                timestamp=now_iso(),
                title="機械的テスト（リポジトリ全体）",
                body="NOT AVAILABLE" if not mech.get("available") else str(mech.get("user_message")),
                extra={"status": "NOT_AVAILABLE" if not mech.get("available") else "UNKNOWN", "machine": mech},
            )
        )

    research_id = None
    if session and not case_id:
        research_id = session.get("research_record_id") or (session.get("experimental_session") or {}).get(
            "last_research_id"
        )
        if research_id:
            events.append(
                _item(
                    "RESEARCH",
                    layer="real",
                    source="session",
                    timestamp=session.get("started_at"),
                    title="ResearchRecord 関連",
                    body=str(research_id),
                    extra={"research_record_id": research_id},
                )
            )

    if session:
        for ev in session_activity(session).get("events") or []:
            if isinstance(ev, dict):
                if case_id and str(ev.get("case_id") or "") != case_id:
                    continue
                events.append(ev)

    events.sort(key=lambda e: str(e.get("timestamp") or ""))
    return {
        "ok": True,
        "kind": "development",
        "cursor_live": cursor_live_status(),
        "job_id": job_id,
        "case_id": case_id,
        "jobs": [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "kind": j.get("kind"),
                "status": j.get("status"),
                "proposal_id": j.get("proposal_id"),
                "request_id": j.get("request_id"),
                "case_id": j.get("case_id"),
            }
            for j in jobs
        ]
        if session is not None
        else [],
        "events": events,
        "note": (
            "Cursor を監視しているのではありません。"
            if not case_id
            else "Case 所属は case_id が一致する記録のみ。Git 横断 snapshot と pytest XML は含みません。"
        ),
    }
