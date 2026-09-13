"""
pre_web 人間レビュー用シート生成（分析のみ）。

人間が記入するのは次の4項目だけ:
  1. Web必要性 (web_need)
  2. Web効果 (web_effect)
  3. 事実性への効果 (factual_effect)
  4. 理由 (reason)

quadrant は人間入力しない。web_need × web_effect から後で自動生成する。

既存ログ・agent実装・heuristic は変更しない。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results" / "run_v0_50_preweb"
STAGE3_HINT = ROOT / "analysis" / "stage3_human_review" / "human_review_dataset.json"
OUT_DIR = ROOT / "analysis" / "pre_web_human_review"
CARDS_DIR = OUT_DIR / "cards"

# ---------------------------------------------------------------------------
# 人間記入の選択肢（意味は README / CHOICES.md に明記）
# ---------------------------------------------------------------------------

WEB_NEED = {
    "必須": "この要求に正しく答えるには Web 検索が事実上必要（ローカルToolや一般知識だけでは足りない）",
    "有用": "Webなしでも一応答えられるが、検索があると明らかに良くなりやすい",
    "任意": "Webありでもなしでも大きな差が出にくく、どちらでもよい",
    "不要": "ローカルTool・リポジトリ・一般知識で十分。検索は本来いらない",
    "判断困難": "比較材料不足・要求が曖昧などで、必要性が決められない",
}

WEB_EFFECT = {
    "大幅改善": "最終回答が Webなし候補より明らかに良い（正確さ・具体性・有用性が大きく上がった）",
    "改善": "最終回答の方が良いが、差は中程度",
    "ほぼ変化なし": "Webの有無で回答品質に実質差がない（同程度の良さ／同程度の不足）",
    "悪化": "最終回答の方が悪い（混乱・幻覚・拒否・冗長など）",
    "判断困難": "片方の本文欠落・検索未実行などで効果を比較できない",
}

FACTUAL_EFFECT = {
    "事実性が改善": "時事・数値・固有名など、事実面が Web 後に良くなった",
    "事実性はほぼ変化なし": "事実の正しさはほぼ同じ（良くも悪くもない）",
    "事実性が悪化・幻覚増": "誤情報・古い情報の断定・根拠なき具体化が増えた",
    "判断困難": "事実性を判定する材料が足りない",
    "Web未実行のため非該当": "search_web が一度も走っていない（比較対象外）",
}

# 4象限の自動生成（人間は書かない）
# 行: Web必須・有益寄り / Web任意・不要寄り
# 列: 改善した / 改善しない・悪化
NEED_BENEFICIAL = frozenset({"必須", "有用"})
NEED_OPTIONAL_UNNEEDED = frozenset({"任意", "不要"})
EFFECT_IMPROVED = frozenset({"大幅改善", "改善"})
EFFECT_NOT_IMPROVED = frozenset({"ほぼ変化なし", "悪化"})

UNNEEDED_LEAN_CATEGORIES = frozenset(
    {
        "web_unneeded_clear",
        "web_word_but_unneeded",
        "existing_tool_ok",
    }
)


def derive_quadrant(web_need: str, web_effect: str) -> dict[str, str | None]:
    """
    人間記入の web_need × web_effect から象限を自動生成する。
    Agent正解ではない。未記入・判断困難は null。
    """
    need = str(web_need or "").strip()
    effect = str(web_effect or "").strip()
    if not need or not effect:
        return {
            "quadrant_code": None,
            "quadrant_label": None,
            "quadrant_note": "web_need と web_effect の両方が埋まってから生成",
        }
    if need == "判断困難" or effect == "判断困難":
        return {
            "quadrant_code": None,
            "quadrant_label": None,
            "quadrant_note": "判断困難を含むため象限外",
        }

    if need in NEED_BENEFICIAL and effect in EFFECT_IMPROVED:
        return {
            "quadrant_code": "ideal",
            "quadrant_label": "◎ 理想的な検索",
            "quadrant_note": "Web必須・有益 × Webで改善",
        }
    if need in NEED_BENEFICIAL and effect in EFFECT_NOT_IMPROVED:
        return {
            "quadrant_code": "search_quality",
            "quadrant_label": "△ 検索品質の問題",
            "quadrant_note": "Web必須・有益 × 改善しない/悪化",
        }
    if need in NEED_OPTIONAL_UNNEEDED and effect in EFFECT_IMPROVED:
        return {
            "quadrant_code": "added_value",
            "quadrant_label": "○ 検索の追加価値",
            "quadrant_note": "Web任意・不要寄り × Webで改善",
        }
    if need in NEED_OPTIONAL_UNNEEDED and effect in EFFECT_NOT_IMPROVED:
        label = "○/△ 無駄な検索" if effect == "ほぼ変化なし" else "△ 害のある余分な検索"
        return {
            "quadrant_code": "wasted_or_harm",
            "quadrant_label": label,
            "quadrant_note": "Web任意・不要寄り × 改善しない/悪化",
        }
    return {
        "quadrant_code": None,
        "quadrant_label": None,
        "quadrant_note": f"未対応の組み合わせ: need={need!r} effect={effect!r}",
    }


def _clip(text: object, n: int = 400) -> str:
    s = str(text or "").replace("\r\n", "\n").strip()
    s = re.sub(r"\s+", " ", s)
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def extract_final_answer_from_stdout(text: str) -> str:
    markers: list[int] = []
    idx = 0
    while True:
        i = text.find("最終回答:", idx)
        if i < 0:
            break
        markers.append(i)
        idx = i + 1
    if not markers:
        return ""
    start = markers[-1] + len("最終回答:")
    rest = text[start:]
    for end_marker in (
        "\n[EXECUTION_IDENTITY] event=capability_outcome",
        "\n[CAPABILITY_OUTCOME_COMPARE]",
        "\n--- STDERR ---",
    ):
        j = rest.find(end_marker)
        if j >= 0:
            rest = rest[:j]
    return rest.strip()


def load_hint_web_need() -> dict[str, str]:
    if not STAGE3_HINT.is_file():
        return {}
    data = json.loads(STAGE3_HINT.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for row in data.get("rows") or data.get("cases") or []:
        cid = row.get("case_id")
        need = row.get("human_web_need")
        if cid and need:
            out[str(cid)] = str(need)
    return out


def format_search_results_text(web_results: dict, web_exec: dict) -> str:
    called = bool(web_exec.get("called") or web_results.get("called"))
    if not called:
        return "（Web検索は実行されませんでした）"
    lines: list[str] = []
    outcomes = web_exec.get("outcomes") or web_results.get("outcomes") or []
    lines.append(
        f"実行あり / call_count={web_exec.get('call_count') or web_results.get('call_count')} / "
        f"outcomes={outcomes}"
    )
    calls = web_results.get("calls") or []
    if not calls:
        lines.append("（詳細ダイジェストなし）")
        return "\n".join(lines)
    for i, call in enumerate(calls, 1):
        lines.append(
            f"[{i}] query={call.get('query')!r} outcome={call.get('outcome')} "
            f"hits={call.get('hit_count')} error={call.get('error')}"
        )
        for h in call.get("hit_digest") or []:
            lines.append(
                f"    - {h.get('title') or '(no title)'} | {h.get('url') or ''}"
            )
            if h.get("snippet"):
                lines.append(f"      {_clip(h.get('snippet'), 160)}")
    return "\n".join(lines)


def load_case_bundle(case_dir: Path) -> dict:
    log = case_dir / "capability_route.jsonl"
    entries = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pre = next((e for e in entries if e.get("kind") == "pre_web_answer_candidate"), {})
    s1 = next((e for e in entries if e.get("kind") == "capability_route_observation"), {})
    s2 = next((e for e in entries if e.get("kind") == "capability_outcome_compare"), {})
    stdout_text = ""
    stdout_path = case_dir / "stdout.txt"
    if stdout_path.is_file():
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")

    pre_block = pre.get("pre_web_answer_candidate") or {}
    chain = s2.get("chain") or {}
    web_exec = chain.get("web_execution") or (s1.get("web_search") or {}).get("execution") or {}
    web_results = chain.get("web_search_results") or {}
    final_surface = chain.get("final_answer") or {}
    final_text = extract_final_answer_from_stdout(stdout_text)
    search_text = format_search_results_text(web_results, web_exec)

    return {
        "case_id": case_dir.name,
        "observation_id": s1.get("observation_id")
        or pre.get("observation_id")
        or s2.get("observation_id"),
        "request": s1.get("request") or pre.get("request") or "",
        "category": (s1.get("extra") or {}).get("collection_category"),
        "group_id": (s1.get("extra") or {}).get("collection_group_id"),
        "route": (s1.get("capability_route") or {}).get("route"),
        "judged_web": ((s1.get("web_search") or {}).get("judgment") or {}).get(
            "judged_appropriate"
        ),
        "web_called": bool(web_exec.get("called")),
        "web_call_count": web_exec.get("call_count"),
        "web_outcomes": list(web_exec.get("outcomes") or []),
        "web_primary_outcome": web_exec.get("primary_outcome"),
        "tools_tried": [
            t.get("tool_name") for t in (s1.get("agent_tools_tried") or [])
        ],
        "pre_web_content": pre_block.get("content") or "",
        "pre_web_surface": (pre_block.get("surface") or {}).get("status"),
        "final_answer_content": final_text,
        "final_answer_surface": final_surface.get("status"),
        "search_results_text": search_text,
        "web_search_results": web_results,
        "web_pattern": (s2.get("compare_summary") or {}).get("web_pattern"),
    }


def priority_flags(row: dict, hint_need: str | None) -> list[str]:
    flags: list[str] = []
    called = bool(row.get("web_called"))
    cat = row.get("category") or ""
    if called and cat in UNNEEDED_LEAN_CATEGORIES:
        flags.append("不要寄りなのに検索した（重点）")
    if called and hint_need == "no_web":
        flags.append("以前ヒントno_webなのに検索")
    if called and (cat in UNNEEDED_LEAN_CATEGORIES or hint_need == "no_web"):
        flags.append("追加価値がないか要確認")
    if called and hint_need in ("ambiguous", "reviewer_uncertain"):
        flags.append("任意・曖昧だが検索あり")
    if called and row.get("web_primary_outcome") == "hits":
        flags.append("hitsあり・検索結果を精読")
    return flags


def build_rows() -> list[dict]:
    hints = load_hint_web_need()
    rows: list[dict] = []
    for case_dir in sorted(p for p in RUN.iterdir() if p.is_dir()):
        if not (case_dir / "capability_route.jsonl").is_file():
            continue
        bundle = load_case_bundle(case_dir)
        hint = hints.get(bundle["case_id"])
        flags = priority_flags(bundle, hint)
        rank = 1 if any("重点" in f or "追加価値" in f for f in flags) else (
            2 if flags else 3
        )
        rows.append(
            {
                **bundle,
                "curator_hint_web_need": hint,
                "review_priority_flags": flags,
                "review_priority_rank": rank,
                # 人間記入（空）
                "web_need": "",
                "web_effect": "",
                "factual_effect": "",
                "reason": "",
                # 自動生成枠（人間は書かない）
                "quadrant_code": None,
                "quadrant_label": None,
                "quadrant_note": "未記入のため未生成",
                "not_agent_gold": True,
            }
        )
    rows.sort(key=lambda r: (r["review_priority_rank"], r["case_id"]))
    return rows


def write_worksheet_csv(rows: list[dict], path: Path) -> Path:
    """
    人間が書く列は末尾4列だけ。他は参照用。
    """
    fields = [
        "優先度",
        "case_id",
        "observation_id",
        "category",
        "ユーザー要求",
        "Web実行したか",
        "検索outcome",
        "使ったTool",
        "Webなし回答（要約）",
        "検索結果（要約）",
        "最終回答（要約）",
        "参考ヒント_以前のweb要否",
        "注目フラグ",
        # ---- ここから人間記入（4項目のみ）----
        "Web必要性",
        "Web効果",
        "事実性への効果",
        "理由",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "優先度": row["review_priority_rank"],
                    "case_id": row["case_id"],
                    "observation_id": row["observation_id"],
                    "category": row.get("category") or "",
                    "ユーザー要求": row.get("request") or "",
                    "Web実行したか": "はい" if row.get("web_called") else "いいえ",
                    "検索outcome": row.get("web_primary_outcome") or "",
                    "使ったTool": ", ".join(row.get("tools_tried") or []),
                    "Webなし回答（要約）": _clip(row.get("pre_web_content"), 350),
                    "検索結果（要約）": _clip(row.get("search_results_text"), 250),
                    "最終回答（要約）": _clip(row.get("final_answer_content"), 350),
                    "参考ヒント_以前のweb要否": row.get("curator_hint_web_need") or "",
                    "注目フラグ": " / ".join(row.get("review_priority_flags") or []),
                    "Web必要性": row.get("web_need") or "",
                    "Web効果": row.get("web_effect") or "",
                    "事実性への効果": row.get("factual_effect") or "",
                    "理由": row.get("reason") or "",
                }
            )
    return path


def _try_write_worksheet(rows: list[dict], path: Path) -> Path | None:
    try:
        return write_worksheet_csv(rows, path)
    except PermissionError as exc:
        print(f"skip locked file: {path} ({exc})")
        return None


def write_choices_md(path: Path) -> None:
    lines = [
        "# レビュー記入ガイド（4項目だけ）",
        "",
        "各ケースで書くのは次の4つです。`quadrant` は書かないでください（後から自動生成）。",
        "",
        "## 1. Web必要性（この要求に Web は要ったか）",
        "",
        "| 選択肢 | 意味 |",
        "|--------|------|",
    ]
    for k, v in WEB_NEED.items():
        lines.append(f"| **{k}** | {v} |")
    lines.extend(
        [
            "",
            "## 2. Web効果（Webなし回答 → 最終回答で品質はどう変わったか）",
            "",
            "| 選択肢 | 意味 |",
            "|--------|------|",
        ]
    )
    for k, v in WEB_EFFECT.items():
        lines.append(f"| **{k}** | {v} |")
    lines.extend(
        [
            "",
            "## 3. 事実性への効果（正しさ・根拠の面）",
            "",
            "| 選択肢 | 意味 |",
            "|--------|------|",
        ]
    )
    for k, v in FACTUAL_EFFECT.items():
        lines.append(f"| **{k}** | {v} |")
    lines.extend(
        [
            "",
            "## 4. 理由",
            "",
            "上の3つを選んだ根拠を短く書く。例:",
            "",
            "- 「天気は予報必須。検索は error で最終も曖昧 → 必要性=必須、効果=悪化」",
            "- 「ローカルCPUで足りるが、検索後の説明が分かりやすくなった → 必要性=不要、効果=改善」",
            "",
            "## 書かないもの",
            "",
            "- **quadrant（4象限）**: `Web必要性` と `Web効果` から後で自動生成",
            "- Agent / heuristic の正誤ラベル",
            "",
            "## 4象限（自動生成の対応表）",
            "",
            "| | Web効果 = 大幅改善/改善 | Web効果 = ほぼ変化なし/悪化 |",
            "|---|---------------------------|------------------------------|",
            "| Web必要性 = 必須/有用 | ◎ 理想的な検索 | △ 検索品質の問題 |",
            "| Web必要性 = 任意/不要 | ○ 検索の追加価値 | ○/△ 無駄（または害）な検索 |",
            "",
            "「不要なのに検索した＝悪い」とは限らない。○（追加価値）を積極的に探す。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _fence(label: str, body: str) -> str:
    text = (body or "").strip() or "(empty)"
    # 本文に ``` が含まれる場合は外側を ~~~~ にする
    fence = "~~~~" if "```" in text else "```"
    return f"{fence}{label}\n{text}\n{fence}"


def render_card(row: dict) -> str:
    flags = row.get("review_priority_flags") or []
    flag_line = f"- 注目: {' / '.join(flags)}" if flags else "- 注目: （通常）"
    return "\n".join(
        [
            f"# {row['case_id']}",
            "",
            f"- observation_id: `{row.get('observation_id')}`",
            f"- category: `{row.get('category')}`",
            f"- Web実行: **{'はい' if row.get('web_called') else 'いいえ'}** "
            f"(outcome=`{row.get('web_primary_outcome')}`)",
            f"- tools: `{row.get('tools_tried')}`",
            flag_line,
            "",
            "---",
            "",
            "## 1. ユーザー要求",
            "",
            _fence("text", row.get("request") or ""),
            "",
            "## 2. Webなし回答（pre_web_answer_candidate）",
            "",
            _fence("text", row.get("pre_web_content") or ""),
            "",
            "## 3. 検索結果（web_search_results · 最終回答ではない）",
            "",
            _fence("text", row.get("search_results_text") or ""),
            "",
            "## 4. 最終回答",
            "",
            _fence("text", row.get("final_answer_content") or ""),
            "",
            "---",
            "",
            "## 記入欄（4項目のみ）",
            "",
            "| 項目 | 記入 |",
            "|------|------|",
            "| Web必要性 | 必須 / 有用 / 任意 / 不要 / 判断困難 |",
            "| Web効果 | 大幅改善 / 改善 / ほぼ変化なし / 悪化 / 判断困難 |",
            "| 事実性への効果 | 事実性が改善 / 事実性はほぼ変化なし / 事実性が悪化・幻覚増 / 判断困難 / Web未実行のため非該当 |",
            "| 理由 | （短文） |",
            "",
            "> quadrant は書かない（後から自動生成）",
            "",
        ]
    )


def write_compare_bundle(rows: list[dict]) -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    index_lines = [
        "# 比較カード一覧",
        "",
        "読む順は常に **ユーザー要求 → Webなし回答 → 検索結果 → 最終回答**。",
        "記入は `review_worksheet.csv` の右端4列、または各カード末尾。",
        "",
        "| 優先 | case | Web実行 | outcome | カード |",
        "|------|------|---------|---------|--------|",
    ]
    all_cards: list[str] = [
        "# pre_web 比較カード（全50件）",
        "",
        "読む順: **1 ユーザー要求 → 2 Webなし回答 → 3 検索結果 → 4 最終回答**",
        "",
        "選択肢の意味: [CHOICES.md](CHOICES.md)",
        "",
    ]
    for row in rows:
        card = render_card(row)
        (CARDS_DIR / f"{row['case_id']}.md").write_text(card, encoding="utf-8")
        all_cards.append(card)
        all_cards.append("\n---\n")
        index_lines.append(
            f"| {row['review_priority_rank']} | {row['case_id']} | "
            f"{'はい' if row.get('web_called') else 'いいえ'} | "
            f"{row.get('web_primary_outcome') or '-'} | "
            f"[cards/{row['case_id']}.md](cards/{row['case_id']}.md) |"
        )
    (OUT_DIR / "COMPARE.md").write_text("\n".join(all_cards), encoding="utf-8")
    (OUT_DIR / "CARDS_INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")


def write_readme(rows: list[dict], path: Path) -> None:
    priority = [r for r in rows if r["review_priority_rank"] <= 2]
    lines = [
        "# pre_web 人間レビュー",
        "",
        "**Agentの正解ではない。** 既存ログ・実装・heuristic・Stage4は変更しない。",
        "",
        "## あなたがやること（これだけ）",
        "",
        "1. [CHOICES.md](CHOICES.md) で選択肢の意味を確認する",
        "2. [COMPARE.md](COMPARE.md) または [cards/](cards/) を **要求→Webなし→検索結果→最終回答** の順で読む",
        "3. [記入シート.csv](記入シート.csv)（または review_worksheet.csv）の右端4列だけ埋める",
        "",
        "| 列名 | 内容 |",
        "|------|------|",
        "| **Web必要性** | この要求に Web は要ったか |",
        "| **Web効果** | Webなし回答と比べて最終回答はどう変わったか |",
        "| **事実性への効果** | 事実の正しさはどう変わったか |",
        "| **理由** | 上記を選んだ短い根拠 |",
        "",
        "**quadrant（4象限）は人間が書かない。** 記入後に次で自動生成する:",
        "",
        "```text",
        "python analysis/build_pre_web_human_review.py --apply-quadrants --worksheet 記入シート.csv",
        "```",
        "",
        "## 4象限（自動生成）",
        "",
        "| | Webで改善 | 改善しない/悪化 |",
        "|---|-----------|----------------|",
        "| Web必須・有益（必須/有用） | ◎ 理想的な検索 | △ 検索品質の問題 |",
        "| Web任意・不要寄り（任意/不要） | ○ 検索の追加価値 | ○/△ 無駄な検索 |",
        "",
        "「不要なのに検索した＝悪い」と決めない。○ を積極的に探す。",
        "",
        f"- 総数: {len(rows)} / Web実行あり: {sum(1 for r in rows if r.get('web_called'))}",
        f"- 優先確認（rank≤2）: {len(priority)}",
        "",
        "## 優先ケース",
        "",
        "| case | category | Web実行 | outcome | フラグ |",
        "|------|----------|---------|---------|--------|",
    ]
    for r in priority:
        lines.append(
            f"| {r['case_id']} | {r.get('category')} | "
            f"{'はい' if r.get('web_called') else 'いいえ'} | "
            f"{r.get('web_primary_outcome')} | "
            f"{' / '.join(r.get('review_priority_flags') or [])} |"
        )
    lines.extend(
        [
            "",
            "## ファイル",
            "",
            "| ファイル | 用途 |",
            "|----------|------|",
            "| `CHOICES.md` | 選択肢の意味 |",
            "| `記入シート.csv` | 記入用（右端4列）※推奨 |",
            "| `review_worksheet.csv` | 同上（ロック時は記入シート.csvを使用） |",
            "| `COMPARE.md` | 全件比較カード |",
            "| `cards/A01.md` など | 1ケース1ファイル |",
            "| `review_dataset.json` | 機械可読 |",
            "| `review_with_quadrants.csv` | 記入後の象限付き（`--apply-quadrants`） |",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def apply_quadrants_from_worksheet(worksheet: Path) -> int:
    """記入済み worksheet を読み、象限列を付けて出力する。"""
    if not worksheet.is_file():
        print(f"missing: {worksheet}")
        return 2
    with worksheet.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out_fields = list(rows[0].keys()) if rows else []
    for col in ("quadrant_code", "quadrant_label", "quadrant_note"):
        if col not in out_fields:
            out_fields.append(col)
    filled = 0
    for row in rows:
        q = derive_quadrant(row.get("Web必要性", ""), row.get("Web効果", ""))
        row["quadrant_code"] = q["quadrant_code"] or ""
        row["quadrant_label"] = q["quadrant_label"] or ""
        row["quadrant_note"] = q["quadrant_note"] or ""
        if q["quadrant_code"]:
            filled += 1
    out_path = OUT_DIR / "review_with_quadrants.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path} (quadrants filled: {filled}/{len(rows)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply-quadrants",
        action="store_true",
        help="記入済み review_worksheet.csv から象限を自動生成する",
    )
    parser.add_argument(
        "--worksheet",
        type=Path,
        default=OUT_DIR / "記入シート.csv",
    )
    args = parser.parse_args(argv)

    if args.apply_quadrants:
        return apply_quadrants_from_worksheet(args.worksheet)

    if not RUN.is_dir():
        raise SystemExit(f"run dir missing: {RUN}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    ws_path = _try_write_worksheet(rows, OUT_DIR / "記入シート.csv")
    _try_write_worksheet(rows, OUT_DIR / "review_worksheet.csv")
    _try_write_worksheet(rows, RUN / "pre_web_compare_review.csv")
    if ws_path is None:
        raise SystemExit("could not write 記入シート.csv")
    write_choices_md(OUT_DIR / "CHOICES.md")
    write_readme(rows, OUT_DIR / "README.md")
    write_compare_bundle(rows)
    payload = {
        "run_dir": str(RUN),
        "not_agent_gold": True,
        "human_fields_only": ["Web必要性", "Web効果", "事実性への効果", "理由"],
        "quadrant_is_auto_derived": True,
        "worksheet_path": str(ws_path),
        "web_need_meanings": WEB_NEED,
        "web_effect_meanings": WEB_EFFECT,
        "factual_effect_meanings": FACTUAL_EFFECT,
        "case_count": len(rows),
        "cases": rows,
    }
    (OUT_DIR / "review_dataset.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_DIR}")
    print(f"worksheet: {ws_path}")
    print("human fields: Web必要性 / Web効果 / 事実性への効果 / 理由")
    print("quadrant: auto via --apply-quadrants (do not fill by hand)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
