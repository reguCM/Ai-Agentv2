"""
Tool 診断フレームワーク（汎用 / 記録・観測・分析のみ）

対象 Tool のコード抜粋と実測ログ/観測データを LLM に読ませ、
原因候補を自力で整理させます。

既存の Tool / ranking / Agent / heuristic / Gate / Pipeline / Stage3/4 は変更しません。
出力は runs/<diagnostic_run_id>/ にのみ追加します。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama import Client

from tools.system.config import get_llm_profile, load_yaml


THIS_DIR = Path(__file__).resolve().parent
SEARCH_QUALITY_DIR = THIS_DIR.parent


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


def _detect_repo_root() -> Path:
    p = THIS_DIR.resolve()
    for _ in range(20):
        if (p / "tools" / "system" / "network" / "search_web.py").is_file():
            return p
        p = p.parent
    return THIS_DIR.resolve()


REPO_ROOT = _detect_repo_root()


def _read_lines(repo_rel_path: str, start: int, end: int) -> str:
    path = (REPO_ROOT / repo_rel_path).resolve()
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, int(start))
    end = min(len(lines), int(end))
    chunk = lines[start - 1 : end]
    numbered = [f"{i+start}|{line}" for i, line in enumerate(chunk)]
    return f"## {repo_rel_path} L{start}-{end}\n" + "\n".join(numbered)


def _build_code_pack(profile: dict[str, Any]) -> str:
    code_cfg = profile.get("code") or {}
    snippets = code_cfg.get("snippets") or []
    notes = code_cfg.get("notes") or ""

    parts: list[str] = []
    if notes:
        parts.append(notes.strip())

    for snip in snippets:
        repo_rel = snip.get("file")
        if not repo_rel:
            continue
        parts.append(
            _read_lines(
                repo_rel,
                snip.get("start_line") or 1,
                snip.get("end_line") or snip.get("start_line") or 1,
            )
        )
    return "\n\n".join(parts).strip()


def _load_search_web_quality_evidence(
    case_ids: list[str],
    *,
    review_dataset_json: Path,
    ranking_csv: Path,
    include_extract_probes: bool = True,
) -> dict[str, dict[str, Any]]:
    """
    search_web 診断用の観測データ整形（search_web 専用）。
    ただし、読み込み方式は profile 側で切り替える前提。
    """

    data = json.loads(review_dataset_json.read_text(encoding="utf-8"))
    records = {r["case_id"]: r for r in data.get("records") or []}

    ranking_rows_by_case: dict[str, list[dict[str, str]]] = {}
    if ranking_csv.is_file():
        with ranking_csv.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                cid = row.get("case_id")
                if not cid:
                    continue
                ranking_rows_by_case.setdefault(cid, []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for cid in case_ids:
        rec = records.get(cid)
        if not rec:
            continue
        mo = rec.get("machine_observation") or {}
        cc = mo.get("counts_chain") or {}
        ret = rec.get("search_web_return") or {}
        ranking_rows = ranking_rows_by_case.get(cid) or []

        # Evidence text（LLMへ渡す内容）は「観測」中心にする
        # LLMが FACT/INFERENCE を分離しやすいよう、観測値を並べる。
        evidence_lines: list[str] = []
        evidence_lines.extend(
            [
                f"case_id: {cid}",
                f"request: {rec.get('request') or ''}",
                f"query: {rec.get('query') or ''}",
                f"time_sensitive: {rec.get('time_sensitive')}",
                "counts:",
                f"  api_raw={cc.get('api_raw')}",
                f"  hit_accepted={cc.get('hit_accepted')}",
                f"  unique_after={cc.get('after_unique')}",
                f"  after_ranking={cc.get('after_ranking')}",
                f"  return={cc.get('return')}",
                f"  llm_received={cc.get('llm_received')}",
                f"api_snippet_nonempty: {rec.get('api_snippet_nonempty')}",
                f"api_snippet_empty: {rec.get('api_snippet_empty')}",
                f"return_snippet_nonempty: {mo.get('snippet_nonempty_in_return')}",
                f"return_snippet_empty: {mo.get('snippet_empty_in_return')}",
                f"ranking_dropped_total: {mo.get('dropped_by_ranking')}",
                f"ranking_dropped_with_snippet: {mo.get('dropped_with_snippet')}",
                f"extract_probe_page_has_usable_text: {mo.get('page_has_text_but_snippet_empty_probe')}",
                "",
                "=== raw_api (要約: 各backend先頭数件のみ) ===",
            ]
        )

        raw_api = rec.get("raw_api") or {}
        for backend, block in raw_api.items():
            evidence_lines.append(f"- backend: {backend}")
            for it in (block.get("items") or [])[:6]:
                sn = str(it.get("snippet") or "").strip()
                evidence_lines.append(
                    f"  api_rank={it.get('api_rank')} title={it.get('title')!r} "
                    f"url={it.get('url')!r} snippet_len={len(sn)} "
                    f"snippet_preview={sn[:120]!r}"
                )

        evidence_lines.extend(["", "=== search_web return hits ==="])
        for i, h in enumerate((ret.get("hits") or []), 1):
            sn = str(h.get("snippet") or "").strip()
            evidence_lines.append(
                f"[{i}] backend={h.get('backend')} title={h.get('title')!r} "
                f"url={h.get('url')!r} snippet_len={len(sn)} snippet_preview={sn[:200]!r}"
            )

        if ranking_rows:
            evidence_lines.extend(["", "=== ranking rows (dropped first then adopted) ==="])
            # CSV already contains adopted/exclude_reason etc.
            # Keep it short: first 30 rows.
            for r in ranking_rows[:30]:
                evidence_lines.append(
                    f"order={r.get('ranking_order')} score={r.get('score')} adopted={r.get('adopted')} "
                    f"exclude_reason={r.get('exclude_reason')!r} has_snippet={r.get('has_snippet')} "
                    f"title={r.get('title')!r} url={r.get('url')!r}"
                )

        if include_extract_probes:
            probes = rec.get("extract_probes") or []
            if probes:
                evidence_lines.extend(["", "=== extracts probes (調査専用) ==="])
                for p in probes[:4]:
                    if p.get("skipped"):
                        continue
                    evidence_lines.append(
                        f"title={p.get('title')!r} extract_len={p.get('extract_len')} "
                        f"page_has_usable_text={p.get('page_has_usable_text')}"
                    )

        out[cid] = {
            "case": rec,
            "evidence_text": "\n".join(evidence_lines).strip(),
        }
    return out


@dataclass
class LLMConfig:
    model_id: str
    model: str
    num_predict: int
    temperature: float
    context_limit: int


def _load_llm_config(model_id: str) -> LLMConfig:
    profile = get_llm_profile(model_id)
    # chat wrapper already exists but we use ollama client for stability.
    model = profile["model"]
    return LLMConfig(
        model_id=model_id,
        model=model,
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") or 0),
        context_limit=int(profile.get("context_limit") or 4096),
    )


def run_llm_json(
    *,
    client: Client,
    model_cfg: LLMConfig,
    system_prompt: str,
    user_prompt: str,
    num_predict: int | None = None,
    retries: int = 2,
) -> dict[str, Any]:
    last_raw = ""
    for i in range(retries + 1):
        extra = "\n有効JSONオブジェクト1つのみ。" if i else ""
        resp = client.chat(
            model=model_cfg.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + extra},
            ],
            options={
                "temperature": model_cfg.temperature,
                "num_ctx": model_cfg.context_limit,
                "num_predict": model_cfg.num_predict if num_predict is None else num_predict,
            },
            keep_alive="10m",
        )
        last_raw = _msg(resp)
        parsed = extract_json(last_raw)
        if parsed and isinstance(parsed, dict):
            return parsed
    return {"_raw": last_raw, "_parse_error": True}


def build_prompts(profile: dict[str, Any], code_pack: str) -> dict[str, str]:
    # 原因候補ラベルを profile から受け取り、プロンプトに固定結論を入れない
    cause_candidates = profile.get("cause_candidates") or {}
    candidate_lines: list[str] = []
    for code, desc in cause_candidates.items():
        candidate_lines.append(f"- {code}: {desc}")
    candidates_block = "\n".join(candidate_lines).strip()

    general_system = (
        "あなたは Tool 診断の分析者です。"
        "コードと観測ログのみを根拠に、原因候補を自力で整理してください。"
        "事前結論（例: Cが原因等）を繰り返さない。"
        "必ず観測事実と推測を分離し、判断不能はunknownにしてください。"
        "検索結果が空でも、'空＝無用'と決めつけないでください（ページ本文の有無等と分離）。"
    )

    code_prompt = (
        "現行コード抜粋を読んで、処理の流れ・入力/出力・外部依存・例外/エラー処理・"
        "観測ログと照合すべきポイントを整理せよ。"
        "結論の優先順位は先に決めない。候補を提示するだけ。"
        "JSONのみ出力。\n\n"
        f"原因候補（候補提示用）:\n{candidates_block}\n\n"
        f"--- コード抜粋 ---\n{code_pack}"
    )

    return {
        "general_system": general_system,
        "code_prompt": code_prompt,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="profiles/<tool>.yaml")
    ap.add_argument("--output-root", default=None, help="runs/ 配下を上書き")
    ap.add_argument("--case-ids", default="", help="カンマ区切り。空ならprofile指定を使用")
    ap.add_argument("--mode", default="evidence_only", choices=["evidence_only", "full"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.is_absolute():
        # 呼び出し側の指定ゆれを吸収:
        #  - プロファイルを diagnostic_framework/ から見て指定する場合
        #  - さらに diagnostic_framework/ を含めて指定してしまう場合
        cand1 = (THIS_DIR / profile_path).resolve()
        cand2 = (THIS_DIR.parent / profile_path).resolve()
        if cand1.is_file():
            profile_path = cand1
        elif cand2.is_file():
            profile_path = cand2
        else:
            profile_path = cand1

    profile = load_yaml(profile_path) or {}

    llm_model_id = str(profile.get("llm_model_id") or profile.get("llm_model") or "qwen3_8b")
    llm_cfg = _load_llm_config(llm_model_id)
    client = Client(timeout=int(profile.get("llm_timeout_seconds") or 180))

    diag_run_id = profile.get("diagnostic_run_id") or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = args.output_root or (THIS_DIR / "runs")
    out_dir = Path(output_root) / diag_run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    case_ids_cfg = profile.get("case_ids") or []
    if args.case_ids.strip():
        case_ids = [c.strip() for c in args.case_ids.split(",") if c.strip()]
    else:
        case_ids = [str(x) for x in case_ids_cfg]

    if profile.get("evidence_type") == "web_effect_review_search_quality_diagnosis":
        evidence_cfg = profile.get("evidence") or {}
        review_dataset_json = (SEARCH_QUALITY_DIR / (evidence_cfg.get("review_dataset_json") or "review_dataset.json")).resolve()
        ranking_csv = (SEARCH_QUALITY_DIR / (evidence_cfg.get("ranking_csv") or "ranking_comparison.csv")).resolve()

        evidence_pack = _load_search_web_quality_evidence(
            case_ids,
            review_dataset_json=review_dataset_json,
            ranking_csv=ranking_csv,
            include_extract_probes=bool(evidence_cfg.get("include_extract_probes", True)),
        )
    else:
        raise NotImplementedError(f"unknown evidence_type: {profile.get('evidence_type')}")

    # CODE pack
    code_pack = _build_code_pack(profile)
    prompts = build_prompts(profile, code_pack)

    # evidence_only mode
    if args.mode == "evidence_only":
        (out_dir / "evidence_dump.json").write_text(
            json.dumps(
                {
                    "run_id": diag_run_id,
                    "model_id": llm_model_id,
                    "case_ids": case_ids,
                    "evidence_type": profile.get("evidence_type"),
                    "evidence_cases": {cid: v.get("evidence_text") for cid, v in evidence_pack.items()},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out_dir / "code_pack.txt").write_text(code_pack, encoding="utf-8")
        (out_dir / "README.md").write_text(
            "\n".join(
                [
                    "# Tool diagnostic run (evidence_only)",
                    "",
                    f"- run_id: {diag_run_id}",
                    f"- model_id: {llm_model_id}",
                    f"- profile: {profile_path}",
                    "- outputs:",
                    "- evidence_dump.json",
                    "- code_pack.txt",
                ]
            ),
            encoding="utf-8",
        )
        print(f"evidence_only done -> {out_dir}")
        return 0

    # full mode: (1) code analysis -> (2) per-case -> (3) synthesis
    code_analysis = run_llm_json(
        client=client,
        model_cfg=llm_cfg,
        system_prompt=prompts["general_system"],
        user_prompt=prompts["code_prompt"],
    )

    case_analyses: dict[str, dict[str, Any]] = {}
    per_case_system = prompts["general_system"]

    # profile should provide a detailed case prompt; fallback to a generic one
    case_prompt_tmpl = profile.get("case_prompt") or (
        "コード抜粋とこのケースの観測ログ（FACT/observedのみ）から、"
        "原因候補（A〜など）を自力で整理せよ。修正案は不要。"
        "JSONのみ出力。\n\n"
        "--- 観測ログ ---\n{evidence}\n\n"
        "--- 必ず分離 ---\n"
        "- observed_facts\n"
        "- speculation\n"
    )
    case_prompt_tmpl = str(case_prompt_tmpl)

    for cid in case_ids:
        ev = evidence_pack.get(cid) or {}
        evidence_text = ev.get("evidence_text") or ""
        user_prompt = case_prompt_tmpl.format(evidence=evidence_text)
        parsed = run_llm_json(
            client=client,
            model_cfg=llm_cfg,
            system_prompt=per_case_system,
            user_prompt=user_prompt,
            num_predict=int(profile.get("case_num_predict") or 2048),
        )
        case_analyses[cid] = parsed
        time.sleep(float(profile.get("per_case_pause_sec") or 0.0))

    # Synthesis
    synth_prompt = profile.get("synthesis_prompt") or (
        "12ケース（{case_ids}）の結果を統合し、原因候補の優先順位を付けよ。"
        "ただし事前結論は繰り返さず、証拠の強さで根拠を明示する。JSONのみ出力。\n\n"
        "--- ケース分析（要約） ---\n{cases_blob}\n"
    )
    cases_blob = json.dumps(case_analyses, ensure_ascii=False)[:600000]
    synth_user_prompt = synth_prompt.format(
        case_ids=",".join(case_ids), cases_blob=cases_blob
    )
    synthesis = run_llm_json(
        client=client,
        model_cfg=llm_cfg,
        system_prompt=prompts["general_system"],
        user_prompt=synth_user_prompt,
        num_predict=int(profile.get("synthesis_num_predict") or 2048),
    )

    payload = {
        "diagnostic_run_id": diag_run_id,
        "model_id": llm_model_id,
        "model": llm_cfg.model,
        "profile_path": str(profile_path),
        "implementation_changed": False,
        "code_analysis": code_analysis,
        "case_analyses": case_analyses,
        "synthesis": synthesis,
    }
    (out_dir / "llm_code_diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Minimal CSV
    with (out_dir / "llm_code_diagnosis.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "primary", "raw_json"])
        for cid in case_ids:
            block = case_analyses.get(cid) or {}
            primary = block.get("primary_cause") or block.get("primary") or ""
            w.writerow([cid, primary, json.dumps(block, ensure_ascii=False)[:20000]])

    # Human sheet
    (out_dir / "HUMAN_DECISION_SHEET.md").write_text(
        "\n".join(
            [
                "# HUMAN_DECISION_SHEET",
                "",
                "LLMの診断を人間がレビューするための欄です。",
                "",
                "## 私の判断（全体）",
                "",
                "- 最も問題だと思う箇所 (A/B/C/D/...) : ",
                "- 次に問題だと思う箇所: ",
                "- Qwen3と同意する点: ",
                "- Qwen3と異なる点: ",
                "- 追加確認が必要な点: ",
                "- 今すぐ修正すべきだと思う点: ",
                "- まだ修正しない方がよい点: ",
                "",
                "---",
            ]
        ),
        encoding="utf-8",
    )

    (out_dir / "CODE_ANALYSIS.md").write_text(
        "# CODE_ANALYSIS\n\n" + json.dumps(code_analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "CASE_ANALYSIS.md").write_text(
        "# CASE_ANALYSIS\n\n"
        + "\n\n".join(
            [f"## {cid}\n\n" + json.dumps(case_analyses.get(cid) or {}, ensure_ascii=False, indent=2) for cid in case_ids]
        ),
        encoding="utf-8",
    )
    (out_dir / "LLM_DIAGNOSIS.md").write_text(
        "# LLM_DIAGNOSIS\n\n" + json.dumps(synthesis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"full done -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

