"""最終回答の完成申告を機械側で拘束する。LLM にお願いするだけではない。"""
from __future__ import annotations

import re
from typing import Any

from ai_tool.policy.evaluate import evaluate_development_work

_COMPLETE_CLAIM = re.compile(
    r"(仕様完成|仕様充足|specification\s*complete|実装完了しました|開発完了しました)",
    re.I,
)


def claims_specification_complete(text: str) -> bool:
    return bool(_COMPLETE_CLAIM.search(str(text or "")))


def apply_final_answer_policy(
    answer: str,
    *,
    items: list[Any] | None = None,
    tests_passed: bool | None = None,
) -> dict[str, Any]:
    """完成申告があるときだけ評価する。通常の Tool 回答は書き換えない。"""
    text = str(answer or "")
    claimed = claims_specification_complete(text)
    if not claimed and not items:
        return {
            "answer": text,
            "applied": False,
            "notice": None,
            "evaluation": None,
        }
    evaluation = evaluate_development_work(
        items=items,
        tests_passed=tests_passed,
        claim_specification_complete=claimed,
        save=True,
    )
    if evaluation.get("may_claim_specification_complete"):
        return {
            "answer": text,
            "applied": True,
            "notice": None,
            "evaluation": evaluation,
        }
    notice = (
        "[DEVELOPMENT_POLICY] specification_status="
        + str(evaluation.get("specification_status"))
        + " test_status="
        + str(evaluation.get("test_status"))
        + " may_claim_specification_complete=false"
        + " blocked_complete_claim="
        + str(evaluation.get("blocked_complete_claim"))
        + "。pytest PASS は仕様完成ではない。項目が全て CONNECTED になるまで仕様完成と判定しない。"
    )
    missing = evaluation.get("decision", {}).get("missing") or []
    if missing:
        notice += " unfinished=" + ",".join(str(row.get("id")) for row in missing[:12])
    out = text.rstrip() + "\n\n" + notice
    return {
        "answer": out,
        "applied": True,
        "notice": notice,
        "evaluation": evaluation,
    }
