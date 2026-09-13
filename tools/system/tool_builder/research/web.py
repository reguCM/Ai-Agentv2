import json
import re
import urllib.error
import urllib.parse
import urllib.request


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 12
MAX_HITS = 5


def http_get(url, *, data=None):
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def compact_hit(title, snippet, url, backend):
    return {
        "title": str(title or "").strip()[:200],
        "snippet": str(snippet or "").strip()[:400],
        "url": str(url or "").strip()[:300],
        "backend": backend,
    }


def search_duckduckgo(query, limit=MAX_HITS):
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
        }
    )
    payload = json.loads(
        http_get(f"https://api.duckduckgo.com/?{params}")
    )
    hits = []
    abstract = payload.get("AbstractText")
    abstract_url = payload.get("AbstractURL")
    if abstract:
        hits.append(
            compact_hit(
                payload.get("Heading") or query,
                abstract,
                abstract_url,
                "duckduckgo",
            )
        )
    for item in payload.get("RelatedTopics") or []:
        if len(hits) >= limit:
            break
        if not isinstance(item, dict):
            continue
        if item.get("Text"):
            hits.append(
                compact_hit(
                    item.get("Text"),
                    item.get("Text"),
                    item.get("FirstURL"),
                    "duckduckgo",
                )
            )
            continue
        for nested in item.get("Topics") or []:
            if len(hits) >= limit:
                break
            if isinstance(nested, dict) and nested.get("Text"):
                hits.append(
                    compact_hit(
                        nested.get("Text"),
                        nested.get("Text"),
                        nested.get("FirstURL"),
                        "duckduckgo",
                    )
                )
    return hits[:limit]


def search_wikipedia(query, limit=MAX_HITS):
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
        http_get(f"https://ja.wikipedia.org/w/api.php?{params}")
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
                "wikipedia",
            )
        )
    return hits[:limit]


HIT_KEYWORDS = (
    "win32_processor",
    "loadpercentage",
    "get-ciminstance",
    "get-wmiobject",
    "wmic cpu",
    "cpu get",
    "numberofcores",
    "nvidia-smi",
    "win32_operatingsystem",
    "freephysicalmemory",
    "totalvisiblememory",
    "physical memory",
    "memory usage",
)

MEMORY_HIT_KEYWORDS = (
    "win32_operatingsystem",
    "freephysicalmemory",
    "totalvisiblememory",
    "totalphysicalmemory",
    "physical memory",
    "memory usage",
    "memory percent",
    "available memory",
    "wmic os",
    "operating system",
)

IRRELEVANT_HIT_TOKENS = (
    "exchange online",
    "kerberos",
    "dev drive",
    "defender for endpoint",
    "performance mode",
    "memory integrity",
    "code integrity",
    "virtualization-based",
    "rc4",
)

GAP_FILLER = (
    "is still unconfirmed",
    "still unconfirmed",
    "is unconfirmed",
    "unconfirmed",
    "が未確認",
    "は未確認",
    "未確認",
    "を取得する方法",
    "の取得方法",
    "を確認する必要があります",
    "を確認する",
    "investigate",
    "how to obtain",
)


def _hit_text(hit):
    return " ".join(
        [
            str(hit.get("title") or ""),
            str(hit.get("snippet") or ""),
            str(hit.get("url") or ""),
        ]
    ).lower()


def structure_search_keywords(question, subject=None, inventory=None):
    """
    Judge missing / followup question から検索用キーワードを機械的に作る。
    正解コマンド名・特定プロパティ名は足さない。
    """
    subject = subject or {}
    inventory = inventory or {}
    compact = inventory if "available_commands" in inventory else {}
    text = str(question or "").strip()
    cleaned = text
    for filler in GAP_FILLER:
        cleaned = re.sub(re.escape(filler), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\"'`]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;/-")
    keywords = []
    if cleaned:
        keywords.append(cleaned)
    subcategory = subject.get("subcategory") or ""
    if subcategory == "memory":
        keywords.extend(["Windows", "physical memory", "memory"])
    elif subcategory:
        keywords.append(str(subcategory))
    for command in compact.get("available_commands") or []:
        name = str(command or "").strip()
        if name:
            keywords.append(name)
    unique = []
    seen = set()
    for item in keywords:
        key = re.sub(r"\s+", " ", str(item or "")).strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(re.sub(r"\s+", " ", str(item or "")).strip())
    return unique


