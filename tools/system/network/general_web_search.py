"""
PROJECT_AGENT 向け一般 Web 検索。

Tool Builder 用の research.web.search_web（MS Learn + HIT_KEYWORDS）とは別経路。
既存 research.web.search_web / ranking / filter は変更・呼び出ししない。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from tools.system.tool_builder.research.web import (
    compact_hit,
    http_get,
    search_duckduckgo,
    search_wikipedia,
    unique_hits,
)

DEFAULT_RETURN_LIMIT = 5
DEFAULT_FETCH_LIMIT = 5


def search_wikipedia_en(query, limit=DEFAULT_FETCH_LIMIT):
    """英語 Wikipedia OpenSearch（research.web は変更せずこちらに置く）。"""
    params = urllib.parse.urlencode(
        {
            "action": "opensearch",
            "search": query,
            "limit": str(limit),
            "namespace": "0",
            "format": "json",
        }
    )
    payload = json.loads(
        http_get(f"https://en.wikipedia.org/w/api.php?{params}")
    )
    titles = payload[1] if len(payload) > 1 else []
    snippets = payload[2] if len(payload) > 2 else []
    urls = payload[3] if len(payload) > 3 else []
    hits = []
    for index, title in enumerate(titles):
        hits.append(
            compact_hit(
                title,
                snippets[index] if index < len(snippets) else "",
                urls[index] if index < len(urls) else "",
                "wikipedia-en",
            )
        )
    return hits[:limit]


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text or ""))


def backend_queries_for_discovery(query: str, backend_name: str) -> list[str]:
    """Discovery-only backend query variants. Original query is always first.

    Wikipedia OpenSearch prefix-matches CJK 「XのY」 to article titles starting with Xの…,
    which can omit the entity page for X. A spaced variant (X Y) is added when safe.
    """
    q = str(query or "").strip()
    if not q:
        return []
    if not str(backend_name).startswith("wikipedia"):
        return [q]
    variants = [q]
    if _has_cjk(q) and "の" in q:
        shaped = re.sub(r"\s*の\s*", " ", q)
        shaped = re.sub(r"\s+", " ", shaped).strip()
        if shaped and shaped != q:
            variants.append(shaped)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in variants:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def discovery_ranking_tokens(query: str) -> list[str]:
    """Tokens for ranking — includes Wikipedia spaced variants when present."""
    seen: set[str] = set()
    ordered: list[str] = []
    for variant in backend_queries_for_discovery(query, "wikipedia-ja"):
        for tok in query_tokens(variant):
            key = tok.lower()
            if key not in seen:
                seen.add(key)
                ordered.append(tok)
    return ordered


def query_tokens(query: str) -> list[str]:
    """汎用トークン分割。特定トピック語のハードコードはしない。"""
    text = str(query or "").strip()
    if not text:
        return []
    tokens = []
    # 空白・句読点で分割（日英混在）
    for part in re.split(r"[\s\u3000、。，．・/\\|（）()【】\[\]「」『』\"'：:；;,.?？!！]+", text):
        part = part.strip()
        if len(part) >= 2:
            tokens.append(part)
    # スペース無しの長いCJK列は全文もフレーズ候補に
    if _has_cjk(text) and text not in tokens:
        tokens.append(text)
    # 重複除去（順序維持）
    seen = set()
    unique = []
    for tok in tokens:
        key = tok.lower()
        if key not in seen:
            seen.add(key)
            unique.append(tok)
    return unique


def score_hit_for_query(hit: dict, query: str, tokens: list[str]) -> int:
    title = str((hit or {}).get("title") or "")
    snippet = str((hit or {}).get("snippet") or "")
    blob = f"{title}\n{snippet}"
    title_l = title.lower()
    blob_l = blob.lower()
    query_l = str(query or "").strip().lower()
    score = 0

    if query_l and query_l in blob_l:
        score += 5
        if query_l in title_l:
            score += 3

    for tok in tokens:
        t = tok.lower()
        if len(t) < 2:
            continue
        if title_l == t:
            score += 6
        elif title_l.startswith(t + " ") or title_l.startswith(t + "（") or title_l.startswith(t + "("):
            score += 4
        elif t in title_l:
            score += 3
        elif t in blob_l:
            score += 1

    if _has_cjk(query) and _has_cjk(blob):
        score += 1

    if tokens:
        head = tokens[0].lower()
        if len(head) >= 2 and (
            title_l == head
            or title_l.startswith(head + " ")
            or title_l.startswith(head + "(")
            or title_l.startswith(head + "（")
        ):
            score += 10

    return score


def enrich_hit_for_discovery(hit: dict, query: str, score: int) -> dict:
    """Add decision-support fields without changing Discovery semantics."""
    out = dict(hit or {})
    snippet = str(out.get("snippet") or "").strip()
    if not snippet:
        title = str(out.get("title") or "").strip()
        snippet = title if title else ""
    out["snippet"] = snippet
    if score >= 5:
        relevance = "high"
    elif score >= 2:
        relevance = "medium"
    elif score >= 1:
        relevance = "low"
    else:
        relevance = "unknown"
    out["relevance_hint"] = relevance
    return out


def rank_hits_for_query(hits, query, limit=DEFAULT_RETURN_LIMIT):
    tokens = discovery_ranking_tokens(query)
    unique = unique_hits(hits)
    scored = [(score_hit_for_query(hit, query, tokens), hit) for hit in unique]
    scored.sort(key=lambda item: item[0], reverse=True)
    positive = [(score, hit) for score, hit in scored if score > 0]
    selected = positive[:limit] if positive else scored[:limit]
    enriched = [enrich_hit_for_discovery(hit, query, score) for score, hit in selected]
    return enriched, scored


def general_web_search(query, limit=None, fetch_limit=None):
    """
    一般Web向け検索。

    limit / return_limit: LLMへ返す件数（省略時 DEFAULT_RETURN_LIMIT）。
    fetch_limit: 各backendから集める候補数（省略時 max(DEFAULT_FETCH_LIMIT, return_limit)）。
    limit=1 でも fetch は複数寄せてから絞る。
    """
    query = str(query or "").strip()
    if not query:
        return {
            "query": query,
            "hits": [],
            "backends_tried": [],
            "error": "query が空です",
            "fetch_limit": None,
            "return_limit": None,
        }

    if limit is None:
        return_limit = DEFAULT_RETURN_LIMIT
    else:
        try:
            return_limit = int(limit)
        except (TypeError, ValueError):
            return {
                "query": query,
                "hits": [],
                "backends_tried": [],
                "error": f"limit が不正です: {limit!r}",
                "fetch_limit": None,
                "return_limit": None,
            }
        if return_limit < 1:
            return {
                "query": query,
                "hits": [],
                "backends_tried": [],
                "error": "limit は 1 以上である必要があります",
                "fetch_limit": None,
                "return_limit": return_limit,
            }

    if fetch_limit is None:
        fetch = max(DEFAULT_FETCH_LIMIT, return_limit)
    else:
        try:
            fetch = int(fetch_limit)
        except (TypeError, ValueError):
            fetch = max(DEFAULT_FETCH_LIMIT, return_limit)
        fetch = max(1, fetch)

    backends = (
        ("duckduckgo", search_duckduckgo),
        ("wikipedia-ja", search_wikipedia),
        ("wikipedia-en", search_wikipedia_en),
    )

    tried = []
    errors = []
    collected = []
    for name, searcher in backends:
        tried.append(name)
        backend_queries = backend_queries_for_discovery(query, name)
        for backend_query in backend_queries:
            try:
                collected.extend(
                    item
                    for item in searcher(backend_query, limit=fetch)
                    if item.get("title") or item.get("snippet")
                )
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
                IndexError,
                TypeError,
                OSError,
            ) as exc:
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                break

    hits, _scored = rank_hits_for_query(collected, query, limit=return_limit)
    if hits:
        return {
            "query": query,
            "hits": hits,
            "backends_tried": tried,
            "error": None,
            "fetch_limit": fetch,
            "return_limit": return_limit,
            "candidates_collected": len(unique_hits(collected)),
            "grounding": {
                "web_evidence_available": True,
                "empty_search": False,
                "discovery_only": True,
            },
        }
    return {
        "query": query,
        "hits": [],
        "backends_tried": tried,
        "error": " / ".join(errors) or "検索結果がありません",
        "fetch_limit": fetch,
        "return_limit": return_limit,
        "candidates_collected": 0,
        "grounding": {
            "web_evidence_available": False,
            "empty_search": True,
            "discovery_only": True,
        },
    }
