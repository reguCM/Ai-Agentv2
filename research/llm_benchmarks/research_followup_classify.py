"""
Research 再調査（follow-up）の機械検査。LLM は呼ばない。

Judge missing + 失敗候補を受けたあと、
Research が前回と異なる候補を出せるかを A/B/C/FAIL で見る。
正解コマンドは見ない。
"""

from tools.system.tool_builder.research.verify import (
    candidate_is_allowed,
    normalize_candidate,
)


GRADE_A = "A"
GRADE_B = "B"
GRADE_C = "C"
GRADE_FAIL = "FAIL"

VAGUE_QUESTION = (
    "調査",
    "確認する必要",
    "方法を教",
    "how to obtain",
    "investigate",
)

MEMORY_INTENT = (
    "win32_",
    "memory",
    "physical",
    "visible",
    "free",
    "wmic",
    "os get",
    "operatingsystem",
    "perf",
    "counter",
)


def _norm(text):
    return " ".join(str(text or "").lower().split())


def _script_text(candidate):
    normalized = normalize_candidate(candidate)
    if not normalized:
        return ""
    command = str(normalized.get("command") or "").lower()
    args = list(normalized.get("args") or [])
    if command == "powershell" and len(args) >= 4:
        return _norm(args[3])
    return _norm(" ".join(str(item) for item in args))


def candidate_fingerprint(candidate):
    normalized = normalize_candidate(candidate)
    if not normalized:
        return None
    return (
        str(normalized.get("command") or "").lower(),
        _script_text(normalized),
    )


def rejected_fingerprints(rejected_commands):
    seen = set()
    for item in rejected_commands or []:
        fingerprint = candidate_fingerprint(item)
        if fingerprint and fingerprint[0]:
            seen.add(fingerprint)
    return seen


def normalize_candidates(payload):
    if not isinstance(payload, dict):
        return []
    raw = payload.get("candidates") or []
    result = []
    for item in raw:
        normalized = normalize_candidate(item)
        if normalized:
            result.append(normalized)
    return result


def is_repeat(candidate, rejected_commands):
    fingerprint = candidate_fingerprint(candidate)
    if not fingerprint or not fingerprint[0]:
        return False
    return fingerprint in rejected_fingerprints(rejected_commands)


def is_vague(candidate, *, inventory, missing=None):
    normalized = normalize_candidate(candidate)
    if not normalized:
        return True
    allowed, _errors, _command, args = candidate_is_allowed(normalized, inventory)
    if not allowed:
        return True
    script = _script_text(normalized)
    if len(script) < 24:
        return True
    if not any(token in script for token in MEMORY_INTENT):
        question = _norm(normalized.get("question"))
        if not any(token in script for token in MEMORY_INTENT) and not any(
            token in question for token in MEMORY_INTENT
        ):
            return True
    question = _norm(normalized.get("question"))
    if any(token in question for token in VAGUE_QUESTION) and len(script) < 40:
        return True
    if missing:
        for item in missing:
            text = _norm(item)
            if text and text == question and len(script) < 40:
                return True
    return False


def inspect_research_followup(
    payload,
    error=None,
    *,
    rejected_commands=None,
    inventory=None,
    missing=None,
):
    inventory = inventory or {"available_commands": ["powershell", "wmic"]}
    json_ok = error not in ("timeout", "no_json") and isinstance(payload, dict)
    candidates = normalize_candidates(payload)
    repeats = [item for item in candidates if is_repeat(item, rejected_commands)]
    different = [item for item in candidates if not is_repeat(item, rejected_commands)]
    substantive = [
        item for item in different if not is_vague(item, inventory=inventory, missing=missing)
    ]

    if not json_ok:
        grade = GRADE_FAIL
    elif not candidates:
        grade = GRADE_FAIL
    elif repeats and not different:
        grade = GRADE_C
    elif repeats and substantive:
        grade = GRADE_A
    elif repeats and not substantive:
        grade = GRADE_C
    elif substantive:
        grade = GRADE_A
    elif different:
        grade = GRADE_B
    else:
        grade = GRADE_FAIL

    return {
        "ok": grade == GRADE_A,
        "grade": grade,
        "json_ok": json_ok,
        "candidate_count": len(candidates),
        "repeat_count": len(repeats),
        "different_count": len(different),
        "substantive_count": len(substantive),
        "fingerprints": [candidate_fingerprint(item) for item in candidates],
        "rejected_fingerprints": sorted(rejected_fingerprints(rejected_commands)),
        "error": error,
    }
