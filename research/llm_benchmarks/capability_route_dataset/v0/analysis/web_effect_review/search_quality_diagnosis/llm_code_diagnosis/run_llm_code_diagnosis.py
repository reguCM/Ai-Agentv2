"""
search_web コード＋実測ログの Qwen3:8b 直接解析（調査専用・実装変更なし）。

- search_web / ranking / Agent / Gate / Pipeline は変更しない
- llm_diagnosis/ は変更しない
- 事前結論（Cが原因等）をプロンプトに含めない
- モデルは qwen3_8b を明示指定（pipeline active_model に依存しない）
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ollama import Client

# リポジトリルートを sys.path へ（cwd 非依存）
_ROOT = Path(__file__).resolve()
for _ in range(12):
    if (_ROOT / "tools" / "system" / "network" / "search_web.py").is_file():
        break
    _ROOT = _ROOT.parent
import sys

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.system.config import get_llm_profile

HERE = Path(__file__).resolve().parent
DIAG = HERE.parent
REPO = _ROOT

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

JA_EN_TABLE = """
| theme | ja query | ja api | ja ret | ja snip+ | en query | en api | en ret | en snip+ |
| drivers_license_jp | 日本の運転免許 取得方法 | 0 | 0 | 0 | Japan driving license how to get | 0 | 0 | 0 |
| ollama | Ollamaとは | 0 | 0 | 0 | Ollama | 18 | 3 | 1 |
| python_313 | Python 3.13 新機能 | 0 | 0 | 0 | Python 3.13 new features | 0 | 0 | 0 |
| rtx3060_current | RTX 3060 現在 立ち位置 | 0 | 0 | 0 | GeForce RTX 3060 current status | 0 | 0 | 0 |
""".strip()

SYSTEM = """あなたは検索パイプラインの原因調査者である。与えられたコード抜粋と実測ログだけを根拠にする。

厳守:
1. 事前結論を繰り返さない。コードとログから独立に判断する
2. 「検索結果がない」と「検索結果の本文（snippet）がない」を同一視しない
3. タイトル/URLだけの候補を、LLMが回答改善に使える有用情報とは扱わない
4. snippet空なら検索結果としての有用性を肯定しない。ただし URL先本文の存在可能性と、現行コードが本文を取らない可能性は分離する
5. 件数一致だけでは D（受け渡し）を完全否定しない。渡った中身が有用かを見る
6. 「日本語だから弱い」を先に置かない。差が出た段階（query/API/ranking/content）を特定する
7. 修正案より「なぜこの結果になったか」を優先する
8. 観測事実と推測を分離する
9. 判断不能は unknown とする

原因候補（優先順位は与えない。複数可。複合は H）:
- A: 検索候補の生成/API取得
- B: ranking / filtering
- C: snippet / description / 本文取得・内容抽出
- D: LLMへの受け渡し
- E: query生成・query言語
- F: エラー処理・リトライ・API制限
- G: その他
- H: 複合要因

整合性ラベル（各主張に付ける）:
code_supported / log_supported / both_supported / log_only / code_only / contradicted / insufficient_evidence

確信度: strong / moderate / weak / unknown

