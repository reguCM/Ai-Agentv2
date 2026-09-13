"""
search_web 仕様書併用コード読解実験。本番 Tool / Agent は変更しない。
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

THIS_DIR = Path(__file__).resolve().parent
SEARCH_QUALITY_DIR = THIS_DIR.parent
RUNS_DIR = THIS_DIR / "runs"
SPEC_PATH = THIS_DIR / "specs" / "search_web_spec.md"

SNIPPETS = [
    {"file": "tools/system/network/search_web.py", "start_line": 1, "end_line": 60},
    {"file": "tools/system/network/general_web_search.py", "start_line": 1, "end_line": 240},
    {"file": "tools/system/tool_builder/research/web.py", "start_line": 1, "end_line": 120},
    {"file": "tools/system/tool_builder/research/web.py", "start_line": 295, "end_line": 305},
    {"file": "agent.py", "start_line": 347, "end_line": 404},
    {"file": "agent.py", "start_line": 520, "end_line": 541},
    {"file": "agent.py", "start_line": 832, "end_line": 858},
    {
        "file": "research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/run_web_effect_pilot.py",
        "start_line": 90,
        "end_line": 160,
    },
]

CASE_IDS = [
    "A06", "E04", "C03", "P02b", "C02", "A03",
    "A04", "C04", "B05", "WB02", "P02a", "E02",
]


def detect_repo() -> Path:
    p = THIS_DIR.resolve()
    for _ in range(20):
        if (p / "tools" / "system" / "network" / "search_web.py").is_file():
            return p
        p = p.parent
    return THIS_DIR.resolve()


REPO = detect_repo()


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 3.0))


def read_snippet(file_rel: str, start: int, end: int) -> str:
    lines = (REPO / file_rel).read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, int(start))
    end = min(len(lines), int(end))
    chunk = [f"{i + start}|{line}" for i, line in enumerate(lines[start - 1 : end])]
    return f"## FILE {file_rel} L{start}-{end}\n" + "\n".join(chunk)


def build_code_pack() -> str:
    parts = [
        "注: Agent 公開 search_web は general_web_search を使う。"
        "Tool Builder 用 research.web.search_web は呼ばない。",
    ]
    for s in SNIPPETS:
        parts.append(read_snippet(s["file"], s["start_line"], s["end_line"]))
    return "\n\n".join(parts)


def load_logs() -> str:
    import sys

    sys.path.insert(0, str(THIS_DIR))
    from run_tool_diagnosis import _load_search_web_quality_evidence

    pack = _load_search_web_quality_evidence(
        CASE_IDS,
        review_dataset_json=SEARCH_QUALITY_DIR / "review_dataset.json",
        ranking_csv=SEARCH_QUALITY_DIR / "ranking_comparison.csv",
        include_extract_probes=True,
    )
    blocks = []
    for cid in CASE_IDS:
        blocks.append((pack.get(cid) or {}).get("evidence_text") or f"(missing {cid})")
    return "\n\n===== CASE =====\n\n".join(blocks)


def extract_json(text: str) -> dict | None:
    text = (text or "").strip()
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


def chat(client: Client, model: str, system: str, user: str, num_ctx: int, num_predict: int) -> str:
    resp = client.chat(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        options={"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict},
        keep_alive="10m",
    )
    msg = getattr(resp, "message", None)
    return "" if msg is None else str(getattr(msg, "content", None) or "")


QUESTIONS = """
6問に JSON のみで答えよ。各問いは次のキーを持つ:
answer, file, line_or_range, function, evidence_quote,
confidence (high|medium|low|unknown),
evidence_level (コードから直接確認できる|仕様書から確認できる|ログから確認できる|推測|判断不能),
uncertainty

行番号が確認できない場合は line_or_range を空文字、answer に「根拠を確認できない」と書いてよい。
存在しない行番号を作るな。コードに無い処理を推測で「存在する」と書くな。

