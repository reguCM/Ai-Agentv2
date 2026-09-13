"""保存済み Matrix レコードの経路追跡。records.jsonl は変更しない。LLM は使わない。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.chat_interface.activity import new_correlation_id
from ai_tool.chat_interface.events import event
from ai_tool.matrix.extract import GPU_ENTITY, entity_from_query
from ai_tool.matrix.store import MatrixStore, save_last_trace
from ai_tool.matrix.verify import records_fingerprint

CAUSE_MISMATCH = "ENTITY_SOURCE_MISMATCH"
CAUSE_UNKNOWN = "NOT DETERMINED"
CAUSE_ALIGNED = "ALIGNED_SOURCE"
LLM_NOTE = "このレコードの provenance に LLM は無い。原因推定に LLM は使っていない。"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_gpu(token: str | None) -> str:
    text = re.sub(r"\s+", " ", str(token or "").upper()).strip()
    text = re.sub(r"^RTX\s*", "RTX ", text)
    return text.strip()


def entity_from_title(title: str) -> str | None:
    match = GPU_ENTITY.search(title or "")
    if not match:
        return None
    return _norm_gpu(match.group(1))


def excerpt_contains_value(excerpt: str | None, value: str | None) -> bool:
    blob = re.sub(r"\s+", "", str(excerpt or "")).casefold()
    want = re.sub(r"\s+", "", str(value or "")).casefold()
    return bool(blob and want and want in blob)


def _latest_verify(record_id: str, log_path: Path) -> dict[str, Any] | None:
    if not log_path.is_file():
        return None
    last: dict[str, Any] | None = None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and str(item.get("record_id") or "") == record_id:
            last = item
    return last


def _sibling_sources(rows: list[dict[str, Any]], ingest_id: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        if str(row.get("ingest_id") or "") != ingest_id:
            continue
        url = str(row.get("source_url") or "").strip()
        title = str(row.get("source_title") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"title": title, "url": url})
    return out


def trace_matrix_record(
    record_id: str,
    *,
    store: MatrixStore | None = None,
    requested_by: str = "user",
) -> dict[str, Any]:
    """保存フィールドと同一 ingest の他レコードだけから経路を復元する。Fetch し直さない。"""
    dest = store or MatrixStore()
    before = records_fingerprint(dest)
    rid = str(record_id or "").strip()
    actor = "matrix_pipeline"
    source = "matrix"
    correlation_id = new_correlation_id().replace("ac-", "mt-", 1)
    base = {
        "correlation_id": correlation_id,
        "requested_by": requested_by,
        "executed_by": actor,
        "actor": actor,
        "source": source,
        "trace_id": f"tr-{uuid.uuid4().hex[:12]}",
    }
    events: list[dict[str, Any]] = []
    rows = dest.all_records()
    row = dest.get_by_id(rid)

    def done(*, cause: str, extra: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "ok": bool(row),
            "llm_used": False,
            "llm_note": LLM_NOTE,
            "research": "NOT_CONNECTED",
            "record_id": rid or None,
            "record": row,
            "cause": cause,
            "traced_at": _now(),
            "events": events,
            "requested_by": requested_by,
            "executed_by": actor,
            "actor": actor,
            "source": source,
            "correlation_id": correlation_id,
            "records_unchanged": records_fingerprint(dest) == before,
            **extra,
        }
        save_last_trace(payload, dest.path.parent / "last_trace.json")
        return payload

    if not rid or row is None:
        events.append(event("error", status="error", error="record が無い", **base))
        events.append(event("search", status="NOT OBSERVED", note="record が無い", **base))
        return done(cause=CAUSE_UNKNOWN, extra={"error": "record が無い"})

    events.append(
        event(
            "matrix_record",
            status="success",
            record_id=row.get("record_id"),
            entity=row.get("entity"),
            attribute=row.get("attribute"),
            value=row.get("value"),
            source_url=row.get("source_url"),
            source_title=row.get("source_title"),
            observed_at=row.get("observed_at"),
            provenance=row.get("provenance"),
            ingest_id=row.get("ingest_id"),
            query=row.get("query"),
            **base,
        )
    )

    ingest_id = str(row.get("ingest_id") or "")
    siblings = _sibling_sources(rows, ingest_id) if ingest_id else []
    if siblings:
        events.append(
            event(
                "search",
                status="observed_from_records",
                query=row.get("query"),
                hit_count=len(siblings),
                titles=[s["title"] for s in siblings],
                urls=[s["url"] for s in siblings],
                omitted=["snippets", "hits_array"],
                note="ingest 時の hits 配列は未保存。同一 ingest_id の source_url から復元した。",
                **base,
            )
        )
    else:
        events.append(
            event(
                "search",
                status="NOT OBSERVED",
                query=row.get("query"),
                note="同一 ingest_id の他レコードも、ingest Event も残っていない。",
                omitted=["hits"],
                **base,
            )
        )

    prov = str(row.get("provenance") or "")
    excerpt = row.get("excerpt")
    fetch_in_prov = "fetch" in prov
    if fetch_in_prov or excerpt:
        events.append(
            event(
                "fetch",
                status="observed_from_record",
                url=row.get("source_url"),
                excerpt_present=bool(excerpt),
                omitted=["main_text", "wikitext"],
                note="provenance に fetch がある、または excerpt がある。本文全文は保存されていない。",
                **base,
            )
        )
    else:
        events.append(
            event(
                "fetch",
                status="NOT OBSERVED",
                url=row.get("source_url"),
                note="provenance に fetch が無く excerpt も無い。",
                **base,
            )
        )

    query_entity = entity_from_query(str(row.get("query") or ""))
    title_entity = entity_from_title(str(row.get("source_title") or ""))
    record_entity = _norm_gpu(str(row.get("entity") or ""))
    mismatch = bool(title_entity and record_entity and title_entity != record_entity)
    has_val = excerpt_contains_value(excerpt if isinstance(excerpt, str) else None, str(row.get("value") or ""))
    events.append(
        event(
            "extract",
            status="observed_from_record",
            entity_from_query=query_entity or None,
            entity_on_record=record_entity or None,
            source_title_entity=title_entity,
            entity_source_mismatch=mismatch,
            excerpt_contains_value=has_val,
            note="entity は query 由来。数値の抽出位置は excerpt に無い場合 NOT DETERMINED。",
            omitted=["extract_event"],
            **base,
        )
    )

    events.append(
        event(
            "normalize",
            status="NOT OBSERVED",
            value=row.get("value"),
            note="normalize 専用の保存 Event は無い。Write 時 value が正規化済みかは未記録。",
            omitted=["normalize_event"],
            **base,
        )
    )

    events.append(
        event(
            "matrix_write",
            status="observed_from_record",
            record_id=row.get("record_id"),
            count=1,
            note="この JSONL 行そのものが write 結果。",
            **base,
        )
    )

    verify_row = _latest_verify(rid, dest.path.parent / "verify.jsonl")
    if verify_row:
        events.append(
            event(
                "verify_result",
                status=str(verify_row.get("result") or "NOT OBSERVED"),
                result=verify_row.get("result"),
                verified_at=verify_row.get("verified_at"),
                note="verify.jsonl の既存結果。今回 fetch し直していない。",
                **base,
            )
        )
        last_verify = str(verify_row.get("result") or "")
    else:
        events.append(
            event(
                "verify_result",
                status="NOT OBSERVED",
                note="この record_id の verify.jsonl が無い。",
                **base,
            )
        )
        last_verify = None

    if mismatch:
        cause = CAUSE_MISMATCH
    elif last_verify == "MATCH" and not mismatch:
        cause = CAUSE_ALIGNED
    else:
        cause = CAUSE_UNKNOWN

    extra = {
        "query": row.get("query"),
        "entity": row.get("entity"),
        "attribute": row.get("attribute"),
        "value": row.get("value"),
        "source_url": row.get("source_url"),
        "source_title": row.get("source_title"),
        "source_title_entity": title_entity,
        "entity_from_query": query_entity or None,
        "entity_source_mismatch": mismatch,
        "excerpt_contains_value": has_val,
        "last_verify": last_verify,
        "search_hits_from_records": siblings,
        "actual_source_target": title_entity or "NOT DETERMINED",
    }
    return done(cause=cause, extra=extra)