JSONのみ出力。"""


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


def read_lines(rel: str, start: int, end: int) -> str:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    chunk = lines[start - 1 : end]
    numbered = [f"{i + start}|{line}" for i, line in enumerate(chunk)]
    return f"## FILE {rel} L{start}-{end}\n" + "\n".join(numbered)


def build_code_pack() -> str:
    parts = [
        "以下は現行コードの抜粋（行番号付き）。Tool Builder 用 research.web.search_web は Agent 公開 search_web からは呼ばれない。",
        read_lines("tools/system/network/search_web.py", 1, 37),
        read_lines("tools/system/network/general_web_search.py", 1, 226),
        read_lines("tools/system/tool_builder/research/web.py", 8, 117),
        read_lines("tools/system/tool_builder/research/web.py", 295, 304),
        read_lines("agent.py", 347, 404),
        read_lines("agent.py", 520, 541),
        read_lines("agent.py", 621, 633),
        read_lines("agent.py", 832, 858),
        read_lines(
            "research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/run_web_effect_pilot.py",
            90,
            114,
        ),
        read_lines("tools/system/capability_route_obs.py", 152, 168),
        "注: classify_search_web_outcome は観測分類。Agent の LLM 経路は raw json.dumps(result)。",
        "注: compact_hit は title/snippet/url/backend のみ。URL先ページの二次GETは general_web_search に存在しない。",
        "注: Wikipedia OpenSearch の payload[2] を snippet に入れる。空文字も hit 化する（title があれば）。",
        "注: score>0 の候補があればそれだけを return_limit 件返す。score は query 文字列の title/snippet 部分一致。",
        "注: search_duckduckgo は Instant Answer（AbstractText / RelatedTopics）。一般SERP 10件ではない。",
        "注: HTTP リトライは search_web 本体に無い。例外は backend 単位で errors に蓄積。hits があれば error=None。",
        "注: ハーネスの _suggest_search_query は英語百科寄りを優先。search_web 本体はクエリ翻訳しない。",
    ]
    return "\n\n".join(parts)


def load_ranking_rows(case_id: str) -> list[dict]:
    path = DIAG / "ranking_comparison.csv"
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("case_id") == case_id:
                rows.append(row)
    return rows


def compact_api(raw: dict) -> list[str]:
    lines = []
    for backend, block in (raw or {}).items():
        lines.append(
            f"- {backend}: status={block.get('http_status')} error={block.get('error')!r} "
            f"raw_count={block.get('raw_count')} snippet_nonempty={block.get('snippet_nonempty')}"
        )
        for it in (block.get("items") or [])[:8]:
            sn = str(it.get("snippet") or "")
            lines.append(
                f"  rank={it.get('api_rank')} title={it.get('title')!r} url={it.get('url') or ''} "
                f"snippet_len={len(sn.strip())} preview={sn[:140]!r}"
            )
    return lines


def build_case_evidence(rec: dict, ranking: list[dict]) -> str:
    mo = rec.get("machine_observation") or {}
    cc = mo.get("counts_chain") or {}
    ret = rec.get("search_web_return") or {}
    lines = [
        f"case_id: {rec.get('case_id')}",
        f"request: {rec.get('request')}",
        f"query: {rec.get('query')}",
        f"time_sensitive: {rec.get('time_sensitive')}",
        f"counts: api_raw={cc.get('api_raw')} hit_accepted={cc.get('hit_accepted')} "
        f"unique={cc.get('after_unique')} ranking={cc.get('after_ranking')} "
        f"return={cc.get('return')} llm_received={cc.get('llm_received')}",
        f"api_snippet_nonempty={rec.get('api_snippet_nonempty')} "
        f"api_snippet_empty={rec.get('api_snippet_empty')}",
        f"return_snippet_nonempty={mo.get('snippet_nonempty_in_return')} "
        f"return_snippet_empty={mo.get('snippet_empty_in_return')}",
        f"ranking_dropped={mo.get('dropped_by_ranking')} "
        f"dropped_with_snippet={mo.get('dropped_with_snippet')}",
        f"extract_page_has_usable_text={mo.get('page_has_text_but_snippet_empty_probe')}",
        f"llm_handoff: {json.dumps(rec.get('llm_handoff') or {}, ensure_ascii=False)}",
        "",
        "=== raw_api ===",
        *compact_api(rec.get("raw_api") or {}),
        "",
        "=== search_web return hits ===",
    ]
    for i, h in enumerate(ret.get("hits") or [], 1):
        sn = str(h.get("snippet") or "")
        lines.append(
            f"[{i}] backend={h.get('backend')} title={h.get('title')!r} "
            f"url={h.get('url')} snippet_len={len(sn.strip())} snippet={sn[:220]!r}"
        )
    dropped = [
        r
        for r in ranking
        if str(r.get("adopted")).lower() in ("false", "0")
    ]
    lines.extend(["", "=== ranking rows (dropped first, then adopted) ==="])
    for r in ranking:
        lines.append(
            f"order={r.get('ranking_order')} score={r.get('score')} adopted={r.get('adopted')} "
            f"reason={r.get('exclude_reason')} has_snippet={r.get('has_snippet')} "
            f"backend={r.get('backend')} title={r.get('title')!r} snippet_len={r.get('snippet_len')}"
        )
    probes = rec.get("extract_probes") or []
    if probes:
        lines.extend(["", "=== extract probes (調査専用・本番未接続) ==="])
        for p in probes:
            if p.get("skipped"):
                continue
            lines.append(
                f"title={p.get('title')!r} extract_len={p.get('extract_len')} "
                f"page_has_usable_text={p.get('page_has_usable_text')} "
                f"preview={str(p.get('extract_preview') or '')[:180]!r}"
            )
    return "\n".join(lines)


def chat_json(
    *,
    client: Client,
    model: str,
    user: str,
    num_ctx: int,
    num_predict: int,
    retries: int = 2,
) -> dict:
    last = ""
    for attempt in range(retries + 1):
        extra = "\n前回失敗。有効なJSONオブジェクト1つのみ。" if attempt else ""
        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user + extra},
            ],
            options={
                "temperature": 0,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
            keep_alive="10m",
        )
        last = _msg(resp)
        parsed = extract_json(last)
        if parsed and isinstance(parsed, dict) and len(parsed) > 1:
            parsed["_raw"] = last
            return parsed
    return {"_parse_error": True, "_raw": last}


CODE_PROMPT = """現行 search_web 経路のコード抜粋を読み、実装が何をしているかを記述せよ。結論の優先順位は先に決めるな。

