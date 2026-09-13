"""
Qwen3:8b コード読解能力検証（診断ハーネス実験のみ・本番Tool変更なし）。

TEST-A: コードのみ
TEST-B: コード＋実測ログ（過去LLM診断なし）
TEST-C: TEST-B結果からの原因診断（誘導・過去診断なし）

num_ctx を大きくし、実際に LLM へ送ったプロンプトを保存する。
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

from tools.system.config import get_llm_profile, load_yaml

THIS_DIR = Path(__file__).resolve().parent
SEARCH_QUALITY_DIR = THIS_DIR.parent
RUNS_DIR = THIS_DIR / "runs"

SNIPPETS = [
    {"file": "tools/system/network/search_web.py", "start_line": 1, "end_line": 60},
    {"file": "tools/system/network/general_web_search.py", "start_line": 1, "end_line": 240},
    {"file": "tools/system/tool_builder/research/web.py", "start_line": 1, "end_line": 120},
    {"file": "tools/system/tool_builder/research/web.py", "start_line": 295, "end_line": 305},
    {"file": "agent.py", "start_line": 347, "end_line": 404},
    {"file": "agent.py", "start_line": 520, "end_line": 541},
    {"file": "agent.py", "start_line": 621, "end_line": 633},
    {"file": "agent.py", "start_line": 832, "end_line": 858},
    {
        "file": "research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/run_web_effect_pilot.py",
        "start_line": 90,
        "end_line": 114,
    },
]

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_repo_root() -> Path:
    p = THIS_DIR.resolve()
    for _ in range(20):
        if (p / "tools" / "system" / "network" / "search_web.py").is_file():
            return p
        p = p.parent
    return THIS_DIR.resolve()


REPO = detect_repo_root()


def estimate_tokens(text: str) -> int:
    """混合日英の粗い推定。記録用であり正確な tokenizer ではない。"""
    return max(1, int(len(text) / 3.0))


def read_snippet(file_rel: str, start: int, end: int) -> tuple[str, int]:
    path = REPO / file_rel
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    file_line_count = len(lines)
    start = max(1, int(start))
    end = min(file_line_count, int(end))
    chunk = lines[start - 1 : end]
    numbered = [f"{i + start}|{line}" for i, line in enumerate(chunk)]
    return f"## FILE {file_rel} L{start}-{end} (file_lines={file_line_count})\n" + "\n".join(
        numbered
    ), file_line_count


def build_code_pack() -> tuple[str, list[dict[str, Any]]]:
    meta = []
    parts = [
        "注: Agent 公開 search_web は general_web_search を呼ぶ。"
        "Tool Builder 用 research.web.search_web（MS Learn）は呼ばない。",
        "注: compact_hit は title/snippet/url/backend のみ。",
    ]
    for snip in SNIPPETS:
        text, nlines = read_snippet(snip["file"], snip["start_line"], snip["end_line"])
        parts.append(text)
        meta.append(
            {
                "file": snip["file"],
                "start_line": snip["start_line"],
                "end_line": snip["end_line"],
                "file_line_count": nlines,
                "chars": len(text),
            }
        )
    pack = "\n\n".join(parts)
    return pack, meta


def load_evidence_text() -> str:
    from run_tool_diagnosis import _load_search_web_quality_evidence

    review = SEARCH_QUALITY_DIR / "review_dataset.json"
    ranking = SEARCH_QUALITY_DIR / "ranking_comparison.csv"
    pack = _load_search_web_quality_evidence(
        CASE_IDS,
        review_dataset_json=review,
        ranking_csv=ranking,
        include_extract_probes=True,
    )
    blocks = []
    for cid in CASE_IDS:
        ev = pack.get(cid) or {}
        blocks.append(ev.get("evidence_text") or f"(missing {cid})")
    return "\n\n===== CASE SEPARATOR =====\n\n".join(blocks)


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


def chat(
    *,
    client: Client,
    model: str,
    system: str,
    user: str,
    num_ctx: int,
    num_predict: int,
) -> tuple[str, dict | None]:
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict},
        keep_alive="10m",
    )
    msg = getattr(resp, "message", None)
    raw = "" if msg is None else str(getattr(msg, "content", None) or "")
    return raw, extract_json(raw)


def measure(name: str, system: str, user: str, num_ctx: int, raw_out: str) -> dict[str, Any]:
    prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{user}"
    prompt_chars = len(prompt)
    prompt_tokens = estimate_tokens(prompt)
    out_chars = len(raw_out or "")
    # 粗い予算: 1 token ≒ 3 chars。余裕 10%
    budget_chars = int(num_ctx * 3 * 0.9)
    truncated_in = prompt_chars > budget_chars
    truncated_out = bool(raw_out) and not raw_out.strip().endswith("}")
    return {
        "test": name,
        "prompt_chars": prompt_chars,
        "prompt_tokens_est": prompt_tokens,
        "output_chars": out_chars,
        "output_tokens_est": estimate_tokens(raw_out or ""),
        "num_ctx": num_ctx,
        "approx_char_budget_90pct": budget_chars,
        "code_or_prompt_likely_truncated_by_ctx": truncated_in,
        "output_possibly_truncated": truncated_out,
        "fits_in_ctx_est": not truncated_in,
    }


TEST_A_SYSTEM = """あなたはコード読解の検証対象である。与えられたコード抜粋だけを根拠にする。
実測ログ・過去の診断・原因仮説は与えられていない。
存在しない処理を推測で「存在する」と書いてはならない。
確認できない場合は「コード上確認できない」と書く。
JSONのみ出力。"""

TEST_A_QUESTIONS = """以下のコード抜粋だけを読み、JSONのみで答えよ。