{
  "q1_path_user_to_llm": {},
  "q2_ranking_vs_filter": {},
  "q3_agent_to_llm": {},
  "q4_json_production_vs_harness": {},
  "q5_wiki_page_body_in_production": {},
  "q6_technical_query_empty_branch": {}
}

q1: ユーザー要求から LLM に検索結果が渡るまでの実際の経路。
q2: ranking で除外されるのか、別の filter か。コード根拠。
q3: 検索結果は Agent から LLM へどう渡るか。コード根拠。画面表示用要約と混同するな。
q4: JSON 化はどこか。本番コードと診断ハーネスを区別せよ。
q5: 本番 Tool はページ本文を取得するか。
q6: 「技術クエリの場合に空結果を返す」条件はコード上に存在するか。あるなら根拠、無いなら無いと書け。
"""

SYSTEM_A = """コードと実測ログだけを根拠にする。仕様書は与えられていない。
SPEC/CODE/OBSERVATION/INFERENCE を混同するな。JSONのみ。"""

SYSTEM_B = """仕様書は設計地図である。答えの行番号は仕様書に無い。
実装の根拠は必ずコードから取る。SPEC と CODE が違うときは CODE を優先。
SPEC/CODE/OBSERVATION/INFERENCE を混同するな。JSONのみ。"""

SYSTEM_C = """仕様書のみが与えられている。コードもログも無い。
ファイル名・行番号が仕様書に無ければ「根拠を確認できない」と書け。
推測で行番号を作るな。JSONのみ。"""


def verify_line_citations(parsed: dict | None) -> list[dict[str, Any]]:
    """提示された file+行が実在するか。存在しない行は重大エラー。"""
    errors = []
    if not parsed:
        return [{"error": "unparsed"}]
    for key, block in parsed.items():
        if not isinstance(block, dict):
            continue
        f = str(block.get("file") or "").strip()
        lr = str(block.get("line_or_range") or "").strip()
        if not f or not lr:
            continue
        nums = [int(x) for x in re.findall(r"\d+", lr)]
        if not nums:
            continue
        path = REPO / f.replace("\\", "/")
        # allow basename-only mistakes to be flagged
        if not path.is_file():
            errors.append({"key": key, "file": f, "issue": "file_not_found", "line_or_range": lr})
            continue
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
    return errors


def human_grade(parsed: dict | None, *, spec_only: bool) -> dict[str, str]:
    if not parsed:
        return {f"q{i}": "failed" for i in range(1, 7)}
    t = json.dumps(parsed, ensure_ascii=False).lower()

    def get(q: str) -> str:
        return json.dumps(parsed.get(q) or {}, ensure_ascii=False).lower()

    g: dict[str, str] = {}
    q1 = get("q1_path_user_to_llm")
    g["q1"] = (
        "passed"
        if "search_web" in q1 and ("general_web" in q1 or "backend" in q1 or "duckduckgo" in q1)
        else "partially_passed"
    )
    q2 = get("q2_ranking_vs_filter")
    if "rank_hits" in q2 or "score" in q2:
        if "title" in q2 and "snippet" in q2:
            g["q2"] = "passed"
        else:
            g["q2"] = "partially_passed"
    else:
        g["q2"] = "failed"
    q3 = get("q3_agent_to_llm")
    dumps = "json.dumps" in q3 or "dumps" in q3
    stdout = "stdout" in q3 or "要約" in q3 or "l520" in q3 or "520" in q3
    if dumps and not (stdout and "llm" in q3 and "520" in q3 and "dumps" not in q3):
        # if they say dumps is llm path
        g["q3"] = "passed" if dumps else "failed"
    elif dumps:
        g["q3"] = "passed"
    elif stdout and not dumps:
        g["q3"] = "failed"
    else:
        g["q3"] = "partially_passed" if "agent" in q3 or "tool" in q3 else "failed"
    q4 = get("q4_json_production_vs_harness")
    if spec_only:
        g["q4"] = "passed" if "確認できない" in q4 or "仕様書" in q4 else "partially_passed"
    else:
        prod = "agent.py" in q4
        harness = "pilot" in q4 or "harness" in q4 or "診断" in q4
        g["q4"] = "passed" if prod and (harness or "dumps" in q4) else "partially_passed" if prod or "dumps" in q4 else "failed"
    q5 = get("q5_wiki_page_body_in_production")
    if any(x in q5 for x in ("ない", "no", "存在しない", "持っていない", "確認できない")):
        if "yes" in q5 and "ある" in q5:
            g["q5"] = "partially_passed"
        else:
            g["q5"] = "passed"
    else:
        g["q5"] = "failed"
    q6 = get("q6_technical_query_empty_branch")
    if any(x in q6 for x in ("ない", "存在しない", "no such", "確認できない")):
        g["q6"] = "passed"
    elif "yes" in q6 or "存在する" in q6:
        g["q6"] = "failed"
    else:
        g["q6"] = "unknown"
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="qwen3_8b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=4096)
    args = ap.parse_args()

    model = get_llm_profile(args.model_id)["model"]
    client = Client(timeout=240)
    spec = SPEC_PATH.read_text(encoding="utf-8")
    code = build_code_pack()
    logs = load_logs()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / run_id / "spec_experiment"
    out.mkdir(parents=True, exist_ok=True)
    (out / "spec_used.md").write_text(spec, encoding="utf-8")
    (out / "code_pack.txt").write_text(code, encoding="utf-8")

    tests = []
    # A
    user_a = "実測ログは参考。根拠の行番号はコードから。\n" + QUESTIONS + "\n--- コード ---\n" + code + "\n--- ログ ---\n" + logs
    tests.append(("TEST_A", SYSTEM_A, user_a, False, True))
    user_b = (
        "仕様書は地図。行番号はコードから。\n"
        + QUESTIONS
        + "\n--- 仕様書 ---\n"
        + spec
        + "\n--- コード ---\n"
        + code
        + "\n--- ログ ---\n"
        + logs
    )
    tests.append(("TEST_B", SYSTEM_B, user_b, False, True))
    user_c = "コードもログも無い。仕様書のみ。\n" + QUESTIONS + "\n--- 仕様書 ---\n" + spec
    tests.append(("TEST_C", SYSTEM_C, user_c, True, False))

    all_parsed = {}
    measurements = []
    for name, system, user, spec_only, _has_code in tests:
        print(name, "...")
        (out / f"actual_prompt_{name}.txt").write_text(
            f"[SYSTEM]\n{system}\n\n[USER]\n{user}", encoding="utf-8"
        )
        raw = chat(client, model, system, user, args.num_ctx, args.num_predict)
        parsed = extract_json(raw)
        (out / f"{name}.md").write_text(
            f"# {name}\n\n```json\n{json.dumps(parsed or {'_raw': raw[:20000]}, ensure_ascii=False, indent=2)}\n```\n",
            encoding="utf-8",
        )
        (out / f"{name}_raw.txt").write_text(raw, encoding="utf-8")
        meas = {
            "test": name,
            "prompt_chars": len(system) + len(user),
            "prompt_tokens_est": estimate_tokens(system + user),
            "output_chars": len(raw),
            "fits_est": estimate_tokens(system + user) < args.num_ctx * 0.9,
        }
        measurements.append(meas)
        cites = verify_line_citations(parsed)
        grade = human_grade(parsed, spec_only=spec_only)
        all_parsed[name] = {
            "parsed": parsed,
            "cite_errors": cites,
            "grade": grade,
            "spec_only": spec_only,
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "num_ctx": args.num_ctx,
        "spec_path": str(SPEC_PATH),
        "measurements": measurements,
        "tests": all_parsed,
        "implementation_changed": False,
    }
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["test", "q1", "q2", "q3", "q4", "q5", "q6", "cite_errors"])
        for name, block in all_parsed.items():
            g = block["grade"]
            w.writerow(
                [
                    name,
                    g.get("q1"),
                    g.get("q2"),
                    g.get("q3"),
                    g.get("q4"),
                    g.get("q5"),
                    g.get("q6"),
                    len(block.get("cite_errors") or []),
                ]
            )

    print("done", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
