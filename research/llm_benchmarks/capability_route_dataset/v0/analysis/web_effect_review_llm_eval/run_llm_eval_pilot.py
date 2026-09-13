"""
Web検索結果・LLM評価一致度パイロット（評価専用・実装変更なし）。

- 既存11件の評価カードを生成し、レビュー専用LLMで Q1–Q7 を記録
- 人間レビューが未入力なら agreement は空欄（推測禁止）
- heuristic / Gate / Pipeline / search_web 実装は変更しない
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import chat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NORMALIZED = ROOT / "web_effect_review" / "normalized" / "review_dataset.json"
HITS_JSON = ROOT / "web_effect_review" / "web_effect_review_hits.json"
PILOT_CASES = HERE / "pilot_11_cases.json"
HUMAN_CSV_CANDIDATES = [
    ROOT / "web_effect_review" / "normalized" / "review_worksheet.csv",
    ROOT / "web_effect_review_human" / "review_worksheet.csv",
]

Q1 = ["◎ 十分に有用", "○ 有用", "△ 少しだけ有用", "× ほぼ無用", "？ 本文なし等で判断不能"]
Q2 = ["◎ 明確に改善", "○ 改善", "△ ほぼ変化なし", "× 劣化", "？ 判断不能"]
Q3 = ["◎ 明確に利用している", "○ 一部利用している", "△ 利用したか不明", "× 利用していない"]
Q4 = ["◎ 十分", "○ ほぼ十分", "△ 不足がある", "× 明確に不足", "？ 判断不能"]
Q5 = ["WEBなし", "WEBあり", "どちらでもよい", "判断不能"]
Q6 = [
    "本文なし",
    "質問と無関係",
    "情報不足",
    "情報が古い可能性",
    "検索結果が少ない",
    "英語のみ",
    "日本語情報不足",
    "その他",
    "問題なし",
]
Q7 = [
    "改善なし",
    "冗長化",
    "回答が曖昧になった",
    "公式情報への丸投げ",
    "検索結果を十分利用していない",
    "検索結果と回答が噛み合っていない",
    "情報が増えて改善",
    "その他",
    "問題なし",
]

HUMAN_TO_LLM_MAP = {
    "検索結果の関係性": "q1_search_usefulness",
    "回答材料として使えそうか": "q1_search_usefulness_alt",
    "Webで情報が増えたか": "q2_web_improvement",
    "Webなしでも十分か": "q4_without_sufficient",
    "どちらを採用したいか": "q5_preference",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msg_content(response) -> str:
    msg = getattr(response, "message", None)
    if msg is None:
        return ""
    c = getattr(msg, "content", None)
    return "" if c is None else str(c)


def load_pilot_case_ids() -> list[str]:
    data = json.loads(PILOT_CASES.read_text(encoding="utf-8"))
    return list(data.get("case_ids") or [])


def load_cases(case_ids: list[str]) -> list[dict]:
    if NORMALIZED.is_file():
        data = json.loads(NORMALIZED.read_text(encoding="utf-8"))
        by_id = {c["case_id"]: c for c in data.get("cases") or []}
        if all(cid in by_id for cid in case_ids):
            return [by_id[cid] for cid in case_ids]
    data = json.loads(HITS_JSON.read_text(encoding="utf-8"))
    by_id = {c["case_id"]: c for c in data.get("cases") or []}
    out = []
    for cid in case_ids:
        c = by_id.get(cid)
        if not c:
            raise KeyError(f"missing case {cid}")
        ws = c.get("web_search") or {}
        res = ws.get("result") or {}
        hits = res.get("hits") if isinstance(res.get("hits"), list) else []
        out.append(
            {
                "case_id": cid,
                "observation_id": f"webeffect-hits-{cid}",
                "request": c.get("request") or "",
                "answer_without_web": c.get("answer_without_web") or "",
                "answer_with_web": c.get("answer_with_web") or "",
                "search_query": ws.get("query") or res.get("query") or "",
                "search_results_raw": hits,
                "normalized_hits": None,
            }
        )
    return out


def hit_body_for_card(hit: dict) -> str:
    if not isinstance(hit, dict):
        return "【本文なし】"
    for key in ("original_text", "snippet", "description", "body", "content"):
        val = hit.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return "【本文なし】"


def build_evaluation_card(case: dict) -> str:
    lines = [
        "### 質問",
        "",
        case.get("request") or "",
        "",
        "### Webなし回答",
        "",
        case.get("answer_without_web") or "",
        "",
        "### 検索クエリ",
        "",
        case.get("search_query") or "",
        "",
        "### 検索結果",
        "",
    ]
    hits = case.get("normalized_hits")
    if hits:
        total = len(hits)
        for h in hits:
            idx = h.get("index") or 0
            lines.extend(
                [
                    f"#### 検索結果 {idx} / {total}",
                    f"タイトル: {h.get('title') or ''}",
                    f"サイト: {h.get('site') or ''}",
                    f"URL: {h.get('url') or ''}",
                    "本文:",
                    h.get("original_text_display")
                    if h.get("content_status") == "available"
                    and (h.get("original_text_display") or "").strip()
                    else "【本文なし】",
                    "",
                ]
            )
    else:
        raw = case.get("search_results_raw") or []
        total = len(raw)
        for i, hit in enumerate(raw, 1):
            title = (hit or {}).get("title") if isinstance(hit, dict) else ""
            url = (hit or {}).get("url") if isinstance(hit, dict) else ""
            site = ""
            if url:
                try:
                    from urllib.parse import urlparse

                    host = urlparse(str(url)).netloc or ""
                    site = host[4:] if host.startswith("www.") else host
                except Exception:  # noqa: BLE001
                    site = ""
            body = hit_body_for_card(hit if isinstance(hit, dict) else {})
            lines.extend(
                [
                    f"#### 検索結果 {i} / {total}",
                    f"タイトル: {title}",
                    f"サイト: {site}",
                    f"URL: {url}",
                    "本文:",
                    body,
                    "",
                ]
            )
    lines.extend(
        [
            "### Webあり回答",
            "",
            case.get("answer_with_web") or "",
            "",
        ]
    )
    return "\n".join(lines).strip()


def load_human_reviews() -> dict[str, dict]:
    """人間記入済み列のみ読む。空欄は推測しない。"""
    out: dict[str, dict] = {}
    if NORMALIZED.is_file():
        data = json.loads(NORMALIZED.read_text(encoding="utf-8"))
        for case in data.get("cases") or []:
            cid = case.get("case_id")
            if not cid:
                continue
            human = {}
            for col, key in HUMAN_TO_LLM_MAP.items():
                val = str(case.get(col) or "").strip()
                if val:
                    human[key] = val
            if human:
                out[cid] = human
    for path in HUMAN_CSV_CANDIDATES:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            id_key = "ケースID" if "ケースID" in (reader.fieldnames or []) else "case_id"
            for row in reader:
                cid = (row.get(id_key) or "").strip()
                if not cid:
                    continue
                human = {}
                for col, key in HUMAN_TO_LLM_MAP.items():
                    val = (row.get(col) or "").strip()
                    if val:
                        human[key] = val
                if human:
                    out[cid] = human
    return out


def extract_json_object(text: str) -> dict | None:
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


def llm_evaluate_card(card_text: str, *, model: str, retries: int = 2) -> dict:
    schema = {
        "q1_search_usefulness": "Q1選択肢のいずれか",
        "q1_reason": "短い日本語",
        "q2_web_improvement": "Q2選択肢",
        "q2_reason": "短い日本語",
        "q3_result_used_in_answer": "Q3選択肢",
        "q3_reason": "短い日本語",
        "q4_without_sufficient": "Q4選択肢",
        "q4_reason": "短い日本語",
        "q5_preference": "Q5選択肢",
        "q5_reason": "短い日本語",
        "q6_search_result_issues": ["Q6から複数"],
        "q6_reason": "短い日本語",
        "q7_web_caused_issues": ["Q7から複数"],
        "q7_reason": "短い日本語",
    }
    prompt = f"""あなたはWeb検索効果のレビュー専用評価者です。
