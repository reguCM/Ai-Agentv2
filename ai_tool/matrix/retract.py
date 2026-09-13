"""誤レコードを検索から除外する。records.jsonl は書き換えない。LLM は使わない。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.chat_interface.activity import new_correlation_id
from ai_tool.matrix.store import MatrixStore, append_retraction, load_retracted_ids
from ai_tool.matrix.verify import records_fingerprint

REASON_MISMATCH = "ENTITY_SOURCE_MISMATCH"
REASON_UNSUPPORTED = "VALUE_NOT_SUPPORTED"
CAUSE_UNKNOWN = "NOT DETERMINED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def retract_matrix_record(
    record_id: str,
    *,
    reason: str,
    cause: str | None = None,
    note: str | None = None,
    store: MatrixStore | None = None,
    requested_by: str = "cursor",
) -> dict[str, Any]:
    """records.jsonl には追記も削除もしない。retractions.jsonl に識別行を残す。"""
    dest = store or MatrixStore()
    before = records_fingerprint(dest)
    rid = str(record_id or "").strip()
    row = dest.get_by_id(rid)
    already = rid in load_retracted_ids(dest.path.parent / "retractions.jsonl")
    payload = {
        "ok": bool(row) and not already,
        "record_id": rid or None,
        "reason": reason,
        "cause": cause,
        "note": note,
        "requested_by": requested_by,
        "executed_by": "matrix_pipeline",
        "actor": "matrix_pipeline",
        "source": "matrix",
        "llm_used": False,
        "correlation_id": new_correlation_id().replace("ac-", "mr-", 1),
        "retracted_at": _now(),
        "records_unchanged": True,
        "already_retracted": already,
        "record": row,
    }
    if not rid or row is None:
        payload["ok"] = False
        payload["error"] = "record が無い"
        payload["records_unchanged"] = records_fingerprint(dest) == before
        return payload
    if already:
        payload["error"] = "既に retraction 済み"
        payload["records_unchanged"] = records_fingerprint(dest) == before
        return payload
    append_retraction(
        {
            "record_id": rid,
            "reason": reason,
            "cause": cause,
            "note": note,
            "entity": row.get("entity"),
            "attribute": row.get("attribute"),
            "value": row.get("value"),
            "source_url": row.get("source_url"),
            "source_title": row.get("source_title"),
            "query": row.get("query"),
            "ingest_id": row.get("ingest_id"),
            "provenance": row.get("provenance"),
            "retracted_at": payload["retracted_at"],
            "correlation_id": payload["correlation_id"],
            "requested_by": requested_by,
        },
        dest.path.parent / "retractions.jsonl",
    )
    payload["records_unchanged"] = records_fingerprint(dest) == before
    return payload
