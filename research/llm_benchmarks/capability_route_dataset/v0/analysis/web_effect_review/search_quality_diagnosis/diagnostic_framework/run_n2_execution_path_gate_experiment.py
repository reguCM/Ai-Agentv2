"""
N2: 原因候補の実行経路存在確認ゲート実験。
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
    THIS_DIR,
    build_code_pack,
    chat,
    estimate_tokens,
    extract_json,
    load_logs,
)

RUNS_DIR = THIS_DIR / "runs"

SYSTEM = """あなたは Tool 診断の補助をする。本番コードは修正しない。
「コード上に関数がある」ことと「公開 search_web 実行経路で呼ばれる」ことを混同するな。
一般知識で処理を補完するな。確認できなければ UNKNOWN。JSONのみ。日本語可。"""

GENERATE_PROMPT = """
# 段階: 原因候補の自由生成（存在ゲートはまだ使わない）

公開 Tool `search_web` の検索品質問題について、考えられる原因候補を自由に列挙せよ。
この段階では候補を削らない。存在しないかもしれない候補も含めてよい（後で検証する）。

与えられたコードと実測ログのみを材料にする。
修正は実行するな。fix_proposal は案のみ。

JSON:
{
  "candidates": [
    {
      "id": "C1",
      "cause_candidate": "",
      "related_mechanism_guess": "",
      "why_plausible": "",
      "code_hint": "",
      "log_hint": "",
      "fix_proposal_not_executed": ""
    }
  ],
  "notes": ""
}

最低5件、最大10件。既知の観察（snippet が空のケース等）も踏まえてよい。
"""

TRADITIONAL_PROMPT = """
# TEST-A: 従来方式の原因診断（N2ゲートなし）

コード＋実測ログから、search_web の検索品質について原因を診断せよ。
存在確認ゲートは使わない。候補を出してそのまま評価してよい。

各候補:
cause_candidate, evidence, confidence (high|medium|low),
strength (STRONG|MODERATE|WEAK|UNKNOWN|REJECTED),
execution_observed (YES|NO|UNKNOWN),
fix_proposal_not_executed

JSON:
{
  "candidates": [],
  "summary": "",
  "known_error_checks": {
    "invented_page_body_fetch_as_cause": "Yes|No",
    "confused_stdout_with_llm_handoff": "Yes|No",
    "confused_ranking_with_collect_filter": "Yes|No",
    "misattributed_limit_slicing": "Yes|No",
    "notes": ""
  }
}
"""

N2_GATE_PROMPT = """
# N2: 実行経路存在確認ゲート

以下の原因候補それぞれについて、公開 Tool search_web の実行経路上に
その処理が接続されているかを判定せよ。

重要:
- 「コード上に似た関数がある」だけでは YES にしない
- 公開入口 search_web → … → 当該処理 の接続がコードから確認できるときだけ YES
- 別経路・未接続・存在しないなら NO
- 抜粋不足で確定できないなら UNKNOWN
- 一般知識（「Web検索なら本文取得もあるはず」）は禁止。確認できなければ UNKNOWN
- N2 は「今回の実行で起きたか」を証明しない。execution_observed は別欄

各候補の出力キー（必須）:
cause_candidate, existence_status (YES|NO|UNKNOWN),
execution_path (短く。確認できた呼び出しの鎖。不明なら空または不明),
evidence (コード根拠。行が確認できなければ空),
file, line_or_range, confidence (high|medium|low),
execution_observed (YES|NO|UNKNOWN),
gate_action (KEEP|EXCLUDE|DO_NOT_ASSERT)

ルール:
- existence_status=NO → gate_action=EXCLUDE（原因から除外）
- existence_status=UNKNOWN → gate_action=DO_NOT_ASSERT（断定禁止。評価では採用不可）
- existence_status=YES → gate_action=KEEP（後段で評価可）

JSON:
{
  "gated": [
    {
      "id": "",
      "cause_candidate": "",
      "existence_status": "YES|NO|UNKNOWN",
      "execution_path": "",
      "evidence": "",
      "file": "",
      "line_or_range": "",
      "confidence": "high|medium|low",
      "execution_observed": "UNKNOWN",
      "gate_action": "KEEP|EXCLUDE|DO_NOT_ASSERT",
      "rationale": ""
    }
  ]
}
"""

N2_PATH_PROMPT = """
# N2+明示経路確認

各原因候補について、可能な範囲で次を埋めてから existence_status を決めよ。

cause_candidate
 → related_function（推定）
 → caller
 → caller_of_caller
 → public_entry (search_web か不明)

接続が1段でも確認できなければ、その先は UNKNOWN。
ファイル名・行番号を推測で埋めるな。確認できない欄は空または「確認できない」。

