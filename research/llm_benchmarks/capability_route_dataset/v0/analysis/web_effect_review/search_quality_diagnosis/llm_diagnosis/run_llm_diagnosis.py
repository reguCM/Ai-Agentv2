"""
search_web 検索品質ボトルネック — LLM独立分析（調査専用・実装変更なし）。

事前結論（Cが問題、rankingが悪い等）をプロンプトに含めない。
A/B/C/D は候補として提示するのみ。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import chat

HERE = Path(__file__).resolve().parent
SRC = HERE.parent
CASE_IDS = [
    "A06",
    "E04",
    "C03",
    "P02b",
    "C02",
    "A03",
    "A04",
    "C04",
    "B05",
    "WB02",
    "P02a",
    "E02",
]

JA_EN_SUMMARY = """
| theme | ja query | ja api | ja ret | ja snip+ | en query | en api | en ret | en snip+ |
| drivers_license_jp | 日本の運転免許 取得方法 | 0 | 0 | 0 | Japan driving license how to get | 0 | 0 | 0 |
| ollama | Ollamaとは | 0 | 0 | 0 | Ollama | 18 | 3 | 1 |
| python_313 | Python 3.13 新機能 | 0 | 0 | 0 | Python 3.13 new features | 0 | 0 | 0 |
| rtx3060_current | RTX 3060 現在 立ち位置 | 0 | 0 | 0 | GeForce RTX 3060 current status | 0 | 0 | 0 |
""".strip()

SYSTEM = """あなたはWeb検索パイプラインの診断分析者です。与えられた観測データのみを根拠に分析する。

厳守:
1. 事前に与えられた結論や優先順位をそのまま繰り返さない。データから独立に判断する
2. タイトル・URLの存在だけで検索結果を有用と評価しない。LLMが回答改善に使える具体的情報があるかを基準にする
3. snippetが空の候補は、検索結果としての有用性を肯定しない
4. ただし URL先に本文が存在する可能性と、現在の取得処理が本文を取れていない可能性は分離する
5. 検索結果の品質問題と、LLMの回答品質問題を混同しない
6. 「検索したのに回答が変わらなかった」＝「検索機能が悪い」とは判断しない
7. 各判断で「観測事実」と「推測」を必ず分離する
8. 判断不能は無理に断定しない

ボトルネック候補（事前優先順位は与えない）:
- A = 候補生成（検索APIが有用候補を返していない、候補数が少ない等）
- B = ranking / 候補絞り込み
- C = 内容取得 / snippet / extract
- D = LLMへの受け渡し
- その他 = 上記以外（クエリ設計、時間依存、言語、検索対象の性質等）

JSON出力時は指定スキーマに従う。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msg(response) -> str:
    msg = getattr(response, "message", None)
    if msg is None:
        return ""
    c = getattr(msg, "content", None)
    return "" if c is None else str(c)


def extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def detect_language(request: str, query: str) -> str:
    jp = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", request or ""))
    qjp = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", query or ""))
    if jp and qjp:
        return "ja"
    if jp and not qjp:
        return "ja_request_en_query"
    if qjp:
        return "ja"
    return "en_or_mixed"


def observed_outcome(rec: dict) -> str:
    ret = rec.get("search_web_return") or {}
    hits = ret.get("hits") or []
    n = len(hits)
    snip = sum(1 for h in hits if str(h.get("snippet") or "").strip())
    api_n = rec.get("api_candidate_count") or 0
    if n == 0:
        if api_n == 0:
            return "return_empty_api_zero"
        return "return_empty_api_had_candidates"
    if snip == 0:
        return "return_hits_all_snippet_empty"
    if snip < n:
        return "return_hits_partial_snippet"
    return "return_hits_all_snippet_nonempty"


def load_ranking(case_id: str) -> list[dict]:
    path = SRC / "ranking_comparison.csv"
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("case_id") == case_id:
                rows.append(row)
    return rows


