"""Matrix 保存値と出典ページの機械照合。正しさの確定・訂正はしない。LLM は使わない。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from ai_tool.chat_interface.activity import new_correlation_id
from ai_tool.chat_interface.events import event
from ai_tool.matrix.extract import page_supports_fact
from ai_tool.matrix.ingest import SCAN_CHARS, fetch_wikipedia_wikitext, wikipedia_title_from_url
from ai_tool.matrix.store import (
    MatrixStore,
    append_verify_log,
    save_last_verify,
)

FetchFn = Callable[..., dict[str, Any]]
WikiFn = Callable[[str], dict[str, Any]]
CAUSE = "NOT_OBSERVED"
NOTE = "MATCH は正しさの確定ではない。NOT_FOUND は誤り確定ではない。"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def records_bytes(store: MatrixStore) -> bytes:
    path = store.path
    if not path.is_file():
        return b""
    return path.read_bytes()


def records_fingerprint(store: MatrixStore) -> dict[str, Any]:
    raw = records_bytes(store)
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "path": str(store.path),
    }


def _fetch_source(
    url: str,
    *,
    fetch_fn: FetchFn | None,
    wiki_fn: WikiFn | None,
) -> tuple[dict[str, Any], str | None, str]:
    wiki_title = wikipedia_title_from_url(url)
    if wiki_title:
        page = (wiki_fn or fetch_wikipedia_wikitext)(wiki_title)
        kind = "wikipedia_wikitext"
    else:
        from ai_tool.experimental.read_url.reader import read_url_text as production_read_url

        reader = fetch_fn or production_read_url
        page = reader(url)
        kind = "read_url_text"
    if not isinstance(page, dict):
        page = {"ok": False, "url": url, "main_text": "", "error": "fetch が dict を返さなかった"}
    return page, wiki_title, kind


def verify_matrix_record(
    record_id: str,
    *,
    store: MatrixStore | None = None,
    fetch_fn: FetchFn | None = None,
    wiki_fn: WikiFn | None = None,
    requested_by: str = "user",
) -> dict[str, Any]:
    """source_url を取得し、保存値を支持する記述があるか見る。レコードは変更しない。"""
    dest = store or MatrixStore()
    before = records_fingerprint(dest)
    correlation_id = new_correlation_id().replace("ac-", "mv-", 1)
    actor = "matrix_pipeline"
    source = "matrix"
    verified_at = _now()
    base = {
        "correlation_id": correlation_id,
        "requested_by": requested_by,
        "executed_by": actor,
        "actor": actor,
        "source": source,
        "verify_id": f"vf-{uuid.uuid4().hex[:12]}",
    }
    events: list[dict[str, Any]] = []
    rid = str(record_id or "").strip()
    row = dest.get_by_id(rid) if rid else None

    def finish(status: str, *, fetch_used: bool = False, error: str | None = None) -> dict[str, Any]:
        events.append(
            event(
                "matrix_verify",
                status="success" if status in {"MATCH", "NOT_FOUND", "FETCH_ERROR", "NOT_AVAILABLE"} else "error",
                result=status,
                cause=CAUSE,
                note=NOTE,
                llm_used=False,
                **base,
            )
        )
        events.append(
            event(
                "verify_result",
                status=status,
                result=status,
                cause=CAUSE,
                note=NOTE,
                **base,
            )
        )
        payload = {
            "ok": True,
            "llm_used": False,
            "research": "NOT_CONNECTED",
            "result": status,
            "cause": CAUSE,
            "note": NOTE,
            "error": error,
            "record_id": rid or None,
            "record": row,
            "entity": (row or {}).get("entity") if row else None,
            "attribute": (row or {}).get("attribute") if row else None,
            "value": (row or {}).get("value") if row else None,
            "source_url": (row or {}).get("source_url") if row else None,
            "source_title": (row or {}).get("source_title") if row else None,
            "observed_at": (row or {}).get("observed_at") if row else None,
            "provenance": (row or {}).get("provenance") if row else None,
            "verified_at": verified_at,
            "verify_path": "source_url → fetch → page_supports_fact",
            "fetch_used": fetch_used,
            "events": events,
            "requested_by": requested_by,
            "executed_by": actor,
            "actor": actor,
            "source": source,
            "correlation_id": correlation_id,
        }
        after = records_fingerprint(dest)
        payload["records_unchanged"] = after == before
        save_last_verify(payload, dest.path.parent / "last_verify.json")
        append_verify_log(
            {
                "record_id": rid,
                "result": status,
                "verified_at": verified_at,
                "correlation_id": correlation_id,
            },
            dest.path.parent / "verify.jsonl",
        )
        return payload

    if not rid:
        err = event("error", status="error", error="record_id が空です", **base)
        events.append(err)
        return finish("NOT_AVAILABLE", error="record_id が空です")
    if row is None:
        err = event("error", status="error", error="record が無い", **base)
        events.append(err)
        return finish("NOT_AVAILABLE", error="record が無い")

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
            **base,
        )
    )

    url = str(row.get("source_url") or "").strip()
    if not url:
        return finish("NOT_AVAILABLE", error="source_url が無い")

    try:
        page, wiki_title, kind = _fetch_source(url, fetch_fn=fetch_fn, wiki_fn=wiki_fn)
    except Exception as exc:  # noqa: BLE001
        events.append(
            event(
                "fetch",
                url=url,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
                omitted=["main_text"],
                **base,
            )
        )
        return finish("FETCH_ERROR", fetch_used=True, error=f"{type(exc).__name__}: {exc}")

    ok = bool(page.get("ok"))
    text = str(page.get("main_text") or page.get("content") or "")[:SCAN_CHARS]
    events.append(
        event(
            "fetch",
            url=url,
            fetch_kind=kind,
            status="success" if ok else "error",
            omitted=["main_text", "wikitext"] if wiki_title else ["main_text"],
            **base,
        )
    )
    if not ok:
        return finish("FETCH_ERROR", fetch_used=True, error=str(page.get("error") or "出典ページを取得できなかった"))

    supported = page_supports_fact(
        entity=str(row.get("entity") or ""),
        attribute=str(row.get("attribute") or ""),
        value=str(row.get("value") or ""),
        text=text,
    )
    return finish("MATCH" if supported else "NOT_FOUND", fetch_used=True)