existence_status 規則は N2 と同じ（YES/NO/UNKNOWN）。
一般知識による補完禁止。
existence_status=NO → EXCLUDE、UNKNOWN → DO_NOT_ASSERT、YES → KEEP。

JSON:
{
  "gated": [
    {
      "id": "",
      "cause_candidate": "",
      "related_function": "",
      "caller": "",
      "caller_of_caller": "",
      "public_entry": "",
      "path_confirmable": true/false,
      "existence_status": "YES|NO|UNKNOWN",
      "execution_path": "",
      "evidence": "",
      "file": "",
      "line_or_range": "",
      "confidence": "high|medium|low",
      "execution_observed": "UNKNOWN",
      "gate_action": "KEEP|EXCLUDE|DO_NOT_ASSERT",
      "rationale": ""
    }
  ]
}
"""

EVALUATE_PROMPT = """
# 原因の最終評価

ゲート通過後（または従来方式）の候補だけを評価せよ。
EXCLUDE 済みは採用するな。DO_NOT_ASSERT / UNKNOWN 存在の候補は strength を REJECTED または UNKNOWN とし、断定するな。

各候補について分離せよ:
1. code_existence (YES|NO|UNKNOWN) — ゲート結果を踏まえる
2. connected_to_public_tool_path (YES|NO|UNKNOWN)
3. execution_observed (YES|NO|UNKNOWN) — ログが無ければ UNKNOWN。コードにあるから観測したとしない
4. consistency_with_logs
5. counter_evidence
6. strength (STRONG|MODERATE|WEAK|UNKNOWN|REJECTED)

