"""
検索結果 → 人間レビュー用正規化（表示層のみ）。

- 原データ破壊禁止 / heuristic・Gate・Pipeline・Stage3/4 非接続
- 有用性の自動採点禁止
- 英語本文の日本語要約はレビュー補助のみ（原文は必ず残す）
- empty ≠ 無関係
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SRC_HITS = HERE.parent / "web_effect_review_hits.json"
SNIPPET_DISPLAY_MAX = 1200

CONTENT_AVAILABLE = "available"
CONTENT_EMPTY = "empty"
CONTENT_EXTRACTION_ERROR = "extraction_error"
CONTENT_UNKNOWN = "unknown"

CONTENT_LABEL_JA = {
    CONTENT_AVAILABLE: "内容を取得できました",
    CONTENT_EMPTY: "ページは存在しますが、内容を取得できませんでした",
    CONTENT_EXTRACTION_ERROR: "内容取得に失敗しました",
    CONTENT_UNKNOWN: "内容取得状態を確認できません",
}

# 人間記入（空欄）。自動入力禁止。
REL_TO_QUESTION = [
    "◎ 直接回答に使える",
    "○ 関係があり、参考になる",
    "△ 少し関係がある",
    "× ほぼ関係ない",
    "？ 内容が確認できず判断できない",
]
JP_READABILITY = [
    "◎ 日本語でそのまま理解できる",
    "○ 英語だが日本語要約があり理解できる",
    "△ 英語のみで読みにくい",
    "× 内容を理解できない",
    "？ 内容なし",
]
AS_MATERIAL = [
    "◎ 重要な回答材料になる",
    "○ 補助材料になる",
    "△ あまり役立たない",
    "× 役立たない",
    "？ 判断できない",
]
INFO_GAIN = [
    "◎ 明確に増えた",
    "○ 少し増えた",
    "△ ほぼ変わらない",
    "× むしろ悪化",
    "？ 判断困難",
]
WITHOUT_ENOUGH = [
    "◎ 十分",
    "○ ほぼ十分",
    "△ 不足あり",
    "× 明らかに不足",
    "？ 判断困難",
]
# 人間向け表示 / 内部値
PREFER_OPTIONS = [
    ("A_WebStrong", "◎ Webありを採用したい"),
    ("B_WebSlight", "○ Webありの方がやや良い"),
    ("C_Same", "△ どちらでもよい"),
    ("D_NoWebSlight", "○ Webなしの方がやや良い"),
    ("E_NoWebStrong", "◎ Webなしを採用したい"),
    ("X_Unknown", "？ 判断困難"),
]


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text or ""))


def detect_language(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return "unknown"
    if has_cjk(s):
        return "ja"
    # 粗い観測用
    if re.search(r"[A-Za-z]{3,}", s):
        return "en"
    return "unknown"


def site_from_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        host = urlparse(str(url)).netloc or ""
        return host[4:] if host.startswith("www.") else host
    except Exception:  # noqa: BLE001
        return ""


def clip(text: str, max_len: int = SNIPPET_DISPLAY_MAX) -> tuple[str, bool]:
    s = str(text or "").strip()
    if len(s) <= max_len:
        return s, False
    return s[:max_len].rstrip() + "…", True


def classify_content_status(hit: dict) -> str:
    if not isinstance(hit, dict):
        return CONTENT_UNKNOWN
    if hit.get("extraction_error") or hit.get("fetch_error"):
        return CONTENT_EXTRACTION_ERROR
    snippet = hit.get("snippet")
    if snippet is None:
        snippet = hit.get("description")
    if snippet is None:
        # フィールド欠落
        body = hit.get("body") or hit.get("content")
        if body is None:
            return CONTENT_EMPTY
        snippet = body
    text = str(snippet).strip()
    if not text:
        return CONTENT_EMPTY
    return CONTENT_AVAILABLE


def extract_raw_text(hit: dict) -> str:
    for key in ("snippet", "description", "body", "content"):
        val = hit.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def summarize_english_to_ja(text: str, model: str | None = None) -> str:
    """レビュー補助の日本語要約のみ。有用性判定はしない。"""
    from tools.system.config import get_llm_profile
    from tools.system.llm import chat

    profile = get_llm_profile()
    use_model = model or profile["model"]
    response = chat(
        model=use_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "次の英語テキストを、事実を増やさず日本語で短く要約してください。"
                    "有用かどうかの評価・断定・推測は書かないでください。"
                    "要約本文だけを出力してください。"
                ),
            },
            {"role": "user", "content": text[:3000]},
        ],
    )
    msg = getattr(response, "message", None)
    content = getattr(msg, "content", None) if msg is not None else None
    return ("" if content is None else str(content)).strip()


def normalize_hit(
    hit: dict,
    *,
    index: int,
    total: int,
    request: str,
    query: str,
    japanese_summary: str | None = None,
) -> dict:
    status = classify_content_status(hit if isinstance(hit, dict) else {})
    title = str((hit or {}).get("title") or "").strip() if isinstance(hit, dict) else ""
    url = str((hit or {}).get("url") or "").strip() if isinstance(hit, dict) else ""
    raw = extract_raw_text(hit) if isinstance(hit, dict) else ""
    display_raw, truncated = clip(raw)
    lang = detect_language(raw) if raw else "unknown"
    ja_summary = japanese_summary
    if status != CONTENT_AVAILABLE:
        ja_summary = None
    elif lang == "ja":
        ja_summary = None
    # en で要約未生成なら後段で埋める

    judgment_hint = ""
    if status == CONTENT_EMPTY:
        judgment_hint = (
            "内容を確認できないため、この結果だけでは有用性を判断できません。"
        )
    elif status == CONTENT_EXTRACTION_ERROR:
        judgment_hint = "内容取得に失敗したため、有用性を判断できません。"
    elif status == CONTENT_UNKNOWN:
        judgment_hint = "内容取得状態を確認できないため、判断が難しいです。"

    card_lines = [
        f"## 検索結果 {index} / {total}",
        "",
        f"**タイトル:** {title or '（なし）'}",
        f"**サイト:** {site_from_url(url) or '（なし）'}",
        f"**URL:** {url or '（なし）'}",
        f"**内容取得状態:** {CONTENT_LABEL_JA.get(status, status)}",
        "",
    ]
    if status == CONTENT_AVAILABLE and display_raw:
        card_lines.append("**原文:**")
        card_lines.append(display_raw)
        if truncated:
            card_lines.append("")
            card_lines.append("（検索結果本文は長いため省略。原データあり）")
        card_lines.append("")
        if lang != "ja" and ja_summary:
            card_lines.append("**日本語要約:**")
            card_lines.append(ja_summary)
            card_lines.append("")
        elif lang != "ja" and not ja_summary:
            card_lines.append("**日本語要約:** （未生成）")
            card_lines.append("")
    else:
        card_lines.append("**内容:**")
        card_lines.append(CONTENT_LABEL_JA.get(status, "内容を確認できませんでした。"))
        card_lines.append("")
        if judgment_hint:
            card_lines.append("**判定可能性:**")
            card_lines.append(judgment_hint)
            card_lines.append("")

    return {
        "index": index,
        "total": total,
        "title": title,
        "site": site_from_url(url),
        "url": url,
        "content_status": status,
        "content_status_label_ja": CONTENT_LABEL_JA.get(status, status),
        "result_language": lang,
        "original_text": raw,
        "original_text_display": display_raw,
        "original_truncated": truncated,
        "japanese_summary": ja_summary,
        "judgment_hint_ja": judgment_hint,
        "card_markdown": "\n".join(card_lines).rstrip(),
        "raw_hit_preserved": True,
    }


def normalize_case(
    case: dict,
    *,
    with_ja_summary: bool = True,
    model: str | None = None,
) -> dict:
    case_id = str(case.get("case_id") or "")
    observation_id = f"webeffect-hits-{case_id}"
    request = case.get("request") or ""
    ws = case.get("web_search") or {}
    res = ws.get("result") or {}
    query = ws.get("query") or res.get("query") or ""
    hits = res.get("hits") if isinstance(res.get("hits"), list) else []
    total = len(hits)

    query_lang = detect_language(query) if query else detect_language(request)
    normalized_hits = []
    for i, hit in enumerate(hits, 1):
        status = classify_content_status(hit if isinstance(hit, dict) else {})
        raw = extract_raw_text(hit) if isinstance(hit, dict) else ""
        lang = detect_language(raw) if raw else "unknown"
        ja_summary = None
        if (
            with_ja_summary
            and status == CONTENT_AVAILABLE
            and lang == "en"
            and raw.strip()
        ):
            try:
                ja_summary = summarize_english_to_ja(raw, model=model)
            except Exception as exc:  # noqa: BLE001
                ja_summary = f"（日本語要約の生成に失敗: {type(exc).__name__}）"
        normalized_hits.append(
            normalize_hit(
                hit if isinstance(hit, dict) else {},
                index=i,
                total=total,
                request=request,
                query=query,
                japanese_summary=ja_summary,
            )
        )

    ja_n = sum(1 for h in normalized_hits if h.get("result_language") == "ja")
    en_n = sum(1 for h in normalized_hits if h.get("result_language") == "en")
    available_n = sum(
        1 for h in normalized_hits if h.get("content_status") == CONTENT_AVAILABLE
    )
    empty_n = sum(1 for h in normalized_hits if h.get("content_status") == CONTENT_EMPTY)

    cards_md = [
        f"# Case {case_id}",
        "",
        f"- observation_id: `{observation_id}`",
        "",
        "## 質問",
        "",
        f"> {request}",
        "",
        "## Webなし完成回答",
        "",
        "```text",
        (case.get("answer_without_web") or "(empty)").strip() or "(empty)",
        "```",
        "",
        "## 検索クエリ",
        "",
        f"> {query}",
        "",
        f"- query_language（観測）: `{query_lang}`",
        f"- has_japanese_result: `{ja_n > 0}` / has_english_result: `{en_n > 0}`",
        f"- available={available_n} / empty={empty_n} / total={total}",
        "",
        "## 検索結果カード",
        "",
    ]
    for h in normalized_hits:
        cards_md.append(h["card_markdown"])
        cards_md.append("")
        cards_md.append("---")
        cards_md.append("")

    cards_md.extend(
        [
            "## Webあり完成回答",
            "",
            "```text",
            (case.get("answer_with_web") or "(empty)").strip() or "(empty)",
            "```",
            "",
            "## 人間レビュー（空欄・自動入力なし）",
            "",
            "- 検索結果の関係性:",
            "- 回答材料として使えそうか:",
            "- 日本語で読みやすいか:",
            "- Webで情報が増えたか:",
            "- Webなしでも十分か:",
            "- どちらを採用したいか:",
            "- コメント:",
            "",
        ]
    )

    return {
        "case_id": case_id,
        "observation_id": observation_id,
        "category": case.get("band") or "",
        "request": request,
        "answer_without_web": case.get("answer_without_web") or "",
        "answer_with_web": case.get("answer_with_web") or "",
        "search_query": query,
        "query_language": query_lang,
        "has_japanese_result": ja_n > 0,
        "has_english_result": en_n > 0,
        "japanese_result_count": ja_n,
        "english_result_count": en_n,
        "available_count": available_n,
        "empty_count": empty_n,
        "search_result_count": total,
        "normalized_hits": normalized_hits,
        "search_results_raw": hits,
        "card_markdown": "\n".join(cards_md),
        # 人間記入欄（空）
        "検索結果の関係性": "",
        "回答材料として使えそうか": "",
        "日本語で読みやすいか": "",
        "Webで情報が増えたか": "",
        "Webなしでも十分か": "",
        "どちらを採用したいか": "",
        "コメント": "",
        "not_auto_scored": True,
        "not_connected_to_agent": True,
    }


def build_all(
    *,
    limit: int | None = None,
    with_ja_summary: bool = True,
    case_ids: list[str] | None = None,
) -> list[dict]:
    data = json.loads(SRC_HITS.read_text(encoding="utf-8"))
    cases = list(data.get("cases") or [])
    if case_ids:
        wanted = set(case_ids)
        cases = [c for c in cases if c.get("case_id") in wanted]
    if limit is not None:
        cases = cases[:limit]
    out = []
    for case in cases:
        print(f"normalize {case.get('case_id')} ...")
        out.append(normalize_case(case, with_ja_summary=with_ja_summary))
    return out


def write_outputs(rows: list[dict]) -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "review_dataset.json").write_text(
        json.dumps(
            {
                "kind": "web_effect_normalized_review",
                "source": str(SRC_HITS.name),
                "not_auto_scored": True,
                "not_connected_to_agent_gate_pipeline": True,
                "case_count": len(rows),
                "cases": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    fields = [
        "ケースID",
        "observation_id",
        "質問",
        "Webなし回答",
        "検索クエリ",
        "検索結果件数",
        "内容取得できた件数",
        "内容なし件数",
        "日本語結果あり",
        "英語結果あり",
        "検索結果カード",
        "Webあり回答",
        "検索結果の関係性",
        "回答材料として使えそうか",
        "日本語で読みやすいか",
        "Webで情報が増えたか",
        "Webなしでも十分か",
        "どちらを採用したいか",
        "コメント",
    ]
    with (HERE / "review_worksheet.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            cards = "\n\n".join(
                h.get("card_markdown") or "" for h in row.get("normalized_hits") or []
            )
            writer.writerow(
                {
                    "ケースID": row["case_id"],
                    "observation_id": row["observation_id"],
                    "質問": row["request"],
                    "Webなし回答": row["answer_without_web"],
                    "検索クエリ": row["search_query"],
                    "検索結果件数": row["search_result_count"],
                    "内容取得できた件数": row["available_count"],
                    "内容なし件数": row["empty_count"],
                    "日本語結果あり": row["has_japanese_result"],
                    "英語結果あり": row["has_english_result"],
                    "検索結果カード": cards,
                    "Webあり回答": row["answer_with_web"],
                    "検索結果の関係性": "",
                    "回答材料として使えそうか": "",
                    "日本語で読みやすいか": "",
                    "Webで情報が増えたか": "",
                    "Webなしでも十分か": "",
                    "どちらを採用したいか": "",
                    "コメント": "",
                }
            )

    compare = [
        "# 正規化レビューカード（Webなし → 検索結果 → Webあり）",
        "",
        "有用性・採用の自動判定はしていない。人間記入欄は空欄。",
        "",
    ]
    for row in rows:
        compare.append(row["card_markdown"])
        compare.append("\n\n")
    (HERE / "review_cards.md").write_text("\n".join(compare), encoding="utf-8")

    # SUMMARY
    empty_cases = [r["case_id"] for r in rows if r["empty_count"] == r["search_result_count"] and r["search_result_count"] > 0]
    available_cases = [r["case_id"] for r in rows if r["available_count"] > 0]
    en_cases = [r["case_id"] for r in rows if r["has_english_result"]]
    ja_cases = [r["case_id"] for r in rows if r["has_japanese_result"]]
    (HERE / "SUMMARY.md").write_text(
        "\n".join(
            [
                "# 正規化バッチ SUMMARY",
                "",
                f"- cases: {len(rows)}",
                f"- with any available content: {len(available_cases)} → {available_cases}",
                f"- all-empty content: {len(empty_cases)} → {empty_cases}",
                f"- has English text: {len(en_cases)}",
                f"- has Japanese text: {len(ja_cases)} → {ja_cases or '（本バッチでは0）'}",
                "",
                "empty は無効判定ではない。有用性不明として人間が判断する。",
                "評価列は空欄。Agent/Gate/Pipeline 非接続。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (HERE / "README.md").write_text(
        "\n".join(
            [
                "# 検索結果 人間レビュー用正規化",
                "",
                "検索結果そのものの自動評価ではなく、**人間が読める表示**への正規化のみ。",
                "",
                "- 原データ (`web_effect_review_hits.json`) は変更しない",
                "- `empty`（内容なし）と「無関係」を分離",
                "- 英語原文は残し、必要なら日本語要約を補助表示",
                "- 有用性・Web効果・採用の自動入力はしない",
                "- heuristic / Gate / Pipeline / Stage3/4 非接続",
                "",
                "主比較: `answer_without_web` → 検索結果カード → `answer_with_web`",
                "",
                "## ファイル",
                "",
                "| ファイル | 内容 |",
                "|----------|------|",
                "| `review_cards.md` | 人間向けカード |",
                "| `review_dataset.json` | 正規化データ |",
                "| `review_worksheet.csv` | 日本語列の記入用 |",
                "| `SUMMARY.md` | 件数サマリ |",
                "",
                "## 再生成",
                "",
                "```text",
                "python normalize_and_build.py --all",
                "python normalize_and_build.py --sample10",
                "python normalize_and_build.py --test",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


class NormalizeTests(unittest.TestCase):
    def test_available_shows_original(self):
        hit = {
            "title": "t",
            "url": "https://example.com/a",
            "snippet": "Ollama is an open-source tool.",
        }
        card = normalize_hit(hit, index=1, total=1, request="q", query="q")
        self.assertEqual(card["content_status"], CONTENT_AVAILABLE)
        self.assertIn("Ollama", card["original_text"])
        self.assertIn("原文", card["card_markdown"])

    def test_empty_not_irrelevant(self):
        hit = {"title": "Python implementations", "url": "https://en.wikipedia.org/x", "snippet": None}
        card = normalize_hit(hit, index=1, total=3, request="tuple", query="Python tuple")
        self.assertEqual(card["content_status"], CONTENT_EMPTY)
        self.assertIn("判断できません", card["judgment_hint_ja"])
        self.assertNotIn("無関係", card["card_markdown"])

    def test_english_keeps_original_and_optional_summary(self):
        hit = {"title": "t", "url": "https://ex.com", "snippet": "Docker is a container platform."}
        card = normalize_hit(
            hit,
            index=1,
            total=1,
            request="q",
            query="q",
            japanese_summary="Dockerはコンテナ基盤です。",
        )
        self.assertEqual(card["result_language"], "en")
        self.assertIn("Docker is a container", card["original_text"])
        self.assertIn("日本語要約", card["card_markdown"])

    def test_japanese_prefers_body_no_forced_summary(self):
        hit = {"title": "t", "url": "https://ja.wikipedia.org/x", "snippet": "これは日本語の説明です。"}
        card = normalize_hit(hit, index=1, total=1, request="q", query="q")
        self.assertEqual(card["result_language"], "ja")
        self.assertIsNone(card["japanese_summary"])

    def test_multiple_hits_independent(self):
        case = {
            "case_id": "T1",
            "band": "W1",
            "request": "req",
            "answer_without_web": "without",
            "answer_with_web": "with",
            "web_search": {
                "query": "q",
                "result": {
                    "hits": [
                        {"title": "a", "url": "https://a", "snippet": None},
                        {"title": "b", "url": "https://b", "snippet": "English text here."},
                    ]
                },
            },
        }
        row = normalize_case(case, with_ja_summary=False)
        self.assertEqual(len(row["normalized_hits"]), 2)
        self.assertEqual(row["normalized_hits"][0]["content_status"], CONTENT_EMPTY)
        self.assertEqual(row["normalized_hits"][1]["content_status"], CONTENT_AVAILABLE)
        self.assertEqual(row["answer_without_web"], "without")
        self.assertEqual(row["answer_with_web"], "with")
        self.assertEqual(row["request"], "req")
        self.assertTrue(row["observation_id"].startswith("webeffect-hits-"))
        self.assertEqual(row["検索結果の関係性"], "")
        self.assertTrue(row["not_connected_to_agent"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample10", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-ja-summary", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args(argv)

    if args.test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(NormalizeTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    if args.sample10:
        # empty / english / mixed を含む固定10件
        sample_ids = [
            "B05",  # all empty
            "C02",  # mixed empty+en
            "C03",  # all empty
            "A04",  # en available
            "C05",  # en
            "WB01",
            "WB02",  # all available en
            "WB04",
            "WB07",
            "WB12",
        ]
        rows = build_all(
            case_ids=sample_ids,
            with_ja_summary=not args.no_ja_summary,
        )
    elif args.all or args.only:
        rows = build_all(
            case_ids=args.only or None,
            with_ja_summary=not args.no_ja_summary,
        )
    else:
        parser.print_help()
        return 2

    write_outputs(rows)
    print(f"wrote {HERE} cases={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
