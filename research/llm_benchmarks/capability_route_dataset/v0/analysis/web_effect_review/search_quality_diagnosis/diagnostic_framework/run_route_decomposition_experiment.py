"""
処理経路分解による Qwen3:8b コード読解実験。
本番 Tool / Agent / ranking は変更しない。既存実験結果は上書きしない。
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
    SEARCH_QUALITY_DIR,
    THIS_DIR,
    build_code_pack,
    chat,
    estimate_tokens,
    extract_json,
    load_logs,
    read_snippet,
)

RUNS_DIR = THIS_DIR / "runs"
SPEC_V2 = THIS_DIR / "specs" / "search_web_spec_v2.md"

# 経路単位。ラベルは機械的区分。正解（「ここがLLM受け渡し」）は書かない。
ROUTE_DEFS: list[dict[str, Any]] = [
    {
        "id": "ROUTE_1_ENTRY",
        "title": "検索入口",
        "static_notes": [
            "search_web は general_web_search を return で呼ぶ（同一ファイル内 import）。",
            "general_web_search 内で backends タプルが定義され、for で searcher が呼ばれる。",
        ],
        "snippets": [
            {"file": "tools/system/network/search_web.py", "start_line": 1, "end_line": 36},
            {"file": "tools/system/network/general_web_search.py", "start_line": 127, "end_line": 205},
        ],
    },
    {
        "id": "ROUTE_2_CANDIDATE_GEN",
        "title": "候補生成（backend）",
        "static_notes": [
            "search_duckduckgo / search_wikipedia は web.py。",
            "search_wikipedia_en は general_web_search.py。",
            "いずれも hits の list を返す。",
        ],
        "snippets": [
            {"file": "tools/system/tool_builder/research/web.py", "start_line": 36, "end_line": 120},
            {"file": "tools/system/network/general_web_search.py", "start_line": 28, "end_line": 55},
        ],
    },
    {
        "id": "ROUTE_3_SHAPE",
        "title": "候補整形（hit 形式）",
        "static_notes": [
            "compact_hit は title/snippet/url/backend の dict を返す。",
            "backend 関数内で compact_hit が呼ばれる。",
        ],
        "snippets": [
            {"file": "tools/system/tool_builder/research/web.py", "start_line": 27, "end_line": 33},
        ],
    },
    {
        "id": "ROUTE_4_RANK_FILTER",
        "title": "ranking / 収集・重複",
        "static_notes": [
            "収集時: title or snippet がある item のみ collected に入る（general_web_search）。",
            "rank_hits_for_query 内で unique_hits と score_hit_for_query が使われる。",
            "unique_hits 定義は web.py。",
        ],
        "snippets": [
            {"file": "tools/system/network/general_web_search.py", "start_line": 85, "end_line": 124},
            {"file": "tools/system/network/general_web_search.py", "start_line": 188, "end_line": 206},
            {"file": "tools/system/tool_builder/research/web.py", "start_line": 295, "end_line": 308},
        ],
    },
    {
        "id": "ROUTE_5_TOOL_RETURN",
        "title": "Tool 結果返却",
        "static_notes": [
            "general_web_search は dict（query, hits, backends_tried, error 等）を return。",
            "search_web はその戻り値をそのまま return。",
        ],
        "snippets": [
            {"file": "tools/system/network/general_web_search.py", "start_line": 206, "end_line": 225},
            {"file": "tools/system/network/search_web.py", "start_line": 14, "end_line": 36},
        ],
    },
    {
        "id": "ROUTE_6_AGENT_MESSAGES",
        "title": "Agent 会話メッセージへの追加",
        "static_notes": [
            "execute_tool(...) の戻り値が result に入る。",
            "messages.append の content に json.dumps(result, ...) または str が入る。",
            "その後 print_tool_result_for_stdout(tool_name, result) が呼ばれる。",
        ],
        "snippets": [
            {"file": "agent.py", "start_line": 832, "end_line": 862},
        ],
    },
    {
        "id": "ROUTE_7_STDOUT_DISPLAY",
        "title": "表示・stdout",
        "static_notes": [
            "summarize_tool_result は dict を組み立てて return する関数。",
            "print_tool_result_for_stdout は summarize_tool_result の戻りを json.dumps して print する。",
        ],
        "snippets": [
            {"file": "agent.py", "start_line": 486, "end_line": 565},
        ],
    },
]


def build_route_pack(route: dict[str, Any]) -> str:
    parts = [
        f"# {route['id']}: {route['title']}",
        "",
        "## 静的に抽出した事実（意味推測なし）",
    ]
    for note in route.get("static_notes") or []:
        parts.append(f"- {note}")
    parts.append("")
    parts.append("## コード断片")
    for s in route["snippets"]:
        parts.append("")
        parts.append(read_snippet(s["file"], s["start_line"], s["end_line"]))
    return "\n".join(parts)


def build_all_route_packs() -> str:
    packs = [build_route_pack(r) for r in ROUTE_DEFS]
    header = (
        "# 処理経路単位コードパック\n\n"
        "各 ROUTE は別単位。ROUTE 同士の接続はコードの呼び出し関係から確認すること。\n"
        "静的メモは import/call/return の事実のみ。役割の正解ラベルではない。\n"
    )
    return header + "\n\n---\n\n".join(packs)


def build_route_map_md() -> str:
    lines = [
        "# route_map（静的抽出）",
        "",
        "人間の意味推測による「正解経路」ではない。コード上の呼び出し・return の事実のみ。",
        "",
        "```text",
        "ROUTE_1_ENTRY",
        "  search_web(query, limit)",
        "    → return general_web_search(...)",
        "  general_web_search",
        "    → for name, searcher in backends: searcher(query, limit=fetch)",
        "    → collected に title or snippet がある item のみ",
        "    → rank_hits_for_query(collected, ...)",
        "    → return dict(...)",
        "",
        "ROUTE_2_CANDIDATE_GEN",
        "  search_duckduckgo / search_wikipedia / search_wikipedia_en",
        "    → compact_hit(...) を呼び hits list を return",
        "",
        "ROUTE_3_SHAPE",
        "  compact_hit → dict(title, snippet, url, backend)",
        "",
        "ROUTE_4_RANK_FILTER",
        "  収集条件: title or snippet",
        "  rank_hits_for_query → unique_hits → score → score>0 優先 → [:limit]",
        "",
        "ROUTE_5_TOOL_RETURN",
        "  general_web_search / search_web の return dict",
        "",
        "ROUTE_6_AGENT_MESSAGES",
        "  result = execute_tool(...)",
        "  messages.append({..., content: json.dumps(result) or result})",
        "  print_tool_result_for_stdout(tool_name, result)",
        "",
        "ROUTE_7_STDOUT_DISPLAY",
        "  summarize_tool_result → print(json.dumps(summary))",
        "```",
        "",
        "注: ROUTE_6 と ROUTE_7 は別断片。接続の有無はコードで確認する。",
        "",
    ]
    return "\n".join(lines)


PHASE1 = """
# 段階1: 各経路の入出力（原因診断はするな）