JSON:
{
  "evaluated": [
    {
      "id": "",
      "cause_candidate": "",
      "code_existence": "",
      "connected_to_public_tool_path": "",
      "execution_observed": "",
      "consistency_with_logs": "",
      "counter_evidence": "",
      "strength": "",
      "kept_as_cause": true/false,
      "fix_proposal_not_executed": ""
    }
  ],
  "rejected_or_excluded": [],
  "summary": "",
  "known_error_checks": {
    "invented_page_body_fetch_as_cause": "Yes|No",
    "confused_stdout_with_llm_handoff": "Yes|No",
    "confused_ranking_with_collect_filter": "Yes|No",
    "misattributed_limit_slicing": "Yes|No",
    "notes": ""
  }
}
"""


def classify_cause_text(text: str) -> dict[str, bool]:
    t = (text or "").lower()
    return {
        "page_body": any(
            x in t
            for x in (
                "本文",
                "ページ抽出",
                "html",
                "スクレイプ",
                "scrape",
                "page body",
                "fetch page",
                "全文取得",
                "コンテンツ抽出",
            )
        ),
        "stdout_llm": any(x in t for x in ("stdout", "要約", "表示専用", "print_tool")),
        "rank_filter_mix": ("ranking" in t or "rank" in t) and ("filter" in t or "収集" in t) and (
            "同一" in t or "同じ" in t or "一緒" in t
        ),
        "limit": "limit" in t or "[:limit]" in t or "件数" in t or "切り詰" in t,
        "snippet_empty": "snippet" in t or "スニペット" in t,
        "backend": "backend" in t or "duckduckgo" in t or "wikipedia" in t or "バックエンド" in t,
        "collect_filter": "title" in t and "snippet" in t or "収集" in t,
        "score": "score" in t or "スコア" in t,
    }


def mechanical_counts(parsed_gen: dict | None, parsed_gate: dict | None, parsed_eval: dict | None) -> dict[str, Any]:
    cands = (parsed_gen or {}).get("candidates") or []
    gated = (parsed_gate or {}).get("gated") or []
    evaluated = (parsed_eval or {}).get("evaluated") or []
    n_yes = sum(1 for g in gated if str(g.get("existence_status") or "").upper() == "YES")
    n_no = sum(1 for g in gated if str(g.get("existence_status") or "").upper() == "NO")
    n_unk = sum(1 for g in gated if str(g.get("existence_status") or "").upper() == "UNKNOWN")
    page_in_gen = sum(1 for c in cands if classify_cause_text(json.dumps(c, ensure_ascii=False))["page_body"])
    page_kept = 0
    for e in evaluated:
        if not e.get("kept_as_cause"):
            continue
        if str(e.get("strength") or "").upper() in {"REJECTED"}:
            continue
        if classify_cause_text(json.dumps(e, ensure_ascii=False))["page_body"]:
            page_kept += 1
    strengths = [str(e.get("strength") or "").upper() for e in evaluated if e.get("kept_as_cause")]
    overclaim = sum(1 for s in strengths if s == "STRONG")
    return {
        "n_generated": len(cands),
        "n_gated": len(gated),
        "n_yes": n_yes,
        "n_no": n_no,
        "n_unknown": n_unk,
        "n_evaluated": len(evaluated),
        "n_kept": sum(1 for e in evaluated if e.get("kept_as_cause")),
        "page_body_in_generated": page_in_gen,
        "page_body_kept_as_cause": page_kept,
        "strong_kept": overclaim,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="qwen3_8b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=8192)
    args = ap.parse_args()

    model = get_llm_profile(args.model_id)["model"]
    client = Client(timeout=600)
    code = build_code_pack()
    logs = load_logs()
    materials = (
        "--- コード ---\n" + code + "\n--- 実測ログ ---\n" + logs
        + "\n\n注: 診断ハーネス由来の断片がコードパックに含まれる場合がある。"
        "公開 search_web 経路と診断専用コードを混同するな。\n"
    )

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / run_id / "n2_execution_path_gate"
    prompts_dir = out / "prompts"
    results_dir = out / "results"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    (out / "materials_code_pack.txt").write_text(code, encoding="utf-8")

    measurements = []
    all_out: dict[str, Any] = {}

    def run(name: str, user: str) -> tuple[str, dict | None]:
        prompt = f"[SYSTEM]\n{SYSTEM}\n\n[USER]\n{user}"
        (prompts_dir / f"{name}.txt").write_text(prompt, encoding="utf-8")
        est = estimate_tokens(SYSTEM + user)
        print(f"  {name} tokens_est={est}", flush=True)
        raw = chat(client, model, SYSTEM, user, args.num_ctx, args.num_predict)
        parsed = extract_json(raw)
        (out / f"{name}_raw.txt").write_text(raw, encoding="utf-8")
        measurements.append(
            {
                "phase": name,
                "prompt_tokens_est": est,
                "output_chars": len(raw),
                "parsed": bool(parsed),
            }
        )
        return raw, parsed

    # --- Shared free generation (for B/C fairness) ---
    print("SHARED_GENERATE", flush=True)
    _, shared_gen = run(
        "SHARED_GENERATE",
        GENERATE_PROMPT + "\n" + materials,
    )
    (results_dir / "SHARED_GENERATE.json").write_text(
        json.dumps(shared_gen or {}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    cand_blob = json.dumps((shared_gen or {}).get("candidates") or shared_gen or {}, ensure_ascii=False, indent=2)

    # --- TEST-A traditional ---
    print("TEST_A", flush=True)
    _, a_parsed = run(
        "TEST_A",
        TRADITIONAL_PROMPT + "\n" + materials,
    )
    a_counts = mechanical_counts(None, None, {"evaluated": (a_parsed or {}).get("candidates") or []})
    # remap traditional candidates as evaluated-like
    a_eval_like = []
    for i, c in enumerate((a_parsed or {}).get("candidates") or []):
        if not isinstance(c, dict):
            continue
        a_eval_like.append(
            {
                **c,
                "kept_as_cause": str(c.get("strength") or "").upper() not in {"REJECTED"},
                "id": c.get("id") or f"A{i+1}",
            }
        )
    a_counts = mechanical_counts(
        {"candidates": a_eval_like},
        None,
        {"evaluated": a_eval_like},
    )
    a_page_gen = sum(
        1 for c in a_eval_like if classify_cause_text(json.dumps(c, ensure_ascii=False))["page_body"]
    )
    a_counts["page_body_in_generated"] = a_page_gen
    a_counts["page_body_kept_as_cause"] = sum(
        1
        for c in a_eval_like
        if c.get("kept_as_cause") and classify_cause_text(json.dumps(c, ensure_ascii=False))["page_body"]
        and str(c.get("strength") or "").upper() not in {"REJECTED", "UNKNOWN"}
    )
    a_payload = {
        "test": "TEST_A",
        "label": "従来方式（N2なし）",
        "parsed": a_parsed,
        "mechanical": a_counts,
        "known_error_checks": (a_parsed or {}).get("known_error_checks"),
    }
    (results_dir / "TEST_A.json").write_text(json.dumps(a_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    all_out["TEST_A"] = a_payload

    # --- TEST-B N2 gate ---
    print("TEST_B", flush=True)
    _, b_gate = run(
        "TEST_B_GATE",
        N2_GATE_PROMPT
        + "\n--- 原因候補（自由生成・未フィルタ） ---\n"
        + cand_blob
        + "\n"
        + materials,
    )
    kept_b = [
        g
        for g in ((b_gate or {}).get("gated") or [])
        if str(g.get("gate_action") or "").upper() == "KEEP"
        or str(g.get("existence_status") or "").upper() == "YES"
    ]
    # still pass UNKNOWN as DO_NOT_ASSERT for evaluate visibility
    for_eval_b = (b_gate or {}).get("gated") or []
    _, b_eval = run(
        "TEST_B_EVAL",
        EVALUATE_PROMPT
        + "\n--- N2ゲート結果（EXCLUDEは採用禁止） ---\n"
        + json.dumps(for_eval_b, ensure_ascii=False, indent=2)
        + "\n"
        + materials,
    )
    b_counts = mechanical_counts(shared_gen, b_gate, b_eval)
    b_payload = {
        "test": "TEST_B",
        "label": "N2ゲートあり",
        "shared_generate_ref": "SHARED_GENERATE",
        "gate": b_gate,
        "evaluated": b_eval,
        "mechanical": b_counts,
        "known_error_checks": (b_eval or {}).get("known_error_checks"),
        "kept_ids": [g.get("id") for g in kept_b],
    }
    (results_dir / "TEST_B.json").write_text(json.dumps(b_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # also save phase prompts aliases
    all_out["TEST_B"] = b_payload

    # --- TEST-C N2 + path ---
    print("TEST_C", flush=True)
    _, c_gate = run(
        "TEST_C_GATE",
        N2_PATH_PROMPT
        + "\n--- 原因候補（自由生成・未フィルタ） ---\n"
        + cand_blob
        + "\n"
        + materials,
    )
    for_eval_c = (c_gate or {}).get("gated") or []
    _, c_eval = run(
        "TEST_C_EVAL",
        EVALUATE_PROMPT
        + "\n--- N2+経路ゲート結果（EXCLUDEは採用禁止） ---\n"
        + json.dumps(for_eval_c, ensure_ascii=False, indent=2)
        + "\n"
        + materials,
    )
    c_counts = mechanical_counts(shared_gen, c_gate, c_eval)
    c_payload = {
        "test": "TEST_C",
        "label": "N2ゲート＋明示経路確認",
        "shared_generate_ref": "SHARED_GENERATE",
        "gate": c_gate,
        "evaluated": c_eval,
        "mechanical": c_counts,
        "known_error_checks": (c_eval or {}).get("known_error_checks"),
    }
    (results_dir / "TEST_C.json").write_text(json.dumps(c_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    all_out["TEST_C"] = c_payload

    # Copy primary prompts with requested names
    for src, dst in [
        ("TEST_A.txt", "TEST_A.txt"),
        ("TEST_B_GATE.txt", "TEST_B.txt"),
        ("TEST_C_GATE.txt", "TEST_C.txt"),
    ]:
        p = prompts_dir / src
        if p.is_file():
            (prompts_dir / dst).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    # comparison.csv
    rows = []
    for tid in ("TEST_A", "TEST_B", "TEST_C"):
        m = all_out[tid]["mechanical"]
        kec = all_out[tid].get("known_error_checks") or {}
        rows.append(
            {
                "test": tid,
                "n_generated_or_listed": m.get("n_generated"),
                "n_yes": m.get("n_yes"),
                "n_no": m.get("n_no"),
                "n_unknown": m.get("n_unknown"),
                "n_kept": m.get("n_kept"),
                "page_body_in_generated": m.get("page_body_in_generated"),
                "page_body_kept_as_cause": m.get("page_body_kept_as_cause"),
                "strong_kept": m.get("strong_kept"),
                "self_page_body": kec.get("invented_page_body_fetch_as_cause"),
                "self_stdout": kec.get("confused_stdout_with_llm_handoff"),
                "self_rank_filter": kec.get("confused_ranking_with_collect_filter"),
                "self_limit": kec.get("misattributed_limit_slicing"),
            }
        )

    with (out / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "model_id": args.model_id,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "temperature": 0,
        "case_ids": CASE_IDS,
        "measurements": measurements,
        "tests": all_out,
        "shared_generate": shared_gen,
        "implementation_changed": False,
        "note": "最終評価は EXPERIMENT_REPORT.md（人間判定）。機械カウントは参考。",
    }
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (out / "README.md").write_text(
        "\n".join(
            [
                "# n2_execution_path_gate",
                "",
                "原因候補が公開 search_web 実行経路上に存在するかを確認する N2 ゲートの検証。",
                "",
                "- TEST-A: 従来原因診断（ゲートなし）",
                "- SHARED_GENERATE → TEST-B: N2 ゲート → 評価",
                "- SHARED_GENERATE → TEST-C: N2+明示経路 → 評価",
                "",
                f"model={model} num_ctx={args.num_ctx} temperature=0",
                "本番コード未変更。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("done", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
