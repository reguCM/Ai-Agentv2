"""開発案件。Run / Report / Git / Test を案件単位にまとめる。新 Core ではない。"""
from __future__ import annotations

import re
from typing import Any

from ai_tool.chat_interface.activity import case_local_agent_bridge
from ai_tool.chat_interface.dev_readonly import get_run, git_snapshot, list_reports, list_runs, mechanical_tests
from ai_tool.chat_interface.dev_timeline import (
    cursor_live_status,
    extract_cursor_test_items,
)
from ai_tool.chat_interface.development_job import list_jobs
from ai_tool.chat_interface.events import now_iso

SAFE_CASE = re.compile(r"^(run|dj)-[A-Za-z0-9._-]+$")
STAMP = re.compile(r"^(\d{8}_\d{6})_(.+)$")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def run_slug(run_id: str) -> str:
    match = STAMP.match(run_id or "")
    return match.group(2) if match else (run_id or "")


def _kind(slug: str, files: list[str], request: str | None) -> str:
    blob = " ".join([slug, request or ""] + files).lower()
    if "matrix" in blob:
        return "matrix"
    if "research" in blob:
        return "research"
    if any(k in blob for k in ("chat_ui", "timeline", "chat_interface", "local_agent_ui")):
        return "ui"
    if any(f.replace("\\", "/").startswith("tools/") for f in files) or "tool" in blob or slug.startswith("get_"):
        return "tool"
    if "test" in slug:
        return "test"
    return "unknown"


def _event(
    type_: str,
    *,
    actor: str,
    source: str,
    title: str,
    body: str | None = None,
    timestamp: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "stream": "development",
        "kind": "development",
        "type": type_,
        "actor": actor,
        "source": source,
        "confidence": "observed",
        "layer": "cursor_report" if source == "cursor_report" else "real",
        "title": title,
        "timestamp": timestamp or now_iso(),
    }
    if body:
        row["body"] = body
    if extra:
        row.update(extra)
    return row


def _match_reports(slug: str) -> list[dict[str, Any]]:
    if not slug:
        return []
    needle = _norm(slug)
    if len(needle) < 6:
        return []
    hits: list[dict[str, Any]] = []
    for item in list_reports().get("reports") or []:
        name = str(item.get("name") or "")
        hay = _norm(name)
        if needle in hay:
            hits.append({"name": name, "mtime": item.get("mtime"), "match": "filename_contains_run_slug"})
    return hits


def _obs_paths(obs: dict[str, Any]) -> tuple[list[str], list[str]]:
    created = [str(p) for p in (obs.get("files_created") or []) if p]
    modified = [str(p) for p in (obs.get("files_modified") or []) if p]
    return created, modified


def _related_git(snap: dict[str, Any], created: list[str], modified: list[str]) -> dict[str, Any]:
    wanted = created + modified
    if not wanted:
        return {
            "available": False,
            "files": [],
            "git_overlap": [],
            "note": "案件関連の変更ファイル：未取得",
        }
    overlap: list[dict[str, str]] = []
    for item in snap.get("files") or []:
        path = str(item.get("path") or "").replace("\\", "/")
        if path in wanted:
            overlap.append({"path": path, "state": str(item.get("state") or ""), "code": str(item.get("code") or "")})
    files = [{"path": p, "state": "added", "origin": "observations.files_created"} for p in created]
    files.extend({"path": p, "state": "modified", "origin": "observations.files_modified"} for p in modified)
    return {
        "available": True,
        "files": files,
        "git_overlap": overlap,
        "note": "observations に書かれたパスです。commit と断定していません。",
    }


def _actor_from_obs(obs: dict[str, Any], summary: dict[str, Any]) -> dict[str, str]:
    if obs.get("local_agent_executed_development") is True:
        return {"actor": "local_agent", "confidence": "observed"}
    unit = obs.get("unit_tests") if isinstance(obs.get("unit_tests"), dict) else {}
    if str(unit.get("executor") or "").lower() == "cursor":
        return {"actor": "cursor", "confidence": "observed"}
    if summary.get("cursor_connected") is True:
        return {"actor": "cursor", "confidence": "observed"}
    return {"actor": "cursor", "confidence": "observed"}


