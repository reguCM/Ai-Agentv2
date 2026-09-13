"""質問 → Matrix 検索 → 十分/不足 → 必要なら既存 ingest。Chat 通常経路ではない。"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from ai_tool.chat_interface.activity import new_correlation_id
from ai_tool.chat_interface.events import event
from ai_tool.matrix.extract import GPU_ENTITY, entity_from_query, normalize_gpu_entity
from ai_tool.matrix.ingest import ingest_web_to_matrix
from ai_tool.matrix.store import MatrixStore, save_last_ask, search_records
from ai_tool.matrix.trace import _latest_verify
from ai_tool.matrix.verify import records_fingerprint

INGESTABLE_ATTRIBUTES = frozenset({"VRAM capacity"})
ATTR_VRAM = "VRAM capacity"
ATTR_PRICE = "used price"


def parse_question(question: str) -> dict[str, Any]:
    """GPU 質問の機械パーサ。未知の聞き方は推測で埋めない。"""
    raw = str(question or "").strip()
    entities: list[str] = []
    seen: set[str] = set()
    for match in GPU_ENTITY.finditer(raw):
        token = normalize_gpu_entity(match.group(1))
        if token and token not in seen:
            seen.add(token)
            entities.append(token)
    blob = raw.casefold()
    attribute: str | None = None
    if re.search(r"中古|価格|price|used\s*price", blob):
        attribute = ATTR_PRICE
    elif re.search(r"vram|容量|メモリ|memory", blob) or re.search(r"どっち|比較|vs\b", blob):
        attribute = ATTR_VRAM
    needed = [{"entity": ent, "attribute": attribute} for ent in entities] if attribute else []
    return {
        "question": raw,
        "entities": entities,
        "attribute": attribute,
        "needed": needed,
        "parsed": bool(entities and attribute),
    }


def _usable_records(rows: list[dict[str, Any]], entity: str, attribute: str) -> list[dict[str, Any]]:
    want_e = normalize_gpu_entity(entity)
    want_a = (attribute or "").casefold()
    out: list[dict[str, Any]] = []
    for row in rows:
        if normalize_gpu_entity(str(row.get("entity") or "")) != want_e:
            continue
        if str(row.get("attribute") or "").casefold() != want_a:
            continue
        if not str(row.get("value") or "").strip():
            continue
        if not str(row.get("source_url") or "").strip():
            continue
        out.append(row)
    return out


def _attach_verify(row: dict[str, Any], store: MatrixStore) -> dict[str, Any]:
    item = dict(row)
    latest = _latest_verify(str(row.get("record_id") or ""), store.path.parent / "verify.jsonl")
    if latest:
        item["verification"] = str(latest.get("result") or "NOT OBSERVED")
        item["verified_at"] = latest.get("verified_at")
    else:
        item["verification"] = "NOT OBSERVED"
        item["verified_at"] = None
    return item


def _mechanical_answer(facts: list[dict[str, Any]]) -> str:
    if not facts:
        return "INSUFFICIENT"
    lines = [
        (
            f"{row.get('entity')} / {row.get('attribute')} = {row.get('value')} "
            f"(source: {row.get('source_url')}; verify: {row.get('verification') or 'NOT OBSERVED'}; "
            f"observed_at: {row.get('observed_at')})"
        )
        for row in facts
    ]
    lines.append("MATCH は出典ページ上に記述を確認したことであり、真実性の確定ではない。")
    return "\n".join(lines)


def _parse_llm_json(text: str) -> dict[str, Any] | None:
    blob = str(text or "").strip()
    if not blob:
        return None
    try:
        data = json.loads(blob)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", blob, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def ask_matrix(
    question: str,
    *,
    fallback: bool = False,
    use_llm: bool = False,
    store: MatrixStore | None = None,
    search_fn: Callable[..., dict[str, Any]] | None = None,
    fetch_fn: Callable[..., dict[str, Any]] | None = None,
    wiki_fn: Callable[[str], dict[str, Any]] | None = None,
    chat_fn: Callable[..., Any] | None = None,
    model: str | None = None,
    requested_by: str = "user",
) -> dict[str, Any]:
    """Matrix を先に使い、不足かつ fallback のときだけ既存 ingest を呼ぶ。"""
    dest = store or MatrixStore()
    before = records_fingerprint(dest)
    correlation_id = new_correlation_id().replace("ac-", "ma-", 1)
    actor = "matrix_pipeline"
    source = "matrix"
    base = {
        "correlation_id": correlation_id,
        "requested_by": requested_by,
        "executed_by": actor,
        "actor": actor,
        "source": source,
    }
    events: list[dict[str, Any]] = []
    web_search_count = 0
    matrix_search_count = 0
    ingest_ids: list[str] = []
    llm_used = False
    llm_model: str | None = None
    llm_summary: str | None = None
    llm_missing: list[dict[str, str]] = []
    parsed = parse_question(question)
    events.append(event("question", status="success", question=parsed["question"], **base))
    needed: list[dict[str, str]] = list(parsed["needed"])

    def pack(*, decision: str, facts: list[dict[str, Any]], answer: str, error: str | None = None) -> dict[str, Any]:
        payload = {
            "ok": decision == "SUFFICIENT",
            "decision": decision,
            "question": parsed["question"],
            "parsed": parsed,
            "needed": needed,
            "records": facts,
            "answer": answer,
            "error": error,
            "web_search_count": web_search_count,
            "matrix_search_count": matrix_search_count,
            "ingest_ids": ingest_ids,
            "llm_used": llm_used,
            "llm_model": llm_model,
            "llm_summary": llm_summary,
            "llm_missing": llm_missing,
            "research": "NOT_CONNECTED",
            "chat_path": "NOT_CONNECTED",
            "events": events,
            "requested_by": requested_by,
            "executed_by": actor,
            "actor": actor,
            "source": source,
            "correlation_id": correlation_id,
            "records_fingerprint_before": before,
            "records_fingerprint_after": records_fingerprint(dest),
        }
        save_last_ask(payload, dest.path.parent / "last_ask.json")
        return payload

    if not parsed["parsed"]:
        events.append(
            event(
                "insufficient",
                status="INSUFFICIENT",
                reason="PARSE_INCOMPLETE",
                note="entity または attribute を機械的に取れない。推測しない。",
                **base,
            )
        )
        return pack(decision="INSUFFICIENT", facts=[], answer="INSUFFICIENT", error="PARSE_INCOMPLETE")

    def lookup() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        nonlocal matrix_search_count
        found: list[dict[str, Any]] = []
        missing: list[dict[str, str]] = []
        rows = dest.all_records()
        for fact in needed:
            matrix_search_count += 1
            hits = _usable_records(
                search_records(rows, entity=fact["entity"], attribute=fact["attribute"]),
                fact["entity"],
                fact["attribute"],
            )
            events.append(
                event(
                    "matrix_search",
                    status="success",
                    entity=fact["entity"],
                    attribute=fact["attribute"],
                    hit_count=len(hits),
                    **base,
                )
            )
            if hits:
                found.extend(_attach_verify(h, dest) for h in hits)
            else:
                missing.append(fact)
        return found, missing

    facts, missing = lookup()
    if not missing:
        events.append(event("sufficient", status="SUFFICIENT", record_count=len(facts), **base))
        if use_llm:
            llm_summary, llm_missing, llm_used, llm_model = _run_llm(
                parsed["question"], facts, chat_fn=chat_fn, model=model, events=events, base=base
            )
            events.append(event("answer", status="success", via="matrix", **base))
            text = (llm_summary or "") + "\n" + _mechanical_answer(facts)
            return pack(decision="SUFFICIENT", facts=facts, answer=text.strip())
        events.append(event("answer", status="success", via="matrix", **base))
        return pack(decision="SUFFICIENT", facts=facts, answer=_mechanical_answer(facts))

    events.append(
        event(
            "insufficient",
            status="INSUFFICIENT",
            missing=missing,
            note="必要な Record が Matrix に無い。",
            **base,
        )
    )
    if use_llm:
        llm_summary, extra_missing, llm_used, llm_model = _run_llm(
            parsed["question"], facts, chat_fn=chat_fn, model=model, events=events, base=base
        )
        for item in extra_missing:
            if item not in needed:
                needed.append(item)
        facts, missing = lookup()
        if not missing and facts:
            events.append(event("sufficient", status="SUFFICIENT", record_count=len(facts), **base))
            events.append(event("answer", status="success", via="matrix", **base))
            text = (llm_summary or "") + "\n" + _mechanical_answer(facts)
            return pack(decision="SUFFICIENT", facts=facts, answer=text.strip())
        if extra_missing:
            events.append(event("insufficient", status="INSUFFICIENT", missing=missing, note="LLM が不足を列挙。検索は機械側。", **base))

    if not fallback:
        events.append(event("answer", status="skipped", via="none", reason="INSUFFICIENT", **base))
        return pack(decision="INSUFFICIENT", facts=facts, answer="INSUFFICIENT")

    for fact in missing:
        attr = fact["attribute"]
        if attr not in INGESTABLE_ATTRIBUTES:
            events.append(
                event(
                    "ingest_skip",
                    status="NOT CONNECTED",
                    entity=fact["entity"],
                    attribute=attr,
                    note="既存 extract がこの attribute を保存しない。新しい抽出器は作らない。",
                    **base,
                )
            )
            continue
        ingest = ingest_web_to_matrix(
            fact["entity"],
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            wiki_fn=wiki_fn,
            store=dest,
            requested_by=requested_by,
        )
        ingest_ids.append(str(ingest.get("ingest_id") or ""))
        if any(ev.get("type") == "search" for ev in ingest.get("events") or []):
            web_search_count += 1
        for ev in ingest.get("events") or []:
            if ev.get("type") != "research":
                events.append(ev)

    facts, missing = lookup()
    if not missing and facts:
        events.append(event("sufficient", status="SUFFICIENT", record_count=len(facts), **base))
        events.append(event("answer", status="success", via="matrix", **base))
        text = _mechanical_answer(facts)
        if llm_summary:
            text = llm_summary + "\n" + text
        return pack(decision="SUFFICIENT", facts=facts, answer=text)
    events.append(
        event(
            "insufficient",
            status="INSUFFICIENT",
            missing=missing,
            note="再調査後も必要 Record が無い。",
            **base,
        )
    )
    events.append(event("answer", status="skipped", via="matrix", reason="INSUFFICIENT", **base))
    return pack(decision="INSUFFICIENT", facts=facts, answer="INSUFFICIENT")


def _run_llm(
    question: str,
    facts: list[dict[str, Any]],
    *,
    chat_fn: Callable[..., Any] | None,
    model: str | None,
    events: list[dict[str, Any]],
    base: dict[str, Any],
) -> tuple[str | None, list[dict[str, str]], bool, str | None]:
    if chat_fn is None:
        events.append(
            event(
                "llm",
                status="NOT CONNECTED",
                actor="local_llm",
                source="ollama",
                note="chat_fn が無い。LLM 判断をしていない。",
                **{k: v for k, v in base.items() if k not in {"actor", "source"}},
            )
        )
        return None, [], False, None
    slim = [
        {
            "entity": r.get("entity"),
            "attribute": r.get("attribute"),
            "value": r.get("value"),
            "source_url": r.get("source_url"),
            "verification": r.get("verification"),
        }
        for r in facts
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "与えられた JSON の Record だけを使え。無い値を作るな。出典を捏造するな。"
                "JSON だけ返せ。形式: {\"summary\": str, \"missing\": [{\"entity\": str, \"attribute\": str}]}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"question": question, "records": slim}, ensure_ascii=False),
        },
    ]
    kwargs: dict[str, Any] = {"messages": messages}
    if model:
        kwargs["model"] = model
    try:
        raw = chat_fn(**kwargs)
    except Exception as exc:  # noqa: BLE001
        events.append(
            event(
                "llm",
                status="error",
                actor="local_llm",
                source="ollama",
                model=model,
                error=f"{type(exc).__name__}: {exc}",
                **{k: v for k, v in base.items() if k not in {"actor", "source"}},
            )
        )
        return None, [], False, model
    content = ""
    used_model = model
    if isinstance(raw, dict):
        msg = raw.get("message") if isinstance(raw.get("message"), dict) else {}
        content = str((msg or {}).get("content") or raw.get("content") or "")
        used_model = str(raw.get("model") or model or "") or model
    else:
        content = str(raw)
    parsed = _parse_llm_json(content) or {}
    summary = str(parsed.get("summary") or "").strip() or None
    missing: list[dict[str, str]] = []
    for item in parsed.get("missing") or []:
        if not isinstance(item, dict):
            continue
        ent = entity_from_query(str(item.get("entity") or ""))
        attr = str(item.get("attribute") or "").strip()
        if not ent or not attr:
            continue
        if attr.casefold() in {"vram", "vram capacity", "容量"}:
            attr = ATTR_VRAM
        missing.append({"entity": ent, "attribute": attr})
    events.append(
        event(
            "llm",
            status="success",
            actor="local_llm",
            source="ollama",
            model=used_model,
            missing=missing,
            note="Record の整理と不足列挙のみ。検索・保存は機械側。",
            **{k: v for k, v in base.items() if k not in {"actor", "source"}},
        )
    )
    return summary, missing, True, used_model
