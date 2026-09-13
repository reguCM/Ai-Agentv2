"""Search hit から知識を機械抽出する。LLM は使わない。hits 本文は保存しない。"""
from __future__ import annotations

import html
import re
from typing import Any

VRAM_NEAR = re.compile(
    r"(?:VRAM|GDDR\d|video\s+memory|graphics\s+memory|グラフィックスメモリ|ビデオメモリ)"
    r".{0,48}?(\d{1,2})\s*(GB|GiB)",
    re.I | re.S,
)
GB_NEAR_VRAM = re.compile(
    r"(\d{1,2})\s*(GB|GiB)\s*(?:of\s+)?(?:GDDR\d(?:X)?|VRAM|memory)",
    re.I,
)
STRIP_QUERY = re.compile(
    r"\b(vram|capacity|specs?|specification|容量|仕様|メモリ|memory)\b",
    re.I,
)
GPU_ENTITY = re.compile(r"(RTX\s*\d{3,4}(?:\s*(?:Ti|SUPER))?)", re.I)
EXCERPT_MAX = 160


def normalize_gpu_entity(token: str | None) -> str:
    text = re.sub(r"\s+", " ", str(token or "").upper()).strip()
    text = re.sub(r"^RTX\s*", "RTX ", text)
    return text.strip()


def entity_from_query(query: str) -> str:
    raw = str(query or "").strip()
    match = GPU_ENTITY.search(raw)
    if match:
        return normalize_gpu_entity(match.group(1))
    cleaned = STRIP_QUERY.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned or raw


def entity_from_source(title: str, url: str = "") -> str | None:
    """出典 title / URL から GPU Entity を取る。query 由来の Entity は使わない。"""
    from urllib.parse import unquote, urlparse

    blobs = [str(title or ""), str(url or "").replace("_", " ").replace("-", " ")]
    parsed = urlparse(str(url or ""))
    if "/wiki/" in parsed.path:
        page = unquote(parsed.path.split("/wiki/", 1)[1]).split("#", 1)[0]
        blobs.append(page.replace("_", " "))
    for blob in blobs:
        match = GPU_ENTITY.search(blob)
        if match:
            return normalize_gpu_entity(match.group(1))
    return None


def source_entity_mismatch(entity: str, title: str, url: str = "") -> bool:
    """出典が別 GPU だと確認できるときだけ True。確認できない場合は False。"""
    want = normalize_gpu_entity(entity)
    src = entity_from_source(title, url)
    if not want or not src:
        return False
    return src != want


def _excerpt(text: str) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) <= EXCERPT_MAX:
        return compact
    return compact[: EXCERPT_MAX - 1] + "…"


def _normalize_blob(text: str) -> str:
    blob = html.unescape(str(text or ""))
    return blob.replace("\xa0", " ").replace("&nbsp;", " ")


def _unit(raw: str) -> str:
    return raw.upper().replace("GIB", "GB")


def _vram_values(text: str, entity: str = "") -> list[tuple[str, str]]:
    """同一 blob から複数容量を拾う。上書きせず列挙する。"""
    blob = _normalize_blob(text)
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    ent = re.sub(r"\s+", " ", entity).strip()
    if ent:
        esc = re.escape(ent)
        paren = re.compile(
            rf"{esc}(?!\s*Ti)(?!\s*SUPER)\s*\(\s*(\d{{1,2}})\s*(GB|GiB)\b",
            re.I,
        )
        for match in paren.finditer(blob):
            item = (match.group(1), _unit(match.group(2)))
            if item not in seen:
                seen.add(item)
                found.append(item)
    compact_ent = re.sub(r"\s+", "", entity).casefold()
    for pattern in (VRAM_NEAR, GB_NEAR_VRAM):
        for match in pattern.finditer(blob):
            if compact_ent:
                start = max(0, match.start() - 96)
                window = blob[start : match.end() + 48]
                if compact_ent not in re.sub(r"\s+", "", window).casefold():
                    continue
            item = (match.group(1), _unit(match.group(2)))
            if item not in seen:
                seen.add(item)
                found.append(item)
    return found


def extract_records_from_hits(
    *,
    query: str,
    hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """戻りは draft dict。record_id / observed_at / ingest_id は ingest が付ける。"""
    entity = entity_from_query(query)
    drafts: list[dict[str, Any]] = []
    seen_facts: set[tuple[str, str, str, str]] = set()
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        title = str(hit.get("title") or "").strip()
        url = str(hit.get("url") or "").strip()
        snippet = str(hit.get("snippet") or "").strip()
        if not title and not url:
            continue
        blob = f"{title} {snippet}"
        for number, unit in _vram_values(blob, entity):
            value = f"{number} {unit}"
            key = (entity.casefold(), "vram capacity", value.casefold(), url)
            if key in seen_facts:
                continue
            seen_facts.add(key)
            drafts.append(
                {
                    "entity": entity,
                    "attribute": "VRAM capacity",
                    "value": value,
                    "source_url": url,
                    "source_title": title,
                    "excerpt": _excerpt(blob) or None,
                }
            )
        mention_key = (entity.casefold(), "cited_by", title.casefold(), url)
        if title and mention_key not in seen_facts:
            seen_facts.add(mention_key)
            drafts.append(
                {
                    "entity": entity,
                    "attribute": "cited_by",
                    "value": title,
                    "source_url": url,
                    "source_title": title,
                    "excerpt": None,
                }
            )
    return drafts


def normalize_capacity(value: str) -> str:
    blob = _normalize_blob(value)
    match = re.match(r"(\d{1,2})\s*(GB|GiB)\b", blob, re.I)
    if match:
        return f"{match.group(1)} {_unit(match.group(2))}"
    return re.sub(r"\s+", " ", blob).strip()


def page_supports_fact(*, entity: str, attribute: str, value: str, text: str) -> bool:
    """ページ本文が保存値を支持する記述を含むか。正しさの確定ではない。"""
    attr = (attribute or "").casefold()
    if "vram" in attr:
        want = normalize_capacity(value)
        found = {f"{number} {unit}" for number, unit in _vram_values(text, entity)}
        return bool(want) and want in found
    blob = _normalize_blob(text)
    val = _normalize_blob(value)
    if not val:
        return False
    entity_compact = re.sub(r"\s+", "", entity or "").casefold()
    for match in re.finditer(re.escape(val), blob, re.I):
        if not entity_compact:
            return True
        start = max(0, match.start() - 96)
        window = blob[start : match.end() + 48]
        if entity_compact in re.sub(r"\s+", "", window).casefold():
            return True
    compact_blob = re.sub(r"\s+", "", blob).casefold()
    compact_val = re.sub(r"\s+", "", val).casefold()
    idx = compact_blob.find(compact_val)
    if idx < 0:
        return False
    if not entity_compact:
        return True
    window = compact_blob[max(0, idx - 96) : idx + len(compact_val) + 48]
    return entity_compact in window