各 ROUTE について JSON で答えよ。推測で補完するな。確認できない項目は "コードから確認できない" と書け。

各 route キー:
inputs, outputs, return_type_or_structure, called_by, calls, next_value_goes_to,
not_confirmable, confidence (high|medium|low), evidence_file, evidence_line_or_range, evidence_quote

出力:
{
  "ROUTE_1_ENTRY": {},
  "ROUTE_2_CANDIDATE_GEN": {},
  "ROUTE_3_SHAPE": {},
  "ROUTE_4_RANK_FILTER": {},
  "ROUTE_5_TOOL_RETURN": {},
  "ROUTE_6_AGENT_MESSAGES": {},
  "ROUTE_7_STDOUT_DISPLAY": {}
}
"""

PHASE2 = """
# 段階2: 経路接続テスト

各接続について:
connected: Yes | No | 不明
evidence: コード根拠（確認できなければ「確認できない」）
file, line_or_range, evidence_quote
confidence: high|medium|low

存在しない接続を作るな。確認できないなら「不明」または connected=No。

{
  "test1_search_to_ranking": {},
  "test2_ranking_to_tool_return": {},
  "test3_tool_return_to_agent": {},
  "test4_agent_to_llm": {},
  "test5_agent_to_stdout": {},
  "test6_stdout_to_llm": {}
}