def build_evidence_card(rec: dict, ranking_rows: list[dict]) -> str:
    lines = [
        f"case_id: {rec['case_id']}",
        f"request: {rec.get('request') or ''}",
        f"search_query: {rec.get('query') or ''}",
        f"time_sensitive: {rec.get('time_sensitive')}",
        f"language_hint: {detect_language(rec.get('request') or '', rec.get('query') or '')}",
        "",
        "=== 段階件数（機械観測） ===",
    ]
    mo = rec.get("machine_observation") or {}
    cc = mo.get("counts_chain") or {}
    for k in ("api_raw", "hit_accepted", "after_unique", "after_ranking", "return", "llm_received"):
        lines.append(f"{k}: {cc.get(k)}")
    lines.extend(
        [
            f"api_snippet_nonempty: {rec.get('api_snippet_nonempty')}",
            f"api_snippet_empty: {rec.get('api_snippet_empty')}",
            f"return_snippet_nonempty: {mo.get('snippet_nonempty_in_return')}",
            f"return_snippet_empty: {mo.get('snippet_empty_in_return')}",
            f"ranking_dropped_total: {mo.get('dropped_by_ranking')}",
            f"ranking_dropped_with_snippet: {mo.get('dropped_with_snippet')}",
            f"extract_probe_page_has_usable_text: {mo.get('page_has_text_but_snippet_empty_probe')}",
            f"llm_handoff_count_match: {rec.get('llm_handoff', {}).get('count_match_live_vs_stored')}",
            f"observed_search_outcome: {observed_outcome(rec)}",
            "",
            "=== API候補（加工前・最大15件） ===",
        ]
    )
    idx = 0
    for backend, block in (rec.get("raw_api") or {}).items():
        for it in (block.get("items") or [])[:8]:
            idx += 1
            if idx > 15:
                break
            sn = str(it.get("snippet") or "").strip()
            lines.append(
                f"[{idx}] backend={backend} title={it.get('title')!r} "
                f"url={it.get('url') or ''} snippet_len={len(sn)} "
                f"snippet_preview={sn[:120]!r}"
            )
        if idx > 15:
            break

    lines.extend(["", "=== search_web return hits ==="])
    for i, h in enumerate((rec.get("search_web_return") or {}).get("hits") or [], 1):
        sn = str(h.get("snippet") or "").strip()
        lines.append(
            f"[{i}] backend={h.get('backend')} title={h.get('title')!r} "
            f"url={h.get('url') or ''} snippet_len={len(sn)} snippet={sn[:200]!r}"
        )

    dropped = [r for r in ranking_rows if r.get("adopted") in ("False", False, "false", "0")]
    dropped_snip = [r for r in dropped if r.get("has_snippet") in ("True", True, "true", "1")]
    lines.extend(["", "=== rankingで採用されなかった候補 ==="])
    for r in dropped[:12]:
        lines.append(
            f"score={r.get('score')} reason={r.get('exclude_reason')} "
            f"has_snippet={r.get('has_snippet')} title={r.get('title')!r} "
            f"backend={r.get('backend')} snippet_len={r.get('snippet_len')}"
        )
    if dropped_snip:
        lines.extend(["", "=== ranking脱落・snippetあり ==="])
        for r in dropped_snip[:8]:
            lines.append(
                f"score={r.get('score')} title={r.get('title')!r} "
                f"backend={r.get('backend')} snippet_len={r.get('snippet_len')}"
            )

    probes = rec.get("extract_probes") or []
    if probes:
        lines.extend(["", "=== 調査専用 Wikipedia extracts（snippet空候補） ==="])
        for p in probes:
            if p.get("skipped"):
                continue
            lines.append(
                f"title={p.get('title')!r} extract_len={p.get('extract_len')} "
                f"page_has_usable_text={p.get('page_has_usable_text')} "
                f"preview={str(p.get('extract_preview') or '')[:150]!r}"
            )

    lines.extend(
        [
            "",
            "=== LLM受け渡し（観測） ===",
            f"agent_passes_full_return: {rec.get('llm_handoff', {}).get('agent_passes_full_return')}",
            f"llm_received_hit_count: {rec.get('llm_handoff', {}).get('llm_received_hit_count')}",
            f"json_bytes: {rec.get('llm_handoff', {}).get('json_bytes')}",
            "",
            "注意: 上記は診断ハーネス再取得データ。回答品質（Webあり/なし差）は材料に含めない。",
        ]
    )
    return "\n".join(lines)


