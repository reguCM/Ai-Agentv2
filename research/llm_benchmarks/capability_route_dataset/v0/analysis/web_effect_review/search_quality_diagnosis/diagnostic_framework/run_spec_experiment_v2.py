"""
search_web 仕様書改良再実験（v2）。本番 Tool / Agent は変更しない。
前回の spec_experiment ファイルは変更しない。
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

# 同一コードパック・同一ログを前回実験と揃える
from run_spec_experiment import (
    CASE_IDS,
    REPO,
    SEARCH_QUALITY_DIR,
    THIS_DIR,
    build_code_pack,
    chat,
    estimate_tokens,
    extract_json,
    load_logs,
)

RUNS_DIR = THIS_DIR / "runs"
SPEC_V1 = THIS_DIR / "specs" / "search_web_spec.md"
SPEC_V2 = THIS_DIR / "specs" / "search_web_spec_v2.md"

QUESTIONS = """
以下の7問に JSON のみで答えよ。文章だけの自由回答は不可。

各問い（q1〜q7）は次のキーを持つ:
- answer: 簡潔な結論
- path: 処理の列（文字列の配列）。例 ["公開入口", "本体", "backend"]
- edges: 配列。各要素は {from, to, evidence, verdict, confidence}
  evidence は「コード上でAの戻り値をBが受け取っている」等。確認できなければ「確認できない」
  verdict は confirmed | unknown
  confidence は high | medium | low
- file, line_or_range, function, evidence_quote
- confidence, evidence_level, uncertainty

evidence_level は次のいずれか:
コードから直接確認できる | 仕様書から確認できる | ログから確認できる | 推測 | 判断不能

行番号が確認できない場合は line_or_range を空文字にせよ。存在しない行番号を作るな。
確認できない矢印は推測でつなぐな。verdict を unknown にせよ。
コードに無い処理を「存在する」と断定するな。
仕様書から実装の関数や行を逆算するな。
意味が似ている処理を同一視するな。

追加キー existence_vs_usage を必ず付ける。各項目は:
exists_in_code: Yes | No | 不明
used_in_search_web_path: Yes | No | 不明
related_to_llm_handoff: Yes | No | 不明
evidence: 短い説明（呼び出し関係。確認できなければ確認できない）
confidence: High | Medium | Low

対象キー（必須）: json.dumps, stdout, ranking, filter, compact

出力スキーマ:
{
  "q1_entry_to_backend": {},
  "q2_ranking_vs_collect_filter": {},
  "q3_agent_to_llm": {},
  "q4_json_where_why_where_to": {},
  "q5_stdout_vs_llm_tool_result": {},
  "q6_page_body_fetch": {},
  "q7_retry": {},
  "existence_vs_usage": {
    "json.dumps": {},
    "stdout": {},
    "ranking": {},
    "filter": {},
    "compact": {}
  }
}

