"""
Web検索評価LLM 評価器自己検証。

- 既存11件の原評価は削除しない
- Q1を検索結果本文のみで独立再評価
- Agent / heuristic / Gate / Pipeline / search_web は変更しない
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
PARENT = HERE.parent
ORIGINAL_EVAL = PARENT / "llm_evaluation.json"
PILOT_CASES = PARENT / "pilot_11_cases.json"
NORMALIZED = (
    PARENT.parent / "web_effect_review" / "normalized" / "review_dataset.json"
)

Q1_POSITIVE = ("◎ 十分に有用", "○ 有用")
Q1_ALLOWED_WHEN_NO_EVIDENCE = ("× ほぼ無用", "？ 本文なし等で判断不能")
Q1_CHOICES = [
    "◎ 十分に有用",
    "○ 有用",
    "△ 少しだけ有用",
    "× ほぼ無用",
    "？ 本文なし等で判断不能",
]
Q2_CHOICES = [
    "◎ 明確に改善",
    "○ 改善",
    "△ ほぼ変化なし",
    "× 劣化",
    "？ 判断不能",
]
Q3_CHOICES = [
    "◎ 明確に利用している",
    "○ 一部利用している",
    "△ 利用したか不明",
    "× 利用していない",
]
Q5_CHOICES = ["WEBなし", "WEBあり", "どちらでもよい", "判断不能"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msg_content(response) -> str:
    msg = getattr(response, "message", None)
    if msg is None:
        return ""
    c = getattr(msg, "content", None)
    return "" if c is None else str(c)


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


def validate_choice(value: str, allowed: list[str]) -> str:
    v = str(value or "").strip()
    if v in allowed:
        return v
    for a in allowed:
        if v and (v in a or a in v):
            return a
    return v


def load_pilot_ids() -> list[str]:
    return list(json.loads(PILOT_CASES.read_text(encoding="utf-8")).get("case_ids") or [])


def load_original_evals() -> dict[str, dict]:
    data = json.loads(ORIGINAL_EVAL.read_text(encoding="utf-8"))
    return {e["case_id"]: e for e in data.get("evaluations") or []}


def load_normalized_by_id() -> dict[str, dict]:
    data = json.loads(NORMALIZED.read_text(encoding="utf-8"))
    return {c["case_id"]: c for c in data.get("cases") or []}


def classify_hit(hit: dict) -> dict:
    status = str(hit.get("content_status") or "").strip()
    original = hit.get("original_text")
    display = hit.get("original_text_display")
    text = ""
    if original is not None and str(original).strip():
        text = str(original).strip()
    elif display is not None and str(display).strip() and str(display).strip() != "【本文なし】":
        text = str(display).strip()

    empty_markers = {"", "【本文なし】", "内容なし", "本文なし", "none", "null", "n/a"}
    is_empty_text = (not text) or text.lower() in empty_markers or text == "【本文なし】"

    if status == "available" and not is_empty_text:
        content_class = "has_content"
    elif status in ("empty", "extraction_error", "unknown") or is_empty_text:
        content_class = "empty_content"
    elif not is_empty_text:
        content_class = "has_content"
    else:
        content_class = "empty_content"

    return {
        "index": hit.get("index"),
        "title": hit.get("title") or "",
        "site": hit.get("site") or "",
        "url": hit.get("url") or "",
        "content_status": status or ("empty" if content_class == "empty_content" else "available"),
        "content_class": content_class,
        "body_preview": (text[:120] + "…") if len(text) > 120 else text,
        "body_len": len(text),
    }


def mechanical_inspect(case: dict, original_llm: dict) -> dict:
    hits = case.get("normalized_hits") or []
    classified = [classify_hit(h) for h in hits]
    has_n = sum(1 for h in classified if h["content_class"] == "has_content")
    empty_n = sum(1 for h in classified if h["content_class"] == "empty_content")
    all_empty = len(classified) > 0 and empty_n == len(classified)

    q1 = str((original_llm or {}).get("q1_search_usefulness") or "").strip()
    q1_violation = bool(all_empty and q1 in Q1_POSITIVE)

    return {
        "case_id": case["case_id"],
        "observation_id": case.get("observation_id") or "",
        "request": case.get("request") or "",
        "search_query": case.get("search_query") or "",
        "hit_count": len(classified),
        "has_content_count": has_n,
        "empty_content_count": empty_n,
        "all_hits_empty": all_empty,
        "hits": classified,
        "original_q1": q1,
        "original_q1_reason": str((original_llm or {}).get("q1_reason") or ""),
        "original_q2": str((original_llm or {}).get("q2_web_improvement") or ""),
        "original_q5": str((original_llm or {}).get("q5_preference") or ""),
        "q1_rule_violation_candidate": q1_violation,
    }


def build_q1_only_card(case: dict) -> str:
    """Q1専用: 質問 + 検索結果のみ。Webあり/なし回答は入れない。"""
    lines = [
        "### 質問",
        "",
        case.get("request") or "",
        "",
        "### 検索クエリ",
        "",
        case.get("search_query") or "",
        "",
        "### 検索結果",
        "",
        "※ 以下の本文だけが情報源です。タイトル・URL・サイト名から内容を推測してはいけません。",
        "※ あなた自身の一般知識を検索結果の内容として扱ってはいけません。",
        "",
    ]
    hits = case.get("normalized_hits") or []
    total = len(hits)
    for h in hits:
        idx = h.get("index") or 0
        body = (
            h.get("original_text_display")
            if h.get("content_status") == "available"
            and (h.get("original_text_display") or "").strip()
            else "【本文なし】"
        )
        if not str(body).strip():
            body = "【本文なし】"
        lines.extend(
            [
                f"#### 検索結果 {idx} / {total}",
                f"タイトル: {h.get('title') or ''}",
                f"サイト: {h.get('site') or ''}",
                f"URL: {h.get('url') or ''}",
                "本文:",
                body,
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_q2_card(case: dict) -> str:
    return "\n".join(
        [
            "### 質問",
            "",
            case.get("request") or "",
            "",
            "### Webなし回答",
            "",
            case.get("answer_without_web") or "",
            "",
            "### Webあり回答",
            "",
            case.get("answer_with_web") or "",
            "",
            "※ Q1（検索結果有用性）は既に別途評価済みです。ここでは完成回答同士の品質差だけを評価してください。",
            "※ 検索結果の有用性をこの比較から推測・逆輸入しないでください。",
        ]
    ).strip()


Q1_SYSTEM = """あなたは検索結果の有用性だけを評価する評価者です。
JSONのみ出力してください。

