"""Web Search → 抽出 → Matrix 追記。Chat / LLM 回答経路ではない。"""
from __future__ import annotations

import json
import re
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote, unquote, urlparse

from ai_tool.chat_interface.activity import new_correlation_id
from ai_tool.chat_interface.events import event
from ai_tool.matrix.extract import (
    entity_from_query,
    entity_from_source,
    extract_records_from_hits,
    normalize_capacity,
    page_supports_fact,
    source_entity_mismatch,
)
from ai_tool.matrix.models import MatrixRecord
from ai_tool.matrix.store import MatrixStore, save_last_ingest
from tools.system.network.search_web import search_web as production_search_web

SearchFn = Callable[..., dict[str, Any]]
FetchFn = Callable[..., dict[str, Any]]
WikiFn = Callable[[str], dict[str, Any]]
PROVENANCE = "web_search → extract → matrix_write"
FETCH_LIMIT = 3
SCAN_CHARS = 8000
WIKI_UA = "AI-Agent-Matrix/0.1 (local knowledge store; mechanical extract)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ingest_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"ing-{stamp}-{uuid.uuid4().hex[:8]}"


def wikipedia_title_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "wikipedia.org" not in host:
        return None
    if "/wiki/" not in parsed.path:
        return None
    title = unquote(parsed.path.split("/wiki/", 1)[1]).split("#", 1)[0].strip("/")
    return title or None