各問いに file, approx_lines（分かる範囲）, function, answer, evidence_quote（短い引用）を付ける。
確認できない場合は answer に「コード上確認できない」と書き、file は空文字。

{
  "q1_entrypoint": {},
  "q2_fetch_candidates": {},
  "q3_ddg_and_wikipedia": {},
  "q4_snippet_source": {},
  "q5_ranking_function": {},
  "q6_ranking_exclude_conditions": {},
  "q7_agent_handoff_path": {},
  "q8_json_dumps_location": {},
  "q9_wikipedia_page_body_in_production": {},
  "q10_retry_exists": {},
  "nonexistent_or_unconfirmed": {
    "items": [
      {"process": "...", "verdict": "absent|present|コード上確認できない", "file": "", "why": ""}
    ]
  }
}

問い:
1. search_web の入口となる関数は何か。
2. 検索候補を取得する処理はどの関数か。
3. DuckDuckGo と Wikipedia はどこで処理されるか。
4. snippet/description はどこから取得されるか。
5. ranking はどの関数か。
6. ranking で候補が除外される条件は何か。
7. 検索結果が Agent 側へ渡される経路。
8. 検索結果を JSON 化して受け渡している箇所。
9. Wikipedia のページ本文取得は本番経路に存在するか（yes/no/コード上確認できない）。
10. 検索失敗時の retry は存在するか（yes/no/コード上確認できない）。

nonexistent_or_unconfirmed では、コードに無い、または確認できない処理を最大3つ。無理に捏造しない。
候補例（存在するとは限らない）: Wikipedia本文GET、自動翻訳、retry、ページ再取得。

--- コード抜粋 ---
"""

TEST_B_SYSTEM = """コードFACTと観測FACTと推測を混同しない。
CODE_FACT: コードから直接確認できること。
OBSERVATION_FACT: 実測ログから直接確認できること。
INFERENCE: 両者を組み合わせた推測。断定しない。
存在しない処理をコードにあると書いてはならない。
JSONのみ。過去の診断結果は与えられていない。"""

TEST_B_USER = """コード抜粋と12ケースの実測ログを照合せよ。

出力:
{
  "code_facts": ["..."],
  "observation_facts": ["...（ケースIDを付ける）"],
  "inferences": ["..."],
  "links_code_to_log": [
    {"case_id": "...", "observation": "...", "matching_code_fact": "...", "file": ""}
  ],
  "cannot_confirm": ["..."]
}

--- コード抜粋 ---
{code}

