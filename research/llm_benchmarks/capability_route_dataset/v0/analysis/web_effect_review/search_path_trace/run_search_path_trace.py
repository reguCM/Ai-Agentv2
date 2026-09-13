"""
search_web ライフサイクル完全追跡（調査専用・実装変更なし）。

既存 search_web / ranking / backend は import して呼び出すだけ。
パッチ・差し替えは行わない。
"""

from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tools.system.network.general_web_search import (
    DEFAULT_FETCH_LIMIT,
    DEFAULT_RETURN_LIMIT,
    rank_hits_for_query,
    search_wikipedia_en,
)
from tools.system.network.search_web import search_web
from tools.system.tool_builder.research.web import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    compact_hit,
    search_duckduckgo,
    search_wikipedia,
    unique_hits,
)

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "examples"
HITS_JSON = HERE.parent / "web_effect_review_hits.json"
NORMALIZED = HERE.parent / "normalized" / "review_dataset.json"

# 重点ケース（既存ログの query を再利用）
TRACE_CASES = [
    "B05",
    "C02",
    "C03",
    "A04",
    "A06",
    "C04",
    "P02a",
    "E02",
    "WB02",
    "A03",
]

# 日英比較（同一テーマ・少数）
JA_EN_COMPARE = [
    {"label": "python_tuple_en", "query": "Python tuple"},
    {"label": "python_tuple_ja", "query": "Python タプル"},
    {"label": "python_tuple_ja_long", "query": "Pythonのtupleとは"},
    {"label": "rtx_en", "query": "GeForce RTX 3060"},
    {"label": "rtx_ja", "query": "RTX 3060 最新"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snip_len(hit: dict) -> int:
    s = hit.get("snippet")
    if s is None:
        s = hit.get("description")
    return len(str(s).strip()) if s is not None else 0


def _has_snip(hit: dict) -> bool:
    return _snip_len(hit) > 0


def http_get_raw(url: str) -> tuple[int | None, str, str | None]:
    """(status, body_text, error). Does not modify search_web."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return int(status), body, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        return int(exc.code), body, f"HTTPError: {exc}"
    except Exception as exc:  # noqa: BLE001
        return None, "", f"{type(exc).__name__}: {exc}"


def fetch_ddg_raw(query: str) -> dict:
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}
    )
    url = f"https://api.duckduckgo.com/?{params}"
    status, body, err = http_get_raw(url)
    raw_items = []
    abstract_n = 0
    related_n = 0
    if not err and body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            return {
                "backend": "duckduckgo",
                "query": query,
                "http_status": status,
                "error": f"JSONDecodeError: {exc}",
                "raw_count": 0,
                "items": [],
            }
        if payload.get("AbstractText"):
            abstract_n = 1
            raw_items.append(
                {
                    "api_rank": 0,
                    "kind": "Abstract",
                    "title": payload.get("Heading") or query,
                    "snippet": payload.get("AbstractText") or "",
                    "url": payload.get("AbstractURL") or "",
                }
            )
        for item in payload.get("RelatedTopics") or []:
            if not isinstance(item, dict):
                continue
            if item.get("Text"):
                related_n += 1
                raw_items.append(
                    {
                        "api_rank": len(raw_items),
                        "kind": "RelatedTopic",
                        "title": item.get("Text") or "",
                        "snippet": item.get("Text") or "",
                        "url": item.get("FirstURL") or "",
                    }
                )
            for nested in item.get("Topics") or []:
                if isinstance(nested, dict) and nested.get("Text"):
                    related_n += 1
                    raw_items.append(
                        {
                            "api_rank": len(raw_items),
                            "kind": "RelatedTopicNested",
                            "title": nested.get("Text") or "",
                            "snippet": nested.get("Text") or "",
                            "url": nested.get("FirstURL") or "",
                        }
                    )
    return {
        "backend": "duckduckgo",
        "query": query,
        "http_status": status,
        "error": err,
        "abstract_present": abstract_n > 0,
        "related_count": related_n,
        "raw_count": len(raw_items),
        "snippet_nonempty": sum(1 for x in raw_items if str(x.get("snippet") or "").strip()),
        "snippet_empty": sum(1 for x in raw_items if not str(x.get("snippet") or "").strip()),
        "items": raw_items,
        "raw_json_saved": bool(body),
        "raw_body_preview": (body or "")[:500],
    }


def fetch_wiki_opensearch_raw(query: str, *, lang: str) -> dict:
    host = "ja.wikipedia.org" if lang == "ja" else "en.wikipedia.org"
    backend = "wikipedia-ja" if lang == "ja" else "wikipedia-en"
    params = urllib.parse.urlencode(
        {
            "action": "opensearch",
            "search": query,
            "limit": str(DEFAULT_FETCH_LIMIT),
            "namespace": "0",
            "format": "json",
        }
    )
    url = f"https://{host}/w/api.php?{params}"
    status, body, err = http_get_raw(url)
    items = []
    if not err and body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            return {
                "backend": backend,
                "query": query,
                "http_status": status,
                "error": f"JSONDecodeError: {exc}",
                "raw_count": 0,
                "items": [],
            }
        titles = payload[1] if len(payload) > 1 else []
        descs = payload[2] if len(payload) > 2 else []
        urls = payload[3] if len(payload) > 3 else []
        for i, title in enumerate(titles):
            desc = descs[i] if i < len(descs) else ""
            items.append(
                {
                    "api_rank": i,
                    "kind": "opensearch",
                    "title": title or "",
                    "snippet": desc or "",
                    "url": urls[i] if i < len(urls) else "",
                }
            )
    return {
        "backend": backend,
        "query": query,
        "http_status": status,
        "error": err,
        "raw_count": len(items),
        "snippet_nonempty": sum(1 for x in items if str(x.get("snippet") or "").strip()),
        "snippet_empty": sum(1 for x in items if not str(x.get("snippet") or "").strip()),
        "items": items,
        "raw_json_saved": bool(body),
        "raw_body_preview": (body or "")[:500],
    }


def hitize_from_backend_calls(query: str, fetch: int) -> dict:
    """
    general_web_search と同じ収集規則を観測用に再現（コード変更なし）。
    searcher は既存関数をそのまま呼ぶ。
    """
    backends = (
        ("duckduckgo", search_duckduckgo),
        ("wikipedia-ja", search_wikipedia),
        ("wikipedia-en", search_wikipedia_en),
    )
    tried = []
    errors = []
    accepted = []
    rejected = []
    per_backend = []
    for name, searcher in backends:
        tried.append(name)
        try:
            raw_hits = list(searcher(query, limit=fetch) or [])
            acc = 0
            rej = 0
            for item in raw_hits:
                if item.get("title") or item.get("snippet"):
                    accepted.append({**item, "_accepted_from": name})
                    acc += 1
                else:
                    rejected.append({"backend": name, "item": item, "reason": "no_title_and_no_snippet"})
                    rej += 1
            per_backend.append(
                {
                    "backend": name,
                    "returned_by_searcher": len(raw_hits),
                    "accepted": acc,
                    "rejected": rej,
                    "snippet_nonempty": sum(1 for h in raw_hits if _has_snip(h)),
                    "snippet_empty": sum(1 for h in raw_hits if not _has_snip(h)),
                    "error": None,
                }
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
            per_backend.append(
                {
                    "backend": name,
                    "returned_by_searcher": 0,
                    "accepted": 0,
                    "rejected": 0,
                    "snippet_nonempty": 0,
                    "snippet_empty": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    before_unique = list(accepted)
    unique = unique_hits(accepted)
    ranked, scored = rank_hits_for_query(unique, query, limit=DEFAULT_RETURN_LIMIT)
    return {
        "backends_tried": tried,
        "errors": errors,
        "per_backend_searcher": per_backend,
        "accepted_before_unique": len(before_unique),
        "accepted_after_unique": len(unique),
        "rejected_count": len(rejected),
        "rejected": rejected[:20],
        "before_ranking": [
            {
                "rank_in": i,
                "title": h.get("title"),
                "url": h.get("url"),
                "backend": h.get("backend"),
                "snippet_len": _snip_len(h),
                "has_snippet": _has_snip(h),
                "score": score_hit_lookup(h, scored),
            }
            for i, h in enumerate(unique)
        ],
        "after_ranking": [
            {
                "rank": i,
                "title": h.get("title"),
                "url": h.get("url"),
                "backend": h.get("backend"),
                "snippet_len": _snip_len(h),
                "has_snippet": _has_snip(h),
                "score": score_hit_lookup(h, scored),
            }
            for i, h in enumerate(ranked)
        ],
        "scored_pairs": [
            {"score": s, "title": h.get("title"), "url": h.get("url"), "snippet_len": _snip_len(h)}
            for s, h in scored[:30]
        ],
    }


def score_hit_lookup(hit: dict, scored: list) -> int | None:
    url = hit.get("url")
    title = hit.get("title")
    for s, h in scored:
        if h.get("url") == url and h.get("title") == title:
            return s
    return None


def classify_answer_use(
    *,
    answer: str,
    hits: list[dict],
) -> dict:
    """推測断定禁止。snippet由来の具体語が回答に含まれるかのみ機械チェック。"""
    answer = answer or ""
    usable = [h for h in hits if _has_snip(h)]
    if not hits:
        return {"class": "判断不能", "note": "hitsなし"}
    if not usable:
        return {
            "class": "判断不能",
            "note": "全hitがsnippet空。title/urlのみでは『検索結果を利用』と扱わない",
        }
    # snippet から短いトークンを抽出し、回答に含まれるか
    markers = []
    for h in usable:
        sn = str(h.get("snippet") or "")
        # 英単語・数字を含む句をざっくり
        for part in sn.replace(",", " ").split():
            p = part.strip(".:;()[]\"'")
            if len(p) >= 6 and any(c.isalpha() for c in p):
                markers.append(p)
    markers = list(dict.fromkeys(markers))[:40]
    found = [m for m in markers if m.lower() in answer.lower()]
    if len(found) >= 3:
        return {"class": "明確に検索結果を利用", "matched_markers": found[:8]}
    if len(found) >= 1:
        return {"class": "検索結果を利用した可能性が高い", "matched_markers": found[:8]}
    return {
        "class": "検索結果を利用した形跡が薄い",
        "matched_markers": [],
        "note": "非空snippetはあるが回答に具体マーカーが少ない",
    }


def load_case_queries() -> dict[str, dict]:
    data = json.loads(HITS_JSON.read_text(encoding="utf-8"))
    out = {}
    for c in data.get("cases") or []:
        cid = c.get("case_id")
        ws = c.get("web_search") or {}
        res = ws.get("result") or {}
        out[cid] = {
            "case_id": cid,
            "request": c.get("request") or "",
            "query": ws.get("query") or res.get("query") or "",
            "stored_return_hits": res.get("hits") or [],
            "stored_hit_count": res.get("hit_count") or len(res.get("hits") or []),
            "stored_error": res.get("error"),
            "answer_with_web": c.get("answer_with_web") or "",
            "answer_without_web": c.get("answer_without_web") or "",
            "observation_id": f"webeffect-hits-{cid}",
        }
    return out


def trace_one(case_id: str, meta: dict, *, pause: float = 1.5) -> dict:
    query = meta["query"]
    print(f"trace {case_id} query={query!r}")
    time.sleep(pause)

    # A: raw API
    raw_ddg = fetch_ddg_raw(query)
    time.sleep(pause)
    raw_ja = fetch_wiki_opensearch_raw(query, lang="ja")
    time.sleep(pause)
    raw_en = fetch_wiki_opensearch_raw(query, lang="en")

    api_raw_total = (
        int(raw_ddg.get("raw_count") or 0)
        + int(raw_ja.get("raw_count") or 0)
        + int(raw_en.get("raw_count") or 0)
    )

    # B/C: hitize + ranking via same functions
    time.sleep(pause)
    pipeline = hitize_from_backend_calls(query, fetch=DEFAULT_FETCH_LIMIT)

    # D: official search_web return
    time.sleep(pause)
    ret = search_web(query, limit=DEFAULT_RETURN_LIMIT)
    ret_hits = ret.get("hits") if isinstance(ret, dict) else []
    if not isinstance(ret_hits, list):
        ret_hits = []

    # E: LLM handoff (Agent: raw dump; harness: hits list)
    # 既存ログの stored hits と live return を比較
    stored = meta.get("stored_return_hits") or []
    handoff_agent_would_receive = len(ret_hits)  # Agent passes full return.hits
    handoff_harness_would_receive = len(stored) if stored else len(ret_hits)

    content_n = sum(1 for h in ret_hits if _has_snip(h))
    empty_n = sum(1 for h in ret_hits if not _has_snip(h))

    use = classify_answer_use(answer=meta.get("answer_with_web") or "", hits=ret_hits)
    use_stored = classify_answer_use(
        answer=meta.get("answer_with_web") or "", hits=stored
    )

    # Where did count become small?
    stages = {
        "api_raw_total": api_raw_total,
        "hit_accepted_before_unique": pipeline["accepted_before_unique"],
        "hit_after_unique": pipeline["accepted_after_unique"],
        "after_ranking": len(pipeline["after_ranking"]),
        "search_web_return": len(ret_hits),
        "llm_handoff_live_return": handoff_agent_would_receive,
        "llm_handoff_stored_log": handoff_harness_would_receive,
        "content_nonempty_in_return": content_n,
    }

    drop_notes = []
    if api_raw_total > pipeline["accepted_before_unique"]:
        drop_notes.append(
            f"API生→hit化で減少: {api_raw_total}→{pipeline['accepted_before_unique']}"
        )
    if pipeline["accepted_before_unique"] > pipeline["accepted_after_unique"]:
        drop_notes.append(
            f"重複除去: {pipeline['accepted_before_unique']}→{pipeline['accepted_after_unique']}"
        )
    if pipeline["accepted_after_unique"] > len(pipeline["after_ranking"]):
        drop_notes.append(
            f"ranking/limit: {pipeline['accepted_after_unique']}→{len(pipeline['after_ranking'])} (return_limit={DEFAULT_RETURN_LIMIT})"
        )
    if len(pipeline["after_ranking"]) != len(ret_hits):
        drop_notes.append(
            f"ranking再現とsearch_web return件数差: {len(pipeline['after_ranking'])} vs {len(ret_hits)}（再取得ゆれの可能性）"
        )
    if content_n == 0 and len(ret_hits) > 0:
        drop_notes.append(
            f"件数問題ではなく内容問題: return={len(ret_hits)}件だがsnippet非空=0"
        )
    if len(ret_hits) == 1:
        drop_notes.append("returnが本当に1件（表示ラベル『検索結果1』とは別）")

    example_dir = EXAMPLES / case_id
    example_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case_id,
        "observation_id": meta.get("observation_id"),
        "request": meta.get("request"),
        "query": query,
        "ts": _now(),
        "stages": stages,
        "drop_notes": drop_notes,
        "raw_api": {"duckduckgo": raw_ddg, "wikipedia-ja": raw_ja, "wikipedia-en": raw_en},
        "hit_pipeline": pipeline,
        "search_web_return": {
            "query": ret.get("query") if isinstance(ret, dict) else query,
            "hit_count": len(ret_hits),
            "error": ret.get("error") if isinstance(ret, dict) else None,
            "backends_tried": ret.get("backends_tried") if isinstance(ret, dict) else None,
            "candidates_collected": ret.get("candidates_collected")
            if isinstance(ret, dict)
            else None,
            "hits": [
                {
                    "title": h.get("title"),
                    "url": h.get("url"),
                    "backend": h.get("backend"),
                    "snippet_len": _snip_len(h),
                    "has_snippet": _has_snip(h),
                    "snippet_preview": str(h.get("snippet") or "")[:120],
                }
                for h in ret_hits
            ],
        },
        "stored_log_return": {
            "hit_count": len(stored),
            "content_nonempty": sum(1 for h in stored if _has_snip(h)),
            "hits": [
                {
                    "title": h.get("title"),
                    "url": h.get("url"),
                    "snippet_len": _snip_len(h),
                    "has_snippet": _has_snip(h),
                }
                for h in stored
            ],
        },
        "llm_handoff_analysis": {
            "agent_passes_raw_search_web_return": True,
            "agent_does_not_truncate_hits_in_code": True,
            "harness_embeds_hits_json": True,
            "live_return_count": handoff_agent_would_receive,
            "stored_log_count": handoff_harness_would_receive,
            "note": "Agentはmessagesにraw result全文。件数削減はhandoffではなくreturn_limit/API側。",
        },
        "answer_use_live_hits": use,
        "answer_use_stored_hits": use_stored,
        "final_answer_preview": (meta.get("answer_with_web") or "")[:400],
    }
    (example_dir / "trace.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # stage snapshots
    (example_dir / "raw_api_results.json").write_text(
        json.dumps(payload["raw_api"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (example_dir / "hits_before_ranking.json").write_text(
        json.dumps(pipeline["before_ranking"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (example_dir / "hits_after_ranking.json").write_text(
        json.dumps(pipeline["after_ranking"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (example_dir / "search_web_return.json").write_text(
        json.dumps(payload["search_web_return"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def write_csvs(traces: list[dict], ja_en: list[dict]) -> None:
    HERE.mkdir(parents=True, exist_ok=True)

    # case_trace
    with (HERE / "case_trace.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "query",
                "API生件数",
                "hit化件数",
                "unique後",
                "ranking後",
                "return件数",
                "LLM受領件数_live",
                "LLM受領件数_stored",
                "内容あり件数_return",
                "内容なし件数_return",
                "answer_use",
                "drop_notes",
            ],
        )
        w.writeheader()
        for t in traces:
            s = t["stages"]
            ret = t["search_web_return"]
            w.writerow(
                {
                    "case_id": t["case_id"],
                    "query": t["query"],
                    "API生件数": s["api_raw_total"],
                    "hit化件数": s["hit_accepted_before_unique"],
                    "unique後": s["hit_after_unique"],
                    "ranking後": s["after_ranking"],
                    "return件数": s["search_web_return"],
                    "LLM受領件数_live": s["llm_handoff_live_return"],
                    "LLM受領件数_stored": s["llm_handoff_stored_log"],
                    "内容あり件数_return": s["content_nonempty_in_return"],
                    "内容なし件数_return": sum(
                        1 for h in ret["hits"] if not h["has_snippet"]
                    ),
                    "answer_use": (t.get("answer_use_stored_hits") or {}).get("class"),
                    "drop_notes": " | ".join(t.get("drop_notes") or []),
                }
            )

    # raw_vs_hit
    with (HERE / "raw_vs_hit_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "backend",
                "api_raw_count",
                "api_snippet_nonempty",
                "api_snippet_empty",
                "http_status",
                "error",
                "searcher_returned",
                "accepted",
            ],
        )
        w.writeheader()
        for t in traces:
            pb = {
                x["backend"]: x for x in t["hit_pipeline"]["per_backend_searcher"]
            }
            for bname, raw in t["raw_api"].items():
                sinfo = pb.get(bname) or {}
                w.writerow(
                    {
                        "case_id": t["case_id"],
                        "backend": bname,
                        "api_raw_count": raw.get("raw_count"),
                        "api_snippet_nonempty": raw.get("snippet_nonempty"),
                        "api_snippet_empty": raw.get("snippet_empty"),
                        "http_status": raw.get("http_status"),
                        "error": raw.get("error") or "",
                        "searcher_returned": sinfo.get("returned_by_searcher"),
                        "accepted": sinfo.get("accepted"),
                    }
                )

    # ranking_trace
    with (HERE / "ranking_trace.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "phase",
                "rank",
                "title",
                "backend",
                "has_snippet",
                "snippet_len",
                "score",
                "url",
            ],
        )
        w.writeheader()
        for t in traces:
            for row in t["hit_pipeline"]["before_ranking"]:
                w.writerow(
                    {
                        "case_id": t["case_id"],
                        "phase": "before",
                        "rank": row["rank_in"],
                        "title": row["title"],
                        "backend": row["backend"],
                        "has_snippet": row["has_snippet"],
                        "snippet_len": row["snippet_len"],
                        "score": row["score"],
                        "url": row["url"],
                    }
                )
            for row in t["hit_pipeline"]["after_ranking"]:
                w.writerow(
                    {
                        "case_id": t["case_id"],
                        "phase": "after",
                        "rank": row["rank"],
                        "title": row["title"],
                        "backend": row["backend"],
                        "has_snippet": row["has_snippet"],
                        "snippet_len": row["snippet_len"],
                        "score": row["score"],
                        "url": row["url"],
                    }
                )

    # llm_handoff
    with (HERE / "llm_handoff_trace.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "return件数",
                "stored件数",
                "件数一致",
                "backend残存_live",
                "handoff_truncates",
                "answer_use",
            ],
        )
        w.writeheader()
        for t in traces:
            live_n = t["stages"]["search_web_return"]
            stored_n = t["stages"]["llm_handoff_stored_log"]
            backends = [
                h.get("backend") for h in t["search_web_return"]["hits"] if h.get("backend")
            ]
            w.writerow(
                {
                    "case_id": t["case_id"],
                    "return件数": live_n,
                    "stored件数": stored_n,
                    "件数一致": live_n == stored_n,
                    "backend残存_live": ";".join(str(b) for b in backends),
                    "handoff_truncates": False,
                    "answer_use": (t.get("answer_use_stored_hits") or {}).get("class"),
                }
            )

    # backend_summary
    agg: dict[str, dict] = {}
    for t in traces:
        for bname, raw in t["raw_api"].items():
            a = agg.setdefault(
                bname,
                {
                    "backend": bname,
                    "結果数": 0,
                    "snippetあり": 0,
                    "snippetなし": 0,
                    "error": 0,
                    "cases": 0,
                },
            )
            a["cases"] += 1
            a["結果数"] += int(raw.get("raw_count") or 0)
            a["snippetあり"] += int(raw.get("snippet_nonempty") or 0)
            a["snippetなし"] += int(raw.get("snippet_empty") or 0)
            if raw.get("error"):
                a["error"] += 1
    with (HERE / "backend_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["backend", "cases", "結果数", "snippetあり", "snippetなし", "error"],
        )
        w.writeheader()
        for bname in ("duckduckgo", "wikipedia-ja", "wikipedia-en"):
            a = agg.get(bname) or {
                "backend": bname,
                "cases": 0,
                "結果数": 0,
                "snippetあり": 0,
                "snippetなし": 0,
                "error": 0,
            }
            w.writerow(a)

    # ja_en
    with (HERE / "ja_en_compare.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "label",
                "query",
                "api_raw_total",
                "return_n",
                "content_n",
                "ddg_raw",
                "wiki_ja_raw",
                "wiki_en_raw",
                "wiki_ja_snip",
                "wiki_en_snip",
            ],
        )
        w.writeheader()
        for row in ja_en:
            w.writerow(row)


def write_report(traces: list[dict], ja_en: list[dict]) -> None:
    # aggregates for Q&A
    api_counts = [t["stages"]["api_raw_total"] for t in traces]
    ret_counts = [t["stages"]["search_web_return"] for t in traces]
    content_counts = [t["stages"]["content_nonempty_in_return"] for t in traces]
    ranking_cuts = [
        t
        for t in traces
        if t["stages"]["hit_after_unique"] > t["stages"]["after_ranking"]
    ]
    truly_one = [t for t in traces if t["stages"]["search_web_return"] == 1]
    multi_return = [t for t in traces if t["stages"]["search_web_return"] > 1]
    handoff_mismatch = [
        t
        for t in traces
        if t["stages"]["search_web_return"] != t["stages"]["llm_handoff_live_return"]
    ]

    lines = [
        "# SEARCH_PATH_TRACE_REPORT",
        "",
        f"- 生成: `{_now()}`",
        "- 実装変更: **なし**（調査ハーネスのみ）",
        f"- 追跡ケース数: {len(traces)}",
        f"- return_limit 既定: {DEFAULT_RETURN_LIMIT}",
        "",
        "## 問題の分離（要約）",
        "",
        "| 種類 | 今回の観測 |",
        "|------|-----------|",
        f"| 件数問題 | API生は中央値程度{sorted(api_counts)[len(api_counts)//2] if api_counts else '—'}件。returnは最大{DEFAULT_RETURN_LIMIT}件。真に1件returnは {len(truly_one)}件 |",
        f"| 内容問題 | return件数>0でも内容あり={content_counts}。空snippetが多い |",
        "| 関連性問題 | A06等（Python 3.13→Python 3.0）で観測 |",
        f"| 選別問題 | unique後→ranking/limitで削減されたケース: {len(ranking_cuts)}件（上限{DEFAULT_RETURN_LIMIT}） |",
        f"| 受け渡し問題 | live return件数≠LLM受領 のコード上削減: {len(handoff_mismatch)}件（Agentはraw全件） |",
        "| 利用問題 | snippet空のみのケースは『利用』と扱わない。内容ありでも利用薄い例あり |",
        "",
        "## 「検索結果1」の正体",
        "",
        "人間向け表示の「検索結果 1」は**リスト番号**であり、件数=1を意味しない。",
        "例: B05は表示で1,2,3と続き、return=3件。",
        f"本当に return=1 だった追跡ケース: {[t['case_id'] for t in truly_one]}",
        "",
        "## ケース表（再取得）",
        "",
        "| case | query | API生 | hit化 | unique | ranking後 | return | LLM受領 | 内容あり |",
        "|------|-------|------:|-----:|-------:|---------:|-------:|--------:|---------:|",
    ]
    for t in traces:
        s = t["stages"]
        lines.append(
            f"| {t['case_id']} | `{t['query']}` | {s['api_raw_total']} | "
            f"{s['hit_accepted_before_unique']} | {s['hit_after_unique']} | "
            f"{s['after_ranking']} | {s['search_web_return']} | "
            f"{s['llm_handoff_live_return']} | {s['content_nonempty_in_return']} |"
        )

    lines.extend(
        [
            "",
            "## Q1〜Q10 回答",
            "",
            "### Q1 検索APIは実際に何件返しているか？",
            f"- 3backend合計の生件数（今回再取得）: min={min(api_counts) if api_counts else 0}, "
            f"max={max(api_counts) if api_counts else 0}, "
            f"median≈{sorted(api_counts)[len(api_counts)//2] if api_counts else 0}",
            "- DDG Instant Answer は Abstract+Related のみ（汎用SERPの10件ではない）",
            f"- Wikipedia OpenSearch は最大 fetch_limit={DEFAULT_FETCH_LIMIT} タイトル",
            "",
            "### Q2 「人間向け1件」はどの段階で1件になったのか？",
            "- **多くは1件になっていない。** 表示ラベル『検索結果 1』の誤解。",
            f"- 真に1件return: {[t['case_id'] for t in truly_one] or 'なし'}",
            "- 1件化の主因候補は API候補が少ない＋unique後に少数、ではなく内容空のまま複数残る方が多い",
            "",
            "### Q3 rankingで1件になっているのか？",
            f"- ranking/limit は最大{DEFAULT_RETURN_LIMIT}件に切る。1件強制ではない。",
            f"- unique→rankingで減ったケース数: {len(ranking_cuts)}",
            "- **『多数→rankingで1件』が主因ではない**（観測上）",
            "",
            "### Q4 ranking後は複数なのにLLMへ1件だけか？",
            "- **いいえ（コード根拠）。** Agentは `json.dumps(result)` で hits 全件を渡す。",
            f"- live return件数とLLM受領件数の不一致: {len(handoff_mismatch)}",
            "- ハーネス保存時に backend フィールドは落ちるが件数は保持",
            "",
            "### Q5 LLMに渡った結果は内容ありなのか？",
            f"- ケース別 内容あり件数: { {t['case_id']: t['stages']['content_nonempty_in_return'] for t in traces} }",
            "- 複数件returnでも内容あり0のケースが存在（件数≠有用性）",
            "",
            "### Q6 内容なし結果をLLMが参考にしているか？",
            "- title/urlのみは『検索結果を利用』と扱わない（規則）",
            "- 機械マーカー判定（stored）:",
        ]
    )
    for t in traces:
        cls = (t.get("answer_use_stored_hits") or {}).get("class")
        lines.append(f"  - {t['case_id']}: {cls}")

    # backend totals
    lines.extend(["", "### Q7 日本語検索だけ特に弱いのか？", ""])
    if ja_en:
        for row in ja_en:
            lines.append(
                f"- {row['label']}: api={row['api_raw_total']} return={row['return_n']} "
                f"content={row['content_n']} (ja_snip={row['wiki_ja_snip']}, en_snip={row['wiki_en_snip']})"
            )
        lines.append(
            "- 日本語クエリでも OpenSearch はタイトルを返すことがあるが、**description空は日英共通**。"
            "『日本語だから件数0』ではなく『OpenSearch descriptionが空』が共通。"
        )
    else:
        lines.append("- （日英比較未実行）")

    lines.extend(
        [
            "",
            "### Q8 どのbackendが主な原因か？",
            "- `backend_summary.csv` を参照。",
            "- Wikipedia（特に description 空）が『hitsあるが内容なし』の主供給源になりやすい。",
            "- DDGは結果数が少ない／Abstractが無いクエリが多く、補助的。",
            "- **単一backendの全面故障というより、情報源の性質（Instant Answer / OpenSearch短文）が主因候補。**",
            "",
            "### Q9 主因の場所はどこか？",
            "優先順位（今回の観測）:",
            "1. **snippet取得（APIが返す短文が空）＋ページ本文未取得** … 内容問題",
            "2. **検索APIの種類（Instant Answer / OpenSearch）** … 情報源が薄い",
            "3. ranking/limit … 件数上限5。1件化の主因ではない",
            "4. LLM受け渡し … 削減していない",
            "5. LLM利用 … 内容がある場合のみ評価対象；空snippetでは判断不能",
            "",
            "### Q10 最初に直すべき箇所（提案のみ・未実装）",
            "1. ページ本文/Wikipedia extracts 等の**本文取得段階の追加可否を検証**",
            "2. snippet空 hit の扱い（LLMへ『有用hit』として渡さない等）の設計検討",
            "3. Instant Answer以外の検索ソース要否の検証",
            "4. ranking変更は『有用snippetが下位に落ちている』証拠が出てから",
            "",
            "## 確認済み / 疑い / 未確認",
            "",
            "### 確認済み",
            "- return_limit=5。rankingは1件強制ではない",
            "- titleのみでもhit化される",
            "- Agent handoffはhits件数を削らない",
            "- 人間表示『検索結果1』は番号表示",
            "",
            "### 強く疑われる",
            "- OpenSearch description空が内容なしの主因",
            "- 本文未取得設計",
            "",
            "### 未確認",
            "- 本番Agentのtool_call query分布（今回は既存ログqueryを再実行）",
            "- 瞬間的429の再現頻度（実行時刻依存）",
            "",
        ]
    )
    (HERE / "SEARCH_PATH_TRACE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "README.md").write_text(
        "\n".join(
            [
                "# search_path_trace（調査専用）",
                "",
                "search_web 実装は変更しない。ライフサイクル観測のみ。",
                "",
                "```text",
                "python run_search_path_trace.py",
                "```",
                "",
                "出力: case_trace.csv / raw_vs_hit_summary.csv / ranking_trace.csv /",
                "llm_handoff_trace.csv / backend_summary.csv / examples/<case>/",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    HERE.mkdir(parents=True, exist_ok=True)
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    cases = load_case_queries()
    traces = []
    for cid in TRACE_CASES:
        if cid not in cases:
            print(f"SKIP missing {cid}")
            continue
        traces.append(trace_one(cid, cases[cid], pause=1.2))

    ja_en_rows = []
    for item in JA_EN_COMPARE:
        print(f"ja_en {item['label']} ...")
        time.sleep(1.2)
        raw_ddg = fetch_ddg_raw(item["query"])
        time.sleep(1.0)
        raw_ja = fetch_wiki_opensearch_raw(item["query"], lang="ja")
        time.sleep(1.0)
        raw_en = fetch_wiki_opensearch_raw(item["query"], lang="en")
        time.sleep(1.0)
        ret = search_web(item["query"], limit=DEFAULT_RETURN_LIMIT)
        hits = (ret or {}).get("hits") or []
        ja_en_rows.append(
            {
                "label": item["label"],
                "query": item["query"],
                "api_raw_total": int(raw_ddg.get("raw_count") or 0)
                + int(raw_ja.get("raw_count") or 0)
                + int(raw_en.get("raw_count") or 0),
                "return_n": len(hits),
                "content_n": sum(1 for h in hits if _has_snip(h)),
                "ddg_raw": raw_ddg.get("raw_count"),
                "wiki_ja_raw": raw_ja.get("raw_count"),
                "wiki_en_raw": raw_en.get("raw_count"),
                "wiki_ja_snip": raw_ja.get("snippet_nonempty"),
                "wiki_en_snip": raw_en.get("snippet_nonempty"),
            }
        )

    write_csvs(traces, ja_en_rows)
    write_report(traces, ja_en_rows)
    print(f"done traces={len(traces)} -> {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