以下の評価カードだけを根拠に、JSONだけを出力してください。

厳守:
- 検索結果本文に無い情報をタイトル/URLから推測しない
- 本文が【本文なし】なら、有用性は原則「？ 本文なし等で判断不能」または「× ほぼ無用」
- 「Webを使うべきか」ではなく、提示された完成回答の品質変化を評価する
- 検索機能改善・heuristic変更の提案は書かない

Q1: {" / ".join(Q1)}
Q2: {" / ".join(Q2)}
Q3: {" / ".join(Q3)}
Q4: {" / ".join(Q4)}
Q5: {" / ".join(Q5)}
Q6(複数): {" / ".join(Q6)}
Q7(複数): {" / ".join(Q7)}

出力JSONキー例:
{json.dumps(schema, ensure_ascii=False, indent=2)}

--- 評価カード ---
{card_text}
"""
    last_raw = ""
    for attempt in range(retries + 1):
        extra = ""
        if attempt:
            extra = "\n前回はJSON解析に失敗しました。必ず有効なJSONオブジェクト1つだけを出力してください。"
        response = chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "JSONのみ出力。評価根拠はカード内の明示情報に限定。",
                },
                {"role": "user", "content": prompt + extra},
            ],
        )
        last_raw = _msg_content(response)
        parsed = extract_json_object(last_raw)
        if parsed and parsed.get("q1_search_usefulness"):
            parsed["_raw_llm_output"] = last_raw
            return parsed
    return {"_raw_llm_output": last_raw}


def validate_choice(value: str, allowed: list[str]) -> str:
    v = str(value or "").strip()
    if v in allowed:
        return v
    for a in allowed:
        if v and v in a:
            return a
    return v


def normalize_llm_eval(parsed: dict) -> dict:
    q6 = parsed.get("q6_search_result_issues") or []
    q7 = parsed.get("q7_web_caused_issues") or []
    if isinstance(q6, str):
        q6 = [q6] if q6.strip() else []
    if isinstance(q7, str):
        q7 = [q7] if q7.strip() else []
    return {
        "q1_search_usefulness": validate_choice(parsed.get("q1_search_usefulness"), Q1),
        "q1_reason": str(parsed.get("q1_reason") or "").strip(),
        "q2_web_improvement": validate_choice(parsed.get("q2_web_improvement"), Q2),
        "q2_reason": str(parsed.get("q2_reason") or "").strip(),
        "q3_result_used_in_answer": validate_choice(
            parsed.get("q3_result_used_in_answer"), Q3
        ),
        "q3_reason": str(parsed.get("q3_reason") or "").strip(),
        "q4_without_sufficient": validate_choice(parsed.get("q4_without_sufficient"), Q4),
        "q4_reason": str(parsed.get("q4_reason") or "").strip(),
        "q5_preference": validate_choice(parsed.get("q5_preference"), Q5),
        "q5_reason": str(parsed.get("q5_reason") or "").strip(),
        "q6_search_result_issues": [
            validate_choice(x, Q6) for x in q6 if str(x).strip()
        ],
        "q6_reason": str(parsed.get("q6_reason") or "").strip(),
        "q7_web_caused_issues": [
            validate_choice(x, Q7) for x in q7 if str(x).strip()
        ],
        "q7_reason": str(parsed.get("q7_reason") or "").strip(),
        "not_agent_judgment": True,
        "not_auto_improvement_recommendation": True,
    }


def agreement(human: str | None, llm: str | None) -> str:
    if not (human and str(human).strip()) or not (llm and str(llm).strip()):
        return ""
    return "一致" if human.strip() == llm.strip() else "不一致"


def build_all_cards(case_ids: list[str]) -> list[dict]:
    cases = load_cases(case_ids)
    return [
        {
            "case_id": case["case_id"],
            "observation_id": case["observation_id"],
            "evaluation_card": build_evaluation_card(case),
        }
        for case in cases
    ]


def merge_evaluations(new_evals: list[dict], *, pilot_ids: list[str]) -> list[dict]:
    existing_path = HERE / "llm_evaluation.json"
    by_id = {e["case_id"]: e for e in new_evals}
    if existing_path.is_file():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        for e in existing.get("evaluations") or []:
            by_id.setdefault(e["case_id"], e)
    return [by_id[cid] for cid in pilot_ids if cid in by_id]


def write_outputs(
    *,
    cases: list[dict],
    cards: list[dict],
    evals: list[dict],
    human: dict[str, dict],
) -> None:
    HERE.mkdir(parents=True, exist_ok=True)

    md_cards = ["# LLM評価用カード（11件）", ""]
    for item in cards:
        md_cards.append(f"## Case {item['case_id']}")
        md_cards.append("")
        md_cards.append(item["evaluation_card"])
        md_cards.append("")
        md_cards.append("---")
        md_cards.append("")
    (HERE / "evaluation_cards.md").write_text("\n".join(md_cards), encoding="utf-8")

    payload = {
        "kind": "web_effect_llm_eval_pilot",
        "ts": _now(),
        "case_count": len(evals),
        "model": evals[0].get("model") if evals else None,
        "not_connected_to_agent_gate_pipeline": True,
        "human_review_not_inferred": True,
        "evaluations": evals,
    }
    (HERE / "llm_evaluation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    csv_fields = [
        "case_id",
        "observation_id",
        "request",
        "q1_search_usefulness",
        "q1_reason",
        "q2_web_improvement",
        "q2_reason",
        "q3_result_used_in_answer",
        "q3_reason",
        "q4_without_sufficient",
        "q4_reason",
        "q5_preference",
        "q5_reason",
        "q6_search_result_issues",
        "q7_web_caused_issues",
    ]
    with (HERE / "llm_evaluation.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=csv_fields)
        w.writeheader()
        for e in evals:
            w.writerow(
                {
                    "case_id": e["case_id"],
                    "observation_id": e["observation_id"],
                    "request": e["request"],
                    "q1_search_usefulness": e["llm"]["q1_search_usefulness"],
                    "q1_reason": e["llm"]["q1_reason"],
                    "q2_web_improvement": e["llm"]["q2_web_improvement"],
                    "q2_reason": e["llm"]["q2_reason"],
                    "q3_result_used_in_answer": e["llm"]["q3_result_used_in_answer"],
                    "q3_reason": e["llm"]["q3_reason"],
                    "q4_without_sufficient": e["llm"]["q4_without_sufficient"],
                    "q4_reason": e["llm"]["q4_reason"],
                    "q5_preference": e["llm"]["q5_preference"],
                    "q5_reason": e["llm"]["q5_reason"],
                    "q6_search_result_issues": ";".join(
                        e["llm"]["q6_search_result_issues"]
                    ),
                    "q7_web_caused_issues": ";".join(e["llm"]["q7_web_caused_issues"]),
                }
            )

    compare_fields = [
        "case_id",
        "metric",
        "human",
        "llm",
        "agreement",
    ]
    compare_rows = []
    metrics = [
        ("Q1", "q1_search_usefulness"),
        ("Q2", "q2_web_improvement"),
        ("Q4", "q4_without_sufficient"),
        ("Q5", "q5_preference"),
    ]
    for e in evals:
        cid = e["case_id"]
        h = human.get(cid) or {}
        for label, key in metrics:
            compare_rows.append(
                {
                    "case_id": cid,
                    "metric": label,
                    "human": h.get(key, ""),
                    "llm": e["llm"].get(key, ""),
                    "agreement": agreement(h.get(key), e["llm"].get(key)),
                }
            )
    with (HERE / "human_vs_llm.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=compare_fields)
        w.writeheader()
        w.writerows(compare_rows)

    # REPORT
    q1_dist = Counter(e["llm"]["q1_search_usefulness"] for e in evals)
    q2_dist = Counter(e["llm"]["q2_web_improvement"] for e in evals)
    q5_dist = Counter(e["llm"]["q5_preference"] for e in evals)
    empty_body_cases = []
    en_only_cases = []
    for e in evals:
        issues = e["llm"].get("q6_search_result_issues") or []
        if "本文なし" in issues:
            empty_body_cases.append(e["case_id"])
        if "英語のみ" in issues or "日本語情報不足" in issues:
            en_only_cases.append(e["case_id"])
    improved = [
        e["case_id"]
        for e in evals
        if e["llm"]["q2_web_improvement"] in ("◎ 明確に改善", "○ 改善")
    ]
    no_change = [
        e["case_id"]
        for e in evals
        if e["llm"]["q2_web_improvement"] == "△ ほぼ変化なし"
    ]
    degraded = [
        e["case_id"]
        for e in evals
        if e["llm"]["q2_web_improvement"] in ("× 劣化",)
    ]
    agree_q1 = [r for r in compare_rows if r["metric"] == "Q1" and r["agreement"]]
    agree_q2 = [r for r in compare_rows if r["metric"] == "Q2" and r["agreement"]]
    agree_q5 = [r for r in compare_rows if r["metric"] == "Q5" and r["agreement"]]
    human_filled_q1 = sum(1 for r in compare_rows if r["metric"] == "Q1" and r["human"])
    human_filled_q2 = sum(1 for r in compare_rows if r["metric"] == "Q2" and r["human"])
    human_filled_q5 = sum(1 for r in compare_rows if r["metric"] == "Q5" and r["human"])

    def rate(agree_list, filled_n):
        if filled_n == 0:
            return "（人間評価未入力のため未計算）"
        match = sum(1 for r in agree_list if r["agreement"] == "一致")
        return f"{match}/{filled_n} = {100*match/filled_n:.0f}%"

    report = [
        "# LLM評価パイロット REPORT",
        "",
        "## 概要",
        "",
        f"- 対象件数: **{len(evals)}**",
        f"- モデル: `{evals[0].get('model') if evals else ''}`",
        "- 実装変更: **なし**（評価資料生成のみ）",
        "- 人間レビュー推測: **なし**",
        "",
        "## Q1–Q7 分布（LLM）",
        "",
        f"- Q1: {dict(q1_dist)}",
        f"- Q2: {dict(q2_dist)}",
        f"- Q5: {dict(q5_dist)}",
        "",
        "## 人間との一致率（完全一致・人間入力がある項目のみ）",
        "",
        f"- Q1: {rate(agree_q1, human_filled_q1)}",
        f"- Q2: {rate(agree_q2, human_filled_q2)}",
        f"- Q5: {rate(agree_q5, human_filled_q5)}",
        "",
        "※ 現在、人間レビューCSVは未入力のため一致率は多く未計算。",
        "",
        "## 観測",
        "",
        f"- 検索結果本文なし（LLM Q6に本文なし）: {empty_body_cases}",
        f"- 英語のみ/日本語不足（LLM Q6）: {en_only_cases}",
        f"- Webありで改善（Q2 ◎/○）: {improved}",
        f"- Webありでほぼ変化なし（Q2 △）: {no_change}",
        f"- Webありで劣化（Q2 ×）: {degraded}",
        "",
        "## 仮説メモ（自動結論なし）",
        "",
        "- A: 本文なしケースで Q1=？ が付くか → 上記 empty_body_cases を参照",
        "- B–E: 人間評価入力後に再集計",
        "",
        "## 次の操作（人間判断）",
        "",
        "1. `llm_evaluation.csv` / `evaluation_cards.md` を確認",
        "2. 人間レビューを `normalized/review_worksheet.csv` に記入",
        "3. 本スクリプトを再実行して `human_vs_llm.csv` の一致率を得る",
        "",
    ]
    (HERE / "REPORT.md").write_text("\n".join(report), encoding="utf-8")

    (HERE / "README.md").write_text(
        "\n".join(
            [
                "# Web検索結果・LLM評価一致度パイロット",
                "",
                "目的: 人間レビューと同等の判断を別LLMが再現できるか測る（**実装変更なし**）。",
                "",
                "- 対象: `pilot_11_cases.json` の11件",
                "- 入力: `web_effect_review/normalized/review_dataset.json`",
                "- CSVをLLMに直接渡さず `evaluation_cards.md` 形式で評価",
                "- 人間未入力時は agreement 空欄",
                "",
                "## 実行",
                "",
                "```text",
                "python run_llm_eval_pilot.py",
                "python run_llm_eval_pilot.py --dry-run",
                "```",
                "",
                "## 出力",
                "",
                "| ファイル | 内容 |",
                "|----------|------|",
                "| evaluation_cards.md | 評価カード |",
                "| llm_evaluation.json / .csv | LLM評価 |",
                "| human_vs_llm.csv | 人間比較 |",
                "| REPORT.md | 集計 |",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="cards only, no LLM")
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="evaluate only these case_id (repeatable)",
    )
    args = parser.parse_args(argv)

    profile = get_llm_profile()
    model = profile["model"]
    case_ids = args.case_id or load_pilot_case_ids()
    cases = load_cases(case_ids)
    human = load_human_reviews()

    cards = []
    evals = []
    for case in cases:
        card_text = build_evaluation_card(case)
        cards.append(
            {
                "case_id": case["case_id"],
                "observation_id": case["observation_id"],
                "evaluation_card": card_text,
            }
        )
        if args.dry_run:
            continue
        print(f"LLM eval {case['case_id']} ...")
        parsed = llm_evaluate_card(card_text, model=model)
        llm = normalize_llm_eval(parsed)
        evals.append(
            {
                "case_id": case["case_id"],
                "observation_id": case["observation_id"],
                "request": case["request"],
                "model": model,
                "evaluation_card": card_text,
                "llm": llm,
                "human_available": case["case_id"] in human,
            }
        )

    if args.dry_run:
        write_outputs(cases=cases, cards=cards, evals=[], human=human)
        # cards only partial write
        md = ["# LLM評価用カード（dry-run）", ""]
        for item in cards:
            md.append(f"## Case {item['case_id']}\n\n{item['evaluation_card']}\n\n---\n")
        (HERE / "evaluation_cards.md").write_text("\n".join(md), encoding="utf-8")
        print(f"dry-run cards={len(cards)}")
        return 0

    if args.case_id:
        pilot_ids = load_pilot_case_ids()
        evals = merge_evaluations(evals, pilot_ids=pilot_ids)
        cards = build_all_cards(pilot_ids)
        cases = load_cases(pilot_ids)
    else:
        cases = cases

    write_outputs(cases=cases, cards=cards, evals=evals, human=human)
    print(f"done evals={len(evals)} -> {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