def hit_is_relevant(hit, *, keywords=None, subject=None):
    text = _hit_text(hit)
    if not text.strip():
        return False
    if any(token in text for token in IRRELEVANT_HIT_TOKENS):
        return False
    subject = subject or {}
    subcategory = subject.get("subcategory") or ""
    if subcategory == "memory":
        if any(token in text for token in MEMORY_HIT_KEYWORDS):
            return True
        for keyword in keywords or []:
            token = str(keyword or "").strip().lower()
            if len(token) >= 4 and token in text:
                return True
        return False
    for keyword in keywords or []:
        token = str(keyword or "").strip().lower()
        if len(token) >= 4 and token in text:
            return True
    return hit_score(hit) > 0


def filter_relevant_hits(hits, *, keywords=None, subject=None, limit=MAX_HITS):
    kept = []
    dropped = []
    for hit in hits or []:
        if hit_is_relevant(hit, keywords=keywords, subject=subject):
            kept.append(hit)
        else:
            dropped.append(hit)
    return {
        "hits": kept[:limit],
        "dropped": dropped,
        "kept_count": len(kept),
        "dropped_count": len(dropped),
    }


def hit_score(hit):
    text = _hit_text(hit)
    return sum(1 for keyword in HIT_KEYWORDS if keyword in text)


def search_learn_microsoft(query, limit=MAX_HITS, locale="en-us"):
    params = urllib.parse.urlencode(
        {
            "search": query,
            "locale": locale,
            "$top": str(limit),
        }
    )
    payload = json.loads(
        http_get(f"https://learn.microsoft.com/api/search?{params}")
    )
    hits = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        hits.append(
            compact_hit(
                item.get("title"),
                item.get("description") or item.get("snippet"),
                item.get("url"),
                "learn.microsoft",
            )
        )
        if len(hits) >= limit:
            break
    return hits[:limit]


def unique_hits(hits):
    seen = set()
    unique = []
    for hit in hits:
        key = hit.get("url") or hit.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique


def rank_hits(hits, limit=MAX_HITS):
    hits = unique_hits(hits)
    scored = [(hit_score(hit), hit) for hit in hits]
    scored.sort(key=lambda item: item[0], reverse=True)
    relevant = [hit for score, hit in scored if score > 0]
    if relevant:
        return relevant[:limit]
    return [hit for _, hit in scored[:limit]]


def search_web(query, limit=MAX_HITS):
    query = str(query or "").strip()
    if not query:
        return {
            "query": query,
            "hits": [],
            "backends_tried": [],
            "error": "query が空です",
        }

    backends = (
        ("learn.microsoft-en", lambda query, limit=MAX_HITS: search_learn_microsoft(query, limit, "en-us")),
        ("learn.microsoft-ja", lambda query, limit=MAX_HITS: search_learn_microsoft(query, limit, "ja-jp")),
        ("duckduckgo", search_duckduckgo),
        ("wikipedia", search_wikipedia),
    )
    tried = []
    errors = []
    collected = []
    for name, searcher in backends:
        tried.append(name)
        try:
            collected.extend(
                item
                for item in searcher(query, limit=limit)
                if item.get("title") or item.get("snippet")
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, IndexError, TypeError) as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    hits = rank_hits(collected, limit=limit)
    if hits:
        return {
            "query": query,
            "hits": hits,
            "backends_tried": tried,
            "error": None,
        }
    return {
        "query": query,
        "hits": [],
        "backends_tried": tried,
        "error": " / ".join(errors) or "検索結果がありません",
    }


SEARCH_HINTS = {
    "cpu": "Win32_Processor LoadPercentage",
    "gpu": "nvidia-smi query gpu",
    "memory": "Windows memory usage percent PowerShell",
}

