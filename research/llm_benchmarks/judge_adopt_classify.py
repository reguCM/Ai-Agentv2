"""
Verifier 成功後の Judge 採用検査。LLM は呼ばない。

usable finding があるとき satisfies_request=true にできるかを見る。
正解コマンドや特定クラス名は見ない。
"""

from tools.ai.tool_builder.research_judge import normalize_judgment


GRADE_ACCEPT = "ACCEPT"
GRADE_MISREJECT = "MISREJECT"
GRADE_FAIL = "FAIL"

MISREJECT_TOKENS = (
    "total physical memory",
    "総物理メモリ",
    "not the memory usage percentage",
    "memory usage percentage which is the metric requested",
    "使用率ではない",
    "used memory is still unconfirmed",
    "搭載容量",
    "totalvisiblememorysize のみ",
)


def _norm(text):
    return str(text or "").strip().lower()


def _join(parts):
    return "\n".join(str(item) for item in parts if str(item or "").strip())


def inspect_judge_adopt_usable(payload, error=None, *, finding_question=None):
    judgment = normalize_judgment(payload)
    json_ok = error not in ("timeout", "no_json") and isinstance(payload, dict)
    accepted = bool(judgment.get("satisfies_request"))
    missing = list(judgment.get("missing") or [])
    reason = judgment.get("reason") or ""
    haystack = _join([reason, _join(missing)])
    misreject = not accepted and any(
        token.lower() in haystack.lower() for token in MISREJECT_TOKENS
    )
    if (
        not accepted
        and finding_question
        and any(_norm(item) == _norm(finding_question) for item in missing)
    ):
        misreject = True
    if not accepted and any(
        phrase in haystack
        for phrase in (
            "数値が得られていません",
            "サンプルが不足",
            "does not directly give the memory usage rate",
        )
    ):
        misreject = True

    if not json_ok:
        grade = GRADE_FAIL
    elif accepted:
        grade = GRADE_ACCEPT
    elif misreject:
        grade = GRADE_MISREJECT
    else:
        grade = GRADE_FAIL

    return {
        "ok": grade == GRADE_ACCEPT,
        "grade": grade,
        "json_ok": json_ok,
        "accepted": accepted,
        "misreject": misreject,
        "missing": missing,
        "reason": reason,
        "satisfies_request": judgment.get("satisfies_request"),
        "proposed_decisions": judgment.get("proposed_decisions") or [],
        "error": error,
    }
