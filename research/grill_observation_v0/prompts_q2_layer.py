"""Prompts for Grill Q2 intermediate layer. Observation only.

Do not seed a specific first Human question.
Do not encode Q-number-specific rules.
"""
from __future__ import annotations

import json
from typing import Any

CLASSIFY_SYSTEM = """あなたは Goal 具体化の中間判定役です。
人間へ質問する前に、その Decision が人間の意図を必要とするかを判定します。
コードは書かない。人間の回答を作らない。JSON のみ返す。

判定の観点:
- human_intent_required: 人間の好み・完成像・利用体験・要求が必要か
- human_impact: 決めた結果が人間の使い方・見た目・体験を変えるか (none/low/medium/high)
- technical_only: 実装手段の差で、Goal 上の人間体験に実質差が小さいか

環境事実として与えられたことは人間に聞かない。
Goal が技術手段の選定を AI に任せているなら、それは判定材料になる。Q番号ルールにはしない。
矛盾チェック: 既存 Goal / Environment / 既知の確定仕様と recommendation が矛盾しないか。
"""

CLASSIFY_SHAPE = {
    "human_intent_required": False,
    "human_impact": "none|low|medium|high",
    "technical_only": True,
    "classification": "ai_decidable|human_required|mixed",
    "next_action": "adopt_recommendation|ask_human|abstain",
    "reason": "判定理由",
    "contradicts_goal_or_env": False,
    "recommendation_ok_to_adopt": True,
    "adopt": {
        "id": "short_id",
        "title": "仕様項目名",
        "value": "確定する値",
        "reason": "採用理由",
    },
}

REEVAL_SYSTEM = """あなたは現在仕様から未確定領域を再構成する役です。
思いついた1件を即 Human 質問にしてはいけない。
まず主要未確定領域を複数挙げ、比較してから、次に進む1件だけ選ぶ。
コードは書かない。人間の回答を作らない。JSON のみ返す。

各候補について:
- goal_impact: Goal 達成への影響 (low/medium/high)
- human_intent_required: 人間の意図が必要か
- human_impact: 人間の使い方・見た目・体験への影響
- rollback_impact: 後で変えると手戻りが大きいか
- cross_cutting_impact: 他項目へ横断するか
- ai_decidable: 今の Goal / Environment / 確定仕様だけで AI が決めてよいか

next.action:
- internal_ai_decision: 今選んだ1件は AI だけで決めてよい。ai_decision に値を入れる
- ask_human: 人間の意図が必要。humanize は別工程。ここでは質問文を完成させない
- none: 主要未確定が無い

項目名の正解リストは無い。現在仕様から自分で抽出する。
既に confirmed の項目を未確定に戻さない。
"""

REEVAL_SHAPE = {
    "unresolved_regions": [
        {
            "id": "short_id",
            "title": "項目名",
            "text": "何が未確定か",
            "goal_impact": "low|medium|high",
            "human_intent_required": True,
            "human_impact": "none|low|medium|high",
            "rollback_impact": "low|medium|high",
            "cross_cutting_impact": "low|medium|high",
            "ai_decidable": False,
            "why": "短い評価",
        }
    ],
    "comparison": "なぜこの順位か",
    "next": {
        "id": "short_id",
        "action": "internal_ai_decision|ask_human|none",
        "reason": "なぜこれを次にするか",
        "ai_decision": {
            "id": "short_id",
            "title": "仕様項目名",
            "value": "AIが選ぶ値",
            "reason": "理由",
            "evidence": "根拠の要約",
        },
    },
}

HUMANIZE_SYSTEM = """あなたは内部 Decision を人間向けの1問へ逆変換する役です。
技術用語の言い換えだけで終わらせない。
人間にとって何が変わるか（使い方 / 見た目 / 体験 / 要求の違い）へ変換する。
一度に1問。コードは書かない。人間の回答を作らない。JSON のみ返す。

候補は有力なものだけ。推奨を1つ付け、短い理由を付ける。
"""

HUMANIZE_SHAPE = {
    "why_ask_human": "今回Humanへ確認する理由",
    "technical_decision": "内部で扱っていた Decision の要約",
    "what_changes_for_human": "人間にとって何が変わるか",
    "conversion_notes": "Technical から Human へどう変換したか",
    "focus_item": {
        "id": "short_id",
        "title": "人間向けの項目名",
        "why_now": "なぜ今これを決めるか",
    },
    "question": "人間向けの質問文（1問）",
    "options": [
        {"id": "A", "label": "短い名前", "description": "使い方・見た目・体験の違い"}
    ],
    "recommendation": {"id": "A", "reason": "短い理由"},
}


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def build_classify_user(*, goal: str, env_facts: dict[str, Any], pending: dict[str, Any], state: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Goal",
            goal,
            "",
            "# Environment facts (already known; do not ask)",
            _dump(env_facts),
            "",
            "# Current system state",
            _dump(state),
            "",
            "# Pending decision (from a previous Grill turn)",
            _dump(pending),
            "",
            "この pending decision は人間へ聞くべきか、AI だけで決めてよいか判定せよ。",
            "AI で決めてよいなら recommendation を採用候補として adopt に書け。",
            "Q番号や特定ライブラリ名を正解として扱うな。中身を見て判定せよ。",
            "出力JSONの形:",
            _dump(CLASSIFY_SHAPE),
        ]
    )


def build_reeval_user(*, goal: str, state: dict[str, Any], internal_budget_left: int) -> str:
    return "\n".join(
        [
            "# Goal",
            goal,
            "",
            "# Current system state",
            _dump(state),
            "",
            f"# Internal AI decision budget remaining: {internal_budget_left}",
            "主要未確定領域を複数抽出し、比較せよ。1件思いついて即質問にするな。",
            "比較後、次の1件だけを next にせよ。",
            "next.action が internal_ai_decision のときだけ ai_decision.value を埋めよ。",
            "ask_human のときは質問文を作るな。",
            "出力JSONの形:",
            _dump(REEVAL_SHAPE),
        ]
    )


def build_humanize_user(
    *,
    goal: str,
    state: dict[str, Any],
    selected_region: dict[str, Any],
    comparison: str,
) -> str:
    return "\n".join(
        [
            "# Goal",
            goal,
            "",
            "# Current system state",
            _dump(state),
            "",
            "# Selected unresolved region (ask human)",
            _dump(selected_region),
            "",
            "# Comparison that led to this choice",
            comparison,
            "",
            "この領域を、人間が判断できる1問へ逆変換せよ。",
            "技術手段の名前を聞く形にしない。体験・見た目・使い方・要求の差にする。",
            "特定の質問文を正解として再現する必要はない。",
            "出力JSONの形:",
            _dump(HUMANIZE_SHAPE),
        ]
    )