--- 実測ログ ---
{logs}
"""

TEST_C_SYSTEM = """原因候補を自分で作れ。事前結論は与えられていない。
各候補に confidence: strong|moderate|weak|unknown。
code_evidence には file と根拠。示せない場合は unknown とし「コード上の根拠を確認できないためunknown」。
「コードにその処理がない」と言うなら file と根拠必須。
JSONのみ。"""

TEST_C_USER = """TEST-B相当の材料から、search_web 品質低下の原因候補を分析せよ。誘導された結論はない。

{
  "cause_candidates": [
    {
      "name": "...",
      "confidence": "strong|moderate|weak|unknown",
      "code_evidence": {"file": "", "what": ""},
      "log_evidence": {"cases": [], "what": ""},
      "counterevidence": [],
      "missing_info": []
    }
  ],
  "ranked": ["name1", "name2"],
  "fix_proposals_not_executed": [],
  "investigation_proposals": [],
  "unknowns": []
}

--- TEST-B JSON ---
{test_b}

--- コード抜粋（再掲） ---
{code}

--- 実測ログ要約（再掲・短縮しない場合は全文） ---
{logs}
"""


def grade_test_a(parsed: dict | None) -> dict[str, Any]:
    """人間検証用の機械照合。LLMの自己採点ではない。"""
    if not parsed:
        return {"overall": "failed", "notes": ["JSON parse failed"], "items": {}}

    def blob(key: str) -> str:
        v = parsed.get(key) or {}
        return json.dumps(v, ensure_ascii=False).lower()

    checks = {
        "q1": ("search_web", ["search_web.py"]),
        "q2": ("general_web_search", ["general_web_search.py"]),
        "q3": ("duckduckgo", ["web.py", "search_duckduckgo"]),
        "q4": ("snippet", ["abstracttext", "opensearch", "payload", "compact_hit"]),
        "q5": ("rank", ["rank_hits_for_query"]),
        "q6": ("score", ["score > 0", "score>0", "positive", "return_limit", "unique"]),
        "q7": ("agent", ["json.dumps", "tool", "messages"]),
        "q8": ("json", ["json.dumps"]),
        "q9_body_absent": ("q9", None),
        "q10_retry_absent": ("q10", None),
    }
    items = {}
    q1 = blob("q1_entrypoint")
    items["q1"] = "passed" if "search_web" in q1 else "failed"
    q2 = blob("q2_fetch_candidates")
    items["q2"] = "passed" if "general_web_search" in q2 or "search_duckduckgo" in q2 else "partially_passed"
    q3 = blob("q3_ddg_and_wikipedia")
    items["q3"] = (
        "passed"
        if ("duckduckgo" in q3 or "search_duckduckgo" in q3)
        and ("wikipedia" in q3)
        else "failed"
    )
    q4 = blob("q4_snippet_source")
    items["q4"] = (
        "passed"
        if any(x in q4 for x in ("abstract", "opensearch", "payload", "compact_hit", "description"))
        else "failed"
    )
    q5 = blob("q5_ranking_function")
    items["q5"] = "passed" if "rank_hits" in q5 else "failed"
    q6 = blob("q6_ranking_exclude_conditions")
    items["q6"] = (
        "passed"
        if any(x in q6 for x in ("score", "limit", "unique", "positive"))
        else "failed"
    )
    q7 = blob("q7_agent_handoff_path")
    items["q7"] = "passed" if "json.dumps" in q7 or "agent.py" in q7 or "tool" in q7 else "failed"
    q8 = blob("q8_json_dumps_location")
    items["q8"] = "passed" if "json.dumps" in q8 or "agent.py" in q8 else "failed"
    q9 = blob("q9_wikipedia_page_body_in_production")
    items["q9"] = (
        "passed"
        if any(x in q9 for x in ("no", "ない", "存在しない", "確認できない"))
        and "yes" not in q9.split("verdict", 1)[0][-40:]
        else "partially_passed"
    )
    # simpler q9: fail if claims body fetch exists as yes
    ans9 = str((parsed.get("q9_wikipedia_page_body_in_production") or {}).get("answer") or "").lower()
    if any(x in ans9 for x in ("存在しない", "ない", "no", "確認できない")):
        items["q9"] = "passed"
    elif "yes" in ans9 or "ある" in ans9:
        items["q9"] = "failed"
    else:
        items["q9"] = "unknown"
    ans10 = str((parsed.get("q10_retry_exists") or {}).get("answer") or "").lower()
    if any(x in ans10 for x in ("ない", "no", "存在しない", "確認できない")):
        items["q10"] = "passed"
    elif "yes" in ans10 or "ある" in ans10:
        items["q10"] = "failed"
    else:
        items["q10"] = "unknown"

    vals = list(items.values())
    if all(v == "passed" for v in vals):
        overall = "passed"
    elif any(v == "failed" for v in vals) and any(v == "passed" for v in vals):
        overall = "partially_passed"
    elif all(v == "failed" for v in vals):
        overall = "failed"
    else:
        overall = "partially_passed"
    return {"overall": overall, "items": items, "notes": ["機械照合。最終判定は人間。"]}


def write_md_json(path: Path, title: str, parsed: dict | None, raw: str, meas: dict) -> None:
    path.write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                f"- model measurements: `{json.dumps(meas, ensure_ascii=False)}`",
                "",
                "## parsed JSON",
                "",
                "```json",
                json.dumps(parsed or {"_unparsed": True}, ensure_ascii=False, indent=2)[:200000],
                "```",
                "",
                "## raw output (truncated in md if huge)",
                "",
                "```",
                (raw or "")[:30000],
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="qwen3_8b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=4096)
    args = ap.parse_args()

    profile = get_llm_profile(args.model_id)
    model = profile["model"]
    client = Client(timeout=240)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / run_id / "code_reading_experiment"
    out.mkdir(parents=True, exist_ok=True)

    code_pack, file_meta = build_code_pack()
    (out / "code_pack.txt").write_text(code_pack, encoding="utf-8")

    import sys

    sys.path.insert(0, str(THIS_DIR))
    logs = load_evidence_text()
    (out / "logs_compact.txt").write_text(logs, encoding="utf-8")

    # TEST-A
    user_a = TEST_A_QUESTIONS + code_pack
    prompt_a = f"[SYSTEM]\n{TEST_A_SYSTEM}\n\n[USER]\n{user_a}"
    (out / "actual_llm_prompt_TEST_A.txt").write_text(prompt_a, encoding="utf-8")
    (out / "actual_llm_prompt.txt").write_text(
        "See actual_llm_prompt_TEST_A.txt / _TEST_B.txt / _TEST_C.txt\n", encoding="utf-8"
    )
    print("TEST-A ...")
    raw_a, parsed_a = chat(
        client=client,
        model=model,
        system=TEST_A_SYSTEM,
        user=user_a,
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
    )
    meas_a = measure("TEST-A", TEST_A_SYSTEM, user_a, args.num_ctx, raw_a)
    grade_a = grade_test_a(parsed_a)
    write_md_json(out / "TEST_A_CODE_READING.md", "TEST-A コード読解", parsed_a, raw_a, meas_a)
    (out / "TEST_A_raw.txt").write_text(raw_a, encoding="utf-8")

    # TEST-B
    user_b = TEST_B_USER.replace("{code}", code_pack).replace("{logs}", logs)
    (out / "actual_llm_prompt_TEST_B.txt").write_text(
        f"[SYSTEM]\n{TEST_B_SYSTEM}\n\n[USER]\n{user_b}", encoding="utf-8"
    )
    print("TEST-B ...")
    raw_b, parsed_b = chat(
        client=client,
        model=model,
        system=TEST_B_SYSTEM,
        user=user_b,
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
    )
    meas_b = measure("TEST-B", TEST_B_SYSTEM, user_b, args.num_ctx, raw_b)
    write_md_json(out / "TEST_B_CODE_LOG_ANALYSIS.md", "TEST-B コード＋ログ", parsed_b, raw_b, meas_b)
    (out / "TEST_B_raw.txt").write_text(raw_b, encoding="utf-8")

    # TEST-C: use TEST-B parsed if available, else raw snippet
    test_b_blob = json.dumps(parsed_b or {"raw_unparsed": (raw_b or "")[:8000]}, ensure_ascii=False)
    # logs may overflow C; keep logs but record size
    user_c = (
        TEST_C_USER.replace("{test_b}", test_b_blob)
        .replace("{code}", code_pack)
        .replace("{logs}", logs)
    )
    (out / "actual_llm_prompt_TEST_C.txt").write_text(
        f"[SYSTEM]\n{TEST_C_SYSTEM}\n\n[USER]\n{user_c}", encoding="utf-8"
    )
    print("TEST-C ...")
    raw_c, parsed_c = chat(
        client=client,
        model=model,
        system=TEST_C_SYSTEM,
        user=user_c,
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
    )
    meas_c = measure("TEST-C", TEST_C_SYSTEM, user_c, args.num_ctx, raw_c)
    write_md_json(out / "TEST_C_CAUSE_DIAGNOSIS.md", "TEST-C 原因診断", parsed_c, raw_c, meas_c)
    (out / "TEST_C_raw.txt").write_text(raw_c, encoding="utf-8")

    results = {
        "generated_at": _now(),
        "model_id": args.model_id,
        "model": model,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "code_file_count": len(SNIPPETS),
        "code_pack_chars": len(code_pack),
        "code_pack_tokens_est": estimate_tokens(code_pack),
        "files": file_meta,
        "measurements": [meas_a, meas_b, meas_c],
        "test_a_mechanical_grade": grade_a,
        "test_a": parsed_a,
        "test_b": parsed_b,
        "test_c": parsed_c,
        "test_a_raw_chars": len(raw_a or ""),
        "test_b_raw_chars": len(raw_b or ""),
        "test_c_raw_chars": len(raw_c or ""),
        "implementation_changed": False,
        "prior_llm_diagnosis_not_in_input": True,
    }
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "test",
                "prompt_chars",
                "prompt_tokens_est",
                "output_chars",
                "fits_in_ctx_est",
                "code_or_prompt_likely_truncated_by_ctx",
                "output_possibly_truncated",
            ],
        )
        w.writeheader()
        for m in (meas_a, meas_b, meas_c):
            w.writerow({k: m.get(k) for k in w.fieldnames})

    (out / "README.md").write_text(
        "\n".join(
            [
                "# code_reading_experiment",
                "",
                f"- run_id: {run_id}",
                f"- model: `{model}`",
                f"- num_ctx: {args.num_ctx}",
                f"- code_pack_chars: {len(code_pack)}",
                "",
                "TEST-A/B/C。過去のLLM診断は入力に含めていない。",
                "本番 search_web は変更していない。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # EXPERIMENT_REPORT skeleton; comparison filled after we read results in same process
    report = build_report(results, grade_a, parsed_a, parsed_b, parsed_c, meas_a, meas_b, meas_c)
    (out / "EXPERIMENT_REPORT.md").write_text(report, encoding="utf-8")

    (out / "prompts_used.md").write_text(
        "\n".join(
            [
                "# 使用プロンプト",
                "",
                "## TEST-A SYSTEM",
                TEST_A_SYSTEM,
                "",
                "## TEST-B SYSTEM",
                TEST_B_SYSTEM,
                "",
                "## TEST-C SYSTEM",
                TEST_C_SYSTEM,
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"done -> {out}")
    return 0


def build_report(
    results: dict,
    grade_a: dict,
    a: dict | None,
    b: dict | None,
    c: dict | None,
    ma: dict,
    mb: dict,
    mc: dict,
) -> str:
    a_ok = grade_a.get("overall")
    b_sep = False
    if b:
        b_sep = bool(b.get("code_facts")) and bool(b.get("observation_facts"))
    c_has = bool(c and (c.get("cause_candidates") or c.get("ranked")))

    # Pattern heuristic (human-verifiable, not LLM self-score)
    pattern = "判定保留（レポート本文を人間確認）"
    if a_ok == "passed" and ma.get("fits_in_ctx_est") and (not b or not mb.get("fits_in_ctx_est")):
        pattern = "パターンC寄り（コード単体は収まるがBで逼迫）の可能性"
    elif a_ok in ("passed", "partially_passed") and not ma.get("code_or_prompt_likely_truncated_by_ctx"):
        if a_ok == "failed":
            pattern = "パターンB寄り"
        elif c_has and b_sep:
            pattern = "パターンAまたはDの切り分けは人間確認（読解はできた可能性）"
        elif a_ok == "passed" and (not c_has):
            pattern = "パターンD寄り（読解はでき原因診断が崩れた）の可能性"

    lines = [
        "# EXPERIMENT_REPORT",
        "",
        f"- generated: {results.get('generated_at')}",
        f"- model: `{results.get('model')}`",
        f"- num_ctx: {results.get('num_ctx')}",
        f"- code files in pack: {results.get('code_file_count')}",
        f"- code_pack_chars: {results.get('code_pack_chars')}",
        f"- code_pack_tokens_est: {results.get('code_pack_tokens_est')}",
        "",
        "## コンテキスト測定",
        "",
        f"- TEST-A prompt_chars={ma.get('prompt_chars')} tokens_est={ma.get('prompt_tokens_est')} fits={ma.get('fits_in_ctx_est')} truncated_in={ma.get('code_or_prompt_likely_truncated_by_ctx')} out_trunc={ma.get('output_possibly_truncated')}",
        f"- TEST-B prompt_chars={mb.get('prompt_chars')} tokens_est={mb.get('prompt_tokens_est')} fits={mb.get('fits_in_ctx_est')} truncated_in={mb.get('code_or_prompt_likely_truncated_by_ctx')} out_trunc={mb.get('output_possibly_truncated')}",
        f"- TEST-C prompt_chars={mc.get('prompt_chars')} tokens_est={mc.get('prompt_tokens_est')} fits={mc.get('fits_in_ctx_est')} truncated_in={mc.get('code_or_prompt_likely_truncated_by_ctx')} out_trunc={mc.get('output_possibly_truncated')}",
        "",
        "実プロンプト: `actual_llm_prompt_TEST_A.txt` 等。code_pack.txt と差分確認可。",
        "",
        "## TEST-A 機械照合（人間確認用）",
        "",
        json.dumps(grade_a, ensure_ascii=False, indent=2),
        "",
        "## TEST-B 要点",
        "",
        f"- parsed: {'yes' if b else 'no'}",
        f"- CODE_FACT/OBSERVATION 分離: {'yes' if b_sep else 'no/partial'}",
        "",
        "## TEST-C 要点",
        "",
        f"- parsed: {'yes' if c else 'no'}",
        f"- cause_candidates: {len((c or {}).get('cause_candidates') or [])}",
        "",
        "## 過去診断との比較（TEST-C後・LLM入力には未使用）",
        "",
        "### データのみ (`llm_diagnosis/`)",
        "- 原因階層: C > A > その他。時間依存は弱い。追加調査は snippet空の本文確認。",
        "",
        "### コード＋ログ 4096ctx (`runs/20260824_164358/`)",
        "- CODE_ANALYSIS が「抜粋に含まれていない」と誤認。ケース分析にコード未添付。",
        "",
        "### 今回（大きめ num_ctx・プロンプト保存）",
        f"- TEST-A 機械 overall: {a_ok}",
        "- 詳細は TEST_C_CAUSE_DIAGNOSIS.md と results.json。",
        "",
        "## パターン仮判定（機械ヒューリスティック・最終は人間）",
        "",
        pattern,
        "",
        "## 最終報告欄（実験オペレータが本文を見て確定）",
        "",
        "### コード読解能力",
        f"機械照合 TEST-A: `{a_ok}` → 人間判定は EXPERIMENT_REPORT 追記または会話報告。",
        "",
        "### コード＋ログの統合能力",
        "`判定は TEST-B の CODE_FACT 分離と links_code_to_log を見ること。`",
        "",
        "### 原因診断能力",
        "`判定は TEST-C の code_evidence に file があるかを見ること。`",
        "",
        "### 前回の「コード不足」判定",
        "`ハーネス入力では誤り（コードはパックに存在）。モデルが読めなかったかは今回 TEST-A。`",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
