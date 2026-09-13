"""
KSS-1.5.1: 人手監査用 ground truth テンプレート生成。

KSS-1.5 live (`kss15_20260820_160911`) を上書きしない。
heuristic を ground truth として扱わない。routing しない。
"""
from __future__ import annotations

import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT

ROOT = REPO_ROOT
HERE = Path(__file__).resolve().parent

import argparse
import json
import uuid
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path

SRC_DEFAULT = (
    ROOT
    / "research"
    / "llm_benchmarks"
    / "knowledge_source_obs"
    / "kss15_20260820_160911"
)
OUT_DIR = ROOT / "research" / "llm_benchmarks" / "knowledge_source_obs"

HUMAN_LABELS = (
    "DIRECT",
    "CORE",
    "RELATED",
    "IRRELEVANT",
    "MISLEADING",
    "UNKNOWN",
)
ANSWER_PRESENCE = (
    "direct",
    "core",
    "related",
    "none",
    "misleading",
    "unknown",
)
SOURCE_QUALITY = (
    "official",
    "authoritative",
    "reputable_secondary",
    "ordinary",
    "unknown",
    "unreliable",
)
LOSS_STAGES = (
    "SEARCH_MISS",
    "DROP_ERROR",
    "CANDIDATE_MISS",
    "VERIFY_ERROR",
    "USABLE_CONVERSION_ERROR",
    "JUDGE_ERROR",
    "PROGRESS_ERROR",
    "PROPOSAL_ERROR",
    "UNKNOWN",
)

MISSING = "missing"