出力スキーマ:
{{
  "flow_summary": "処理の流れ",
  "api_what_is_fetched": "...",
  "normalization": "...",
  "snippet_source": "...",
  "page_body_fetch_exists": true/false,
  "extracts_in_production": true/false,
  "ranking_rule": "score計算と採用条件",
  "return_limit_rule": "...",
  "llm_handoff_rule": "...",
  "error_retry": "...",
  "japanese_handling": "...",
  "english_handling": "...",
  "query_generation_where": "本体かハーネスか",
  "stdout_vs_llm_path": "...",
  "code_facts": ["事実1"],
  "not_in_code": ["コードに無いもの"]
}}

--- コード抜粋 ---
{code}
"""

CASE_PROMPT = """コード抜粋とこのケースの実測ログから、なぜこの検索結果になったかを説明する。修正案より原因。

特に区別せよ:
- APIに候補が無い / あるが有用でない / 有用候補がある / レスポンス不完全 / 429等
- snippet空 と ページ本文なし は別
- rankingで落ちたなら、scoreが低い理由をコードの score_hit_for_query で説明
- LLMに渡った件数だけでなく title/url/snippet の中身

出力スキーマ:
{{
  "case_id": "...",
  "request": "...",
  "query": "...",
  "why_this_result": "コードとログを結び付けた原因説明",
  "api_stage": {{"judgment": "...", "observed_facts": [], "speculation": [], "evidence": "both_supported|..."}},
  "ranking_stage": {{"judgment": "...", "why_low_score": "...", "observed_facts": [], "speculation": [], "evidence": "..."}},
  "content_stage": {{"judgment": "...", "snippet_empty_vs_page_body": "...", "observed_facts": [], "speculation": [], "evidence": "..."}},
  "handoff_stage": {{"judgment": "...", "content_useful_to_llm": "yes|partial|no|unknown", "observed_facts": [], "speculation": [], "evidence": "..."}},
  "query_language_stage": {{"judgment": "...", "where_difference": "query|api|ranking|content|none|unknown", "observed_facts": [], "speculation": []}},
  "timeliness": {{"applicable": true/false, "currentness_usable": "yes|no|unknown", "judgment": "..."}},
  "suspected_causes": ["A","B","C","D","E","F","G","H"],
  "cause_confidence": {{"A": "strong|moderate|weak|unknown", "B": "...", "C": "...", "D": "...", "E": "...", "F": "...", "G": "...", "H": "..."}},
  "primary_cause": "A|B|C|D|E|F|G|H",
  "recommended_investigation_not_fix": "次に調べるべき箇所（修正しない）"
}}