CASE_PROMPT = """以下の観測データのみを根拠に、このケースの検索パイプラインを分析し、JSONのみ出力せよ。

各項目で judgment（判断文）、observed_facts（観測事実の配列）、speculation（推測の配列）を分ける。

出力スキーマ:
{{
  "case_id": "...",
  "request": "...",
  "language": "...",
  "api_candidate_count": 0,
  "returned_count": 0,
  "non_empty_snippet_count": 0,
  "ranking_dropped_candidates": 0,
  "page_has_usable_text": false,
  "llm_received_count": 0,
  "llm_received_usable_evidence": "yes|partial|no|unknown",
  "observed_search_outcome": "...",
  "judgments": {{
    "1_llm_usable_info": {{"judgment": "...", "observed_facts": [], "speculation": []}},
    "2_api_had_useful_candidates": {{"judgment": "...", "observed_facts": [], "speculation": []}},
    "3_ranking_lost_useful": {{"judgment": "...", "observed_facts": [], "speculation": []}},
    "4_content_fetch_failed": {{"judgment": "...", "observed_facts": [], "speculation": []}},
    "5_llm_handoff_problem": {{"judgment": "...", "observed_facts": [], "speculation": []}},
    "6_ja_en_difference": {{"judgment": "...", "observed_facts": [], "speculation": []}},
    "7_timeliness_if_applicable": {{"judgment": "...", "observed_facts": [], "speculation": []}}
  }},
  "suspected_bottlenecks": ["A|B|C|D|その他", ...],
  "suspected_bottleneck_reason": "..."
}}

--- 観測データ ---
{evidence}
"""


SYNTHESIS_PROMPT = """以下は12ケースのLLMケース分析サマリーである。全体分析をJSONのみ出力せよ。

事前結論の繰り返し禁止。証拠の強さに基づき独立判断。

出力スキーマ:
{{
  "A_overall_summary": "...",
  "B_bottleneck_ranking": [
    {{"category": "A|B|C|D|その他", "rank": 1, "strength": "strong|moderate|weak", "reason": "..."}}
  ],
  "C_evidence_by_pattern": {{
    "snippet_empty_but_candidates_exist": "...",
    "ranking_dropped_candidates": "...",
    "page_has_usable_text_but_snippet_empty": "...",
    "few_api_candidates": "...",
    "ja_en_difference": "...",
    "time_sensitive_queries": "..."
  }},
  "D_fix_now_vs_investigate": {{
    "fix_now": ["..."],
    "investigate_more": ["..."]
  }},
  "E_one_next_investigation": "...",
  "F_human_must_decide": ["..."]
}}

--- 日英比較（別実験・同一ハーネス） ---
{ja_en}

--- ケース分析サマリー ---
{cases}
"""


def llm_analyze_case(evidence: str, *, model: str) -> dict:
    prompt = CASE_PROMPT.format(evidence=evidence)
    for attempt in range(3):
        extra = "\n有効JSONオブジェクト1つのみ。" if attempt else ""
        resp = chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt + extra},
            ],
        )
        raw = _msg(resp)
        parsed = extract_json(raw)
        if parsed and parsed.get("case_id"):
            parsed["_raw"] = raw
            return parsed
    return {"_raw": raw, "_parse_error": True}


def llm_synthesize(case_summaries: str, *, model: str) -> dict:
    prompt = SYNTHESIS_PROMPT.format(ja_en=JA_EN_SUMMARY, cases=case_summaries)
    for attempt in range(3):
        extra = "\n有効JSONオブジェクト1つのみ。" if attempt else ""
        resp = chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt + extra},
            ],
        )
        raw = _msg(resp)
        parsed = extract_json(raw)
        if parsed and parsed.get("A_overall_summary"):
            parsed["_raw"] = raw
            return parsed
    return {"_raw": raw, "_parse_error": True}


