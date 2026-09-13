"""Web answer boundary — enforce limits when web evidence is unavailable.

Uses machine-readable WebSessionTracker state, NOT LLM self-reports.
"""
from __future__ import annotations

import re
from typing import Any

from tools.system.network.web_status import (
    WebSessionTracker,
    user_visible_status_message,
)

# Numeric claims that imply web-verified facts (conservative patterns)
_UNSUPPORTED_NUMERIC = re.compile(
    r"(?:約|およそ|推計)?\s*"
    r"(?:"
    r"[0-9]{1,3}[,，][0-9]{3,}"  # 2,750,000
    r"|[0-9]{4,}"  # 2750000
    r"|[0-9]{1,4}\s*万人"  # 275万人
    r"|[0-9]{1,3}\s*万"  # 275万
    r")\s*(?:万人|人|件|%|percent)?",
    re.I,
)
_WEB_VERIFIED_PHRASES = re.compile(
    r"(?:Web(?:検索)?(?:で|により)|検索(?:結果|で)(?:による|確認)|"
    r"according to (?:the )?web|verified (?:from|on) (?:the )?web)",
    re.I,
)

_FAILURE_STATUSES = frozenset(
    {
        "SEARCH_FAILED",
        "FETCH_FAILED",
        "EXTRACTION_FAILED",
        "NO_EVIDENCE",
    }
)

_SAFE_ANSWER = {
    "SEARCH_FAILED": (
        "Web検索を実行しましたが、該当する結果を取得できませんでした。"
        "Web上で確認済みの具体的数値・事実は提供できません。"
    ),
    "FETCH_FAILED": (
        "Web検索で候補は見つかりましたが、ページの取得に失敗しました。"
        "Web上で確認済みの具体的数値・事実は提供できません。"
    ),
    "EXTRACTION_FAILED": (
        "Webページは取得しましたが、回答に必要な本文を抽出できませんでした。"
        "Web上で確認済みの具体的数値・事実は提供できません。"
    ),
    "NO_EVIDENCE": (
        "Webページは取得しましたが、質問に必要な根拠が本文に見つかりませんでした。"
        "Web上で確認済みの具体的数値・事実は提供できません。"
    ),
}


def detect_unsupported_web_claims(answer: str) -> dict[str, bool]:
    text = str(answer or "")
    return {
        "has_numeric_claim": bool(_UNSUPPORTED_NUMERIC.search(text)),
        "has_web_verified_phrrasing": bool(_WEB_VERIFIED_PHRASES.search(text)),
    }


def apply_web_answer_boundary(
    answer: str,
    session: WebSessionTracker,
    *,
    web_required: bool | None = None,
) -> dict[str, Any]:
    """
    Apply answer control based on aggregated web status.

    Returns dict with:
      answer, boundary_applied, system_notice, web_status, claims_detected
    """
    aggregate = session.aggregate()
    overall = aggregate.get("overall")
    claims = detect_unsupported_web_claims(answer)

    if web_required is None:
        web_required = session.web_tools_used()

    result: dict[str, Any] = {
        "answer": answer,
        "boundary_applied": False,
        "system_notice": user_visible_status_message(aggregate),
        "web_status": aggregate,
        "claims_detected": claims,
        "web_required": web_required,
    }

    if not web_required or overall in (None, "NOT_APPLICABLE", "SUCCESS"):
        return result

    if overall == "PARTIAL":
        if claims["has_numeric_claim"] and aggregate.get("fetch_fact_ready_count", 0) == 0:
            result["boundary_applied"] = True
            result["answer"] = _SAFE_ANSWER.get("NO_EVIDENCE", answer)
        return result

    if overall not in _FAILURE_STATUSES:
        return result

    unsupported = (
        claims["has_numeric_claim"]
        or claims["has_web_verified_phrrasing"]
    )
    if unsupported:
        result["boundary_applied"] = True
        result["answer"] = _SAFE_ANSWER.get(str(overall), _SAFE_ANSWER["SEARCH_FAILED"])
        if result["system_notice"] is None:
            result["system_notice"] = user_visible_status_message(aggregate)

    return result