def _case_from_run(run_meta: dict[str, Any], snap: dict[str, Any] | None) -> dict[str, Any] | None:
    run_id = str(run_meta.get("run_id") or "")
    if not run_id:
        return None
    detail = get_run(run_id)
    if not detail.get("ok"):
        return None
    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
    obs = detail.get("observations") if isinstance(detail.get("observations"), dict) else {}
    slug = run_slug(run_id)
    created, modified = _obs_paths(obs)
    files = created + modified
    request = str(obs.get("request") or "").strip() or None
    actor_info = _actor_from_obs(obs, summary)
    actor = actor_info["actor"]
    reports = _match_reports(slug)
    claim = detail.get("cursor_test_report") if isinstance(detail.get("cursor_test_report"), dict) else None
    items = extract_cursor_test_items(summary, obs)
    mech = detail.get("mechanical_tests") or mechanical_tests()
    ts = run_meta.get("summary_mtime")
    events: list[dict[str, Any]] = []
    for path in created:
        events.append(
            _event(
                "ARTIFACT",
                actor=actor,
                source="run",
                title=path,
                body="追加",
                timestamp=ts,
                extra={"path": path, "change": "added"},
            )
        )
    for path in modified:
        events.append(
            _event(
                "ARTIFACT",
                actor=actor,
                source="run",
                title=path,
                body="変更",
                timestamp=ts,
                extra={"path": path, "change": "modified"},
            )
        )
    for report in reports:
        events.append(
            _event(
                "REPORT",
                actor=actor,
                source="report",
                title=str(report.get("name")),
                body="報告書",
                timestamp=report.get("mtime") or ts,
                extra={"report": report.get("name")},
            )
        )
    events.append(
        _event(
            "RUN",
            actor=actor,
            source="run",
            title=f"Run {run_id}",
            body=str(summary.get("judgment") or "UNKNOWN"),
            timestamp=ts,
            extra={"run_id": run_id, "judgment": summary.get("judgment")},
        )
    )
    if claim and claim.get("text"):
        events.append(
            _event(
                "CURSOR_REPORT",
                actor="cursor",
                source="cursor_report",
                title="Cursor Report",
                body=str(claim.get("text")),
                timestamp=ts,
                extra={"counts_as_pytest": False, "items": items},
            )
        )
    elif items:
        events.append(
            _event(
                "CURSOR_REPORT",
                actor="cursor",
                source="cursor_report",
                title="Cursor Report",
                body=f"{len(items)} tests (Cursor Report)",
                timestamp=ts,
                extra={"counts_as_pytest": False, "items": items},
            )
        )
    events.append(
        _event(
            "TEST",
            actor="mechanical",
            source="pytest_xml" if mech.get("available") else "missing",
            title="機械的テスト",
            body="NOT AVAILABLE" if not mech.get("available") else str(mech.get("user_message")),
            timestamp=ts,
            extra={
                "status": "NOT_AVAILABLE" if not mech.get("available") else "UNKNOWN",
                "counts_as_pytest": bool(mech.get("available")),
            },
        )
    )
    related_git = _related_git(snap or {}, created, modified) if snap is not None else {
        "available": bool(files),
        "files": [{"path": p, "state": "added"} for p in created] + [{"path": p, "state": "modified"} for p in modified],
        "git_overlap": [],
        "note": "一覧では Git 全体を読んでいません。詳細で照合します。",
    }
    title = request[:80] if request else slug
    return {
        "id": f"run-{run_id}",
        "run_id": run_id,
        "slug": slug,
        "title": title,
        "title_source": "observations.request" if request else "run_id_slug",
        "request": request,
        "request_status": "observed" if request else "missing",
        "request_note": None if request else "依頼文：未取得",
        "actor": actor,
        "confidence": actor_info["confidence"],
        "kind": _kind(slug, files, request),
        "status": summary.get("judgment") or "UNKNOWN",
        "judgment_ja": summary.get("judgment_ja"),
        "timestamp": ts,
        "reports": reports,
        "cursor_report": claim,
        "cursor_tests": items,
        "mechanical_tests": {
            "status": "NOT_AVAILABLE" if not mech.get("available") else "UNKNOWN",
            "source": mech.get("source"),
            "user_message": mech.get("user_message") or "機械的テスト結果：未取得",
        },
        "related_git": related_git,
        "events": events,
        "note": "Cursor 内部操作のログではありません。リポジトリに残った成果物です。",
    }