SEARCH_QUERY_TEMPLATES = {
    "cpu": [
        "Get-CimInstance Win32_Processor LoadPercentage",
        "wmic cpu get LoadPercentage",
        "Get-WmiObject Win32_Processor LoadPercentage PowerShell",
    ],
    "gpu": [
        "nvidia-smi query gpu temperature utilization",
    ],
    "memory": [
        "Windows physical memory PowerShell WMI",
        "Windows OS physical memory wmic",
    ],
}


def legacy_build_search_queries(item, subject=None, inventory=None):
    """Intent 失敗時のみ使う旧経路（SEARCH_HINTS / TEMPLATES）。"""
    subject = subject or {}
    inventory = inventory or {}
    compact = inventory if "available_commands" in inventory else {}
    subcategory = subject.get("subcategory") or ""
    queries = []
    for template in SEARCH_QUERY_TEMPLATES.get(subcategory, []):
        queries.append(template)
    queries.append(build_search_query(item, subject=subject, inventory=compact))
    if item.get("followup") and item.get("question"):
        question = str(item.get("question") or "").strip()
        keywords = structure_search_keywords(
            question, subject=subject, inventory=compact
        )
        if keywords:
            queries.append(" ".join(keywords))
        hint = SEARCH_HINTS.get(subcategory, subcategory)
        if question and hint:
            queries.append(
                f"{' '.join(keywords)} {hint}" if keywords else f"{question} {hint}"
            )
    unique = []
    seen = set()
    for query in queries:
        query = re.sub(r"\s+", " ", str(query or "")).strip()
        if query and query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def build_search_queries(
    item,
    subject=None,
    inventory=None,
    *,
    user_request=None,
    search_intent=None,
    searched_queries=None,
    discovered_techniques=None,
    allow_legacy_fallback=True,
):
    """
    Phase A 主経路: SearchIntent から探索クエリを生成する。
    followup では missing 連結 + subcategory hint 再付与を行わない。
    """
    from tools.system.tool_builder.research import query_intent as qi

    subject = subject or {}
    inventory = inventory or {}
    compact = inventory if "available_commands" in inventory else {}
    request_text = qi.resolve_user_request(user_request, item=item)
    intent = search_intent
    if not isinstance(intent, dict) or not intent:
        if request_text:
            intent = qi.extract_search_intent(
                request_text,
                subject=subject,
                proposal={"subcategory": subject.get("subcategory")},
                prefer_llm=False,
            )
        elif item.get("followup") and item.get("question"):
            # followup のみ: missing 文 + subcategory から弱い Intent
            intent = qi.fallback_intent_from_text(
                str(item.get("question") or ""),
                subject=subject,
            )
            # missing 文だけだと target が空になりがち → subject を優先済み
        else:
            intent = None

    queries = []
    if item.get("followup"):
        missing = []
        if item.get("question"):
            missing.append(item.get("question"))
        queries = qi.build_followup_queries(
            intent,
            missing,
            discovered=discovered_techniques,
            searched=searched_queries,
            max_queries=2,
        )
    elif intent:
        queries = qi.build_exploration_queries(intent, max_queries=3)

    queries = qi.dedupe_queries(queries, searched=searched_queries, limit=3)
    if queries:
        return queries
    if allow_legacy_fallback:
        return qi.dedupe_queries(
            legacy_build_search_queries(item, subject=subject, inventory=compact),
            searched=searched_queries,
            limit=3,
        )
    return []


def build_search_query(item, subject=None, inventory=None):
    """旧単一クエリ生成（legacy fallback 用）。"""
    subject = subject or {}
    inventory = inventory or {}
    compact = inventory if "available_commands" in inventory else {}
    subcategory = subject.get("subcategory") or ""
    parts = [
        " ".join(compact.get("available_commands") or []),
        SEARCH_HINTS.get(subcategory, subcategory),
    ]
    query = " ".join(part for part in parts if str(part).strip())
    return re.sub(r"\s+", " ", query).strip()