q1: 公開入口から backend までの実際の経路。
q2: ranking と収集・filter を区別し、それぞれの役割。同一視するな。
q3: 検索結果が最終的に LLM へ渡るまでの実際の経路。表示処理と混同するな。
q4: JSON 化があるなら、どこで、何のため、その JSON はどこへ行くか。複数あるなら用途ごとに分けよ。本番と診断ハーネスを区別せよ。
q5: stdout やログ出力は「LLM への Tool 結果」か「単なる表示・ログ」か。
q6: 本文が無いとき、本番公開経路はページ本文取得を実際に行うか。無いなら無いと書け。推測で補完するな。
q7: retry はあるか。あるなら契機と再試行対象。無いなら無い。確認できなければ不明。
"""

SYSTEM_A = """コードと実測ログだけを根拠にする。仕様書は与えられていない。
存在する処理と、実際の経路で使われる処理を区別せよ。
定義だけでなく caller / callee / 戻り値の行き先を確認せよ。
表示・ログと LLM 入力を混同するな。
SPEC/CODE/OBSERVATION/INFERENCE を混同するな。JSONのみ。"""

SYSTEM_B = """仕様書は設計地図である。答えの行番号や関数の役割断定は仕様書に無い。
実装の根拠は必ずコードから取る。SPEC と CODE が違うときは CODE を優先。
存在する処理と、実際の経路で使われる処理を区別せよ。
表示・ログと LLM 入力を混同するな。
SPEC/CODE/OBSERVATION/INFERENCE を混同するな。JSONのみ。"""

SYSTEM_C = """改良仕様書は設計地図と調査原則である。実装の答えは仕様書に無い。
原則A〜Eに従い、存在と使用、表示と受け渡し、呼び出し関係を分離せよ。
仕様書から実装を逆算するな。SPEC と CODE が違うときは CODE を優先。
確認できないことは不明とせよ。JSONのみ。"""


def resolve_cited_file(file_ref: str) -> Path | None:
    f = str(file_ref or "").replace("\\", "/").strip()
    if not f:
        return None
    p = REPO / f
    if p.is_file():
        return p
    name = Path(f).name
    if not name:
        return None
    hits = [
        m
        for m in REPO.rglob(name)
        if ".venv" not in m.parts and "site-packages" not in m.parts
    ]
    if len(hits) == 1:
        return hits[0]
    agent = REPO / "agent.py"
    if name == "agent.py" and agent.is_file():
        return agent
    return None


def verify_line_citations(parsed: dict | None) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not parsed:
        return [{"error": "unparsed"}]

    def walk(obj: Any, key: str) -> None:
        if isinstance(obj, dict):
            f = str(obj.get("file") or "").strip()
            lr = str(obj.get("line_or_range") or "").strip()
            if f and lr:
                nums = [int(x) for x in re.findall(r"\d+", lr)]
                path = resolve_cited_file(f)
                if path is None:
                    errors.append(
                        {"key": key, "file": f, "issue": "file_not_found", "line_or_range": lr}
                    )
                else:
                    nlines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                    for n in nums:
                        if n < 1 or n > nlines:
                            errors.append(
                                {
                                    "key": key,
                                    "file": f,
                                    "resolved": str(path.relative_to(REPO)).replace("\\", "/"),
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


def mechanical_hints(parsed: dict | None) -> dict[str, str]:
    """機械ヒントのみ。最終判定は EXPERIMENT_REPORT の人間評価。"""
    if not parsed:
        return {f"q{i}": "unparsed" for i in range(1, 8)}
    blob = json.dumps(parsed, ensure_ascii=False).lower()
    hints = {
        "mentions_dumps": "json.dumps" in blob or "dumps(" in blob,
        "mentions_520": "520" in blob or "l520" in blob,
        "mentions_850": "850" in blob or "851" in blob or "858" in blob,
        "mentions_messages": "messages" in blob,
        "mentions_stdout": "stdout" in blob or "要約" in blob,
        "mentions_rank": "rank_hits" in blob or "score > 0" in blob or "score>0" in blob,
        "mentions_title_or_snippet": "title" in blob and "snippet" in blob,
        "unknown_used": "不明" in blob or "確認できない" in blob or '"unknown"' in blob,
        "invented_compact_hit_py": "compact_hit.py" in blob,
    }
    return {k: str(v) for k, v in hints.items()}


def write_test_md(path: Path, name: str, parsed: dict | None, raw: str) -> None:
    body = ["# " + name, ""]
    if parsed:
        body.append("```json")
        body.append(json.dumps(parsed, ensure_ascii=False, indent=2))
        body.append("```")
    else:
        body.append("（JSON 解析失敗。原文は `_raw.txt`）")
        body.append("")
        body.append("```")
        body.append(raw[:30000])
        body.append("```")
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="qwen3_8b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=8192)
    args = ap.parse_args()

    model = get_llm_profile(args.model_id)["model"]
    client = Client(timeout=600)
    spec_v1 = SPEC_V1.read_text(encoding="utf-8")
    spec_v2 = SPEC_V2.read_text(encoding="utf-8")
    code = build_code_pack()
    logs = load_logs()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / run_id / "spec_experiment_v2"
    out.mkdir(parents=True, exist_ok=True)

    (out / "spec_v1.md").write_text(spec_v1, encoding="utf-8")
    (out / "spec_v2.md").write_text(spec_v2, encoding="utf-8")
    (out / "spec_used.md").write_text(
        "# 本実験で使用した仕様書\n\n"
        "- TEST-A: なし\n"
        "- TEST-B: `specs/search_web_spec.md`（前回と同じ。本ディレクトリ `spec_v1.md`）\n"
        "- TEST-C: `specs/search_web_spec_v2.md`（本ディレクトリ `spec_v2.md`）\n",
        encoding="utf-8",
    )
    (out / "code_pack.txt").write_text(code, encoding="utf-8")

    common_tail = QUESTIONS + "\n--- コード ---\n" + code + "\n--- ログ ---\n" + logs
    tests = [
        (
            "TEST_A",
            SYSTEM_A,
            "実測ログは参考。根拠の行番号はコードから。仕様書は無い。\n" + common_tail,
        ),
        (
            "TEST_B",
            SYSTEM_B,
            "仕様書は地図。行番号はコードから。\n"
            + QUESTIONS
            + "\n--- 仕様書（v1） ---\n"
            + spec_v1
            + "\n--- コード ---\n"
            + code
            + "\n--- ログ ---\n"
            + logs,
        ),
        (
            "TEST_C",
            SYSTEM_C,
            "改良仕様書は地図と調査原則。実装根拠はコードから。\n"
            + QUESTIONS
            + "\n--- 仕様書（v2） ---\n"
            + spec_v2
            + "\n--- コード ---\n"
            + code
            + "\n--- ログ ---\n"
            + logs,
        ),
    ]

    all_parsed: dict[str, Any] = {}
    measurements = []
    for name, system, user in tests:
        print(name, "prompt_est_tokens", estimate_tokens(system + user), flush=True)
        (out / f"actual_llm_prompt_{name}.txt").write_text(
            f"[SYSTEM]\n{system}\n\n[USER]\n{user}", encoding="utf-8"
        )
        raw = chat(client, model, system, user, args.num_ctx, args.num_predict)
        parsed = extract_json(raw)
        write_test_md(out / f"{name}.md", name, parsed, raw)
        (out / f"{name}_raw.txt").write_text(raw, encoding="utf-8")
        meas = {
            "test": name,
            "prompt_chars": len(system) + len(user),
            "prompt_tokens_est": estimate_tokens(system + user),
            "output_chars": len(raw),
            "fits_est": estimate_tokens(system + user) < args.num_ctx * 0.9,
        }
        measurements.append(meas)
        all_parsed[name] = {
            "parsed": parsed,
            "cite_errors": verify_line_citations(parsed),
            "mechanical_hints": mechanical_hints(parsed),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "model_id": args.model_id,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "temperature": 0,
        "case_ids": CASE_IDS,
        "spec_v1": str(SPEC_V1.as_posix()),
        "spec_v2": str(SPEC_V2.as_posix()),
        "measurements": measurements,
        "tests": all_parsed,
        "implementation_changed": False,
        "previous_spec_experiment_untouched": True,
        "note": "mechanical_hints は最終判定ではない。人間評価は EXPERIMENT_REPORT.md。",
    }
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "test",
                "parsed",
                "cite_error_count",
                "mentions_dumps",
                "mentions_520",
                "mentions_850",
                "mentions_messages",
                "mentions_stdout",
                "mentions_rank",
                "invented_compact_hit_py",
                "unknown_used",
            ]
        )
        for name, block in all_parsed.items():
            h = block["mechanical_hints"]
            w.writerow(
                [
                    name,
                    bool(block["parsed"]),
                    len(block.get("cite_errors") or []),
                    h.get("mentions_dumps"),
                    h.get("mentions_520"),
                    h.get("mentions_850"),
                    h.get("mentions_messages"),
                    h.get("mentions_stdout"),
                    h.get("mentions_rank"),
                    h.get("invented_compact_hit_py"),
                    h.get("unknown_used"),
                ]
            )

    (out / "README.md").write_text(
        "\n".join(
            [
                "# spec_experiment_v2",
                "",
                "Qwen3:8b が search_web のコード経路を追跡できるかを測る実験。",
                "本番 Tool / Agent / ranking は変更していない。",
                "",
                "- TEST-A: 仕様書なし（コード＋ログ）",
                "- TEST-B: 前回仕様書 `search_web_spec.md`",
                "- TEST-C: 改良仕様書 `search_web_spec_v2.md`",
                "",
                f"model={model} num_ctx={args.num_ctx} temperature=0",
                "",
                "最終評価は EXPERIMENT_REPORT.md（機械ヒントは results.csv）。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("done", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