--- コード抜粋 ---
{code}

--- 実測ログ ---
{evidence}
"""

SYN_PROMPT = """12ケースのコード読解＋ケース分析を統合せよ。事前結論の繰り返し禁止。

出力スキーマ:
{{
  "final_ranking_text": "最有力:\\n...\\n次点:\\n...\\n補助:\\n...\\n否定的:\\n...",
  "ranking": [
    {{"category": "A|B|C|D|E|F|G|H", "role": "最有力|次点|補助|否定的", "confidence": "strong|moderate|weak|unknown", "code_evidence": "...", "log_evidence": "...", "n_cases": 0, "evidence_kind": "both_supported|..."}}
  ],
  "overall_why": "現在のコードでこの結果になる理由",
  "patterns": {{
    "api_no_or_few_candidates": "...",
    "snippet_empty_but_hits": "...",
    "ranking_dropped": "...",
    "page_text_but_snippet_empty": "...",
    "ja_en": "...",
    "time_sensitive": "...",
    "handoff_count_vs_content": "..."
  }},
  "cause_then_code_then_log_then_investigate": [
    {{"cause": "...", "code": "...", "log": "...", "investigate": "..."}}
  ],
  "qwen_uncertainty": "...",
  "next_one_investigation": "..."
}}

--- コード要点（再掲は短い） ---
{code_short}

--- 日英比較実験（機械件数） ---
{ja_en}

--- ケース分析 ---
{cases}
"""

COMPARE_PROMPT = """以前の「観測データのみ」のQwen3分析と、今回の「コード＋ログ」分析を比較せよ。どちらが正しいかは断定しない。

以前の合成:
{prev}

今回の合成:
{curr}

ケース別 primary_cause（今回）:
{primaries}

