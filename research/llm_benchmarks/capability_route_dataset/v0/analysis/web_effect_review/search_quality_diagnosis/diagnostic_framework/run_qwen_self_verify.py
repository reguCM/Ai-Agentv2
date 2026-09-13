"""
Qwen3:8b 自己検証・修正提案テスト（記録・観測・分析のみ）

入力:
  diagnostic_framework/runs/<input_run_id>/llm_code_diagnosis.json

出力:
  diagnostic_framework/runs/<new_run_id>/self_verify/

目的:
  前回提示された原因候補を Qwen3 が再検証し、
  - FACT（観測事実）/ 推測
  - 原因候補の支持/否定/不明
  - 優先順位付きの修正案（提案のみ）と追加調査案（提案のみ）
  - 最終的な「自動修正許可」可否
  を一貫して出せるか確認する。
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama import Client

from tools.system.config import get_llm_profile


THIS_DIR = Path(__file__).resolve().parent
RUNS_DIR = THIS_DIR / "runs"


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


def run_llm_json(*, client: Client, model: str, system: str, user: str, num_predict: int) -> dict[str, Any]:
    resp = client.chat(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        options={"temperature": 0, "num_ctx": 8192, "num_predict": num_predict},
        keep_alive="10m",
    )
    raw = _msg(resp)
    parsed = extract_json(raw)
    if not parsed:
        return {"_raw": raw, "_parse_error": True}
    parsed["_raw"] = raw
    return parsed


def build_case_observed_facts(case_analyses: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for cid, c in (case_analyses or {}).items():
        obs = c.get("observed_facts")
        out.append({"case_id": cid, "observed_facts": obs})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-run-id", default="20260824_164358")
    ap.add_argument("--llm-model-id", default="qwen3_8b")
    ap.add_argument("--num-predict", type=int, default=3072)
    args = ap.parse_args()

    input_path = RUNS_DIR / args.input_run_id / "llm_code_diagnosis.json"
    if not input_path.is_file():
        raise FileNotFoundError(f"missing input: {input_path}")

    profile = get_llm_profile(args.llm_model_id)
    model = profile["model"]
    client = Client(timeout=int(profile.get("timeout_seconds") or 180))

    data = json.loads(input_path.read_text(encoding="utf-8"))
    priority_causes = (data.get("synthesis") or {}).get("priority_causes") or []
    code_analysis = data.get("code_analysis") or {}
    case_analyses = data.get("case_analyses") or {}

    observed_cases = build_case_observed_facts(case_analyses)

    new_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / new_run_id / "self_verify"
    out_dir.mkdir(parents=True, exist_ok=True)

    system = (
        "あなたは診断の自己検証者です。"
        "入力された「前回の原因候補」を、コード＋観測事実に基づいて再検証してください。"
        "事前結論（例: 'Cが原因'）は与えられていない前提で、毎回根拠を確認してください。"
        "各原因候補について、FACT/支持/否定/推測/不明を分離してください。"
        "修正案は提案のみ（実行しない）。"
        "JSONのみ出力。"
    )

    user = {
        "input_run_id": args.input_run_id,
        "model": model,
        "previous_priority_causes": priority_causes,
        "code_analysis_summary": code_analysis,
        "observed_cases": observed_cases,
        "requirements": {
            "for_each_cause": [
                "FACT（観測事実）",
                "支持する証拠（どのケースでどう観測されたか）",
                "否定する証拠（反例）",
                "単なる推測",
                "判断不能（unknown）",
                "撤回/優先順位下げ/維持 のいずれか"
            ],
            "outputs": [
                "現時点で修正すべき項目（優先順位付き、原因→根拠→提案→リスク→テスト）",
                "追加調査項目（優先順位付き、なぜ必要か）",
                "自動修正許可の可否（許可しない場合は理由）"
            ],
        },
    }

    case_verify_prompt = (
        "以下のJSON入力を材料に、自己検証と修正提案を行ってください。\n"
        "以下の出力スキーマに厳密に従ってJSONのみ出力してください。\n\n"
        "出力スキーマ:\n"
        "{\n"
        '  "diagnostic_run_id": "string",\n'
        '  "auto_fix_permission": {\n'
        '    "allowed_now": true/false,\n'
        '    "reason": "string",\n'
        "    \"blocking_unknowns\": [\"...\"]\n"
        "  },\n"
        '  "reassessed_causes": [\n'
        "    {\n"
        '      "original_cause": "string",\n'
        '      "status": "keep|downgrade|withdraw|unknown",\n'
        '      "revised_confidence": "strong|moderate|weak|unknown",\n'
        '      "facts": ["..."],\n'
        '      "supporting_evidence": ["..."],\n'
        '      "contradicting_evidence": ["..."],\n'
        '      "speculation": ["..."],\n'
        '      "unknowns": ["..."],\n'
        '      "why": "string"\n'
        "    }\n"
        "  ],\n"
        '  "fix_priorities_not_executed": [\n'
        "    {\n"
        '      "priority": 1,\n'
        '      "cause_unit": "string",\n'
        '      "what_to_change": "string",\n'
        '      "why": "string",\n'
        '      "expected_improvement": "string",\n'
        '      "risks_side_effects": ["..."],\n'
        '      "tests_after_change": ["..."]\n'
        "    }\n"
        "  ],\n"
        '  "investigation_priorities": [\n'
        "    {\n"
        '      "priority": 1,\n'
        '      "cause_unit_or_hypothesis": "string",\n'
        '      "why_need_investigation": "string",\n'
        '      "what_to_check_next": ["..."]\n'
        "    }\n"
        "  ],\n"
        "  \"global_notes\": \"string\"\n"
        "}\n\n"
        "--- 入力 ---\n"
        f"{json.dumps(user, ensure_ascii=False, indent=2)}"
    )

    result = run_llm_json(
        client=client,
        model=model,
        system=system,
        user=case_verify_prompt,
        num_predict=args.num_predict,
    )

    (out_dir / "self_verify.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # human-friendly markdown
    md_lines = [
        "# SELF_VERIFY (Qwen3:8b)",
        "",
        f"- input_run_id: {args.input_run_id}",
        f"- output_run_id: {new_run_id}",
        f"- model: {model}",
        "",
        "## auto_fix_permission",
        "",
        "```json",
        json.dumps(result.get("auto_fix_permission") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## reassessed_causes",
    ]
    for item in result.get("reassessed_causes") or []:
        md_lines.extend(
            [
                f"### {item.get('original_cause')}",
                f"- status: {item.get('status')} (confidence={item.get('revised_confidence')})",
                f"- why: {item.get('why')}",
                "",
                "**unknowns**",
                "- " + "\n- ".join(item.get("unknowns") or []) if item.get("unknowns") else "- (none)",
                "",
            ]
        )
    md_lines.extend(
        [
            "## fix_priorities_not_executed",
            "",
            "```json",
            json.dumps(result.get("fix_priorities_not_executed") or [], ensure_ascii=False, indent=2),
            "```",
            "",
            "## investigation_priorities",
            "",
            "```json",
            json.dumps(result.get("investigation_priorities") or [], ensure_ascii=False, indent=2),
            "```",
        ]
    )
    (out_dir / "SELF_VERIFY.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"done -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