def case_to_markdown(c: dict) -> str:
    j = c.get("judgments") or {}
    lines = [
        f"## {c.get('case_id')}",
        "",
        f"- request: {c.get('request')}",
        f"- language: {c.get('language')}",
        f"- api_candidate_count: {c.get('api_candidate_count')}",
        f"- returned_count: {c.get('returned_count')}",
        f"- non_empty_snippet_count: {c.get('non_empty_snippet_count')}",
        f"- ranking_dropped_candidates: {c.get('ranking_dropped_candidates')}",
        f"- page_has_usable_text: {c.get('page_has_usable_text')}",
        f"- llm_received_count: {c.get('llm_received_count')}",
        f"- llm_received_usable_evidence: {c.get('llm_received_usable_evidence')}",
        f"- observed_search_outcome: {c.get('observed_search_outcome')}",
        f"- suspected_bottlenecks: {c.get('suspected_bottlenecks')}",
        "",
    ]
    labels = [
        ("1_llm_usable_info", "1. LLMにとって有用な情報を含んでいたか"),
        ("2_api_had_useful_candidates", "2. API段階に有用候補が存在した可能性"),
        ("3_ranking_lost_useful", "3. rankingで有用候補が失われた可能性"),
        ("4_content_fetch_failed", "4. 内容取得に失敗している可能性"),
        ("5_llm_handoff_problem", "5. LLM受け渡し段階の問題"),
        ("6_ja_en_difference", "6. 日英差"),
        ("7_timeliness_if_applicable", "7. 現在性（時間依存の場合）"),
    ]
    for key, title in labels:
        block = j.get(key) or {}
        lines.extend(
            [
                f"### {title}",
                f"**判断:** {block.get('judgment') or ''}",
                "",
                "**観測事実:**",
            ]
        )
        for f in block.get("observed_facts") or []:
            lines.append(f"- {f}")
        lines.extend(["", "**推測:**"])
        for s in block.get("speculation") or []:
            lines.append(f"- {s}")
        lines.append("")
    lines.append("---\n")
    return "\n".join(lines)


def synthesis_to_markdown(s: dict) -> str:
    lines = [
        "# LLM_DIAGNOSIS",
        "",
        f"- 生成: `{_now()}`",
        "",
        "## A. 全体総括",
        "",
        s.get("A_overall_summary") or "",
        "",
        "## B. ボトルネック候補ランキング",
        "",
    ]
    for item in s.get("B_bottleneck_ranking") or []:
        lines.append(
            f"{item.get('rank')}. **{item.get('category')}** "
            f"（強度: {item.get('strength')}）— {item.get('reason')}"
        )
    ev = s.get("C_evidence_by_pattern") or {}
    lines.extend(
        [
            "",
            "## C. 根拠（パターン別）",
            "",
            "### snippet空だが候補存在",
            ev.get("snippet_empty_but_candidates_exist") or "",
            "",
            "### rankingで脱落",
            ev.get("ranking_dropped_candidates") or "",
            "",
            "### page_has_usable_text だが snippet空",
            ev.get("page_has_usable_text_but_snippet_empty") or "",
            "",
            "### API候補少数",
            ev.get("few_api_candidates") or "",
            "",
            "### 日英差",
            ev.get("ja_en_difference") or "",
            "",
            "### 時間依存質問",
            ev.get("time_sensitive_queries") or "",
            "",
            "## D. 今すぐ修正 vs 追加調査",
            "",
            "**今すぐ修正候補:**",
        ]
    )
    for x in (s.get("D_fix_now_vs_investigate") or {}).get("fix_now") or []:
        lines.append(f"- {x}")
    lines.extend(["", "**追加調査:**"])
    for x in (s.get("D_fix_now_vs_investigate") or {}).get("investigate_more") or []:
        lines.append(f"- {x}")
    lines.extend(
        [
            "",
            "## E. 次に1つだけ調査するなら",
            "",
            s.get("E_one_next_investigation") or "",
            "",
            "## F. 人間が最終判断すべき事項",
            "",
        ]
    )
    for x in s.get("F_human_must_decide") or []:
        lines.append(f"- {x}")
    return "\n".join(lines)