def list_cases(*, category: str = "all") -> dict[str, Any]:
    snap = None
    cases: list[dict[str, Any]] = []
    for run_meta in list_runs().get("runs") or []:
        case = _case_from_run(run_meta, snap)
        if case:
            cases.append(case)
    cat = (category or "all").strip().lower()
    if cat == "latest":
        cases = cases[:1]
    elif cat == "cursor":
        cases = [c for c in cases if c.get("actor") == "cursor"]
    elif cat in {"tool", "ui", "test", "research", "matrix"}:
        cases = [c for c in cases if c.get("kind") == cat]
    elif cat not in {"all", ""}:
        cases = cases
    summaries = [
        {
            "id": c["id"],
            "title": c["title"],
            "title_source": c["title_source"],
            "request_status": c["request_status"],
            "actor": c["actor"],
            "kind": c["kind"],
            "status": c["status"],
            "run_id": c.get("run_id"),
            "timestamp": c.get("timestamp"),
        }
        for c in cases
    ]
    return {
        "ok": True,
        "kind": "development",
        "cursor_live": cursor_live_status(),
        "filter": cat or "all",
        "cases": summaries,
        "note": "案件は Run を単位にしています。Cursor ライブ状態は含みません。",
    }


def get_case(case_id: str) -> dict[str, Any]:
    if not case_id or not SAFE_CASE.match(case_id):
        return {"ok": False, "error": "不正な案件 ID です", "error_kind": "invalid_id"}
    if not case_id.startswith("run-"):
        return {"ok": False, "error": "指定された案件はありません", "error_kind": "not_found"}
    run_id = case_id[4:]
    meta = next((r for r in (list_runs().get("runs") or []) if r.get("run_id") == run_id), None)
    if not meta:
        return {"ok": False, "error": "指定された案件はありません", "error_kind": "not_found"}
    snap = git_snapshot()
    case = _case_from_run(meta, snap)
    if not case:
        return {"ok": False, "error": "指定された案件はありません", "error_kind": "not_found"}
    repo = {
        "modified": (snap.get("counts") or {}).get("modified"),
        "added": (snap.get("counts") or {}).get("added"),
        "deleted": (snap.get("counts") or {}).get("deleted"),
        "untracked": (snap.get("counts") or {}).get("untracked"),
        "branch": snap.get("branch"),
        "head": snap.get("head"),
        "note": "リポジトリ全体の現在状態です。この案件の変更とは限りません。",
    }
    return {
        "ok": True,
        "kind": "development",
        "cursor_live": cursor_live_status(),
        "case": case,
        "repository_status": repo,
        "local_agent_bridge": case_local_agent_bridge(),
        "note": "確認できた成果物だけを Timeline にしています。操作途中のイベントは作っていません。",
    }


def session_jobs_as_notes(session: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Chat UI 上の依頼記録。Cursor 案件とは別。架空の Cursor 作業にはしない。"""
    notes = []
    for job in list_jobs(session):
        notes.append(
            {
                "id": job.get("id"),
                "title": job.get("title"),
                "request": job.get("request"),
                "actor": "local_agent",
                "source": "session",
                "kind": job.get("kind"),
                "proposal_id": job.get("proposal_id"),
                "request_id": job.get("request_id"),
                "note": "Chat UI で記録した依頼です。Cursor が実行したことの証明ではありません。",
            }
        )
    return notes