def _new_id(prefix="gt"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def load_frozen_kss15(src: Path):
    summary = json.loads((src / "summary.json").read_text(encoding="utf-8"))
    # freeze key metrics only (do not rewrite source)
    m = summary.get("metrics") or {}
    rs = summary.get("run_stats") or {}
    return {
        "source_experiment_id": summary.get("experiment_id"),
        "source_dir": str(src),
        "frozen_observation": {
            "cases_total": rs.get("cases_total", summary.get("cases_total")),
            "cases_completed": rs.get("cases_completed"),
            "cases_failed": rs.get("cases_failed"),
            "cases_valid_for_measurement": rs.get("cases_valid_for_measurement"),
            "searches_observed": rs.get("searches_observed"),
            "hits_observed": rs.get("hits_observed"),
            "kept_hits": rs.get("kept_hits", m.get("kept_hits")),
            "dropped_hits": rs.get("dropped_hits", m.get("dropped_hits")),
            "successful_runs": m.get("successful_runs"),
            "failed_runs": m.get("failed_runs"),
            "dropped_with_core": m.get("dropped_with_core"),
            "dropped_with_direct": m.get("dropped_with_direct"),
            "dropped_with_lead": m.get("dropped_with_lead"),
            "failed_runs_with_answer_in_dropped": m.get(
                "failed_runs_with_answer_in_dropped"
            ),
            "failed_runs_with_answer_in_kept": m.get(
                "failed_runs_with_answer_in_kept"
            ),
            "failed_runs_with_no_answer_found": m.get(
                "failed_runs_with_no_answer_found"
            ),
            "heuristic_dropped_answer_rate_observed": m.get("dropped_answer_rate"),
            "note": (
                "heuristic_dropped_answer_rate is NOT ground truth; "
                "do not treat 0.778 as confirmed precision"
            ),
        },
        "environment": summary.get("environment"),
        "per_case": summary.get("per_case"),
    }


def extract_hits(src: Path):
    dropped = []
    kept_core_fail_unique = []
    case_meta = {}

    for path in sorted(src.glob("kss15__*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        case = rec.get("case")
        case_meta[case] = {
            "case": case,
            "pass": rec.get("pass"),
            "fail_stage": rec.get("fail_stage"),
            "stop_reason": rec.get("stop_reason"),
            "request": rec.get("request"),
            "valid_for_kss15_measurement": (rec.get("metrics") or {}).get(
                "valid_for_kss15_measurement"
            ),
            "dropped_hits_state": (rec.get("metrics") or {}).get("dropped_hits_state"),
            "live_search_executed": (rec.get("metrics") or {}).get(
                "live_search_executed"
            ),
        }
        seen_kept = OrderedDict()
        for rnd in rec.get("rounds") or []:
            part = rnd.get("web_hit_partition") or {}
            for hit in part.get("records") or []:
                base = {
                    "case": case,
                    "round": rnd.get("round"),
                    "final_pass": rec.get("pass"),
                    "fail_stage": rec.get("fail_stage"),
                    "stop_reason": rec.get("stop_reason"),
                    "original_question": rec.get("request"),
                    "query": hit.get("query"),
                    "url": hit.get("url"),
                    "title": hit.get("title"),
                    "snippet": hit.get("snippet"),
                    "domain": hit.get("domain"),
                    "source": hit.get("source"),
                    "kept": hit.get("kept"),
                    "drop_reason": hit.get("drop_reason"),
                    "position_rank": hit.get("position_rank"),
                    "existing_hit_score": hit.get("existing_hit_score"),
                    "candidate_link": hit.get("candidate_link"),
                    "search_id": hit.get("search_id"),
                    "hit_id": hit.get("hit_id"),
                    "heuristic_answer_presence": hit.get("heuristic_answer_presence"),
                    "heuristic_reasons": hit.get("heuristic_reasons")
                    or hit.get("answer_presence_reasons"),
                    "source_file": path.name,
                }
                if hit.get("kept") is False:
                    dropped.append(base)
                elif (
                    rec.get("pass") is False
                    and hit.get("kept") is True
                    and hit.get("heuristic_answer_presence") in ("core", "direct")
                ):
                    url = hit.get("url") or ""
                    if url and url not in seen_kept:
                        seen_kept[url] = {**base, "dedupe": "first_round_unique_url"}
        kept_core_fail_unique.extend(seen_kept.values())

    return dropped, kept_core_fail_unique, case_meta


def make_audit_entry(hit, *, bucket):
    return {
        "audit_id": _new_id("k151"),
        "bucket": bucket,
        "human_audit_status": "pending",
        "case": hit.get("case"),
        "round": hit.get("round"),
        "original_question": hit.get("original_question"),
        "query": hit.get("query"),
        "url": hit.get("url"),
        "title": hit.get("title"),
        "snippet": hit.get("snippet"),
        "domain": hit.get("domain"),
        "source": hit.get("source"),
        "kept": hit.get("kept"),
        "drop_reason": hit.get("drop_reason"),
        "position_rank": hit.get("position_rank"),
        "existing_hit_score": hit.get("existing_hit_score"),
        "candidate_link": hit.get("candidate_link"),
        "search_id": hit.get("search_id"),
        "hit_id": hit.get("hit_id"),
        "final_pass": hit.get("final_pass"),
        "fail_stage": hit.get("fail_stage"),
        "stop_reason": hit.get("stop_reason"),
        "heuristic_answer_presence": hit.get("heuristic_answer_presence"),
        "heuristic_reasons": hit.get("heuristic_reasons"),
        # Human fields (fill later)
        "human_label": MISSING,  # DIRECT|CORE|RELATED|IRRELEVANT|MISLEADING|UNKNOWN
        "answer_presence": MISSING,  # direct|core|related|none|misleading|unknown
        "source_quality": MISSING,
        "answer_location": MISSING,
        "answer_excerpt_reference": MISSING,
        "human_rationale": MISSING,
        "drop_heuristic_error": MISSING,  # true if useful dropped wrongly
        "notes": MISSING,
        "allowed_human_labels": list(HUMAN_LABELS),
        "allowed_answer_presence": list(ANSWER_PRESENCE),
        "allowed_source_quality": list(SOURCE_QUALITY),
        "label_guide": {
            "DIRECT": "質問そのものへの直接的な回答・解決情報",
            "CORE": "直接回答ではないが回答を構築する核心情報",
            "RELATED": "関連だが単独では核心にならない",
            "IRRELEVANT": "有用性がほぼない",
            "MISLEADING": "関連して見えるが誤情報・文脈違い・適用不能",
            "UNKNOWN": "ページ内容を十分確認できない",
        },
        "constraints": {
            "heuristic_is_not_ground_truth": True,
            "answer_present_is_not_success": True,
            "do_not_auto_reinject_dropped": True,
        },
    }


def make_case_loss_forms(case_meta):
    forms = []
    for case, meta in case_meta.items():
        if meta.get("pass") is True:
            continue
        forms.append(
            {
                "form_id": _new_id("loss"),
                "case": case,
                "final_pass": meta.get("pass"),
                "fail_stage": meta.get("fail_stage"),
                "stop_reason": meta.get("stop_reason"),
                "request": meta.get("request"),
                "valid_for_kss15_measurement": meta.get(
                    "valid_for_kss15_measurement"
                ),
                "human_audit_status": "pending",
                "answer_present_in_web": MISSING,  # true|false|unknown (not success)
                "run_success": bool(meta.get("pass")),
                "primary_loss_stage": MISSING,
                "secondary_loss_stage": MISSING,
                "allowed_loss_stages": list(LOSS_STAGES),
                "loss_stage_guide": {
                    "SEARCH_MISS": "有用情報を取得できていない",
                    "DROP_ERROR": "有用hitをdroppedした",
                    "CANDIDATE_MISS": "kept有用情報がcandidate化されなかった",
                    "VERIFY_ERROR": "verificationで採用できなかった",
                    "USABLE_CONVERSION_ERROR": "usable findingへ変換できなかった",
                    "JUDGE_ERROR": "usableがあるのにjudgeで不適切",
                    "PROGRESS_ERROR": "継続/終了判断が不適切",
                    "PROPOSAL_ERROR": "research以前のproposal失敗",
                    "UNKNOWN": "観測だけでは判定不能",
                },
                "notes": MISSING,
            }
        )
    return forms


def write_worksheet(entries, loss_forms, out_path: Path):
    lines = [
        "# KSS-1.5.1 人手監査ワークシート（日本語版）",
        "",
        "**状態: `human_audit_status = pending` ／ `routing_ready = false`**",
        "",
        "> **今回調べたいのは「AIが最終的に成功したか」ではありません。**",
        ">",
        "> AIが検索で取得したページの中に、本来なら回答に使える情報が存在していたのに、",
        "> それをAIが捨てたり、後段で利用できなかったケースがあったかを調べます。",
        ">",
        "> したがって、「run_success = false」（最終失敗）でも、その検索結果の中に答えが",
        "> 存在している可能性があります。",
        ">",
        "> 逆に、`answer_presence = core` でも、それだけで「AIが成功すべきだった」と",
        "> 断定するものではありません。",
        "",
        "AIの自動判定（heuristic）は**正解ではありません**。必ず人間が記入してください。",
        "この監査結果だけを理由に routing や confidence 閾値は実装しません。",
        "",
        "## 用語の説明（記入時に参照）",
        "",
        "### human_label（この検索結果は質問に役立つか）",
        "",
        "- **DIRECT（直接的な回答）**：質問に対する答えがほぼそのまま書かれている",
        "- **CORE（核心的な情報）**：これを使えば回答を組み立てられる",
        "- **RELATED（関連情報）**：関連ではあるが、質問への回答としては弱い",
        "- **IRRELEVANT（無関係）**：質問とはほぼ無関係",
        "- **MISLEADING（誤導の可能性）**：関連しているように見えるが、回答を誤らせる可能性がある",
        "- **UNKNOWN（判断できない）**：判断できない",
        "",
        "### answer_presence（このページの中に、質問の答えはあるか）",
        "",
        "「この検索結果の中に、質問への答えが存在するか」を判定します。",
        "",
        "- **direct（直接ある）**：答えが直接存在する",
        "- **core（核心がある）**：答えそのものではないが、回答の核心となる情報がある",
        "- **related（関連のみ）**：関連情報はあるが、答えとしては不十分",
        "- **none（なし）**：答えにつながる情報がない",
        "- **misleading（誤導）**：誤った方向へ導く情報",
        "- **unknown（不明）**：判断できない",
        "",
        "### source_quality（情報源として信頼できるか）",
        "",
        "- **official（公式）**：公式情報",
        "- **authoritative（権威ある情報）**：公的機関・メーカー等の権威ある情報",
        "- **reputable_secondary（信頼できる二次情報）**：信頼性の高い二次情報",
        "- **ordinary（一般）**：一般的な情報源",
        "- **unknown（不明）**：判断できない",
        "- **unreliable（低い）**：信頼性が低い",
        "",
        "---",
        "",
        f"## A. 捨てられた検索結果の監査（全 {sum(1 for e in entries if e.get('bucket')=='DROPPED_ALL')} 件）",
        "",
        "**目的:** AIが捨てた検索結果の中に、本当に使える情報があったか？",
        "",
        "今回は9件すべて確認します。",
        "",
    ]
    dropped = [e for e in entries if e.get("bucket") == "DROPPED_ALL"]
    for i, e in enumerate(dropped, 1):
        lines.extend(_entry_block_ja(i, e))

    kept = [e for e in entries if e.get("bucket") == "FAILED_KEPT_CORE_UNIQUE"]
    lines.extend(
        [
            "---",
            "",
            f"## B. 失敗したケースで残っていた検索結果の監査（{len(kept)} 件）",
            "",
            "**目的:** AIが残した検索結果は、本当に質問への回答に役立つものだったか？",
            "",
            "（失敗ケースで、AIのheuristicが core/direct としたものを優先。URL重複は除外済み）",
            "",
        ]
    )
    for i, e in enumerate(kept, 1):
        lines.extend(_entry_block_ja(i, e))

    lines.extend(
        [
            "---",
            "",
            "## C. 失敗した場所の監査",
            "",
            "**目的:** Web検索から最終回答までのどこで情報が失われた可能性があるか？",
            "",
            "選択肢:",
            "",
            "- **SEARCH_MISS**：検索段階で見つけられなかった",
            "- **DROP_ERROR**：検索結果を誤って捨てた",
            "- **CANDIDATE_MISS**：候補として拾えなかった",
            "- **VERIFY_ERROR**：検証段階で失敗した",
            "- **USABLE_CONVERSION_ERROR**：使える情報に変換できなかった",
            "- **JUDGE_ERROR**：LLMの判断で失敗した",
            "- **PROGRESS_ERROR**：調査継続・終了判断で失敗した",
            "- **PROPOSAL_ERROR**：Tool提案段階で失敗した",
            "- **UNKNOWN**：判断できない",
            "",
            "主因と副因がある場合は `primary_loss_stage` / `secondary_loss_stage` に分けて記入。",
            "",
        ]
    )
    for form in loss_forms:
        success_ja = "成功" if form.get("run_success") else "失敗"
        lines.extend(
            [
                f"### ケース `{form.get('case')}`",
                "",
                f"- 最終結果（run_success）: **{success_ja}**（`{form.get('run_success')}`）※これは「ページに答えがあったか」とは別",
                f"- 失敗段階 fail_stage / 停止理由: `{form.get('fail_stage')}` / `{form.get('stop_reason')}`",
                f"- 質問: {form.get('request')}",
                "",
                f"- **answer_present_in_web**（Web上に答えがあったか）: `{form.get('answer_present_in_web')}`",
                "  - 記入: `true`（あった） / `false`（なかった） / `unknown`（不明）",
                "  - ※ここが true でも「成功すべき」とは断定しない",
                f"- **primary_loss_stage**（主に失われた段階）: `{form.get('primary_loss_stage')}`",
                f"- **secondary_loss_stage**（副次的な段階）: `{form.get('secondary_loss_stage')}`",
                f"- **notes**（メモ）: `{form.get('notes')}`",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "## 記入後の手順",
            "",
            "1. このワークシートの内容を `ground_truth_labels.json` に転記する"
            "（または `ground_truth_template.json` の同名フィールドを編集）。",
            "2. 集計: `python _kss151_human_audit.py --apply-labels <filled.json> --out-dir <この実験ディレクトリ>`",
            "3. サンプル数が少ない場合、精度は「観測サンプル／小標本の見積もり」として扱う。",
            "4. **この結果だけで routing や confidence 閾値は実装しない。**",
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _kept_dropped_ja(kept):
    if kept is True:
        return "残した検索結果（KEPT）"
    if kept is False:
        return "捨てた検索結果（DROPPED）"
    return "不明"


def _entry_block_ja(i, e):
    kept = e.get("kept")
    lines = [
        f"### {i}. 監査ID `{e.get('audit_id')}` ／ ケース `{e.get('case')}` ／ ラウンド {e.get('round')}",
        "",
        "#### 質問",
        "",
        f"{e.get('original_question')}",
        "",
        f"- 検索クエリ: {e.get('query')}",
        f"- 最終結果: pass=`{e.get('final_pass')}` ／ fail_stage=`{e.get('fail_stage')}` ／ stop=`{e.get('stop_reason')}`",
        "",
        "#### 検索結果",
        "",
        f"- タイトル: {e.get('title')}",
        f"- URL: {e.get('url')}",
        f"- ドメイン: `{e.get('domain')}`",
        f"- 抜粋: {(e.get('snippet') or '')[:400]}",
        f"- 順位 / hit_score: {e.get('position_rank')} / {e.get('existing_hit_score')}",
        "",
        "#### AIはどう扱ったか",
        "",
        f"- **{_kept_dropped_ja(kept)}**",
        f"- 捨てた理由 drop_reason: `{e.get('drop_reason')}`",
        f"- AIの自動判定 heuristic（参考・正解ではない）: `{e.get('heuristic_answer_presence')}`",
        f"- candidateとの接続: `{json.dumps(e.get('candidate_link'), ensure_ascii=False)}`",
        "",
        "#### 人間が判断すること",
        "",
        "① **この検索結果は質問に役立つか？**（`human_label`）",
        "",
        f"- 記入欄: `{e.get('human_label')}`",
        "- 選択: **DIRECT（直接的な回答）** / **CORE（核心的な情報）** / **RELATED（関連情報）** / **IRRELEVANT（無関係）** / **MISLEADING（誤導の可能性）** / **UNKNOWN（判断できない）**",
        "",
        "② **このページの中に、質問の答えはあるか？**（`answer_presence`）",
        "",
        f"- 記入欄: `{e.get('answer_presence')}`",
        "- 選択: **direct（直接ある）** / **core（核心がある）** / **related（関連のみ）** / **none（なし）** / **misleading（誤導）** / **unknown（不明）**",
        "",
        "③ **情報源として信頼できるか？**（`source_quality`）",
        "",
        f"- 記入欄: `{e.get('source_quality')}`",
        "- 選択: **official（公式）** / **authoritative（権威ある情報）** / **reputable_secondary（信頼できる二次情報）** / **ordinary（一般）** / **unknown（不明）** / **unreliable（低い）**",
        "",
        "④ **どこに答えがあるか？**（`answer_location` / `answer_excerpt_reference`）",
        "",
        f"- 場所: `{e.get('answer_location')}` ← 見出し・段落など。分からなければ `不明`",
        f"- 参照メモ: `{e.get('answer_excerpt_reference')}` ← 再確認できる短い手がかり",
        "",
        "⑤ **なぜそう判断したか？**（`human_rationale`）",
        "",
        f"- 記入欄: `{e.get('human_rationale')}` ← 日本語で1～2文",
        "",
    ]
    if kept is False:
        lines.extend(
            [
                "⑥ **AIがこの検索結果を捨てたのは間違いだったか？**（`drop_heuristic_error`）",
                "",
                f"- 記入欄: `{e.get('drop_heuristic_error')}`",
                "- `true`：捨てるべきではなかった",
                "- `false`：捨てて問題なかった",
                "- `unknown`：判断できない",
                "",
            ]
        )
    lines.extend(
        [
            f"- その他メモ notes: `{e.get('notes')}`",
            "",
        ]
    )
    return lines


def empty_report_counts():
    return {
        "dropped_total": 0,
        "human_direct": MISSING,
        "human_core": MISSING,
        "human_related": MISSING,
        "human_none": MISSING,
        "human_misleading": MISSING,
        "human_unknown": MISSING,
        "kept_audited": 0,
        "kept_direct": MISSING,
        "kept_core": MISSING,
        "kept_related": MISSING,
        "kept_none": MISSING,
        "kept_misleading": MISSING,
        "kept_unknown": MISSING,
        "failure_loss_stage_counts": {k: MISSING for k in LOSS_STAGES},
        "heuristic_calibration": {
            "status": "pending_human_labels",
            "note": "small-n; do not claim true precision",
            "confusion_matrix": MISSING,
            "heuristic_direct_precision": MISSING,
            "heuristic_core_precision": MISSING,
            "heuristic_answer_presence_precision": MISSING,
            "heuristic_false_negative_rate": MISSING,
            "heuristic_false_positive_rate": MISSING,
        },
    }


def write_report(meta, entries, loss_forms, out_path: Path):
    frozen = meta.get("frozen_observation") or {}
    dropped_n = sum(1 for e in entries if e["bucket"] == "DROPPED_ALL")
    kept_n = sum(1 for e in entries if e["bucket"] == "FAILED_KEPT_CORE_UNIQUE")
    lines = [
        "# KSS-1.5.1 Human Audit Ground Truth",
        "",
        f"- experiment_id: see summary.json",
        f"- source_experiment: `{meta.get('source_experiment_id')}` (immutable)",
        f"- human_audit_status: **pending**",
        f"- routing_ready: **false**",
        "",
        "## Frozen KSS-1.5 observation (not rewritten)",
        "",
        f"```json\n{json.dumps(frozen, ensure_ascii=False, indent=2)}\n```",
        "",
        "> Do **not** treat `heuristic_dropped_answer_rate_observed` as confirmed precision.",
        "",
        "## Audit scope",
        "",
        f"- Dropped hits to audit: **{dropped_n}** (all)",
        f"- Failed kept (heuristic core/direct, unique URL): **{kept_n}**",
        f"- Failure loss-stage forms: **{len(loss_forms)}**",
        "",
        "## A. Dropped audit (pending)",
        "",
        f"- dropped_total: {dropped_n}",
        "- human_direct/core/related/none/misleading/unknown: **missing** until labeled",
        "",
        "## B. Kept audit (pending)",
        "",
        f"- kept_audited (planned): {kept_n}",
        "- human counts: **missing** until labeled",
        "",
        "## C. Failure loss stage (pending)",
        "",
        "- All stages: **missing** until case forms filled",
        "",
        "## D. Heuristic calibration (pending)",
        "",
        "- confusion matrix / precision / FPR / FNR: **missing**",
        "- When computed: report as *observed sample / small-n / human-audit estimate* only",
        "",
        "## Non-goals (explicit)",
        "",
        "- No Web retry / force / search-count change",
        "- No confidence thresholds / HELP / 上位LLM routing",
        "- No Phase 5.1 formalize",
        "- No proving 'lead → continue search' yet (needs trajectory accumulation → KSS-1.6)",
        "",
        "## Next",
        "",
        "1. Fill `human_audit_worksheet.md` / `ground_truth_template.json`",
        "2. Apply labels → regenerate report counts",
        "3. KSS-1.6: compare SEARCH/DROP/VERIFY/JUDGE/PROGRESS improvement options",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def apply_labels(template_path: Path, labels_path: Path, out_dir: Path):
    """Optional: merge filled labels and compute small-n calibration."""
    tmpl = json.loads(template_path.read_text(encoding="utf-8"))
    labels_doc = json.loads(labels_path.read_text(encoding="utf-8"))
    by_id = {
        x["audit_id"]: x
        for x in (labels_doc.get("entries") or [])
        if x.get("audit_id")
    }
    filled = 0
    for e in tmpl.get("entries") or []:
        lab = by_id.get(e["audit_id"])
        if not lab:
            continue
        for key in (
            "human_label",
            "answer_presence",
            "source_quality",
            "answer_location",
            "answer_excerpt_reference",
            "human_rationale",
            "drop_heuristic_error",
            "notes",
            "human_audit_status",
        ):
            if key in lab and lab[key] not in (None, "", MISSING):
                e[key] = lab[key]
        if e.get("human_label") not in (None, "", MISSING):
            e["human_audit_status"] = "labeled"
            filled += 1

    loss_by_case = {
        x["case"]: x for x in (labels_doc.get("loss_forms") or []) if x.get("case")
    }
    for form in tmpl.get("loss_forms") or []:
        lab = loss_by_case.get(form["case"])
        if not lab:
            continue
        for key in (
            "answer_present_in_web",
            "primary_loss_stage",
            "secondary_loss_stage",
            "notes",
            "human_audit_status",
        ):
            if key in lab and lab[key] not in (None, "", MISSING):
                form[key] = lab[key]
        if form.get("primary_loss_stage") not in (None, "", MISSING):
            form["human_audit_status"] = "labeled"

    # counts
    def count_labels(bucket_pred, field="human_label"):
        c = Counter()
        n = 0
        for e in tmpl.get("entries") or []:
            if not bucket_pred(e):
                continue
            if e.get(field) in (None, "", MISSING):
                continue
            n += 1
            c[str(e.get(field)).upper() if field == "human_label" else e.get(field)] += 1
        return n, c

    drop_n, drop_c = count_labels(lambda e: e.get("bucket") == "DROPPED_ALL")
    kept_n, kept_c = count_labels(
        lambda e: e.get("bucket") == "FAILED_KEPT_CORE_UNIQUE"
    )

    # confusion heuristic vs human answer_presence
    matrix = Counter()
    valuable_h = {"direct", "core", "lead"}
    valuable_human = {"direct", "core"}
    tp = fp = tn = fn = 0
    paired = 0
    for e in tmpl.get("entries") or []:
        h = e.get("heuristic_answer_presence")
        a = e.get("answer_presence")
        if a in (None, "", MISSING):
            continue
        paired += 1
        matrix[f"{h}->{a}"] += 1
        pred = h in valuable_h
        truth = a in valuable_human
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif (not pred) and truth:
            fn += 1
        else:
            tn += 1

    def rate(num, den):
        if den == 0:
            return MISSING
        return round(num / den, 3)

    loss_counts = Counter()
    for form in tmpl.get("loss_forms") or []:
        st = form.get("primary_loss_stage")
        if st not in (None, "", MISSING):
            loss_counts[st] += 1

    pending = any(
        e.get("human_audit_status") == "pending" for e in (tmpl.get("entries") or [])
    ) or any(
        f.get("human_audit_status") == "pending" for f in (tmpl.get("loss_forms") or [])
    )

    report_counts = {
        "dropped_total": sum(1 for e in tmpl["entries"] if e["bucket"] == "DROPPED_ALL"),
        "human_direct": drop_c.get("DIRECT", 0) if drop_n else MISSING,
        "human_core": drop_c.get("CORE", 0) if drop_n else MISSING,
        "human_related": drop_c.get("RELATED", 0) if drop_n else MISSING,
        "human_none": drop_c.get("IRRELEVANT", 0) if drop_n else MISSING,
        "human_misleading": drop_c.get("MISLEADING", 0) if drop_n else MISSING,
        "human_unknown": drop_c.get("UNKNOWN", 0) if drop_n else MISSING,
        "dropped_labeled": drop_n,
        "kept_audited": sum(
            1 for e in tmpl["entries"] if e["bucket"] == "FAILED_KEPT_CORE_UNIQUE"
        ),
        "kept_direct": kept_c.get("DIRECT", 0) if kept_n else MISSING,
        "kept_core": kept_c.get("CORE", 0) if kept_n else MISSING,
        "kept_related": kept_c.get("RELATED", 0) if kept_n else MISSING,
        "kept_none": kept_c.get("IRRELEVANT", 0) if kept_n else MISSING,
        "kept_misleading": kept_c.get("MISLEADING", 0) if kept_n else MISSING,
        "kept_unknown": kept_c.get("UNKNOWN", 0) if kept_n else MISSING,
        "kept_labeled": kept_n,
        "failure_loss_stage_counts": {
            k: loss_counts.get(k, 0) for k in LOSS_STAGES
        }
        if loss_counts
        else {k: MISSING for k in LOSS_STAGES},
        "heuristic_calibration": {
            "status": "partial" if paired else "pending_human_labels",
            "paired_n": paired,
            "note": "observed sample / small-n / human-audit estimate only",
            "confusion_matrix": dict(matrix),
            "heuristic_answer_presence_precision": rate(tp, tp + fp),
            "heuristic_false_positive_rate": rate(fp, fp + tn),
            "heuristic_false_negative_rate": rate(fn, fn + tp),
            "heuristic_direct_precision": MISSING,
            "heuristic_core_precision": MISSING,
            "tp_fp_tn_fn": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        },
    }

    tmpl["report_counts"] = report_counts
    tmpl["human_audit_status"] = "pending" if pending else "labeled"
    tmpl["routing_ready"] = False
    out = out_dir / "ground_truth_filled.json"
    out.write_text(json.dumps(tmpl, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "calibration_summary.json").write_text(
        json.dumps(report_counts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {out}")
    print(f"labeled_entries≈{filled} paired_for_confusion={paired} routing_ready=False")
    return report_counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(SRC_DEFAULT))
    parser.add_argument("--apply-labels", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument(
        "--regen-worksheet",
        default="",
        help="既存 ground_truth_template.json から日本語ワークシートだけ再生成",
    )
    args = parser.parse_args()
    src = Path(args.src)

    if args.regen_worksheet:
        exp_dir = Path(args.regen_worksheet)
        tmpl = json.loads(
            (exp_dir / "ground_truth_template.json").read_text(encoding="utf-8")
        )
        write_worksheet(
            tmpl.get("entries") or [],
            tmpl.get("loss_forms") or [],
            exp_dir / "human_audit_worksheet.md",
        )
        # 英語版を残したい場合の退避はしない（ユーザー要求は日本語版へ変更）
        print(f"Wrote Japanese worksheet: {exp_dir / 'human_audit_worksheet.md'}")
        return

    if args.apply_labels:
        out_dir = Path(args.out_dir) if args.out_dir else Path(args.apply_labels).parent
        apply_labels(out_dir / "ground_truth_template.json", Path(args.apply_labels), out_dir)
        return

    exp_id = "kss151_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    exp_dir = OUT_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    meta = load_frozen_kss15(src)
    dropped, kept_unique, case_meta = extract_hits(src)

    entries = [make_audit_entry(h, bucket="DROPPED_ALL") for h in dropped]
    entries.extend(
        make_audit_entry(h, bucket="FAILED_KEPT_CORE_UNIQUE") for h in kept_unique
    )
    loss_forms = make_case_loss_forms(case_meta)

    template = {
        "phase": "kss-1.5.1",
        "experiment_id": exp_id,
        "human_audit_status": "pending",
        "routing_ready": False,
        "not_for_decision": True,
        "source_kss15": meta,
        "entries": entries,
        "loss_forms": loss_forms,
        "report_counts": empty_report_counts(),
        "report_counts_note": "pending until human labels; A/B/C/D sections stay missing",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    # patch empty report with known planned totals
    template["report_counts"]["dropped_total"] = len(dropped)
    template["report_counts"]["kept_audited"] = len(kept_unique)

    (exp_dir / "ground_truth_template.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (exp_dir / "manifest.json").write_text(
        json.dumps(
            {
                "experiment_id": exp_id,
                "phase": "kss-1.5.1",
                "purpose": "human audit ground truth for discarded/kept web evidence",
                "source_experiment_id": meta.get("source_experiment_id"),
                "source_immutable": True,
                "routing": False,
                "human_audit_status": "pending",
                "dropped_to_audit": len(dropped),
                "failed_kept_unique_to_audit": len(kept_unique),
                "loss_forms": len(loss_forms),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_worksheet(entries, loss_forms, exp_dir / "human_audit_worksheet.md")
    write_report(meta, entries, loss_forms, exp_dir / "report.md")

    summary = {
        "experiment_id": exp_id,
        "phase": "kss-1.5.1",
        "human_audit_status": "pending",
        "routing_ready": False,
        "source_experiment_id": meta.get("source_experiment_id"),
        "source_immutable": True,
        "frozen_observation": meta.get("frozen_observation"),
        "audit_scope": {
            "dropped_total": len(dropped),
            "failed_kept_core_unique": len(kept_unique),
            "loss_forms": len(loss_forms),
            "dropped_by_case": dict(Counter(h["case"] for h in dropped)),
            "kept_unique_by_case": dict(Counter(h["case"] for h in kept_unique)),
        },
        "report_counts": template["report_counts"],
        "files": [
            "ground_truth_template.json",
            "human_audit_worksheet.md",
            "report.md",
            "manifest.json",
        ],
        "non_goals": [
            "routing",
            "confidence thresholds",
            "web force / retry",
            "treat heuristic rate 0.778 as confirmed",
            "answer_present = success",
        ],
    }
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Wrote {exp_dir}")
    print(f"dropped_to_audit={len(dropped)} kept_unique_fail_core={len(kept_unique)}")
    print("human_audit_status=pending routing_ready=False")


if __name__ == "__main__":
    main()