test1: 検索候補収集の結果は ranking のどの入力へ渡るか。接続はあるか。
test2: ranking の戻りは Tool 返却にどう繋がるか。
test3: Tool 返却値は Agent のどこで受け取られるか。
test4: Agent から LLM へ値が渡る接続はあるか。あるならどの処理か。
test5: Agent から stdout 表示への接続はあるか。
test6: stdout 表示の結果が LLM 入力へ渡る接続はあるか。（重要: 無ければ No）
"""

PHASE3 = """
# 段階3: 判定問題

各問: answer, connected_or_same_if_applicable, evidence, file, line_or_range, evidence_quote,
confidence, inventing_unseen_code (Yes|No)

{
  "problem_A_json_dumps_purpose": {},
  "problem_B_json_dumps_receiver": {},
  "problem_C_stdout_is_llm_input": {},
  "problem_D_ranking_vs_collect_filter_same": {},
  "problem_E_wiki_empty_snippet_body_fetch": {},
  "problem_F_no_unseen_assertions": {}
}

A: json.dumps(result) は何のためか（用途をコードから）。
B: その文字列（content）を誰が受け取るか。確認できなければ不明。
C: stdout への表示処理は LLM への入力経路か。Yes/No/不明。
D: ranking の score 条件と、候補収集時の filter 条件は同一処理か。
E: Wikipedia snippet が空のとき、コード上どこで本文取得するか。無ければ無い。
F: 上記でコードに無い処理を「ある」と断定していないか自己点検。
"""

PHASE4_LOG = """
# 段階4: ログ統合（観測とコードを分離）

与えられた実測ログについて、代表ケースを選び JSON のみで答えよ。

各ケースまたは全体について:
{
  "cases": [
    {
      "case_id": "",
      "observation": "ログに書かれている事実のみ",
      "code_fact": "コードから確認できる事実のみ",
      "inference": "両者から導ける推論（なければ空）",
      "undecidable": "判断不能な点",
      "code_route_id": "該当しそうな ROUTE id または不明",
      "confidence": "high|medium|low"
    }
  ],
  "summary": ""
}

ログ結果をコード経路と同一視するな。ログに無いことをコードから捏造するな。
"""

PHASE5_CAUSE = """
# 段階5: 原因診断（修正は実行するな。案のみ）

検索品質問題について、コードと（あれば）ログから原因候補を挙げよ。JSONのみ。

{
  "candidates": [
    {
      "cause": "",
      "code_evidence": "",
      "log_evidence": "",
      "support": "",
      "counter_evidence": "",
      "unknown": "",
      "priority": "high|medium|low",
      "further_investigation": "",
      "fix_proposal_only": ""
    }
  ],
  "overall_confidence": "high|medium|low",
  "path_understanding_used": "経路理解を使ったか短く"
}