def human_decision_sheet(cases: list[dict], synthesis: dict) -> str:
    lines = [
        "# HUMAN_DECISION_SHEET",
        "",
        "LLM分析のレビュー用。各欄に記入してください。",
        "",
        "## 全体",
        "",
        "### LLMの全体総括に同意するか",
        "",
        "（記入）",
        "",
        "### LLMのボトルネックランキングで最も問題だと思う箇所",
        "",
        "（記入: A / B / C / D / その他）",
        "",
        "### 次に修正するならどこか",
        "",
        "（記入）",
        "",
        "### 追加調査が必要か",
        "",
        "（記入: はい/いいえ + 内容）",
        "",
        "### LLMの分析で見落としている点",
        "",
        "（記入）",
        "",
        "---",
        "",
        "## ケース別",
        "",
    ]
    for c in cases:
        lines.extend(
            [
                f"### {c.get('case_id')}: {c.get('request', '')[:50]}",
                "",
                f"- LLM判断（有用情報）: {(c.get('judgments') or {}).get('1_llm_usable_info', {}).get('judgment', '')[:120]}",
                f"- LLM疑い: {c.get('suspected_bottlenecks')}",
                "",
                "| 項目 | 記入 |",
                "|------|------|",
                "| LLMの分析に同意するか | |",
                "| 最も問題だと思う箇所 (A/B/C/D/その他) | |",
                "| 次に修正するならどこか | |",
                "| 追加調査が必要か | |",
                "| LLMの見落とし | |",
                "",
            ]
        )
    lines.extend(
        [
            "---",
            "",
            "## LLM全体分析メモ（参照）",
            "",
            synthesis.get("A_overall_summary") or "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    profile = get_llm_profile(args.model)
    model = profile["model"]

    data = json.loads((SRC / "review_dataset.json").read_text(encoding="utf-8"))
    records = {r["case_id"]: r for r in data.get("records") or []}

    case_analyses = []
    for cid in CASE_IDS:
        rec = records.get(cid)
        if not rec:
            print(f"SKIP {cid}")
            continue
        ranking = load_ranking(cid)
        evidence = build_evidence_card(rec, ranking)
        print(f"LLM analyze {cid} ...")
        analysis = llm_analyze_case(evidence, model=model)
        # fill metrics from record if LLM omitted
        mo = rec.get("machine_observation") or {}
        cc = mo.get("counts_chain") or {}
        analysis.setdefault("case_id", cid)
        analysis.setdefault("request", rec.get("request"))
        analysis.setdefault("language", detect_language(rec.get("request") or "", rec.get("query") or ""))
        analysis.setdefault("api_candidate_count", rec.get("api_candidate_count"))
        analysis.setdefault("returned_count", cc.get("return"))
        analysis.setdefault("non_empty_snippet_count", mo.get("snippet_nonempty_in_return"))
        analysis.setdefault("ranking_dropped_candidates", mo.get("dropped_by_ranking"))
        analysis.setdefault(
            "page_has_usable_text", mo.get("page_has_text_but_snippet_empty_probe")
        )
        analysis.setdefault("llm_received_count", cc.get("llm_received"))
        analysis.setdefault("observed_search_outcome", observed_outcome(rec))
        case_analyses.append(analysis)

    summary_parts = []
    for c in case_analyses:
        summary_parts.append(
            json.dumps(
                {
                    "case_id": c.get("case_id"),
                    "observed_search_outcome": c.get("observed_search_outcome"),
                    "llm_received_usable_evidence": c.get("llm_received_usable_evidence"),
                    "suspected_bottlenecks": c.get("suspected_bottlenecks"),
                    "judgments": {
                        k: v.get("judgment") if isinstance(v, dict) else v
                        for k, v in (c.get("judgments") or {}).items()
                    },
                },
                ensure_ascii=False,
            )
        )
    print("LLM synthesis ...")
    synthesis = llm_synthesize("\n".join(summary_parts), model=model)

    out = {
        "generated_at": _now(),
        "model": model,
        "case_analyses": case_analyses,
        "synthesis": synthesis,
    }
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "llm_diagnosis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    csv_fields = [
        "case_id",
        "request",
        "language",
        "api_candidate_count",
        "returned_count",
        "non_empty_snippet_count",
        "ranking_dropped_candidates",
        "page_has_usable_text",
        "llm_received_count",
        "llm_received_usable_evidence",
        "observed_search_outcome",
        "suspected_bottlenecks",
        "j1_usable",
        "j2_api",
        "j3_ranking",
        "j4_content",
        "j5_handoff",
        "j6_ja_en",
        "j7_timeliness",
    ]
    with (HERE / "llm_diagnosis.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        for c in case_analyses:
            j = c.get("judgments") or {}
            w.writerow(
                {
                    "case_id": c.get("case_id"),
                    "request": c.get("request"),
                    "language": c.get("language"),
                    "api_candidate_count": c.get("api_candidate_count"),
                    "returned_count": c.get("returned_count"),
                    "non_empty_snippet_count": c.get("non_empty_snippet_count"),
                    "ranking_dropped_candidates": c.get("ranking_dropped_candidates"),
                    "page_has_usable_text": c.get("page_has_usable_text"),
                    "llm_received_count": c.get("llm_received_count"),
                    "llm_received_usable_evidence": c.get("llm_received_usable_evidence"),
                    "observed_search_outcome": c.get("observed_search_outcome"),
                    "suspected_bottlenecks": "|".join(c.get("suspected_bottlenecks") or []),
                    "j1_usable": (j.get("1_llm_usable_info") or {}).get("judgment"),
                    "j2_api": (j.get("2_api_had_useful_candidates") or {}).get("judgment"),
                    "j3_ranking": (j.get("3_ranking_lost_useful") or {}).get("judgment"),
                    "j4_content": (j.get("4_content_fetch_failed") or {}).get("judgment"),
                    "j5_handoff": (j.get("5_llm_handoff_problem") or {}).get("judgment"),
                    "j6_ja_en": (j.get("6_ja_en_difference") or {}).get("judgment"),
                    "j7_timeliness": (j.get("7_timeliness_if_applicable") or {}).get("judgment"),
                }
            )

    case_md = ["# CASE_ANALYSIS", "", f"- model: `{model}`", f"- generated: `{_now()}`", ""]
    for c in case_analyses:
        case_md.append(case_to_markdown(c))
    (HERE / "CASE_ANALYSIS.md").write_text("\n".join(case_md), encoding="utf-8")
    (HERE / "LLM_DIAGNOSIS.md").write_text(synthesis_to_markdown(synthesis), encoding="utf-8")
    (HERE / "HUMAN_DECISION_SHEET.md").write_text(
        human_decision_sheet(case_analyses, synthesis), encoding="utf-8"
    )
    (HERE / "README.md").write_text(
        "\n".join(
            [
                "# llm_diagnosis",
                "",
                "search_web 品質ボトルネックの LLM 独立分析（実装変更なし）。",
                "",
                f"- model: `{model}`",
                "",
                "```text",
                "python run_llm_diagnosis.py",
                "```",
                "",
                "出力:",
                "- CASE_ANALYSIS.md — ケース別分析",
                "- LLM_DIAGNOSIS.md — 全体分析",
                "- llm_diagnosis.json / .csv",
                "- HUMAN_DECISION_SHEET.md — 人間レビュー用",
                "",
                "事前結論をプロンプトに含めない設計。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"done -> {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
