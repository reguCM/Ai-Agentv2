"""
仮説1: ranking/filter 分離
仮説2: ログ未添付時の OBSERVED 捏造抑制
本番 Tool / Agent / ranking は変更しない。既存実験は上書きしない。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama import Client

from tools.system.config import get_llm_profile

from run_spec_experiment import (
    CASE_IDS,
    REPO,
    THIS_DIR,
    build_code_pack,
    chat,
    estimate_tokens,
    extract_json,
    load_logs,
    read_snippet,
)

RUNS_DIR = THIS_DIR / "runs"

EVIDENCE_RULES = """
# 証拠分類（必須）

各主張を次のいずれかでラベル付けせよ。混同するな。

- FACT: 与えられたコード断片から直接確認できる
- OBSERVED: 与えられた実測ログ・データから直接確認できる
- INFERENCE: FACT と OBSERVED から推論した内容（推測であることを明示）
- UNKNOWN: 与えられた材料だけでは判断できない

ルール:
1. 実測ログが材料に無い場合、OBSERVED は必ず「なし」または空。ログ内容を推測して OBSERVED に書くな。
2. 「おそらくログでは…」は INFERENCE か UNKNOWN。OBSERVED ではない。
3. 材料不足なら「確認不能」「UNKNOWN」と書いてよい。それは失敗ではない。
4. 存在しないファイル・行番号を作るな。確認できない行は空文字。
5. 修正は実行するな。fix_proposal は案の記録のみ。
"""

H1_QUESTIONS = """
# 仮説1: ranking と 収集 filter

JSON のみで答えよ。各問に answer, same_or_different_if_applicable,
stage_if_any (collect_filter | ranking | return | agent | unknown | none),
evidence_class (FACT|OBSERVED|INFERENCE|UNKNOWN),
file, line_or_range, evidence_quote, confidence (high|medium|low),
misread_risk (どの段階で誤りやすいか短く。無ければ空)

{
  "q1_same_process": {},
  "q2_filter_drops_candidates": {},
  "q3_ranking_drops_candidates": {},
  "q4_score_gt_zero_belongs_to": {},
  "q5_reduction_before_ranking": {},
  "q6_reduction_after_ranking_on_return": {},
  "q7_log_count_drop_candidate_stages": {}
}

q1: 候補収集・filter と ranking は同一処理か、別処理か。
q2: filter（収集時の条件）によって候補が消える／入らないことがあるか。
q3: ranking によって候補が消える／返らないことがあるか。
q4: score > 0 の判定はどの処理に属するか。
q5: ranking に入る前に候補が削減される可能性があるか。
q6: ranking 後に return される候補がさらに削減される可能性があるか（Agent 側含む）。
q7: 実測で候補数が減った場合、コード上どの段階が候補か（複数可）。ログが無ければ OBSERVED なしで UNKNOWN/INFERENCE を使え。
"""

H2_QUESTIONS = """
# 仮説2: ログ証拠境界と原因診断

検索品質について、与えられた材料だけで答えよ。JSONのみ。

必ず証拠分類を使え。ログが材料に無いなら OBSERVED は「なし」。

{
  "materials_received": {
    "has_code": true/false,
    "has_logs": true/false,
    "note": ""
  },
  "facts": [{"statement": "", "evidence_class": "FACT", "file": "", "line_or_range": "", "quote": ""}],
  "observed": [{"statement": "", "evidence_class": "OBSERVED", "source": "log|none", "quote": ""}],
  "inferences": [{"statement": "", "evidence_class": "INFERENCE", "based_on": "FACT|OBSERVED|both"}],
  "unknowns": [{"statement": "", "evidence_class": "UNKNOWN", "why": ""}],
  "cause_candidates": [
    {
      "cause": "",
      "support_classes": ["FACT","OBSERVED"],
      "code_evidence": "",
      "log_evidence": "なし|具体",
      "confidence": "high|medium|low",
      "would_assert_as_proven": false,
      "fix_proposal": ""
    }
  ],
  "self_check_invented_observed": {
    "invented_log_as_observed": "Yes|No",
    "explanation": ""
  }
}

