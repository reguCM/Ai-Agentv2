"""
Verifier 失敗後の Judge 検査。LLM は呼ばない。

再調査へ戻れるかは retry_ok。
missing の質は A / B / C / FAIL。
正解コマンドや特定クラス名は見ない。
A は要求達成に必要な不足対象（計測対象）を具体化できること。
"""

from tools.ai.tool_builder.research_judge import items_from_missing, normalize_judgment


GRADE_A = "A"
GRADE_B = "B"
GRADE_C = "C"
GRADE_FAIL = "FAIL"

FETCH_IN_MISSING = (
    "get-ciminstance",
    "get-wmiobject",
    "powershell -",
    "wmic ",
    "subprocess",
    "-command",
    "-noprofile",
)

ERROR_ECHO = (
    "0 で除算",
    "除算しようとしました",
    "実環境で確認できなかった",
)

GAP_TOKENS = (
    "総物理メモリ",
    "総メモリ",
    "使用中メモリ",
    "使用メモリ",
    "空きメモリ",
    "物理メモリ",
    "利用可能メモリ",
    "total physical memory",
    "used memory",
    "still unconfirmed",
)

VAGUE_METHOD = (
    "正しい方法",
    "正しい計算方法",
    "取得方法を確認",
    "取得方法を調査",
    "取得方法を教",
    "方法を確認",
    "調査する必要",
    "調べる必要",
    "コマンドやスクリプト",
    "スクリプトを調",
)

RECOGNIZED_TOKENS = (
    "除算",
    "計算に失敗",
    "計算でき",
    "不足",
    "未確認",
    "sample",
    "サンプル",
    "使用率ではない",
    "要求を満たさ",
    "値が取れて",
    "使用率の値",
    "メモリ情報",
)


def _norm(text):
    return str(text or "").strip().lower()


def _has_any(text, tokens):
    hay = _norm(text)
    return any(_norm(token) and _norm(token) in hay for token in tokens)


def _join(parts):
    return "\n".join(str(item) for item in parts if str(item or "").strip())


def extra_research_text(payload):
    if not isinstance(payload, dict):
        return ""
    extra = payload.get("next_research")
    if extra is None:
        extra = payload.get("next_research_question")
    if isinstance(extra, list):
        return _join(extra)
    return str(extra or "")


def command_in_text(text):
    hay = _norm(text)
    return any(token in hay for token in FETCH_IN_MISSING)


def vague_method_only(text):
    return _has_any(text, VAGUE_METHOD) and not _has_any(text, GAP_TOKENS)


def inspect_judge_verify_retry(payload, error=None):
    judgment = normalize_judgment(payload)
    json_ok = error not in ("timeout", "no_json") and isinstance(payload, dict)
    not_accepted = not judgment.get("satisfies_request")
    missing = list(judgment.get("missing") or [])
    missing_text = _join(missing)
    reason = judgment.get("reason") or ""
    next_research = extra_research_text(payload)
    question_text = _join([missing_text, next_research])
    haystack = _join([reason, missing_text, next_research])
    has_missing = bool(missing)
    command_in_missing = command_in_text(question_text)
    next_items = items_from_missing(missing)
    retry_research = bool(next_items)
    retry_ok = (
        json_ok
        and not_accepted
        and has_missing
        and retry_research
        and not command_in_missing
    )
    echo = _has_any(missing_text, ERROR_ECHO) and not _has_any(
        missing_text, GAP_TOKENS
    )
    has_gap = _has_any(missing_text, GAP_TOKENS)
    vague = vague_method_only(missing_text) or all(
        vague_method_only(item) for item in missing
    )
    recognized = _has_any(haystack, RECOGNIZED_TOKENS) or _has_any(
        haystack, ERROR_ECHO
    )

    if not json_ok or not not_accepted:
        grade = GRADE_FAIL
    elif echo:
        grade = GRADE_C
    elif retry_ok and has_gap and not vague:
        grade = GRADE_A
    elif retry_ok and recognized:
        grade = GRADE_B
    elif retry_ok:
        grade = GRADE_B
    else:
        grade = GRADE_FAIL

    return {
        "ok": grade == GRADE_A,
        "grade": grade,
        "retry_ok": retry_ok,
        "json_ok": json_ok,
        "not_accepted": not_accepted,
        "has_missing": has_missing,
        "retry_research": retry_research,
        "command_in_missing": command_in_missing,
        "echo": echo,
        "has_gap": has_gap,
        "vague": vague,
        "recognized": recognized,
        "missing": missing,
        "reason": reason,
        "next_research": next_research or None,
        "satisfies_request": judgment.get("satisfies_request"),
        "next_questions": [item.get("question") for item in next_items],
        "error": error,
    }