def fetch_wikipedia_wikitext(title: str) -> dict[str, Any]:
    """HTML 正規化で表が落ちる Wikipedia 向け。本文全文は返すが呼び出し側が保存しない。"""
    page = str(title or "").strip()
    api = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=parse&page={quote(page)}&redirects=1&prop=wikitext&format=json"
    )
    req = urllib.request.Request(api, headers={"User-Agent": WIKI_UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "ok": False,
            "url": api,
            "title": page,
            "main_text": "",
            "error": f"{type(exc).__name__}: {exc}",
        }
    parsed = data.get("parse") if isinstance(data, dict) else None
    if not isinstance(parsed, dict):
        return {"ok": False, "url": api, "title": page, "main_text": "", "error": "parse が無い"}
    wt = parsed.get("wikitext")
    text = str((wt or {}).get("*") or "") if isinstance(wt, dict) else ""
    return {
        "ok": bool(text),
        "url": api,
        "title": str(parsed.get("title") or page),
        "main_text": text[:SCAN_CHARS],
        "error": None if text else "wikitext が空",
    }


def _hit_count(result: dict[str, Any]) -> int:
    hits = result.get("hits")
    return len(hits) if isinstance(hits, list) else 0


def ingest_web_to_matrix(
    query: str,
    *,
    search_fn: SearchFn | None = None,
    fetch_fn: FetchFn | None = None,
    wiki_fn: WikiFn | None = None,
    store: MatrixStore | None = None,
    requested_by: str = "user",
    limit: int | None = None,
) -> dict[str, Any]:
    """search_web を呼び、抽出できた事実だけを追記する。hits / 本文は Matrix に置かない。"""
    q = str(query or "").strip()
    correlation_id = new_correlation_id().replace("ac-", "mx-", 1)
    ingest_id = _ingest_id()
    actor = "matrix_pipeline"
    source = "matrix"
    events: list[dict[str, Any]] = []
    base = {
        "correlation_id": correlation_id,
        "requested_by": requested_by,
        "executed_by": actor,
        "actor": actor,
        "source": source,
        "ingest_id": ingest_id,
    }

    if not q:
        err = event("error", status="error", error="query が空です", **base)
        events.append(err)
        payload = {
            "ok": False,
            "error": "query が空です",
            "ingest_id": ingest_id,
            "correlation_id": correlation_id,
            "query": q,
            "records": [],
            "events": events,
            "llm_used": False,
        }
        save_last_ingest(payload)
        return payload

    fn = search_fn or production_search_web
    kwargs: dict[str, Any] = {"query": q}
    if limit is not None:
        kwargs["limit"] = limit
    raw = fn(**kwargs)
    if not isinstance(raw, dict):
        raw = {"query": q, "hits": [], "error": "search_web が dict を返さなかった"}
    hits = raw.get("hits") if isinstance(raw.get("hits"), list) else []
    count = _hit_count(raw)
    search_status = "error" if raw.get("error") else "success"
    events.append(
        event(
            "search",
            query=q,
            hit_count=count,
            backends_tried=raw.get("backends_tried"),
            status=search_status,
            omitted=["hits"],
            **base,
        )
    )

    drafts = extract_records_from_hits(query=q, hits=hits)
    query_entity = entity_from_query(q)
    has_fact = any(d.get("attribute") == "VRAM capacity" for d in drafts)
    fetch_used = False
    fetched_text: dict[str, str] = {}
    from ai_tool.experimental.read_url.reader import read_url_text as production_read_url

    reader = fetch_fn or production_read_url
    fetched = 0
    for hit in hits:
        if fetched >= FETCH_LIMIT:
            break
        if not isinstance(hit, dict):
            continue
        url = str(hit.get("url") or "").strip()
        title = str(hit.get("title") or "").strip()
        if not url:
            continue
        if source_entity_mismatch(query_entity, title, url):
            continue
        wiki_title = wikipedia_title_from_url(url)
        needle = re.sub(r"\s+", "", query_entity).casefold()
        hay = re.sub(r"\s+", "", title + url).casefold()
        matching = bool(needle and needle in hay)
        if not matching:
            continue
        if not wiki_title and has_fact:
            continue
        fetched += 1
        fetch_used = True
        try:
            if wiki_title:
                page = (wiki_fn or fetch_wikipedia_wikitext)(wiki_title)
            else:
                page = reader(url)
        except Exception as exc:  # noqa: BLE001
            events.append(
                event(
                    "fetch",
                    url=url,
                    fetch_kind="wikipedia_wikitext" if wiki_title else "read_url_text",
                    status="error",
                    error=f"{type(exc).__name__}: {exc}",
                    omitted=["main_text"],
                    **base,
                )
            )
            continue
        if not isinstance(page, dict):
            page = {"ok": False, "url": url}
        text = str(page.get("main_text") or "")[:SCAN_CHARS]
        status = "success" if page.get("ok") else "error"
        events.append(
            event(
                "fetch",
                url=url,
                fetch_kind="wikipedia_wikitext" if wiki_title else "read_url_text",
                status=status,
                omitted=["main_text", "wikitext"] if wiki_title else ["main_text"],
                **base,
            )
        )
        if text:
            fetched_text[url] = text
        extra_hits = [
            {
                "title": str(hit.get("title") or page.get("title") or ""),
                "url": url,
                "snippet": text,
            }
        ]
        for draft in extract_records_from_hits(query=q, hits=extra_hits):
            if draft not in drafts:
                drafts.append(draft)

    events.append(
        event(
            "extract",
            status="success" if drafts else "empty",
            draft_count=len(drafts),
            note="LLM は使っていない。snippet / main_text 全文は保存しない。entity は query から仮置きし、次段で出典と照合する。",
            **base,
        )
    )

    normalized: list[dict[str, Any]] = []
    for draft in drafts:
        item = dict(draft)
        if str(item.get("attribute") or "") == "VRAM capacity":
            item["value"] = normalize_capacity(str(item.get("value") or ""))
        normalized.append(item)
    events.append(
        event(
            "normalize",
            status="success" if normalized else "empty",
            draft_count=len(normalized),
            note="容量表記の単位正規化のみ。Entity / Source 判定ではない。",
            **base,
        )
    )

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ok: set[tuple[str, str, str, str]] = set()
    for draft in normalized:
        title = str(draft.get("source_title") or "")
        url = str(draft.get("source_url") or "")
        attr = str(draft.get("attribute") or "")
        value = str(draft.get("value") or "")
        src_ent = entity_from_source(title, url)
        if source_entity_mismatch(query_entity, title, url):
            rejected.append(
                {
                    "reason": "ENTITY_SOURCE_MISMATCH",
                    "entity": query_entity,
                    "source_title_entity": src_ent,
                    "attribute": attr,
                    "value": value,
                    "source_title": title,
                    "source_url": url,
                }
            )
            continue
        if attr == "VRAM capacity":
            blob = fetched_text.get(url) or str(draft.get("excerpt") or "")
            if blob and not page_supports_fact(
                entity=query_entity,
                attribute=attr,
                value=value,
                text=blob,
            ):
                rejected.append(
                    {
                        "reason": "VALUE_NOT_SUPPORTED",
                        "entity": query_entity,
                        "source_title_entity": src_ent,
                        "attribute": attr,
                        "value": value,
                        "source_title": title,
                        "source_url": url,
                    }
                )
                continue
        key = (query_entity.casefold(), attr.casefold(), value.casefold(), url)
        if key in seen_ok:
            continue
        seen_ok.add(key)
        accepted.append(draft)

    mismatch_n = sum(1 for row in rejected if row["reason"] == "ENTITY_SOURCE_MISMATCH")
    unsupported_n = sum(1 for row in rejected if row["reason"] == "VALUE_NOT_SUPPORTED")
    check_status = "ok"
    if rejected and not accepted:
        check_status = str(rejected[0]["reason"])
    elif rejected:
        check_status = "filtered"
    events.append(
        event(
            "entity_source_check",
            status=check_status,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            entity_source_mismatch_count=mismatch_n,
            value_not_supported_count=unsupported_n,
            rejected=rejected,
            note="query Entity と出典 Entity を同一視しない。本文に無い VRAM 値は保存しない。",
            **base,
        )
    )

    observed_at = _now()
    chain = "web_search → fetch → extract → matrix_write" if fetch_used else PROVENANCE
    records: list[MatrixRecord] = []
    for draft in accepted:
        record = MatrixRecord(
            record_id=f"mr-{uuid.uuid4().hex[:12]}",
            entity=str(draft["entity"]),
            attribute=str(draft["attribute"]),
            value=str(draft["value"]),
            source_url=str(draft.get("source_url") or ""),
            source_title=str(draft.get("source_title") or ""),
            observed_at=observed_at,
            provenance=chain,
            ingest_id=ingest_id,
            query=q,
            excerpt=draft.get("excerpt"),
        )
        records.append(record)

    dest = store or MatrixStore()
    if records:
        dest.append_many(records)
        events.append(
            event(
                "matrix_write",
                status="success",
                count=len(records),
                record_ids=[r.record_id for r in records],
                **base,
            )
        )
        events.append(
            event(
                "matrix_result",
                status="success",
                count=len(records),
                records=[r.to_dict() for r in records],
                **base,
            )
        )
    else:
        events.append(
            event(
                "matrix_write",
                status="skipped",
                count=0,
                reason=check_status if rejected else "empty",
                note="MATRIX_WRITE を実行しない。",
                **base,
            )
        )
    payload = {
        "ok": bool(records),
        "error": None if records else (raw.get("error") or "抽出できた知識が無い"),
        "ingest_id": ingest_id,
        "correlation_id": correlation_id,
        "query": q,
        "hit_count": count,
        "llm_used": False,
        "research": "NOT_CONNECTED",
        "records": [r.to_dict() for r in records],
        "rejected": rejected,
        "events": events,
        "requested_by": requested_by,
        "executed_by": actor,
        "actor": actor,
        "source": source,
    }
    save_last_ingest(payload, dest.path.parent / "last_ingest.json")
    return payload
