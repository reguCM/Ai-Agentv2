"""Run the provisional diagnostic Selector on a registered problem.

Does not modify production Tools. Does not overwrite existing experiment runs.
Does not call Ollama / large LLMs.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from selector import DiagnosticSelector, evaluate_against_gold, load_json

THIS_DIR = Path(__file__).resolve().parent
RUNS_DIR = THIS_DIR.parent / "runs"


def write_markdown(result: dict, eval_result: dict, gold: dict, out: Path) -> None:
    lines = [
        "# SELECTOR_EVAL — search_web 既存診断に対する暫定Selector",
        "",
        "- 種類: ルールベース＋知識ベース（機械学習なし）",
        "- 本番 Tool / Agent / ranking: **未変更**",
        "- 既存実験: **再実行・上書きなし**。成果物パスを再利用",
        f"- problem_id: `{result['problem_id']}`",
        f"- auto_fix: **{result['auto_fix']}**",
        "",
        "## 問題特徴",
        "",
        "```json",
        json.dumps(result["features"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 選択パイプライン",
        "",
    ]
    for i, mid in enumerate(result["selected_pipeline"], 1):
        item = next(x for x in result["selected"] if x["method_id"] == mid)
        lines.append(
            f"{i}. **{mid}**（role={item.get('role')}, confidence={item.get('confidence')}, status={item.get('status')}）"
        )
        lines.append(f"   - 理由: {item.get('reason')}")
        if item.get("rule_ids"):
            lines.append(f"   - rules: {', '.join(item['rule_ids'])}")
        if item.get("reusable_artifacts"):
            lines.append("   - 再利用成果物:")
            for p in item["reusable_artifacts"]:
                lines.append(f"     - `{p}`")
        lines.append("")

    lines.extend(["## 未選択", ""])
    for item in result["not_selected"]:
        lines.append(
            f"- **{item['method_id']}**: {item.get('not_selected_reason')}"
        )
    lines.extend(["", "## 警告", ""])
    for w in result["warnings"]:
        lines.append(f"- {w}")

    lines.extend(
        [
            "",
            "## 再利用",
            "",
            f"- can_reuse_past_experiments: {result['reuse']['can_reuse_past_experiments']}",
            f"- experiments: {', '.join(result['reuse']['experiments'])}",
            f"- {result['reuse']['note']}",
            "",
            "## 評価（知識ベース期待との照合）",
            "",
            f"- all_ok: **{eval_result['checks']['all_ok']}**",
            "",
        ]
    )
    for k, v in eval_result["checks"].items():
        if k == "all_ok":
            continue
        lines.append(f"- {k}: {v}")
    lines.append("")
    if eval_result["missing_must_select"]:
        lines.append(f"- 欠けている must_select: {eval_result['missing_must_select']}")
    else:
        lines.append("- 欠けている must_select: なし")
    if eval_result["forbidden_selected"]:
        lines.append(f"- 禁止手法が選択された: {eval_result['forbidden_selected']}")
    else:
        lines.append("- 禁止手法の選択: なし")
    lines.extend(
        [
            "",
            "### 期待（gold）",
            "",
            f"- must_select: {gold['must_select']}",
            f"- must_not_select: {gold['must_not_select']}",
            f"- may_select: {gold['may_select']}",
            "",
            "## この評価が意味しないこと",
            "",
            "- Selector が search_web の真因を当てたわけではない。",
            "- 小型→大型パイプラインが検証済みになったわけではない。",
            "- 診断方法の自律選択（LLM 自身が選ぶ）が検証されたわけではない。",
            "- 本番検索の修正許可ではない。",
            "",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--problem",
        default=str(THIS_DIR / "problems" / "search_web_quality.json"),
    )
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    problem = load_json(Path(args.problem))
    gold = load_json(THIS_DIR / "expected_eval.json")
    sel = DiagnosticSelector.from_default_paths()
    result = sel.select(problem)
    eval_result = evaluate_against_gold(result, gold)

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        out_dir = RUNS_DIR / stamp / "selector_eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "selector_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "selector_eval.json").write_text(
        json.dumps(eval_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(result, eval_result, gold, out_dir / "SELECTOR_EVAL.md")
    (out_dir / "README.md").write_text(
        "暫定Selector評価。既存実験は再利用のみ。本番Tool未変更。\n",
        encoding="utf-8",
    )
    print(str(out_dir))
    print("all_ok=", eval_result["checks"]["all_ok"])
    print("pipeline=", result["selected_pipeline"])


if __name__ == "__main__":
    main()