絶対禁止:
- タイトル・URL・サイト名から本文内容を推測すること
- 一般知識を検索結果の内容として扱うこと
- URLを開いたつもりで補完すること
- Webあり回答の良さから検索結果が有用だったと推論すること
- 「この質問について知識がありますか」という観点で評価すること

評価対象は「提示された検索結果本文が、質問への回答材料として使えるか」だけです。
検索結果本文が空（【本文なし】）の場合、その結果から得られる具体的情報は0です。"""


def llm_eval_q1(card: str, *, model: str, retries: int = 2) -> dict:
    prompt = f"""次のカードの検索結果本文だけを根拠に評価してください。

まず内部判定:
- usable_evidence: true または false

usable_evidence=false の条件（いずれか）:
- 全検索結果が本文なし
- 本文があるが質問と無関係
- 本文に回答材料となる具体的情報が存在しない

usable_evidence=true:
- 本文中に質問への回答材料として具体的に利用できる情報が存在する

次に人間向けQ1へ変換:
- usable_evidence=false の場合、Q1は「× ほぼ無用」または「？ 本文なし等で判断不能」のみ
- usable_evidence=true の場合のみ「◎ 十分に有用」「○ 有用」「△ 少しだけ有用」を許可

出力JSON:
{{
  "usable_evidence": true/false,
  "usable_evidence_reason": "短い日本語（本文の有無と関係性のみ）",
  "q1_search_usefulness": "{" / ".join(Q1_CHOICES)}",
  "q1_reason": "短い日本語"
}}

--- 評価カード ---
{card}
"""
    last_raw = ""
    for attempt in range(retries + 1):
        extra = ""
        if attempt:
            extra = "\n前回はJSON解析失敗。有効なJSONオブジェクト1つだけを出力。"
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": Q1_SYSTEM},
                {"role": "user", "content": prompt + extra},
            ],
        )
        last_raw = _msg_content(response)
        parsed = extract_json_object(last_raw)
        if parsed and "usable_evidence" in parsed:
            parsed["_raw_llm_output"] = last_raw
            return parsed
    return {"_raw_llm_output": last_raw}


def llm_eval_q2_plus(card: str, *, model: str, retries: int = 2) -> dict:
    prompt = f"""Webなし完成回答とWebあり完成回答を比較してください。
