"""
Build v0 Stage 3 Human Review Dataset (analysis only, no agent/heuristic code changes).

- human_web_need is a HUMAN REVIEW scaffold label, NOT an automatic gold score for the agent
- classification is candidate tags for later Stage 3, NOT finalized misjudgment verdicts
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results" / "run_v0_50"
CASES_PATH = ROOT / "cases.json"
OUT_DIR = ROOT / "analysis" / "stage3_human_review"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Human review labels (CURATOR scaffold). Not agent ground-truth for scoring.
# human_web_need:
#   needs_web | no_web | ambiguous | reviewer_uncertain
# content_topic: semantic bucket for aggregation
# ---------------------------------------------------------------------------

HUMAN = {
    "A01": ("needs_web", "news", "今日のニュースは時間依存の外部情報"),
    "A02": ("needs_web", "current_info", "為替の現在水準は現在情報"),
    "A03": ("needs_web", "time_dependent", "最近の発表は時間依存"),
    "A04": ("needs_web", "current_info", "今の株価雰囲気は現在情報"),
    "A05": ("needs_web", "weather", "明日の天気は予報・外部"),
    "A06": ("needs_web", "current_info", "特定版の変更点は通常外部確認向き"),
    "B01": ("no_web", "local_observation", "CPU使用率はローカル観測"),
    "B02": ("no_web", "local_observation", "GPU状態はローカル観測"),
    "B03": ("no_web", "file_ops", "registry読取はファイル操作"),
    "B04": ("no_web", "file_ops", "ローカル文書要約"),
    "B05": ("no_web", "general_knowledge", "言語一般知識で足りうる"),
    "B06": ("no_web", "file_ops", "ディレクトリ一覧はファイル操作"),
    "C01": ("ambiguous", "time_dependent", "最近どうなってるはWebもローカルも取りうる"),
    "C02": ("ambiguous", "product_external", "詳しくは知識でもWebでも可"),
    "C03": ("ambiguous", "current_info", "今の扱いは文脈依存"),
    "C04": ("ambiguous", "time_dependent", "事情が広い"),
    "C05": ("ambiguous", "time_dependent", "実用性評価は主観・文脈依存"),
    "D01": ("no_web", "file_ops", "ローカル実装説明が主目的（Web語あり）"),
    "D02": ("no_web", "file_ops", "registry一覧はローカル（最新という語あり）"),
    "D03": ("no_web", "file_ops", "tools.json確認はローカル（現在という語あり）"),
    "D04": ("no_web", "file_ops", "リポジトリ内検索が主目的（ニュース語あり）"),
    "D05": ("no_web", "file_ops", "コード上の形式説明が主目的（検索結果語あり）"),
    "E01": ("needs_web", "time_dependent", "時事論点の整理は外部情報向き（明示Web語なし）"),
    "E02": ("needs_web", "product_external", "プラン差は変わりうる製品情報"),
    "E03": ("needs_web", "current_info", "自治体ルールは外部確認向き"),
    "E04": ("ambiguous", "general_knowledge", "一般手続きは知識でもWebでも可"),
    "E05": ("needs_web", "time_dependent", "次の発表時期は時間依存"),
    "F01": ("needs_web", "niche_or_fictional", "存在確認自体に検索が要るが成功は別問題"),
    "F02": ("needs_web", "niche_or_fictional", "架空企業の売上は検索しても困難"),
    "F03": ("needs_web", "niche_or_fictional", "極端ニッチ"),
    "F04": ("needs_web", "current_info", "多言語比較は検索・照合が重い"),
    "F05": ("needs_web", "niche_or_fictional", "古い入手困難情報"),
    "G01": ("no_web", "local_observation", "GPUプロセス一覧はローカル"),
    "G02": ("no_web", "file_ops", "yaml確認はファイル"),
    "G03": ("no_web", "file_ops", "ファイル探索"),
    "G04": ("no_web", "local_observation", "CPU状態はローカル"),
    "G05": ("no_web", "file_ops", "registry列挙はファイル"),
    "G06": ("reviewer_uncertain", "tool_gap", "新機能要求。Webが必要かは別問題"),
    "G07": ("reviewer_uncertain", "tool_gap", "同上"),
    "G08": ("reviewer_uncertain", "tool_gap", "同上"),
    "G09": ("reviewer_uncertain", "tool_gap", "同上"),
    "G10": ("reviewer_uncertain", "tool_gap", "同上"),
    "H01": ("ambiguous", "composite", "File必須＋外部補完は任意寄り"),
    "H02": ("ambiguous", "composite", "GPUローカル＋消費電力の一般情報"),
    "H03": ("ambiguous", "composite", "コード読取必須＋一般設計議論は任意"),
    "P01a": ("needs_web", "weather", "明日の大阪の天気"),
    "P01b": ("needs_web", "weather", "明日雨か（天気）"),
    "P01c": ("needs_web", "weather", "傘＝天気判断"),
    "P02a": ("ambiguous", "product_external", "製品説明は知識でもWebでも可"),
    "P02b": ("needs_web", "current_info", "今の立ち位置は現在性あり"),
}


def primary_outcome(outcomes: list) -> str | None:
    if not outcomes:
        return None
    for pref in ("hits", "error", "empty_hits", "blocked", "other"):
        if pref in outcomes:
            return pref
    return outcomes[-1]


def classify_candidates(
    *,
    human_web: str,
    judged: bool,
    called: bool,
    outcomes: list,
    route: str,
    route_reason: str,
    related: list,
    tools: list,
    case_id: str,
) -> tuple[list[str], str]:
    """
    Stage3 *candidates* only. Not final verdicts / not auto gold.
    Letters C/D/F/G/E map to draft families below for human scan.
    """
    tags: list[str] = []
    notes: list[str] = []

    # C: layer mismatch family
    if (not judged) and called:
        tags.append("C_layer_mismatch_underflag_candidate")
        notes.append("heuristic judged_no だが LLM が search_web 実行")
    if judged and not called:
        tags.append("C_layer_mismatch_overflag_candidate")
        notes.append("heuristic judged_yes だが search_web 未実行")

    # D: search-path family (independent of whether search was 'needed')
    po = primary_outcome(outcomes)
    if called and po == "error":
        tags.append("D_search_path_error_candidate")
        notes.append("検索実行後 outcome=error（判断正誤とは別）")
    if called and po == "hits":
        tags.append("D_search_path_hits_candidate")
        notes.append("検索で hits あり（利用可否は未判定）")
    if called and po == "empty_hits":
        tags.append("D_search_path_empty_candidate")
        notes.append("empty_hits")
    if called and po == "blocked":
        tags.append("D_search_path_blocked_candidate")
        notes.append("Gate blocked")

    # F: route / related family
    if route == "uncertain" and "no_related" in (route_reason or ""):
        tags.append("F_route_uncertain_saturated_candidate")
        notes.append("related空で uncertain に落ちた構造")
    if route == "agent_continue" and related:
        tags.append("F_related_continue_not_sufficiency_candidate")
        notes.append("relatedありで continue（達成保証ではない）")
    if route == "needs_new_tool":
        tags.append("F_new_tool_hint_collision_candidate")
        notes.append("needs_new_tool 発火（D02は registryに 衝突の疑い）")

    # G: tool-capability / behavior family
    if human_web == "no_web" and any(t in tools for t in ("cpu_status", "get_gpu_status", "get_gpu_processes", "list_files", "read_file", "search_files")):
        tags.append("G_existing_tool_path_candidate")
        notes.append("人間レビュー上no_webでローカルTool実行あり")
    if human_web in ("reviewer_uncertain",) and "search_web" in tools:
        tags.append("G_tool_gap_but_searched_candidate")
        notes.append("不足候補要求なのに検索が走った")
    if human_web == "no_web" and called:
        tags.append("G_no_web_human_but_llm_searched_candidate")
        notes.append("人間レビューno_webだがLLM検索（要レビュー）")

    # E: evidence / answer surface family
    if called and po == "error":
        tags.append("E_insufficient_search_evidence_candidate")
        notes.append("検索失敗のため根拠不足になりやすい")
    if called and po == "hits":
        tags.append("E_hits_use_unverified_candidate")
        notes.append("hitsあるが回答利用は未検証")

    if not tags:
        tags.append("X_review_needed")
        notes.append("上記ファミリに明確に入らず要目視")

    # Stable aligned cases (also useful)
    if judged and called:
        tags.append("aligned_heuristic_yes_llm_called")
    if (not judged) and (not called):
        tags.append("aligned_heuristic_no_llm_not_called")

    return tags, "; ".join(notes)


def load_row(case: dict) -> dict:
    cid = case["id"]
    entries = [
        json.loads(line)
        for line in (RUN / cid / "capability_route.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    s1 = next(e for e in entries if e["kind"] == "capability_route_observation")
    s2 = next(e for e in entries if e["kind"] == "capability_outcome_compare")
    webj = (s1.get("web_search") or {}).get("judgment") or {}
    webe = (s1.get("web_search") or {}).get("execution") or {}
    answer = ((s2.get("chain") or {}).get("final_answer") or {})
    human_web, topic, human_note = HUMAN[cid]
    judged = bool(webj.get("judged_appropriate"))
    called = bool(webe.get("called"))
    outcomes = list(webe.get("outcomes") or [])
    tools = [t.get("tool_name") for t in (s1.get("agent_tools_tried") or [])]
    related = [t.get("name") for t in (s1.get("related_tools") or [])]
    route = (s1.get("capability_route") or {}).get("route")
    route_reason = (s1.get("capability_route") or {}).get("reason")
    tags, why = classify_candidates(
        human_web=human_web,
        judged=judged,
        called=called,
        outcomes=outcomes,
        route=route or "",
        route_reason=route_reason or "",
        related=related,
        tools=tools,
        case_id=cid,
    )
    return {
        "case_id": cid,
        "design_category": case.get("category"),
        "group_id": case.get("group_id"),
        "request": case.get("request"),
        "observe_goal": case.get("observe_goal"),
        "content_topic": topic,
        "human_web_need": human_web,
        "human_web_need_note": human_note,
        "human_web_need_is_gold_score": False,
        "heuristic_judgment": judged,
        "heuristic_web_reason": webj.get("reason"),
        "heuristic_route": route,
        "heuristic_route_reason": route_reason,
        "related_tools": related,
        "llm_called_search_web": called,
        "llm_tools_tried": tools,
        "search_outcomes": outcomes,
        "search_primary_outcome": primary_outcome(outcomes),
        "answer_surface_status": answer.get("status"),
        "answer_surface_proxy": answer.get("outcome_proxy"),
        "web_pattern": (s2.get("compare_summary") or {}).get("web_pattern"),
        "classification_candidates": tags,
        "classification_reason": why,
        "misjudgment_final": None,
        "notes_for_reviewer": (
            "Do not treat human_web_need as automatic agent score. "
            "Separate judgment layer vs search-path failure."
        ),
    }


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    rows = [load_row(c) for c in cases]
    assert len(rows) == 50

    # Aggregations
    by_topic = defaultdict(list)
    for r in rows:
        by_topic[r["content_topic"]].append(r)

    topic_summary = {}
    for topic, items in sorted(by_topic.items()):
        topic_summary[topic] = {
            "n": len(items),
            "human_web_need": dict(Counter(i["human_web_need"] for i in items)),
            "heuristic_yes": sum(1 for i in items if i["heuristic_judgment"]),
            "llm_called": sum(1 for i in items if i["llm_called_search_web"]),
            "search_primary": dict(
                Counter(i["search_primary_outcome"] for i in items)
            ),
            "layer_underflag": sum(
                1
                for i in items
                if "C_layer_mismatch_underflag_candidate" in i["classification_candidates"]
            ),
            "layer_overflag": sum(
                1
                for i in items
                if "C_layer_mismatch_overflag_candidate" in i["classification_candidates"]
            ),
            "search_error": sum(
                1
                for i in items
                if "D_search_path_error_candidate" in i["classification_candidates"]
            ),
        }

    paraphrase = defaultdict(list)
    for r in rows:
        if r.get("group_id"):
            paraphrase[r["group_id"]].append(
                {
                    "case_id": r["case_id"],
                    "human_web_need": r["human_web_need"],
                    "heuristic_judgment": r["heuristic_judgment"],
                    "llm_called": r["llm_called_search_web"],
                    "search_primary_outcome": r["search_primary_outcome"],
                    "answer_surface_proxy": r["answer_surface_proxy"],
                    "heuristic_route": r["heuristic_route"],
                    "classification_candidates": r["classification_candidates"],
                }
            )

    # Extract C/D/F/G/E candidate lists
    families = {
        "C_layer_mismatch": [],
        "D_search_path": [],
        "F_route_related": [],
        "G_tool_capability": [],
        "E_evidence_answer": [],
    }
    for r in rows:
        for tag in r["classification_candidates"]:
            if tag.startswith("C_"):
                families["C_layer_mismatch"].append(
                    {"case_id": r["case_id"], "tag": tag, "reason": r["classification_reason"]}
                )
            elif tag.startswith("D_"):
                families["D_search_path"].append(
                    {"case_id": r["case_id"], "tag": tag, "reason": r["classification_reason"]}
                )
            elif tag.startswith("F_"):
                families["F_route_related"].append(
                    {"case_id": r["case_id"], "tag": tag, "reason": r["classification_reason"]}
                )
            elif tag.startswith("G_"):
                families["G_tool_capability"].append(
                    {"case_id": r["case_id"], "tag": tag, "reason": r["classification_reason"]}
                )
            elif tag.startswith("E_"):
                families["E_evidence_answer"].append(
                    {"case_id": r["case_id"], "tag": tag, "reason": r["classification_reason"]}
                )

    # Deduplicate family lists by case+tag
    for k, lst in families.items():
        seen = set()
        uniq = []
        for item in lst:
            key = (item["case_id"], item["tag"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(item)
        families[k] = uniq

    axis_draft = {
        "C_layer_mismatch": [
            "C_layer_mismatch_underflag_candidate",
            "C_layer_mismatch_overflag_candidate",
        ],
        "D_search_path": [
            "D_search_path_error_candidate",
            "D_search_path_hits_candidate",
            "D_search_path_empty_candidate",
            "D_search_path_blocked_candidate",
        ],
        "F_route_related": [
            "F_route_uncertain_saturated_candidate",
            "F_related_continue_not_sufficiency_candidate",
            "F_new_tool_hint_collision_candidate",
        ],
        "G_tool_capability": [
            "G_existing_tool_path_candidate",
            "G_tool_gap_but_searched_candidate",
            "G_no_web_human_but_llm_searched_candidate",
        ],
        "E_evidence_answer": [
            "E_insufficient_search_evidence_candidate",
            "E_hits_use_unverified_candidate",
        ],
        "notes": [
            "Candidates only; misjudgment_final stays null until human finalizes axes.",
            "human_web_need is curator scaffold, not automatic agent score.",
            "Separate judgment-layer issues from search-path failures (D_*).",
            "n=50 is too small to generalize.",
        ],
    }

    additional = [
        {
            "why": "heuristic語ギャップの再現（最近/明日/天気 vs 最新/現在/ニュース）",
            "n": "6-8",
            "category_focus": "time_dependent / weather / news contrast",
        },
        {
            "why": "search hits成功連鎖の観測が不足（D_search_path_hits が稀）",
            "n": "4-6",
            "category_focus": "stable English / evergreen topics",
        },
        {
            "why": "new_tool ヒント衝突の確認（F_new_tool / registryに 型）",
            "n": "2-3",
            "category_focus": "short substring collisions",
        },
        {
            "why": "human no_web なのに LLM検索（G_no_web_human_but_llm_searched）がほぼ無い／逆にD系overflagの再現",
            "n": "3-4",
            "category_focus": "web_word_but_unneeded paraphrases",
        },
    ]

    payload = {
        "dataset_name": "v0 Stage 3 Human Review Dataset",
        "version": "v0-stage3-review-1",
        "case_count": len(rows),
        "principles": [
            "No automatic gold correctness for PROJECT_AGENT",
            "human_web_need is separate human-review column",
            "heuristic_judgment / llm_called / search_outcome / answer_surface are separated",
            "classification_candidates are not final misjudgment labels",
            "Do not implement heuristic fixes in this step",
            "n=50 insufficient to generalize",
            "Separate judgment issues from web-search tool failures",
        ],
        "axis_draft": axis_draft,
        "topic_summary": topic_summary,
        "paraphrase_groups": dict(paraphrase),
        "family_extractions": {
            k: {"count": len(v), "items": v} for k, v in families.items()
        },
        "additional_collection_proposals": additional,
        "rows": rows,
    }

    (OUT_DIR / "human_review_dataset.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # CSV flat
    flat_fields = [
        "case_id",
        "design_category",
        "group_id",
        "content_topic",
        "request",
        "human_web_need",
        "human_web_need_note",
        "heuristic_judgment",
        "heuristic_route",
        "llm_called_search_web",
        "search_primary_outcome",
        "answer_surface_proxy",
        "web_pattern",
        "classification_candidates",
        "classification_reason",
        "misjudgment_final",
    ]
    with (OUT_DIR / "human_review_dataset.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flat_fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = dict(r)
            row["classification_candidates"] = "|".join(r["classification_candidates"])
            w.writerow(row)

    # Markdown table (compact)
    lines = [
        "# v0 Stage 3 Human Review Dataset",
        "",
        "**実装変更なし。** `human_web_need` は人間レビュー用スキャフォールドであり、Agent採点の自動正解ではない。",
        "`classification_candidates` は草案タグ。`misjudgment_final` はすべて null。",
        "",
        "## 列の意味",
        "",
        "| 列 | 意味 |",
        "|----|------|",
        "| human_web_need | 人間レビュー用のWeb必要性（needs_web/no_web/ambiguous/reviewer_uncertain） |",
        "| heuristic_judgment | capability_route 観測の judged_appropriate |",
        "| llm_called_search_web | Toolループで search_web が実行されたか |",
        "| search_primary_outcome | hits/error/…（検索経路。判断正誤ではない） |",
        "| answer_surface_proxy | Stage2表面プロキシ（真偽ではない） |",
        "| classification_candidates | Stage3草案タグ（C/D/F/G/Eファミリ） |",
        "",
        "## 50件一覧",
        "",
        "| case | human_web_need | heuristic | llm_called | search | answer | classification (primary) | reason (short) |",
        "|------|----------------|-----------|------------|--------|--------|--------------------------|----------------|",
    ]
    for r in rows:
        primary = next(
            (
                t
                for t in r["classification_candidates"]
                if t.startswith(("C_", "D_", "F_", "G_", "E_"))
            ),
            r["classification_candidates"][0],
        )
        lines.append(
            "| {case} | {hw} | {hj} | {lc} | {so} | {ans} | `{cls}` | {why} |".format(
                case=r["case_id"],
                hw=r["human_web_need"],
                hj=r["heuristic_judgment"],
                lc=r["llm_called_search_web"],
                so=r["search_primary_outcome"],
                ans=r["answer_surface_proxy"],
                cls=primary,
                why=(r["classification_reason"] or "")[:60],
            )
        )

    lines.extend(
        [
            "",
            "## コンテンツトピック別集計",
            "",
            "```json",
            json.dumps(topic_summary, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 言い換えgroup",
            "",
            "```json",
            json.dumps(dict(paraphrase), ensure_ascii=False, indent=2),
            "```",
            "",
            "## C/D/F/G/E 候補件数",
            "",
        ]
    )
    for k, v in families.items():
        lines.append(f"- **{k}**: {len(v)} tags assigned across cases")

    lines.extend(
        [
            "",
            "## 追加収集提案（不足カテゴリのみ）",
            "",
        ]
    )
    for a in additional:
        lines.append(f"- ({a['n']}) {a['why']} — focus: {a['category_focus']}")

    lines.extend(
        [
            "",
            "## 限界",
            "",
            "- n=50 では一般化できない。",
            "- 判断層のずれと Web検索機能失敗（D_*）を混同しない。",
            "- heuristic 修正案は本成果物では実装しない。",
            "",
        ]
    )
    (OUT_DIR / "HUMAN_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Axis draft standalone
    (OUT_DIR / "stage3_axis_draft.json").write_text(
        json.dumps(axis_draft, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {OUT_DIR}")
    print("family counts", {k: len(v) for k, v in families.items()})
    print("topic keys", list(topic_summary))


if __name__ == "__main__":
    main()