修正を実行するな。断定しすぎるな。不明を許す。
"""

SYSTEM = """あなたはコード経路の静的読解をする。
存在する処理と実際に接続する処理を区別せよ。
表示・stdout と会話メッセージへの追加を混同するな。
推測で経路を補完するな。確認できないことは不明／コードから確認できないと書け。
存在しないファイル・行番号を作るな。JSONのみ。"""


def resolve_cited_file(file_ref: str) -> Path | None:
    f = str(file_ref or "").replace("\\", "/").strip()
    if not f:
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
            f = str(obj.get("file") or obj.get("evidence_file") or "").strip()
            lr = str(obj.get("line_or_range") or obj.get("evidence_line_or_range") or "").strip()
            if f and lr:
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


def mechanical_hints(blob: str) -> dict[str, str]:
    t = (blob or "").lower()
    return {
        "mentions_dumps": str("json.dumps" in t or "dumps(" in t),
        "mentions_520": str("520" in t or "l520" in t),
        "mentions_850": str("850" in t or "851" in t or "858" in t),
        "mentions_messages": str("messages" in t),
        "stdout_to_llm_yes": str(
            '"test6_stdout_to_llm"' in t
            and re.search(r'test6_stdout_to_llm[^}]*"connected"\s*:\s*"yes"', t, re.I) is not None
        ),
        "problem_c_yes": str(
            re.search(r'problem_c_stdout_is_llm_input[^}]*"answer"\s*:\s*"[^"]*yes', t, re.I) is not None
            or re.search(r'problem_c_stdout[^}]*:\s*"Yes"', t) is not None
        ),
        "unknown_used": str("不明" in t or "確認できない" in t or "コードから確認できない" in t),
        "invented_compact_hit_py": str("compact_hit.py" in t),
    }


def run_phase(
    client: Client,
    model: str,
    num_ctx: int,
    num_predict: int,
    system: str,
    user: str,
) -> tuple[str, dict | None]:
    raw = chat(client, model, system, user, num_ctx, num_predict)
    return raw, extract_json(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="qwen3_8b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=8192)
    ap.add_argument(
        "--tests",
        default="A,B,C,D",
        help="Comma list of tests to run (A,B,C,D)",
    )
    args = ap.parse_args()

    model = get_llm_profile(args.model_id)["model"]
    client = Client(timeout=600)
    bulk = build_code_pack()
    routes = build_all_route_packs()
    route_map = build_route_map_md()
    spec_v2 = SPEC_V2.read_text(encoding="utf-8")
    logs = load_logs()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / run_id / "route_decomposition_experiment"
    packs_dir = out / "route_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)

    (out / "route_map.md").write_text(route_map, encoding="utf-8")
    for r in ROUTE_DEFS:
        (packs_dir / f"{r['id']}.md").write_text(build_route_pack(r), encoding="utf-8")
    (packs_dir / "ALL_ROUTES.md").write_text(routes, encoding="utf-8")
    (out / "code_pack_bulk.txt").write_text(bulk, encoding="utf-8")

    test_defs = {
        "A": {
            "name": "TEST_A",
            "label": "従来方式（まとまったコード）",
            "material": "--- コード（一括） ---\n" + bulk,
            "with_logs_early": False,
            "with_logs_phase4": False,
            "with_logs_cause": False,
            "extra_spec": "",
        },
        "B": {
            "name": "TEST_B",
            "label": "仕様書v2＋まとまったコード",
            "material": "--- 仕様書v2 ---\n" + spec_v2 + "\n--- コード（一括） ---\n" + bulk,
            "with_logs_early": False,
            "with_logs_phase4": False,
            "with_logs_cause": False,
            "extra_spec": "",
        },
        "C": {
            "name": "TEST_C",
            "label": "処理経路分解コード",
            "material": "--- route_map ---\n" + route_map + "\n--- 経路単位コード ---\n" + routes,
            "with_logs_early": False,
            "with_logs_phase4": False,
            "with_logs_cause": False,
            "extra_spec": "",
        },
        "D": {
            "name": "TEST_D",
            "label": "処理経路分解＋実測ログ",
            "material": "--- route_map ---\n" + route_map + "\n--- 経路単位コード ---\n" + routes,
            "with_logs_early": False,
            "with_logs_phase4": True,
            "with_logs_cause": True,
            "extra_spec": "",
        },
    }

    selected = [x.strip().upper() for x in args.tests.split(",") if x.strip()]
    all_results: dict[str, Any] = {}
    measurements = []

    for key in selected:
        td = test_defs[key]
        name = td["name"]
        print(name, td["label"], flush=True)
        phases_out: dict[str, Any] = {}
        prompt_parts = []

        phase_specs = [
            ("phase1_route_io", PHASE1, td["material"]),
            ("phase2_connections", PHASE2, td["material"]),
            ("phase3_judgments", PHASE3, td["material"]),
        ]
        if td["with_logs_phase4"]:
            phase_specs.append(
                (
                    "phase4_log_integration",
                    PHASE4_LOG,
                    td["material"] + "\n--- 実測ログ ---\n" + logs,
                )
            )
        cause_mat = td["material"]
        if td["with_logs_cause"]:
            cause_mat = cause_mat + "\n--- 実測ログ ---\n" + logs
        phase_specs.append(("phase5_cause", PHASE5_CAUSE, cause_mat))

        for phase_name, questions, material in phase_specs:
            user = (
                f"条件: {td['label']}\n"
                "段階を飛ばさず、この段階の指示だけに答えよ。\n\n"
                + questions
                + "\n\n"
                + material
            )
            prompt_text = f"[SYSTEM]\n{SYSTEM}\n\n[USER]\n{user}"
            prompt_parts.append(f"===== {phase_name} =====\n{prompt_text}")
            print(f"  {phase_name} tokens_est={estimate_tokens(SYSTEM + user)}", flush=True)
            raw, parsed = run_phase(
                client, model, args.num_ctx, args.num_predict, SYSTEM, user
            )
            (out / f"{name}_{phase_name}_raw.txt").write_text(raw, encoding="utf-8")
            (out / f"{name}_{phase_name}.md").write_text(
                f"# {name} {phase_name}\n\n```json\n"
                + json.dumps(parsed or {"_raw": raw[:25000]}, ensure_ascii=False, indent=2)
                + "\n```\n",
                encoding="utf-8",
            )
            meas = {
                "test": name,
                "phase": phase_name,
                "prompt_chars": len(SYSTEM) + len(user),
                "prompt_tokens_est": estimate_tokens(SYSTEM + user),
                "output_chars": len(raw),
                "parsed": bool(parsed),
            }
            measurements.append(meas)
            cites = verify_citations(parsed)
            phases_out[phase_name] = {
                "parsed": parsed,
                "cite_errors": cites,
                "mechanical_hints": mechanical_hints(json.dumps(parsed or {}, ensure_ascii=False)),
            }

        (out / f"actual_llm_prompt_{name}.md").write_text(
            "\n\n".join(prompt_parts), encoding="utf-8"
        )
        all_results[name] = {
            "label": td["label"],
            "phases": phases_out,
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "model_id": args.model_id,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "temperature": 0,
        "case_ids": CASE_IDS,
        "measurements": measurements,
        "tests": all_results,
        "implementation_changed": False,
        "note": "最終評価は EXPERIMENT_REPORT.md。機械ヒントは参考。",
    }
    (out / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "test",
                "phase",
                "parsed",
                "cite_errors",
                "mentions_dumps",
                "mentions_520",
                "mentions_850",
                "mentions_messages",
                "stdout_to_llm_yes",
                "unknown_used",
            ]
        )
        for name, block in all_results.items():
            for phase, pdata in block["phases"].items():
                h = pdata["mechanical_hints"]
                w.writerow(
                    [
                        name,
                        phase,
                        bool(pdata["parsed"]),
                        len(pdata.get("cite_errors") or []),
                        h.get("mentions_dumps"),
                        h.get("mentions_520"),
                        h.get("mentions_850"),
                        h.get("mentions_messages"),
                        h.get("stdout_to_llm_yes"),
                        h.get("unknown_used"),
                    ]
                )

    (out / "README.md").write_text(
        "\n".join(
            [
                "# route_decomposition_experiment",
                "",
                "Qwen3:8b にコードを処理経路単位で渡すと経路追跡が改善するかを測る。",
                "本番 Tool / Agent / ranking は変更していない。",
                "",
                "- TEST-A: まとまったコード",
                "- TEST-B: search_web_spec_v2 + まとまったコード",
                "- TEST-C: 経路分解コード",
                "- TEST-D: 経路分解 + 実測ログ",
                "",
                f"model={model} num_ctx={args.num_ctx} temperature=0",
                "",
                "段階: 1入出力 → 2接続 → 3判定 → (D)4ログ → 5原因診断",
                "評価は EXPERIMENT_REPORT.md。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("done", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