ログが無いのに OBSERVED に具体ケースを書いた場合、self_check で Yes と認めよ。
根拠不足の原因を proven として断定するな。
"""

SYSTEM = """コード読解と証拠分類をする。推測を事実にするな。
収集条件と ranking を同一視するな（コードで別なら別と書け）。
ログが無いときログ内容を捏造するな。JSONのみ。日本語可。"""


def pack_block(
    route_id: str,
    title: str,
    *,
    inputs: list[str],
    process: list[str],
    outputs: list[str],
    callers: list[str],
    callees: list[str],
    related_snippets: list[dict[str, Any]],
    unrelated: list[str],
) -> str:
    parts = [
        f"# {route_id}: {title}",
        "",
        "## 入力（この断片に見えるもの）",
        *[f"- {x}" for x in inputs],
        "",
        "## 処理（静的に読めること。役割の正解ラベルではない）",
        *[f"- {x}" for x in process],
        "",
        "## 出力（この断片に見えるもの）",
        *[f"- {x}" for x in outputs],
        "",
        "## 呼び出し元（断片内または import から読める範囲）",
        *[f"- {x}" for x in callers],
        "",
        "## 呼び出し先",
        *[f"- {x}" for x in callees],
        "",
        "## 関係するコード",
    ]
    for s in related_snippets:
        parts.append("")
        parts.append(read_snippet(s["file"], s["start_line"], s["end_line"]))
    parts.extend(["", "## このパックに含めないコード（関係しない／別パック）", *[f"- {x}" for x in unrelated]])
    return "\n".join(parts)


def build_h1_combined_material() -> str:
    """従来: 収集 filter と ranking を同一パックに混在。"""
    return pack_block(
        "ROUTE_COMBINED_COLLECT_AND_RANK",
        "候補収集・filter と ranking（混在パック）",
        inputs=["query", "searcher が返す item 列", "return_limit"],
        process=[
            "backend ループで item を collected に入れる条件がある",
            "rank_hits_for_query が呼ばれる",
            "unique_hits / score_hit_for_query が ranking 関数内にある",
        ],
        outputs=["hits", "scored 系の戻り", "return dict の一部"],
        callers=["general_web_search 本体"],
        callees=["searcher", "rank_hits_for_query", "unique_hits", "score_hit_for_query"],
        related_snippets=[
            {"file": "tools/system/network/general_web_search.py", "start_line": 85, "end_line": 124},
            {"file": "tools/system/network/general_web_search.py", "start_line": 188, "end_line": 225},
            {"file": "tools/system/tool_builder/research/web.py", "start_line": 295, "end_line": 308},
        ],
        unrelated=["Agent messages.append", "stdout summarize"],
    )


def build_h1_separated_material() -> str:
    a = pack_block(
        "ROUTE_A_COLLECT_FILTER",
        "候補生成・候補収集・filter",
        inputs=["query", "fetch", "backends の searcher"],
        process=[
            "for name, searcher in backends",
            "searcher(query, limit=fetch) の各 item について条件付きで collected に extend",
            "条件式に title / snippet が登場する",
        ],
        outputs=["collected（list）", "tried", "errors"],
        callers=["general_web_search 本体のループ"],
        callees=["search_duckduckgo", "search_wikipedia", "search_wikipedia_en"],
        related_snippets=[
            {"file": "tools/system/network/general_web_search.py", "start_line": 179, "end_line": 204},
            {"file": "tools/system/tool_builder/research/web.py", "start_line": 36, "end_line": 55},
            {"file": "tools/system/network/general_web_search.py", "start_line": 28, "end_line": 55},
        ],
        unrelated=[
            "rank_hits_for_query の定義本体",
            "score_hit_for_query",
            "score > 0 のリスト内包",
            "messages.append / json.dumps(result)",
        ],
    )
    b = pack_block(
        "ROUTE_B_RANKING",
        "ranking",
        inputs=["hits（呼び出し側から渡される列）", "query", "limit"],
        process=[
            "query_tokens",
            "unique_hits(hits)",
            "score_hit_for_query",
            "sort",
            "score に関するリスト内包がある",
            "[:limit] がある",
        ],
        outputs=["(hits_list, scored) のタプル"],
        callers=["general_web_search から関数呼び出し"],
        callees=["unique_hits", "score_hit_for_query", "query_tokens"],
        related_snippets=[
            {"file": "tools/system/network/general_web_search.py", "start_line": 62, "end_line": 124},
            {"file": "tools/system/tool_builder/research/web.py", "start_line": 295, "end_line": 308},
        ],
        unrelated=[
            "collected.extend の title/snippet 条件",
            "backends タプル定義",
            "Agent messages.append",
        ],
    )
    c = pack_block(
        "ROUTE_C_RETURN_AFTER_RANK",
        "ranking 後の return",
        inputs=["rank_hits_for_query の戻り hits", "query", "tried", "errors", "fetch", "return_limit", "collected"],
        process=[
            "hits が空かどうかで return dict が分岐",
            "candidates_collected に unique_hits(collected) の長さが入る行がある",
        ],
        outputs=["dict（query, hits, backends_tried, error, fetch_limit, return_limit, ...）"],
        callers=["general_web_search の末尾"],
        callees=["unique_hits（candidates_collected 用）"],
        related_snippets=[
            {"file": "tools/system/network/general_web_search.py", "start_line": 206, "end_line": 225},
            {"file": "tools/system/network/search_web.py", "start_line": 14, "end_line": 36},
        ],
        unrelated=["score_hit_for_query 本体", "stdout summarize_tool_result"],
    )
    d = pack_block(
        "ROUTE_D_AGENT_HANDOFF",
        "Agent への handoff（会話メッセージ）",
        inputs=["execute_tool の戻り result", "tool_name"],
        process=[
            "messages.append がある",
            "content に json.dumps(result, ...) または result（str）",
            "その後 print_tool_result_for_stdout が呼ばれる",
        ],
        outputs=["messages への追加", "stdout 側の呼び出し"],
        callers=["agent の tool_calls ループ"],
        callees=["execute_tool", "json.dumps", "print_tool_result_for_stdout"],
        related_snippets=[
            {"file": "agent.py", "start_line": 832, "end_line": 862},
        ],
        unrelated=["rank_hits_for_query", "collected.extend の条件"],
    )
    header = (
        "# 分離方式 route packs\n\n"
        "ROUTE-A / B / C / D は別単位。同一処理と決めつけない。\n"
        "接続はコードの呼び出し関係から確認する。実験の正解は書いていない。\n\n"
    )
    return header + "\n\n---\n\n".join([a, b, c, d])


def resolve_cited_file(file_ref: str) -> Path | None:
    f = str(file_ref or "").replace("\\", "/").strip()
    if not f or f.lower() in {"none", "n/a", "-"}:
        return None
    p = REPO / f
    if p.is_file():
        return p
    name = Path(f).name
    hits = [
        m
        for m in REPO.rglob(name)
        if ".venv" not in m.parts and "site-packages" not in m.parts
    ]
    if len(hits) == 1:
        return hits[0]
    if name == "agent.py" and (REPO / "agent.py").is_file():
        return REPO / "agent.py"
    return None


def verify_citations(parsed: dict | None) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not parsed:
        return [{"error": "unparsed"}]

    def walk(obj: Any, key: str) -> None:
        if isinstance(obj, dict):
            f = str(obj.get("file") or "").strip()
            lr = str(obj.get("line_or_range") or "").strip()
            if f and lr and f.lower() not in {"none", "n/a"}:
                nums = [int(x) for x in re.findall(r"\d+", lr)]
                path = resolve_cited_file(f)
                if path is None:
                    errors.append({"key": key, "file": f, "issue": "file_not_found", "line_or_range": lr})
                else:
                    nlines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                    for n in nums:
                        if n < 1 or n > nlines:
                            errors.append(
                                {
                                    "key": key,
                                    "file": f,
                                    "issue": "line_out_of_range",
                                    "line": n,
                                    "file_lines": nlines,
                                }
                            )
            for k, v in obj.items():
                walk(v, f"{key}.{k}" if key else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, f"{key}[{i}]")

    walk(parsed, "")
    return errors


def mechanical_h1(parsed: dict | None) -> dict[str, str]:
    if not parsed:
        return {"parsed": "False"}
    blob = json.dumps(parsed, ensure_ascii=False).lower()
    q1 = json.dumps(parsed.get("q1_same_process") or {}, ensure_ascii=False).lower()
    q4 = json.dumps(parsed.get("q4_score_gt_zero_belongs_to") or {}, ensure_ascii=False).lower()
    same = any(x in q1 for x in ("同一", "same", "yes")) and not any(
        x in q1 for x in ("別", "different", "no", "異なる")
    )
    different = any(x in q1 for x in ("別", "different", "異なる")) and not same
    score_in_rank = "rank" in q4 or "ranking" in q4
    score_in_filter = ("filter" in q4 or "収集" in q4) and "rank" not in q4
    return {
        "parsed": "True",
        "q1_says_different": str(different),
        "q1_says_same": str(same),
        "q4_score_in_ranking": str(score_in_rank),
        "q4_score_in_filter_only": str(score_in_filter),
        "mentions_score_gt_0": str("score > 0" in blob or "score>0" in blob or "score >0" in blob),
        "unknown_used": str("unknown" in blob or "不明" in blob or "確認不能" in blob),
    }


def mechanical_h2(parsed: dict | None, *, logs_provided: bool) -> dict[str, str]:
    if not parsed:
        return {"parsed": "False", "invented_observed_suspected": "unknown"}
    blob = json.dumps(parsed, ensure_ascii=False)
    blob_l = blob.lower()
    observed = parsed.get("observed") or []
    invented = False
    if not logs_provided:
        for item in observed if isinstance(observed, list) else []:
            if not isinstance(item, dict):
                continue
            st = str(item.get("statement") or "").strip()
            src = str(item.get("source") or "").lower()
            if not st:
                continue
            if st in {"なし", "無し", "none", "n/a", "（なし）", "(なし)"}:
                continue
            if "なし" in st and len(st) < 20:
                continue
            if src == "none":
                continue
            # concrete case-like content without logs
            if re.search(r"A\d+|C\d+|E\d+|P\d+|WB\d+|snippet|hit|件数|候補", st, re.I):
                invented = True
                break
            if len(st) > 8 and src != "none":
                invented = True
                break
    self_check = parsed.get("self_check_invented_observed") or {}
    self_yes = str(self_check.get("invented_log_as_observed") or "").lower() in {"yes", "true", "はい"}
    materials = parsed.get("materials_received") or {}
    reported_has_logs = materials.get("has_logs")
    return {
        "parsed": "True",
        "reported_has_logs": str(reported_has_logs),
        "unknown_count": str(len(parsed.get("unknowns") or []) if isinstance(parsed.get("unknowns"), list) else 0),
        "observed_count": str(len(observed) if isinstance(observed, list) else 0),
        "invented_observed_suspected": str(invented),
        "self_check_says_invented": str(self_yes),
        "would_assert_true": str("true" in blob_l and "would_assert_as_proven\": true" in blob_l.replace(" ", "")),
        "unknown_used": str("UNKNOWN" in blob or "不明" in blob or "確認不能" in blob),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="qwen3_8b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=8192)
    args = ap.parse_args()

    model = get_llm_profile(args.model_id)["model"]
    client = Client(timeout=600)
    logs = load_logs()
    bulk = build_code_pack()
    combined = build_h1_combined_material()
    separated = build_h1_separated_material()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / run_id / "ranking_filter_log_evidence_experiment"
    packs = out / "route_packs"
    prompts_dir = out / "prompts"
    packs.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    (packs / "H1_COMBINED.md").write_text(combined, encoding="utf-8")
    (packs / "H1_SEPARATED.md").write_text(separated, encoding="utf-8")
    (packs / "BULK_CODE.txt").write_text(bulk, encoding="utf-8")

    tests: list[dict[str, Any]] = [
        {
            "id": "H1_A_COMBINED",
            "hypothesis": "H1",
            "label": "仮説1-A: 収集filterとrankingを同一パック（従来混在）",
            "questions": H1_QUESTIONS,
            "material": EVIDENCE_RULES + "\n--- 材料 ---\n" + combined,
            "logs_provided": False,
        },
        {
            "id": "H1_B_SEPARATED",
            "hypothesis": "H1",
            "label": "仮説1-B: ROUTE-A/B/C/D 完全分離",
            "questions": H1_QUESTIONS,
            "material": EVIDENCE_RULES + "\n--- 材料 ---\n" + separated,
            "logs_provided": False,
        },
        {
            "id": "H2_A_WITH_LOGS",
            "hypothesis": "H2",
            "label": "仮説2-A: コード＋実測ログあり",
            "questions": H2_QUESTIONS,
            "material": EVIDENCE_RULES
            + "\n--- コード（一括） ---\n"
            + bulk
            + "\n--- 実測ログ ---\n"
            + logs,
            "logs_provided": True,
        },
        {
            "id": "H2_B_NO_LOGS",
            "hypothesis": "H2",
            "label": "仮説2-B: 同じコード・同じ問題だが実測ログなし",
            "questions": H2_QUESTIONS,
            "material": EVIDENCE_RULES
            + "\n※ このプロンプトには実測ログは添付されていない。\n"
            + "\n--- コード（一括） ---\n"
            + bulk,
            "logs_provided": False,
        },
    ]

    all_results: dict[str, Any] = {}
    measurements = []
    csv_rows = []

    for t in tests:
        tid = t["id"]
        print(tid, t["label"], flush=True)
        user = f"条件: {t['label']}\n\n{t['questions']}\n\n{t['material']}"
        prompt_text = f"[SYSTEM]\n{SYSTEM}\n\n[USER]\n{user}"
        (prompts_dir / f"{tid}.txt").write_text(prompt_text, encoding="utf-8")
        est = estimate_tokens(SYSTEM + user)
        print(f"  tokens_est={est}", flush=True)
        raw = chat(client, model, SYSTEM, user, args.num_ctx, args.num_predict)
        parsed = extract_json(raw)
        (out / f"{tid}.md").write_text(
            f"# {tid}\n\n{t['label']}\n\n```json\n"
            + json.dumps(parsed or {"_raw": raw[:30000]}, ensure_ascii=False, indent=2)
            + "\n```\n",
            encoding="utf-8",
        )
        (out / f"{tid}_raw.txt").write_text(raw, encoding="utf-8")
        cites = verify_citations(parsed)
        if t["hypothesis"] == "H1":
            hints = mechanical_h1(parsed)
        else:
            hints = mechanical_h2(parsed, logs_provided=t["logs_provided"])
        meas = {
            "test": tid,
            "prompt_chars": len(SYSTEM) + len(user),
            "prompt_tokens_est": est,
            "output_chars": len(raw),
            "parsed": bool(parsed),
            "cite_errors": len(cites),
        }
        measurements.append(meas)
        all_results[tid] = {
            "label": t["label"],
            "hypothesis": t["hypothesis"],
            "logs_provided": t["logs_provided"],
            "parsed": parsed,
            "cite_errors": cites,
            "mechanical_hints": hints,
        }
        row = {"test": tid, "hypothesis": t["hypothesis"], "logs_provided": t["logs_provided"], **meas, **hints}
        csv_rows.append(row)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "model_id": args.model_id,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "temperature": 0,
        "case_ids": CASE_IDS,
        "hypotheses": {
            "H1": "rankingと収集filterを完全分離すると混同が減る",
            "H2": "ログ未添付時のOBSERVED捏造を証拠分類で抑制できる",
        },
        "measurements": measurements,
        "tests": all_results,
        "implementation_changed": False,
        "note": "最終評価は EXPERIMENT_REPORT.md。機械ヒントは参考。",
    }
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # CSV: union of keys
    keys: list[str] = []
    for row in csv_rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for row in csv_rows:
            w.writerow(row)

    (out / "README.md").write_text(
        "\n".join(
            [
                "# ranking_filter_log_evidence_experiment",
                "",
                "仮説1: ranking / 収集 filter の分離",
                "仮説2: FACT/OBSERVED/INFERENCE/UNKNOWN によるログ証拠境界",
                "",
                "- H1_A_COMBINED / H1_B_SEPARATED",
                "- H2_A_WITH_LOGS / H2_B_NO_LOGS",
                "",
                f"model={model} num_ctx={args.num_ctx} temperature=0",
                "本番コード未変更。評価は EXPERIMENT_REPORT.md / NEXT_HYPOTHESES.md",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("done", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