検索結果の有用性は評価しないでください（Q1とは独立）。

出力JSON:
{{
  "q2_web_improvement": "{" / ".join(Q2_CHOICES)}",
  "q2_reason": "短い日本語",
  "q3_result_used_in_answer": "{" / ".join(Q3_CHOICES)}",
  "q3_reason": "短い日本語（回答テキストの差分から判断。検索結果の有無を推測しない）",
  "q5_preference": "{" / ".join(Q5_CHOICES)}",
  "q5_reason": "短い日本語"
}}

--- 評価カード ---
{card}
"""
    last_raw = ""
    for attempt in range(retries + 1):
        extra = ""
        if attempt:
            extra = "\n前回はJSON解析失敗。有効なJSONオブジェクト1つだけを出力。"
        response = chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "JSONのみ。完成回答同士の品質差だけを評価。検索結果有用性は評価しない。",
                },
                {"role": "user", "content": prompt + extra},
            ],
        )
        last_raw = _msg_content(response)
        parsed = extract_json_object(last_raw)
        if parsed and parsed.get("q2_web_improvement"):
            parsed["_raw_llm_output"] = last_raw
            return parsed
    return {"_raw_llm_output": last_raw}


def enforce_q1_consistency(
    *,
    usable_evidence: bool,
    q1: str,
    all_hits_empty: bool,
) -> tuple[str, str | None]:
    """usable_evidence=false なら ◎/○ を禁止。機械補正した場合は note を返す。"""
    q1 = validate_choice(q1, Q1_CHOICES)
    if usable_evidence:
        return q1, None
    if q1 in Q1_POSITIVE or q1 == "△ 少しだけ有用":
        forced = "？ 本文なし等で判断不能" if all_hits_empty else "× ほぼ無用"
        return forced, (
            f"usable_evidence=false のため Q1={q1!r} を禁止し {forced!r} に補正"
        )
    if q1 not in Q1_ALLOWED_WHEN_NO_EVIDENCE and not q1:
        forced = "？ 本文なし等で判断不能" if all_hits_empty else "× ほぼ無用"
        return forced, f"空/不正なQ1を {forced!r} に補正"
    return q1, None


def normalize_recheck(
    q1_parsed: dict,
    q2_parsed: dict,
    *,
    all_hits_empty: bool,
) -> dict:
    usable_raw = q1_parsed.get("usable_evidence")
    if isinstance(usable_raw, str):
        usable = usable_raw.strip().lower() in ("true", "1", "yes")
    else:
        usable = bool(usable_raw)

    # 機械: 全emptyなら usable_evidence は必ず false
    mechanical_override = False
    if all_hits_empty and usable:
        usable = False
        mechanical_override = True

    q1_raw = validate_choice(q1_parsed.get("q1_search_usefulness"), Q1_CHOICES)
    q1, consistency_note = enforce_q1_consistency(
        usable_evidence=usable, q1=q1_raw, all_hits_empty=all_hits_empty
    )

    return {
        "usable_evidence": usable,
        "usable_evidence_reason": str(q1_parsed.get("usable_evidence_reason") or "").strip(),
        "mechanical_usable_evidence_override": mechanical_override,
        "q1_search_usefulness": q1,
        "q1_reason": str(q1_parsed.get("q1_reason") or "").strip(),
        "q1_before_consistency_fix": q1_raw if consistency_note else None,
        "q1_consistency_note": consistency_note,
        "q2_web_improvement": validate_choice(
            q2_parsed.get("q2_web_improvement"), Q2_CHOICES
        ),
        "q2_reason": str(q2_parsed.get("q2_reason") or "").strip(),
        "q3_result_used_in_answer": validate_choice(
            q2_parsed.get("q3_result_used_in_answer"), Q3_CHOICES
        ),
        "q3_reason": str(q2_parsed.get("q3_reason") or "").strip(),
        "q5_preference": validate_choice(q2_parsed.get("q5_preference"), Q5_CHOICES),
        "q5_reason": str(q2_parsed.get("q5_reason") or "").strip(),
    }


def write_outputs(rows: list[dict], *, model: str) -> None:
    HERE.mkdir(parents=True, exist_ok=True)

    payload = {
        "kind": "web_effect_llm_eval_self_check",
        "ts": _now(),
        "model": model,
        "case_count": len(rows),
        "original_eval_preserved": True,
        "human_comparison_not_run": True,
        "not_connected_to_agent_gate_pipeline": True,
        "cases": rows,
    }
    (HERE / "self_check.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    csv_fields = [
        "case_id",
        "all_hits_empty",
        "has_content_count",
        "empty_content_count",
        "original_q1",
        "recheck_q1",
        "usable_evidence",
        "q1_rule_violation_candidate",
        "q1_changed",
        "recheck_reason",
        "original_q2",
        "recheck_q2",
        "original_q5",
        "recheck_q5",
        "q1_consistency_note",
    ]
    with (HERE / "self_check.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=csv_fields)
        w.writeheader()
        for r in rows:
            orig = r["original_llm_evaluation"]
            rec = r["recheck_llm_evaluation"]
            w.writerow(
                {
                    "case_id": r["case_id"],
                    "all_hits_empty": r["all_hits_empty"],
                    "has_content_count": r["has_content_count"],
                    "empty_content_count": r["empty_content_count"],
                    "original_q1": orig.get("q1_search_usefulness", ""),
                    "recheck_q1": rec.get("q1_search_usefulness", ""),
                    "usable_evidence": rec.get("usable_evidence", ""),
                    "q1_rule_violation_candidate": r["q1_rule_violation_candidate"],
                    "q1_changed": r["q1_changed"],
                    "recheck_reason": r["recheck_reason"],
                    "original_q2": orig.get("q2_web_improvement", ""),
                    "recheck_q2": rec.get("q2_web_improvement", ""),
                    "original_q5": orig.get("q5_preference", ""),
                    "recheck_q5": rec.get("q5_preference", ""),
                    "q1_consistency_note": rec.get("q1_consistency_note") or "",
                }
            )

    # SELF_CHECK.md
    md = [
        "# SELF_CHECK — 評価器自己検証",
        "",
        f"- 生成時刻: `{_now()}`",
        f"- モデル: `{model}`",
        "- 原評価ファイルは削除・上書きしていない",
        "",
        "## 本文なしケース一覧（全ヒット empty）",
        "",
    ]
    empty_cases = [r for r in rows if r["all_hits_empty"]]
    if not empty_cases:
        md.append("（なし）")
    else:
        md.append("| case_id | 原Q1 | 再Q1 | violation候補 | Q1変更 |")
        md.append("|---------|------|------|---------------|--------|")
        for r in empty_cases:
            md.append(
                f"| {r['case_id']} | {r['original_llm_evaluation'].get('q1_search_usefulness','')} "
                f"| {r['recheck_llm_evaluation'].get('q1_search_usefulness','')} "
                f"| {r['q1_rule_violation_candidate']} | {r['q1_changed']} |"
            )
    md.extend(["", "## 全ケース 元評価 → 再評価", ""])
    for r in rows:
        o = r["original_llm_evaluation"]
        n = r["recheck_llm_evaluation"]
        md.extend(
            [
                f"### {r['case_id']}",
                "",
                f"- 質問: {r['request']}",
                f"- has_content={r['has_content_count']} / empty={r['empty_content_count']} / all_empty={r['all_hits_empty']}",
                f"- q1_rule_violation_candidate: **{r['q1_rule_violation_candidate']}**",
                f"- q1_changed: **{r['q1_changed']}**",
                f"- recheck_reason: {r['recheck_reason']}",
                "",
                "| 項目 | 元評価 | 再評価 |",
                "|------|--------|--------|",
                f"| usable_evidence | — | {n.get('usable_evidence')} |",
                f"| Q1 | {o.get('q1_search_usefulness','')} | {n.get('q1_search_usefulness','')} |",
                f"| Q2 | {o.get('q2_web_improvement','')} | {n.get('q2_web_improvement','')} |",
                f"| Q5 | {o.get('q5_preference','')} | {n.get('q5_preference','')} |",
                "",
                f"- 原Q1理由: {o.get('q1_reason','')}",
                f"- 再Q1理由: {n.get('q1_reason','')}",
                "",
            ]
        )
    (HERE / "SELF_CHECK.md").write_text("\n".join(md), encoding="utf-8")

    # REPORT
    viol = [r for r in rows if r["q1_rule_violation_candidate"]]
    changed = [r for r in rows if r["q1_changed"]]
    empty_n = len(empty_cases)
    recheck_positive_on_empty = [
        r
        for r in empty_cases
        if r["recheck_llm_evaluation"].get("q1_search_usefulness") in Q1_POSITIVE
    ]
    consistency_fixes = [
        r for r in rows if r["recheck_llm_evaluation"].get("q1_consistency_note")
    ]

    report = [
        "# SELF_CHECK_REPORT — 評価器自己検証",
        "",
        "## 概要",
        "",
        "- 対象: 既存11件（検索・Agent・heuristic・Gate・Pipeline・既存データは未変更）",
        "- 人間レビュー比較: **未実施**",
        "- 原評価: 保持（`llm_evaluation.json` 未削除）",
        "",
        "## 1. 本文なしケース数（全ヒット empty）",
        "",
        f"**{empty_n}件**: {[r['case_id'] for r in empty_cases]}",
        "",
        "## 2. 本文なしなのに原Q1=◎/○だった件数",
        "",
        f"**{len(viol)}件**: {[r['case_id'] for r in viol]}",
        "",
    ]
    for r in viol:
        report.append(
            f"- `{r['case_id']}`: 原Q1=`{r['original_llm_evaluation'].get('q1_search_usefulness')}` "
            f"/ 理由: {r['original_llm_evaluation'].get('q1_reason','')}"
        )
    report.extend(
        [
            "",
            "## 3. 再評価後（本文なしケースのQ1）",
            "",
        ]
    )
    for r in empty_cases:
        report.append(
            f"- `{r['case_id']}`: `{r['recheck_llm_evaluation'].get('q1_search_usefulness')}` "
            f"(usable_evidence={r['recheck_llm_evaluation'].get('usable_evidence')})"
        )
    report.extend(
        [
            "",
            f"- 再評価後も本文なしでQ1=◎/○のまま: **{len(recheck_positive_on_empty)}件** "
            f"{[r['case_id'] for r in recheck_positive_on_empty]}",
            "",
            "## 4. Q1変更件数",
            "",
            f"**{len(changed)}件**: {[r['case_id'] for r in changed]}",
            "",
            "## 5. 変更理由",
            "",
        ]
    )
    for r in changed:
        report.append(f"- `{r['case_id']}`: {r['recheck_reason']}")
    if consistency_fixes:
        report.extend(["", "### 整合性ルールによる機械補正", ""])
        for r in consistency_fixes:
            report.append(
                f"- `{r['case_id']}`: {r['recheck_llm_evaluation'].get('q1_consistency_note')}"
            )
    report.extend(
        [
            "",
            "## 6. 評価器がルール違反した可能性",
            "",
            "断定ではなく候補として記録。",
            "",
            f"- `q1_rule_violation_candidate=true`: **{len(viol)}件**",
            "- 典型パターン: 検索結果本文が空なのに、Webなし/あり回答の品質を根拠にQ1を◎/○とした",
            f"- 強化プロンプト＋Q1独立評価後、本文なしで◎/○残留: **{len(recheck_positive_on_empty)}件**",
            "",
            "## 7. 評価器として利用する場合の注意点",
            "",
            "1. **Q1とQ2を同一プロンプトで同時評価すると、回答品質がQ1へ逆輸入されやすい**",
            "2. Q1は検索結果本文のみのカードで独立評価し、`usable_evidence` を先に取る",
            "3. `usable_evidence=false` なら Q1=◎/○ を機械的に禁止するガードが有効",
            "4. 本自己検証通過後に、人間レビューとの一致率測定へ進む",
            "",
            "---",
            "",
            "## 最終報告（3分離）",
            "",
            "### A. 検索結果評価能力（Q1）",
            "",
            f"- 原評価でルール違反候補: {len(viol)}/{empty_n or 'n/a'}（本文なしケース中）",
            f"- 再評価後、本文なしで◎/○残留: {len(recheck_positive_on_empty)}",
            "- 結論メモ: 単一プロンプト同時評価ではQ1が不安定。独立評価＋整合性ガードで改善可能。",
            "",
            "### B. Webあり／なし回答比較能力（Q2/Q5）",
            "",
            "- 今回はQ2をQ1から分離して再評価した（自己一貫性の確認）。人間正解との一致は未測定。",
            "",
            "### C. 人間との一致",
            "",
            "- **今回は算出しない**（自己検証完了後に実施）。",
            "",
        ]
    )
    (HERE / "SELF_CHECK_REPORT.md").write_text("\n".join(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="機械検査のみ")
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args(argv)

    profile = get_llm_profile()
    model = profile["model"]
    pilot_ids = args.case_id or load_pilot_ids()
    originals = load_original_evals()
    normalized = load_normalized_by_id()

    rows: list[dict] = []
    for cid in pilot_ids:
        case = normalized.get(cid)
        if not case:
            raise KeyError(f"missing normalized case {cid}")
        orig_eval = originals.get(cid) or {}
        orig_llm = orig_eval.get("llm") or {}
        mech = mechanical_inspect(case, orig_llm)

        if args.dry_run:
            recheck = {
                "usable_evidence": None,
                "q1_search_usefulness": "",
                "q1_reason": "(dry-run)",
                "q2_web_improvement": "",
                "q5_preference": "",
            }
            q1_changed = False
            recheck_reason = "dry-run: LLM再評価スキップ"
        else:
            print(f"self-check Q1 {cid} ...")
            q1_card = build_q1_only_card(case)
            q1_parsed = llm_eval_q1(q1_card, model=model)
            print(f"self-check Q2 {cid} ...")
            q2_card = build_q2_card(case)
            q2_parsed = llm_eval_q2_plus(q2_card, model=model)
            recheck = normalize_recheck(
                q1_parsed, q2_parsed, all_hits_empty=mech["all_hits_empty"]
            )
            orig_q1 = str(orig_llm.get("q1_search_usefulness") or "").strip()
            new_q1 = str(recheck.get("q1_search_usefulness") or "").strip()
            q1_changed = orig_q1 != new_q1
            reasons = []
            if mech["q1_rule_violation_candidate"]:
                reasons.append(
                    "原評価は全本文なしなのにQ1=◎/○（ルール違反候補）。独立Q1再評価で修正"
                )
            if q1_changed:
                reasons.append(f"Q1: {orig_q1!r} → {new_q1!r}")
            if recheck.get("q1_consistency_note"):
                reasons.append(recheck["q1_consistency_note"])
            if recheck.get("mechanical_usable_evidence_override"):
                reasons.append("全ヒットemptyのため usable_evidence を false に機械上書き")
            if not reasons:
                reasons.append("独立再評価実施（Q1変更なし）")
            recheck_reason = "；".join(reasons)

        rows.append(
            {
                "case_id": cid,
                "observation_id": mech["observation_id"],
                "request": mech["request"],
                "search_query": mech["search_query"],
                "hit_count": mech["hit_count"],
                "has_content_count": mech["has_content_count"],
                "empty_content_count": mech["empty_content_count"],
                "all_hits_empty": mech["all_hits_empty"],
                "hits": mech["hits"],
                "original_llm_evaluation": {
                    "q1_search_usefulness": orig_llm.get("q1_search_usefulness", ""),
                    "q1_reason": orig_llm.get("q1_reason", ""),
                    "q2_web_improvement": orig_llm.get("q2_web_improvement", ""),
                    "q2_reason": orig_llm.get("q2_reason", ""),
                    "q3_result_used_in_answer": orig_llm.get(
                        "q3_result_used_in_answer", ""
                    ),
                    "q5_preference": orig_llm.get("q5_preference", ""),
                    "q5_reason": orig_llm.get("q5_reason", ""),
                    "q6_search_result_issues": orig_llm.get(
                        "q6_search_result_issues", []
                    ),
                },
                "recheck_llm_evaluation": recheck,
                "q1_rule_violation_candidate": mech["q1_rule_violation_candidate"],
                "q1_changed": q1_changed,
                "recheck_reason": recheck_reason,
            }
        )

    write_outputs(rows, model=model)
    print(f"done self_check cases={len(rows)} -> {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
