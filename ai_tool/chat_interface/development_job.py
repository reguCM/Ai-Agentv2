"""Session 上の薄い Development Job。新しい Core ではない。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from ai_tool.chat_interface.classify import intent_of
from ai_tool.chat_interface.events import now_iso

JOB_ROUTES = {"tool_creation", "development"}
SAFE_JOB = re.compile(r"^dj-[A-Za-z0-9._-]+$")


def new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"dj-{stamp}-{uuid.uuid4().hex[:6]}"


def empty_jobs() -> list[dict[str, Any]]:
    return []


def _event(
    type_: str,
    *,
    layer: str,
    source: str,
    title: str,
    body: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "stream": "development",
        "kind": "development",
        "type": type_,
        "layer": layer,
        "source": source,
        "title": title,
        "timestamp": now_iso(),
    }
    if body:
        item["body"] = body
    if extra:
        item.update(extra)
    return item


def maybe_record_job(
    session: dict[str, Any],
    text: str,
    route: str,
    *,
    case_id: str | None = None,
) -> dict[str, Any] | None:
    """開発依頼だけを Job にする。通常 Chat では作らない。Cursor は起動しない。"""
    if route not in JOB_ROUTES:
        return None
    jobs = session.setdefault("development_jobs", [])
    job_id = new_job_id()
    title = text.strip().replace("\n", " ")[:80]
    job = {
        "id": job_id,
        "created_at": now_iso(),
        "title": title,
        "request": text,
        "kind": route,
        "intent": intent_of(route),
        "status": "recorded",
        "case_id": case_id,
        "cursor_live": "NOT_OBSERVED",
        "cursor_report": None,
        "related_runs": [],
        "related_git_changes": [],
        "test_results": {
            "cursor_report": None,
            "machine": {"status": "NOT_AVAILABLE", "source": "missing"},
        },
        "research_record_id": session.get("research_record_id"),
        "session_id": session.get("session_id"),
        "events": [
            _event(
                "REQUEST",
                layer="real",
                source="session",
                title="開発依頼",
                body=text,
                extra={"job_id": job_id, "case_id": case_id},
            ),
            _event(
                "LOCAL_AGENT",
                layer="summary",
                source="local_agent",
                title="開発依頼として受付",
                body="Cursor には接続していません。成果物がリポジトリに残れば Timeline に出ます。",
                extra={"job_id": job_id, "case_id": case_id},
            ),
        ],
        "note": "薄い追跡用レコードです。Cursor のライブ状態は含みません。",
    }
    jobs.append(job)
    return job


def list_jobs(session: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not session:
        return []
    jobs = session.get("development_jobs") or []
    return [j for j in jobs if isinstance(j, dict) and j.get("id")]


def get_job(session: dict[str, Any] | None, job_id: str) -> dict[str, Any] | None:
    if not job_id or not SAFE_JOB.match(job_id):
        return None
    for job in list_jobs(session):
        if job.get("id") == job_id:
            return job
    return None