出力スキーマ:
{{
  "table": {{
    "C": {{"data_only": "...", "code_plus_log": "...", "changed": true/false, "more_specific": true/false}},
    "A": {{"data_only": "...", "code_plus_log": "...", "changed": true/false, "more_specific": true/false}},
    "B": {{"data_only": "...", "code_plus_log": "...", "changed": true/false, "more_specific": true/false}},
    "D": {{"data_only": "...", "code_plus_log": "...", "changed": true/false, "more_specific": true/false}},
    "日本語": {{"data_only": "...", "code_plus_log": "...", "changed": true/false, "more_specific": true/false}},
    "時間依存": {{"data_only": "...", "code_plus_log": "...", "changed": true/false, "more_specific": true/false}},
    "その他": {{"data_only": "...", "code_plus_log": "...", "changed": true/false, "more_specific": true/false}}
  }},
  "became_more_specific": "...",
  "still_wrong_or_uncertain": "...",
  "level1_facts_ok": "yes|partial|no",
  "level2_split_ok": "yes|partial|no",
  "level3_priority_ok": "yes|partial|no",
  "level4_human_next_step": "人間判断待ち。Qwen提案は..."
}}
"""


def mechanical_notes(records: list[dict]) -> dict:
    """ハーネス側の機械照合。Qwen判断ではない。"""
    empty_snip_all = []
    extract_true = []
    dropped_snip = []
    few_api = []
    for rec in records:
        cid = rec["case_id"]
        mo = rec.get("machine_observation") or {}
        if mo.get("snippet_empty_in_return") and not mo.get("snippet_nonempty_in_return"):
            empty_snip_all.append(cid)
        if mo.get("page_has_text_but_snippet_empty_probe"):
            extract_true.append(cid)
        if (mo.get("dropped_with_snippet") or 0) > 0:
            dropped_snip.append(cid)
        if (rec.get("api_candidate_count") or 0) <= 3:
            few_api.append(cid)
    return {
        "return_all_snippet_empty": empty_snip_all,
        "extract_true_cases": extract_true,
        "ranking_dropped_with_snippet": dropped_snip,
        "api_le_3": few_api,
        "wb02_note": "WB02 は return snippet 全件非空。extract True は A03/A04/C04。",
        "e04_handoff": "E04 は return件数=LLM受領件数。件数削減は観測されない。",
        "time_sensitive_ids": [
            r["case_id"] for r in records if r.get("time_sensitive")
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="qwen3_8b")
    parser.add_argument("--num-ctx", type=int, default=24576)
    parser.add_argument("--num-predict", type=int, default=3072)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    profile = get_llm_profile(args.model_id)
    model = profile["model"]
    client = Client(timeout=args.timeout)

    data = json.loads((DIAG / "review_dataset.json").read_text(encoding="utf-8"))
    records = {r["case_id"]: r for r in data.get("records") or []}
    rec_list = [records[c] for c in CASE_IDS if c in records]

    code_pack = build_code_pack()
    code_short = "\n".join(
        [
            "search_web -> general_web_search",
            "backends: DDG Instant Answer, Wiki JA OpenSearch, Wiki EN OpenSearch",
            "compact_hit: title/snippet/url/backend; no page GET",
            "hit if title or snippet; empty snippet kept",
            "score: query substring in title/snippet; positive scores only if any >0",
            "return_limit default 5; Agent json.dumps(full result)",
            "no retry in search_web; harness may suggest English encyclopedia query",
        ]
    )

    print(f"model={model} code analysis ...")
    code_analysis = chat_json(
        client=client,
        model=model,
        user=CODE_PROMPT.format(code=code_pack),
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
    )

    case_analyses = []
    for cid in CASE_IDS:
        rec = records.get(cid)
        if not rec:
            print(f"SKIP {cid}")
            continue
        ranking = load_ranking_rows(cid)
        evidence = build_case_evidence(rec, ranking)
        print(f"case {cid} ...")
        analysis = chat_json(
            client=client,
            model=model,
            user=CASE_PROMPT.format(code=code_pack, evidence=evidence),
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
        )
        analysis.setdefault("case_id", cid)
        analysis.setdefault("request", rec.get("request"))
        analysis.setdefault("query", rec.get("query"))
        case_analyses.append(analysis)

    case_blob = json.dumps(
        [
            {
                "case_id": c.get("case_id"),
                "primary_cause": c.get("primary_cause"),
                "suspected_causes": c.get("suspected_causes"),
                "cause_confidence": c.get("cause_confidence"),
                "why": (c.get("why_this_result") or "")[:400],
                "handoff_useful": (c.get("handoff_stage") or {}).get("content_useful_to_llm"),
                "timeliness": c.get("timeliness"),
            }
            for c in case_analyses
        ],
        ensure_ascii=False,
        indent=2,
    )

    print("synthesis ...")
    synthesis = chat_json(
        client=client,
        model=model,
        user=SYN_PROMPT.format(
            code_short=code_short, ja_en=JA_EN_TABLE, cases=case_blob
        ),
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
    )

    prev_path = DIAG / "llm_diagnosis" / "llm_diagnosis.json"
    prev = json.loads(prev_path.read_text(encoding="utf-8"))
    prev_syn = {
        k: v
        for k, v in (prev.get("synthesis") or {}).items()
        if not str(k).startswith("_")
    }
    print("compare ...")
    comparison = chat_json(
        client=client,
        model=model,
        user=COMPARE_PROMPT.format(
            prev=json.dumps(prev_syn, ensure_ascii=False),
            curr=json.dumps(
                {k: v for k, v in synthesis.items() if not str(k).startswith("_")},
                ensure_ascii=False,
            ),
            primaries=json.dumps(
                {c.get("case_id"): c.get("primary_cause") for c in case_analyses},
                ensure_ascii=False,
            ),
        ),
        num_ctx=min(args.num_ctx, 16384),
        num_predict=2048,
    )

    mech = mechanical_notes(rec_list)
    payload = {
        "generated_at": _now(),
        "model": model,
        "model_id": args.model_id,
        "files_read": [
            "tools/system/network/search_web.py",
            "tools/system/network/general_web_search.py",
            "tools/system/tool_builder/research/web.py",
            "agent.py",
            "run_web_effect_pilot.py (_suggest_search_query)",
            "tools/system/capability_route_obs.py",
            "raw_api/*.json via review_dataset.json records",
            "stage_trace via records",
            "ranking_comparison.csv",
            "SUMMARY.md ja_en table",
        ],
        "implementation_changed": False,
        "llm_diagnosis_dir_unchanged": True,
        "code_analysis": code_analysis,
        "case_analyses": case_analyses,
        "synthesis": synthesis,
        "comparison_with_data_only_qwen": comparison,
        "mechanical_crosscheck_not_qwen": mech,
        "layers": {
            "機械観測": "review_dataset / stage_trace / ranking_comparison",
            "コード": "search_web / general_web_search / compact_hit / agent json.dumps",
            "Qwen3解釈": "code_analysis / case_analyses / synthesis",
            "人間判断": "HUMAN_DECISION_SHEET.md 未記入",
        },
    }

    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "llm_code_diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    write_markdowns(
        code_analysis,
        case_analyses,
        synthesis,
        comparison,
        mech,
        model,
        rec_list,
    )
    print(f"done -> {HERE}")
    return 0


def _jblock(title: str, block: dict | None) -> str:
    block = block or {}
    lines = [
        f"### {title}",
        f"**判断:** {block.get('judgment') or ''}",
        f"**evidence:** {block.get('evidence') or ''}",
    ]
    if block.get("why_low_score"):
        lines.append(f"**低score理由:** {block.get('why_low_score')}")
    if block.get("snippet_empty_vs_page_body"):
        lines.append(f"**snippet空 vs 本文:** {block.get('snippet_empty_vs_page_body')}")
    if block.get("content_useful_to_llm"):
        lines.append(f"**LLM中身の有用性:** {block.get('content_useful_to_llm')}")
    if block.get("where_difference"):
        lines.append(f"**差の段階:** {block.get('where_difference')}")
    lines.append("**観測事実:**")
    for x in block.get("observed_facts") or []:
        lines.append(f"- {x}")
    lines.append("**推測:**")
    for x in block.get("speculation") or []:
        lines.append(f"- {x}")
    return "\n".join(lines)


def write_markdowns(
    code_analysis: dict,
    cases: list[dict],
    synthesis: dict,
    comparison: dict,
    mech: dict,
    model: str,
    rec_list: list[dict],
) -> None:
    ca = {k: v for k, v in code_analysis.items() if not str(k).startswith("_")}
    code_md = [
        "# CODE_ANALYSIS",
        "",
        f"- model: `{model}`",
        f"- generated: `{_now()}`",
        "",
        "## Qwen3 によるコード読解（解釈層）",
        "",
        json.dumps(ca, ensure_ascii=False, indent=2),
        "",
        "## ハーネスが渡したコード事実（Qwen判断ではない）",
        "",
        "- Agent 公開 `search_web` は `general_web_search` を呼ぶ",
        "- 本文スクレイピング / Wikipedia extracts は本番経路に無い",
        "- compact_hit は title/snippet/url/backend のみ",
        "- ranking は query 部分一致スコア、score>0 優先、return_limit=5",
        "- LLM へは `json.dumps(result)` 全文。stdout 要約は表示専用",
        "- クエリ英語化はハーネス `_suggest_search_query`。本体は翻訳しない",
        "",
    ]
    (HERE / "CODE_ANALYSIS.md").write_text("\n".join(code_md), encoding="utf-8")

    case_md = ["# CASE_ANALYSIS", "", f"- model: `{model}`", ""]
    for c in cases:
        case_md.extend(
            [
                f"## {c.get('case_id')}",
                "",
                f"- request: {c.get('request')}",
                f"- query: {c.get('query')}",
                f"- primary_cause: {c.get('primary_cause')}",
                f"- suspected: {c.get('suspected_causes')}",
                f"- confidence: {c.get('cause_confidence')}",
                "",
                "### なぜこの結果か",
                "",
                c.get("why_this_result") or "",
                "",
                _jblock("API", c.get("api_stage")),
                "",
                _jblock("ranking", c.get("ranking_stage")),
                "",
                _jblock("内容取得", c.get("content_stage")),
                "",
                _jblock("LLM受け渡し", c.get("handoff_stage")),
                "",
                _jblock("query/言語", c.get("query_language_stage")),
                "",
                f"### 時間依存\n{json.dumps(c.get('timeliness') or {}, ensure_ascii=False)}",
                "",
                f"### 次の調査（修正しない）\n{c.get('recommended_investigation_not_fix') or ''}",
                "",
                "---",
                "",
            ]
        )
    (HERE / "CASE_ANALYSIS.md").write_text("\n".join(case_md), encoding="utf-8")

    syn = {k: v for k, v in synthesis.items() if not str(k).startswith("_")}
    cmp_ = {k: v for k, v in comparison.items() if not str(k).startswith("_")}
    diag_md = [
        "# LLM_CODE_DIAGNOSIS",
        "",
        f"- model: `{model}`",
        f"- generated: `{_now()}`",
        "- 実装変更: なし",
        "",
        "## 層の分離",
        "",
        "| 層 | 内容 |",
        "|----|------|",
        "| 機械観測 | 件数・snippet有無・ranking脱落・extracts |",
        "| コード | search_web 経路の実装 |",
        "| Qwen3解釈 | 下記 ① |",
        "| 人間判断 | 未実施（HUMAN_DECISION_SHEET） |",
        "",
        "## ① Qwen3の最終結論",
        "",
        "```text",
        syn.get("final_ranking_text") or json.dumps(syn.get("ranking"), ensure_ascii=False, indent=2),
        "```",
        "",
        "## ② 根拠",
        "",
    ]
    for item in syn.get("ranking") or []:
        diag_md.extend(
            [
                f"### {item.get('category')} ({item.get('role')}, {item.get('confidence')})",
                f"- コード: {item.get('code_evidence')}",
                f"- ログ: {item.get('log_evidence')}",
                f"- ケース数: {item.get('n_cases')}",
                f"- 整合性: {item.get('evidence_kind')}",
                "",
            ]
        )
    diag_md.extend(
        [
            "## なぜこうなるか（Qwen）",
            "",
            syn.get("overall_why") or "",
            "",
            "## パターン",
            "",
            json.dumps(syn.get("patterns") or {}, ensure_ascii=False, indent=2),
            "",
            "## 原因 → コード → ログ → 調査箇所",
            "",
            json.dumps(syn.get("cause_then_code_then_log_then_investigate") or [], ensure_ascii=False, indent=2),
            "",
            "## ③ コードとログの整合性（Qwenラベル）",
            "",
            "各 ranking 項目の evidence_kind を参照。",
            "",
            "## ④ Qwen3自身の不確実性",
            "",
            syn.get("qwen_uncertainty") or "",
            "",
            f"次に1つ調査: {syn.get('next_one_investigation') or ''}",
            "",
            "## 以前のQwen3（データのみ）との比較（Qwen）",
            "",
            json.dumps(cmp_, ensure_ascii=False, indent=2),
            "",
            "## ハーネス機械照合（Qwen判断ではない）",
            "",
            json.dumps(mech, ensure_ascii=False, indent=2),
            "",
            "### 過去の取り違え再発チェック（機械）",
            "",
            f"- WB02 を extract True / snippet空の代表にすると誤り。実測 extract True: {mech.get('extract_true_cases')}",
            f"- 時間依存ケースID: {mech.get('time_sensitive_ids')}。snippet全空なら現在性材料は不足し得る。",
            f"- E04 D: {mech.get('e04_handoff')}",
            "",
        ]
    )
    (HERE / "LLM_CODE_DIAGNOSIS.md").write_text("\n".join(diag_md), encoding="utf-8")

    fields = [
        "case_id",
        "request",
        "query",
        "primary_cause",
        "suspected_causes",
        "conf_A",
        "conf_B",
        "conf_C",
        "conf_D",
        "conf_E",
        "conf_F",
        "handoff_useful",
        "timeliness_usable",
        "why_short",
    ]
    with (HERE / "llm_code_diagnosis.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in cases:
            conf = c.get("cause_confidence") or {}
            tl = c.get("timeliness") or {}
            w.writerow(
                {
                    "case_id": c.get("case_id"),
                    "request": c.get("request"),
                    "query": c.get("query"),
                    "primary_cause": c.get("primary_cause"),
                    "suspected_causes": "|".join(c.get("suspected_causes") or []),
                    "conf_A": conf.get("A"),
                    "conf_B": conf.get("B"),
                    "conf_C": conf.get("C"),
                    "conf_D": conf.get("D"),
                    "conf_E": conf.get("E"),
                    "conf_F": conf.get("F"),
                    "handoff_useful": (c.get("handoff_stage") or {}).get(
                        "content_useful_to_llm"
                    ),
                    "timeliness_usable": tl.get("currentness_usable"),
                    "why_short": (c.get("why_this_result") or "")[:200],
                }
            )

    human = [
        "# HUMAN_DECISION_SHEET",
        "",
        "人間レビュー用。Qwen3の結論を正解としない。まだ最終判断・修正は行わない前提の記入欄。",
        "",
        "## 私の判断（全体）",
        "",
        "### 最も問題だと思う箇所",
        "",
        "（記入: A/B/C/D/E/F/G/H）",
        "",
        "自由記述:",
        "",
        "",
        "### 次に問題だと思う箇所",
        "",
        "（記入）",
        "",
        "自由記述:",
        "",
        "",
        "### Qwen3と同意する点",
        "",
        "（記入）",
        "",
        "### Qwen3と異なる点",
        "",
        "（記入）",
        "",
        "### 追加確認が必要な点",
        "",
        "（記入）",
        "",
        "### 今すぐ修正すべきだと思う点",
        "",
        "（記入。本実験では実行しない）",
        "",
        "### まだ修正しない方がよい点",
        "",
        "（記入）",
        "",
        "---",
        "",
        "## Qwen3結論メモ（参照）",
        "",
        "```text",
        syn.get("final_ranking_text") or "",
        "```",
        "",
        "---",
        "",
        "## ケース別",
        "",
    ]
    for c in cases:
        human.extend(
            [
                f"### {c.get('case_id')}: {(c.get('request') or '')[:60]}",
                "",
                f"- Qwen primary: {c.get('primary_cause')} / suspected: {c.get('suspected_causes')}",
                f"- Qwen why: {(c.get('why_this_result') or '')[:180]}",
                "",
                "最も問題だと思う箇所:",
                "",
                "次に問題だと思う箇所:",
                "",
                "Qwen3と同意する点:",
                "",
                "Qwen3と異なる点:",
                "",
                "追加確認:",
                "",
                "---",
                "",
            ]
        )
    (HERE / "HUMAN_DECISION_SHEET.md").write_text("\n".join(human), encoding="utf-8")

    (HERE / "README.md").write_text(
        "\n".join(
            [
                "# llm_code_diagnosis",
                "",
                "Qwen3:8b に search_web 実装コードと実測ログを直接読ませる原因調査。",
                "",
                "**実装変更なし。** `llm_diagnosis/` は変更しない。",
                "",
                "```text",
                "python run_llm_code_diagnosis.py --model-id qwen3_8b",
                "```",
                "",
                "pipeline.yaml の active_model には依存しない（qwen3_8b を明示）。",
                "",
                "出力: CODE_ANALYSIS.md CASE_ANALYSIS.md LLM_CODE_DIAGNOSIS.md",
                "llm_code_diagnosis.json/csv HUMAN_DECISION_SHEET.md",
                "",
                "層: 機械観測 / コード / Qwen3解釈 / 人間判断 を分離して記録。",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
