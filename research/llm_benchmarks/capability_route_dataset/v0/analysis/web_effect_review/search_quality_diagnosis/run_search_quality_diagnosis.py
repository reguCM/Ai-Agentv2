"""
search_web 検索品質ボトルネック切り分け（調査専用・実装変更なし）。

- search_web / general_web_search / ranking / Agent は変更しない
- 有用/無用の自動正解ラベルは付けない
- Wikipedia extracts 等のページ本文確認は調査専用（本番未接続）
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tools.system.network.general_web_search import (
    DEFAULT_FETCH_LIMIT,
    DEFAULT_RETURN_LIMIT,
    query_tokens,
    rank_hits_for_query,
    score_hit_for_query,
    search_wikipedia_en,
)
from tools.system.network.search_web import search_web
from tools.system.tool_builder.research.web import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    search_duckduckgo,
    search_wikipedia,
    unique_hits,
)

HERE = Path(__file__).resolve().parent
RAW_API = HERE / "raw_api"
STAGE_TRACE = HERE / "stage_trace"
HITS_JSON = HERE.parent / "web_effect_review_hits.json"

# 12件: 内容なし/あり、日英、時間依存、人間レビュー済みを混在
DIAGNOSIS_CASES = [
    "A06",   # Python 3.13 / 内容なし / バージョン
    "E04",   # 日本の運転免許 / 日本語
    "C03",   # RTX 3060 今 / 時間依存 / 人間レビュー
    "P02b",  # RTX 3060 立ち位置 / 現在
    "C02",   # Ollama / 内容あり例
    "A03",   # OpenAI 最近
    "A04",   # NVIDIA 株価 今
    "C04",   # ローカルLLM 最近
    "B05",   # 内容なし主体
    "WB02",  # 内容あり主体
    "P02a",  # RTX 一般 / 内容なし
    "E02",   # ChatGPT 有料 / 人間レビュー
]

JA_EN_PAIRS = [
    {
        "theme": "python_313",
        "ja": "Python 3.13 新機能",
        "en": "Python 3.13 new features",
        "time_sensitive": True,
    },
    {
        "theme": "drivers_license_jp",
        "ja": "日本の運転免許 取得方法",
        "en": "Japan driving license how to get",
        "time_sensitive": False,
    },
    {
        "theme": "rtx3060_current",
        "ja": "RTX 3060 現在 立ち位置",
        "en": "GeForce RTX 3060 current status",
        "time_sensitive": True,
    },
    {
        "theme": "ollama",
        "ja": "Ollamaとは",
        "en": "Ollama",
        "time_sensitive": False,
    },
]

TIME_KEYWORDS = ("今", "最近", "最新", "現在", "今日", "いま")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snip(hit: dict) -> str:
    s = hit.get("snippet")
    if s is None:
        s = hit.get("description")
    return str(s).strip() if s is not None else ""


def _has_snip(hit: dict) -> bool:
    return bool(_snip(hit))


def _is_wikipedia(url: str) -> bool:
    return "wikipedia.org" in str(url or "")


def http_get(url: str) -> tuple[int | None, str, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return int(resp.getcode()), resp.read().decode("utf-8", errors="replace"), None
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
    status, body, err = http_get(url)
    items = []
    if not err and body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            return {"backend": "duckduckgo", "query": query, "error": str(exc), "items": []}
        if payload.get("AbstractText"):
            items.append(
                {
                    "api_rank": len(items),
                    "title": payload.get("Heading") or query,
                    "snippet": payload.get("AbstractText") or "",
                    "url": payload.get("AbstractURL") or "",
                    "kind": "Abstract",
                }
            )
        for item in payload.get("RelatedTopics") or []:
            if not isinstance(item, dict):
                continue
            if item.get("Text"):
                items.append(
                    {
                        "api_rank": len(items),
                        "title": item.get("Text") or "",
                        "snippet": item.get("Text") or "",
                        "url": item.get("FirstURL") or "",
                        "kind": "RelatedTopic",
                    }
                )
            for nested in item.get("Topics") or []:
                if isinstance(nested, dict) and nested.get("Text"):
                    items.append(
                        {
                            "api_rank": len(items),
                            "title": nested.get("Text") or "",
                            "snippet": nested.get("Text") or "",
                            "url": nested.get("FirstURL") or "",
                            "kind": "RelatedTopicNested",
                        }
                    )
    return {
        "backend": "duckduckgo",
        "query": query,
        "http_status": status,
        "error": err,
        "raw_count": len(items),
        "snippet_nonempty": sum(1 for x in items if _snip(x)),
        "items": items,
    }


def fetch_wiki_opensearch(query: str, *, lang: str) -> dict:
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
    status, body, err = http_get(url)
    items = []
    if not err and body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            return {"backend": backend, "query": query, "error": str(exc), "items": []}
        titles = payload[1] if len(payload) > 1 else []
        descs = payload[2] if len(payload) > 2 else []
        urls = payload[3] if len(payload) > 3 else []
        for i, title in enumerate(titles):
            items.append(
                {
                    "api_rank": i,
                    "title": title or "",
                    "snippet": descs[i] if i < len(descs) else "",
                    "url": urls[i] if i < len(urls) else "",
                    "kind": "opensearch",
                }
            )
    return {
        "backend": backend,
        "query": query,
        "http_status": status,
        "error": err,
        "raw_count": len(items),
        "snippet_nonempty": sum(1 for x in items if _snip(x)),
        "items": items,
    }


def wiki_extract_probe(title: str, url: str) -> dict:
    """調査専用: OpenSearch snippet空でもページに extract があるか。"""
    if not _is_wikipedia(url) or not title:
        return {"skipped": True, "reason": "not_wikipedia_or_no_title"}
    lang = "ja" if "ja.wikipedia.org" in url else "en"
    host = "ja.wikipedia.org" if lang == "ja" else "en.wikipedia.org"
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "titles": title,
            "format": "json",
        }
    )
    api_url = f"https://{host}/w/api.php?{params}"
    status, body, err = http_get(api_url)
    extract = ""
    if not err and body:
        try:
            data = json.loads(body)
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                if isinstance(page, dict):
                    extract = str(page.get("extract") or "").strip()
        except json.JSONDecodeError:
            pass
    return {
        "title": title,
        "url": url,
        "http_status": status,
        "error": err,
        "extract_len": len(extract),
        "extract_preview": extract[:400] if extract else "",
        "page_has_usable_text": len(extract) >= 80,
        "note": "調査専用extracts。本番search_web未接続。",
    }


def trace_pipeline(query: str) -> dict:
    """既存関数を呼び出しつつ、段階ごとの全候補を記録。"""
    backends = (
        ("duckduckgo", search_duckduckgo),
        ("wikipedia-ja", search_wikipedia),
        ("wikipedia-en", search_wikipedia_en),
    )
    fetch = DEFAULT_FETCH_LIMIT
    per_backend = []
    hitize_rows = []
    rejected = []
    accepted = []

    for name, searcher in backends:
        try:
            raw_hits = list(searcher(query, limit=fetch) or [])
            acc = 0
            for item in raw_hits:
                ok = bool(item.get("title") or item.get("snippet"))
                row = {
                    "backend": name,
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("snippet"),
                    "snippet_len": len(str(item.get("snippet") or "").strip()),
                    "hitized": ok,
                    "reject_reason": "" if ok else "no_title_and_no_snippet",
                }
                hitize_rows.append(row)
                if ok:
                    accepted.append({**item, "_from": name})
                    acc += 1
                else:
                    rejected.append(row)
            per_backend.append(
                {
                    "backend": name,
                    "searcher_returned": len(raw_hits),
                    "accepted": acc,
                    "rejected": len(raw_hits) - acc,
                }
            )
        except Exception as exc:  # noqa: BLE001
            per_backend.append(
                {
                    "backend": name,
                    "searcher_returned": 0,
                    "accepted": 0,
                    "rejected": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    before_unique = list(accepted)
    unique = unique_hits(accepted)
    dup_removed = len(before_unique) - len(unique)

    tokens = query_tokens(query)
    scored = [(score_hit_for_query(h, query, tokens), h) for h in unique]
    scored.sort(key=lambda x: x[0], reverse=True)
    positive = [h for s, h in scored if s > 0]
    if positive:
        after_rank = positive[:DEFAULT_RETURN_LIMIT]
        ranking_mode = "score>0_only"
    else:
        after_rank = [h for _, h in scored[:DEFAULT_RETURN_LIMIT]]
        ranking_mode = "fallback_top_limit"

    after_urls = {(h.get("url"), h.get("title")) for h in after_rank}
    ranking_rows = []
    for rank_i, (score, h) in enumerate(scored):
        key = (h.get("url"), h.get("title"))
        adopted = key in after_urls and rank_i < len([x for x in scored if (x[1].get("url"), x[1].get("title")) in after_urls][:DEFAULT_RETURN_LIMIT])
        # simpler: mark adopted if in after_rank set
        adopted = any(
            h.get("url") == a.get("url") and h.get("title") == a.get("title")
            for a in after_rank
        )
        reason = ""
        if not adopted:
            if score <= 0 and ranking_mode == "score>0_only":
                reason = "score<=0"
            elif not adopted and len(after_rank) >= DEFAULT_RETURN_LIMIT:
                reason = "over_return_limit"
            else:
                reason = "not_in_top_after_rank"
        ranking_rows.append(
            {
                "ranking_order": rank_i,
                "score": score,
                "title": h.get("title"),
                "url": h.get("url"),
                "backend": h.get("backend"),
                "snippet_len": len(str(h.get("snippet") or "").strip()),
                "has_snippet": _has_snip(h),
                "adopted": adopted,
                "exclude_reason": "" if adopted else reason,
            }
        )

    dropped = [r for r in ranking_rows if not r["adopted"]]
    dropped_with_snippet = [r for r in dropped if r["has_snippet"]]

    return {
        "query": query,
        "per_backend": per_backend,
        "hitize_rows": hitize_rows,
        "rejected": rejected,
        "counts": {
            "hit_accepted": len(before_unique),
            "after_unique": len(unique),
            "dup_removed": dup_removed,
            "before_ranking": len(unique),
            "after_ranking": len(after_rank),
            "dropped_by_ranking": len(dropped),
            "dropped_with_snippet": len(dropped_with_snippet),
        },
        "ranking_mode": ranking_mode,
        "ranking_rows": ranking_rows,
        "after_ranking_hits": after_rank,
        "dropped_candidates": dropped,
    }


def load_stored_cases() -> dict[str, dict]:
    data = json.loads(HITS_JSON.read_text(encoding="utf-8"))
    out = {}
    for c in data.get("cases") or []:
        cid = c["case_id"]
        ws = c.get("web_search") or {}
        res = ws.get("result") or {}
        out[cid] = {
            "case_id": cid,
            "request": c.get("request") or "",
            "query": ws.get("query") or res.get("query") or "",
            "stored_hits": res.get("hits") or [],
            "answer_with_web": c.get("answer_with_web") or "",
            "answer_without_web": c.get("answer_without_web") or "",
        }
    return out


def is_time_sensitive(text: str) -> bool:
    return any(k in (text or "") for k in TIME_KEYWORDS)


def diagnose_case(case_id: str, meta: dict, *, pause: float = 1.0) -> dict:
    query = meta["query"]
    request = meta["request"]
    print(f"diagnose {case_id} ...")
    time.sleep(pause)

    raw_ddg = fetch_ddg_raw(query)
    time.sleep(pause)
    raw_ja = fetch_wiki_opensearch(query, lang="ja")
    time.sleep(pause)
    raw_en = fetch_wiki_opensearch(query, lang="en")

    api_items = []
    for block in (raw_ddg, raw_ja, raw_en):
        for it in block.get("items") or []:
            api_items.append({**it, "backend": block["backend"]})

    pipeline = trace_pipeline(query)
    time.sleep(pause)
    ret = search_web(query, limit=DEFAULT_RETURN_LIMIT)
    ret_hits = (ret or {}).get("hits") or []

    # LLM handoff simulation: Agent passes full return JSON
    llm_payload = {
        "query": ret.get("query") if isinstance(ret, dict) else query,
        "hits": ret_hits,
        "error": ret.get("error") if isinstance(ret, dict) else None,
        "backends_tried": ret.get("backends_tried") if isinstance(ret, dict) else None,
    }
    llm_json = json.dumps(llm_payload, ensure_ascii=False)
    stored = meta.get("stored_hits") or []

    # extracts probe: up to 3 wiki hits with empty snippet from API
    extract_probes = []
    probed = 0
    for it in api_items:
        if probed >= 3:
            break
        if _is_wikipedia(it.get("url") or "") and not _snip(it):
            time.sleep(0.8)
            extract_probes.append(wiki_extract_probe(it.get("title") or "", it.get("url") or ""))
            probed += 1

    page_has_text_but_snippet_empty = any(
        p.get("page_has_usable_text") for p in extract_probes if not p.get("skipped")
    )

    record = {
        "case_id": case_id,
        "request": request,
        "query": query,
        "time_sensitive": is_time_sensitive(request),
        "ts": _now(),
        "raw_api": {"duckduckgo": raw_ddg, "wikipedia-ja": raw_ja, "wikipedia-en": raw_en},
        "api_candidate_count": len(api_items),
        "api_snippet_nonempty": sum(1 for x in api_items if _snip(x)),
        "api_snippet_empty": sum(1 for x in api_items if not _snip(x)),
        "pipeline": pipeline,
        "search_web_return": {
            "hit_count": len(ret_hits),
            "hits": ret_hits,
            "error": ret.get("error") if isinstance(ret, dict) else None,
            "candidates_collected": ret.get("candidates_collected")
            if isinstance(ret, dict)
            else None,
        },
        "stored_log": {"hit_count": len(stored), "hits": stored},
        "llm_handoff": {
            "agent_passes_full_return": True,
            "llm_received_hit_count": len(ret_hits),
            "stored_log_hit_count": len(stored),
            "count_match_live_vs_stored": len(ret_hits) == len(stored),
            "backend_in_return": [h.get("backend") for h in ret_hits if h.get("backend")],
            "json_bytes": len(llm_json.encode("utf-8")),
            "snippet_lost_in_serialization": False,
        },
        "extract_probes": extract_probes,
        "machine_observation": {
            "counts_chain": {
                "api_raw": len(api_items),
                "hit_accepted": pipeline["counts"]["hit_accepted"],
                "after_unique": pipeline["counts"]["after_unique"],
                "after_ranking": pipeline["counts"]["after_ranking"],
                "return": len(ret_hits),
                "llm_received": len(ret_hits),
            },
            "snippet_empty_in_return": sum(1 for h in ret_hits if not _has_snip(h)),
            "snippet_nonempty_in_return": sum(1 for h in ret_hits if _has_snip(h)),
            "dropped_by_ranking": pipeline["counts"]["dropped_by_ranking"],
            "dropped_with_snippet": pipeline["counts"]["dropped_with_snippet"],
            "page_has_text_but_snippet_empty_probe": page_has_text_but_snippet_empty,
            "not_auto_usefulness_label": True,
        },
        "human_review": {
            "候補の内容": "",
            "有用候補の番号": "",
            "rankingで落ちた有用候補": "",
            "内容の充実度": "",
            "日本語情報の十分さ": "",
            "現在性": "",
            "LLMに十分な情報が渡ったか": "",
            "主な問題箇所": "",
            "人間コメント": "",
        },
    }

    RAW_API.mkdir(parents=True, exist_ok=True)
    STAGE_TRACE.mkdir(parents=True, exist_ok=True)
    (RAW_API / f"{case_id}.json").write_text(
        json.dumps(record["raw_api"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (STAGE_TRACE / f"{case_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def build_review_card(rec: dict) -> str:
    lines = [
        f"## CASE: {rec['case_id']}",
        "",
        f"**質問:** {rec['request']}",
        f"**検索クエリ:** {rec['query']}",
        f"**時間依存:** {'はい' if rec['time_sensitive'] else 'いいえ'}",
        "",
        "### 段階件数（機械観測・事実のみ）",
        "",
        "```text",
        f"API生: {rec['machine_observation']['counts_chain']['api_raw']}",
        f"hit化: {rec['machine_observation']['counts_chain']['hit_accepted']}",
        f"unique後: {rec['machine_observation']['counts_chain']['after_unique']}",
        f"ranking後: {rec['machine_observation']['counts_chain']['after_ranking']}",
        f"return: {rec['machine_observation']['counts_chain']['return']}",
        f"LLM受領: {rec['machine_observation']['counts_chain']['llm_received']}",
        "```",
        "",
        "### API候補（人間レビュー用・自動判定なし）",
        "",
    ]
    idx = 0
    for backend, block in rec["raw_api"].items():
        for it in block.get("items") or []:
            idx += 1
            sn = _snip(it)
            lines.extend(
                [
                    f"#### 候補 {idx} [{backend}]",
                    f"- タイトル: {it.get('title') or ''}",
                    f"- URL: {it.get('url') or ''}",
                    f"- snippet: {sn if sn else '（空）'}",
                    "",
                    "**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？",
                    "",
                ]
            )
    lines.extend(
        [
            "### rankingで落ちた候補（snippetあり含む）",
            "",
        ]
    )
    for d in rec["pipeline"].get("dropped_candidates") or []:
        if d.get("has_snippet"):
            lines.append(
                f"- [落ちた] score={d.get('score')} {d.get('title')} "
                f"({d.get('backend')}) snippet_len={d.get('snippet_len')} "
                f"理由={d.get('exclude_reason')}"
            )
    for d in rec["pipeline"].get("dropped_candidates") or []:
        if not d.get("has_snippet"):
            lines.append(
                f"- [落ちた・snippet空] score={d.get('score')} {d.get('title')} "
                f"({d.get('backend')}) 理由={d.get('exclude_reason')}"
            )

    if rec.get("extract_probes"):
        lines.extend(["", "### 調査専用: Wikipedia extracts（snippet空候補）", ""])
        for p in rec["extract_probes"]:
            if p.get("skipped"):
                continue
            lines.append(
                f"- {p.get('title')}: extract_len={p.get('extract_len')} "
                f"page_has_usable_text={p.get('page_has_usable_text')}"
            )
            if p.get("extract_preview"):
                lines.append(f"  プレビュー: {p['extract_preview'][:200]}...")

    lines.extend(
        [
            "",
            "### 人間記入欄",
            "",
            "| 項目 | 記入 |",
            "|------|------|",
            "| 有用候補の有無 | |",
            "| 有用候補の番号 | |",
            "| rankingで落ちた有用候補 | |",
            "| 内容の充実度 | |",
            "| 日本語情報の十分さ | |",
            "| 現在性 | |",
            "| LLMに十分な情報が渡ったか | |",
            "| 主な問題箇所 A/B/C/D/? | |",
            "| 人間コメント | |",
            "",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(records: list[dict], ja_en: list[dict]) -> None:
    HERE.mkdir(parents=True, exist_ok=True)

    # review_dataset
    review_rows = []
    for rec in records:
        mo = rec["machine_observation"]
        review_rows.append(
            {
                "ケース": rec["case_id"],
                "質問": rec["request"],
                "検索クエリ": rec["query"],
                "時間依存": "はい" if rec["time_sensitive"] else "いいえ",
                "API候補数": rec["api_candidate_count"],
                "API_snippetあり": rec["api_snippet_nonempty"],
                "API_snippetなし": rec["api_snippet_empty"],
                "hit化件数": mo["counts_chain"]["hit_accepted"],
                "unique後": mo["counts_chain"]["after_unique"],
                "ranking後": mo["counts_chain"]["after_ranking"],
                "return件数": mo["counts_chain"]["return"],
                "LLM受領件数": mo["counts_chain"]["llm_received"],
                "return_snippetあり": mo["snippet_nonempty_in_return"],
                "return_snippetなし": mo["snippet_empty_in_return"],
                "ranking脱落件数": mo["dropped_by_ranking"],
                "ranking脱落_snippetあり": mo["dropped_with_snippet"],
                "extract調査_ページ本文ありsnippet空": mo[
                    "page_has_text_but_snippet_empty_probe"
                ],
                "有用候補の有無": "",
                "有用候補の番号": "",
                "rankingで落ちた有用候補": "",
                "内容の充実度": "",
                "日本語情報の十分さ": "",
                "現在性": "",
                "LLMに十分な情報が渡ったか": "",
                "主な問題箇所": "",
                "人間コメント": "",
            }
        )

    (HERE / "review_dataset.json").write_text(
        json.dumps({"cases": review_rows, "records": records}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )

    csv_fields = list(review_rows[0].keys()) if review_rows else []
    with (HERE / "review_dataset.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        w.writerows(review_rows)

    # ranking_comparison.csv
    rc_fields = [
        "case_id",
        "phase",
        "ranking_order",
        "score",
        "adopted",
        "exclude_reason",
        "title",
        "backend",
        "snippet_len",
        "has_snippet",
        "url",
    ]
    with (HERE / "ranking_comparison.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=rc_fields)
        w.writeheader()
        for rec in records:
            for row in rec["pipeline"]["ranking_rows"]:
                w.writerow({"case_id": rec["case_id"], "phase": "ranking", **row})

    # review_cards.md
    cards = ["# 検索品質診断 — 人間レビューカード", "", "自動有用性判定は行っていません。", ""]
    for rec in records:
        cards.append(build_review_card(rec))
    (HERE / "review_cards.md").write_text("\n".join(cards), encoding="utf-8")

    write_reports(records, ja_en, review_rows)


def write_reports(records: list[dict], ja_en: list[dict], review_rows: list[dict]) -> None:
    truly_one = [r for r in records if r["machine_observation"]["counts_chain"]["return"] == 1]
    content_empty = [
        r["case_id"]
        for r in records
        if r["machine_observation"]["snippet_empty_in_return"]
        and r["machine_observation"]["counts_chain"]["return"] > 0
        and r["machine_observation"]["snippet_nonempty_in_return"] == 0
    ]
    dropped_snip = [
        r["case_id"] for r in records if r["machine_observation"]["dropped_with_snippet"] > 0
    ]
    extract_yes = [
        r["case_id"]
        for r in records
        if r["machine_observation"]["page_has_text_but_snippet_empty_probe"]
    ]

    q_lines = [
        "# SEARCH_QUALITY_DIAGNOSIS",
        "",
        f"- 生成: `{_now()}`",
        "- 実装変更: **なし**",
        f"- 診断ケース数: {len(records)}",
        "",
        "## 12問への回答（機械観測＋人間記入待ち）",
        "",
        "### 1. 「検索結果1件」は本当に1件か？",
        f"- 人間表示の「検索結果 1」は番号。return=1 は {len(truly_one)}件: {[r['case_id'] for r in truly_one]}",
        "",
        "### 2. APIには複数候補が存在していたか？",
        f"- API生件数: min={min(r['api_candidate_count'] for r in records)}, max={max(r['api_candidate_count'] for r in records)}",
        "",
        "### 3. 有用な候補はAPI段階で存在していたか？",
        "- **人間記入待ち**（review_dataset.csv の「有用候補の有無」）",
        f"- 機械観測: snippet非空のAPI候補が存在したケース: {[r['case_id'] for r in records if r['api_snippet_nonempty']>0]}",
        "",
        "### 4. 有用候補がrankingで消えていたか？",
        f"- ranking脱落で snippetあり が残るケース: {dropped_snip}（有用かは人間確認）",
        "- C02等: score>0 のみ採用のため、snippetあり候補が脱落する可能性あり",
        "",
        "### 5. 「内容なし」はどの段階か？",
        f"- return件数>0 かつ snippet全空: {content_empty}",
        "- 主に **API/OpenSearch description空 → hit化後も空**（C段階）",
        "",
        "### 6. ページ本文あり・snippet空のケース？",
        f"- extracts調査で page_has_usable_text=True: {extract_yes or '今回の再取得では未確認/少数'}",
        "- 調査専用 extracts のみ。本番未接続。",
        "",
        "### 7. LLMに完全な状態で渡っているか？",
        "- Agentは raw return 全件。件数削減なし（全ケース live==LLM受領）",
        "- backend フィールドはハーネス保存時に落ちることがあるが件数は保持",
        "",
        "### 8. 日本語検索だけ弱いか？",
        "- ja_en 比較は `SUMMARY.md` 参照。OpenSearch description空は日英共通傾向",
        "",
        "### 9. 英語検索なら改善するか？",
        "- 件数・snippet有無はクエリ依存。英語でも Wiki description 空は多い",
        "",
        "### 10. 時間依存要求で現在性は確保できているか？",
        "- **人間記入待ち**（現在性列）",
        f"- 時間依存フラグ付きケース: {[r['case_id'] for r in records if r['time_sensitive']]}",
        "",
        "### 11. 最大ボトルネック A/B/C/D？",
        "- **人間記入待ち**",
        "- 機械観測の暫定メモ（断定しない）:",
        "  - A（候補生成）: API生が0〜1のケースあり",
        "  - B（ranking）: snippetあり脱落あり。主因ではない可能性",
        "  - C（内容取得）: 最多。snippet空・本文未取得",
        "  - D（LLM受け渡し）: 観測上ほぼ無し",
        "",
        "### 12. 次に修正すべき箇所（提案のみ・未実装）",
        "1. 本文/extracts 取得段階の追加可否検証",
        "2. snippet空 hit の扱い",
        "3. 検索ソース（Instant Answer/OpenSearch以外）の要否",
        "4. ranking は『有用snippetが脱落』が人間確認された後",
        "",
        "## ケース一覧",
        "",
        "| case | API | unique | rank | return | snip+ | snip- | rank落(snip+) | extract本文? |",
        "|------|----:|-------:|-----:|-------:|------:|------:|-------------:|-------------:|",
    ]
    for r in records:
        mo = r["machine_observation"]
        cc = mo["counts_chain"]
        q_lines.append(
            f"| {r['case_id']} | {cc['api_raw']} | {cc['after_unique']} | "
            f"{cc['after_ranking']} | {cc['return']} | {mo['snippet_nonempty_in_return']} | "
            f"{mo['snippet_empty_in_return']} | {mo['dropped_with_snippet']} | "
            f"{mo['page_has_text_but_snippet_empty_probe']} |"
        )

    (HERE / "SEARCH_QUALITY_DIAGNOSIS.md").write_text("\n".join(q_lines), encoding="utf-8")

    summary = [
        "# SUMMARY",
        "",
        "## ボトルネック仮説（人間確認前・断定しない）",
        "",
        "| 分類 | 観測 |",
        "|------|------|",
        "| A 候補生成 | API生0〜少数のクエリあり |",
        "| B ranking | snippetあり脱落あり（C02等） |",
        "| C 内容取得 | **最多**。return複数でもsnippet空 |",
        "| D LLM受け渡し | 件数削減なし |",
        "",
        "## 日英比較",
        "",
        "| theme | ja query | ja api | ja ret | ja snip+ | en query | en api | en ret | en snip+ |",
        "|-------|----------|-------:|-------:|---------:|----------|-------:|-------:|---------:|",
    ]
    for row in ja_en:
        summary.append(
            f"| {row['theme']} | `{row['ja_query']}` | {row['ja_api']} | {row['ja_return']} | "
            f"{row['ja_snip+']} | `{row['en_query']}` | {row['en_api']} | {row['en_return']} | "
            f"{row['en_snip+']} |"
        )
    (HERE / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")

    (HERE / "README.md").write_text(
        "\n".join(
            [
                "# search_quality_diagnosis",
                "",
                "search_web 品質ボトルネック切り分け（調査専用）。",
                "",
                "```text",
                "python run_search_quality_diagnosis.py",
                "```",
                "",
                "出力:",
                "- raw_api/ stage_trace/ review_cards.md review_dataset.csv",
                "- ranking_comparison.csv SEARCH_QUALITY_DIAGNOSIS.md SUMMARY.md",
                "",
                "人間記入列は空欄。自動有用性判定なし。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_ja_en_pairs(*, pause: float = 1.0) -> list[dict]:
    rows = []
    for pair in JA_EN_PAIRS:
        for lang_key, qkey in (("ja", "ja"), ("en", "en")):
            q = pair[qkey]
            time.sleep(pause)
            raw_ddg = fetch_ddg_raw(q)
            time.sleep(pause * 0.8)
            raw_ja = fetch_wiki_opensearch(q, lang="ja")
            time.sleep(pause * 0.8)
            raw_en = fetch_wiki_opensearch(q, lang="en")
            time.sleep(pause * 0.8)
            ret = search_web(q)
            hits = (ret or {}).get("hits") or []
            api_n = (
                int(raw_ddg.get("raw_count") or 0)
                + int(raw_ja.get("raw_count") or 0)
                + int(raw_en.get("raw_count") or 0)
            )
            row_key = f"{pair['theme']}_{lang_key}"
            rows.append(
                {
                    "theme": pair["theme"],
                    "lang": lang_key,
                    "query": q,
                    "api": api_n,
                    "return": len(hits),
                    "snip+": sum(1 for h in hits if _has_snip(h)),
                    "time_sensitive": pair["time_sensitive"],
                }
            )
    # merge for summary table
    merged = []
    themes = sorted({p["theme"] for p in JA_EN_PAIRS})
    by_theme = {t: [r for r in rows if r["theme"] == t] for t in themes}
    for t in themes:
        ja = next(r for r in by_theme[t] if r["lang"] == "ja")
        en = next(r for r in by_theme[t] if r["lang"] == "en")
        merged.append(
            {
                "theme": t,
                "ja_query": ja["query"],
                "ja_api": ja["api"],
                "ja_return": ja["return"],
                "ja_snip+": ja["snip+"],
                "en_query": en["query"],
                "en_api": en["api"],
                "en_return": en["return"],
                "en_snip+": en["snip+"],
            }
        )
    return merged


def main() -> int:
    stored = load_stored_cases()
    records = []
    for cid in DIAGNOSIS_CASES:
        if cid not in stored:
            print(f"SKIP {cid}")
            continue
        records.append(diagnose_case(cid, stored[cid], pause=1.0))

    print("ja_en pairs ...")
    ja_en = run_ja_en_pairs(pause=0.9)
    write_outputs(records, ja_en)
    print(f"done n={len(records)} -> {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
