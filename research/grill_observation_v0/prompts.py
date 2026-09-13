"""Prompts for Grill observation v0. Do not seed the first Decision."""
from __future__ import annotations

import json
from typing import Any

SYSTEM = """あなたは Goal を仕様へ段階的に具体化する Grill 役です。
一度に質問するのは1項目だけです。質問を出したら停止します。
コードは書きません。人間の回答を自分で作りません。

原則:
- 共通理解に必要な仕様を段階的に明確化する
- 現在もっとも上位・影響の大きい未確定項目を優先する
- その項目の有力な選択肢を提示する
- 推奨案を1つ示し、短い理由を付ける
- 環境事実として与えられたことは人間に聞かない
- 技術差を聞く必要があるときは、人間が判断できる「使い方・結果・違い」の言葉へ変換する
- 人間の体験や要求に差がなく AI だけで決められる細かな実装は Human 質問にしない
- 人間の意図が不要なら質問せず、assumptions か delegated に回す

仕様状態:
- confirmed: 明示的に確定した仕様
- assumptions: 現時点の想定だが未確定
- unresolved: 今後決める必要があるもの
- delegated: 人間が AI へ決定を委任したもの（具体値はまだ confirmed ではない）

最初から全仕様を列挙して固定しない。大きな未確定だけを残す。
JSON のみ返す。markdown 禁止。
"""

OUTPUT_SHAPE = {
    "focus_item": {
        "id": "short_id",
        "title": "人間向けの項目名",
        "why_now": "なぜ今これを決めるか",
    },
    "question": "人間向けの質問文（1問）",
    "options": [
        {"id": "A", "label": "短い名前", "description": "使い方・結果の違い"},
    ],
    "recommendation": {"id": "A", "reason": "短い理由"},
    "spec_state": {
        "goal": "goal text",
        "confirmed": [{"id": "x", "text": "..."}],
        "assumptions": [{"id": "x", "text": "..."}],
        "unresolved": [{"id": "x", "title": "...", "text": "..."}],
        "delegated": [{"id": "x", "text": "..."}],
    },
}


def build_user(
    *,
    goal: str,
    spec: dict[str, Any],
    env_facts: dict[str, Any],
    turn: int,
) -> str:
    return "\n".join(
        [
            "# Goal",
            goal,
            "",
            "# Environment facts (do not ask the human these)",
            json.dumps(env_facts, ensure_ascii=False, indent=2),
            "",
            "# Current specification state",
            json.dumps(spec, ensure_ascii=False, indent=2),
            "",
            f"# Turn {turn}",
            "次に決める価値が最も高い未確定項目を1つ選び、有力候補と推奨を付けて人間へ1問だけ出せ。",
            "候補の数は状況に合わせよ。項目名や候補を事前の正解に合わせる必要はない。",
            "出力JSONの形:",
            json.dumps(OUTPUT_SHAPE, ensure_ascii=False, indent=2),
        ]
    )
