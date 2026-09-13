"""
調査ラウンド後の機械的な停止判定。

LLM は要求を満たすかと missing を出す。
進展があるか・止めるかはモデルに依存しない。
"""

IMPLEMENT = "implement"
CONTINUE = "continue"
STOP = "stop"

REASON_FINDINGS_COMPLETE = "findings_complete"
REASON_MISSING_RESOLVED = "missing_resolved"
REASON_NEW_INFORMATION = "new_information"
REASON_NO_PROGRESS = "no_progress"
REASON_STAGNATION = "stagnation"
REASON_MAX_ROUNDS = "max_research_rounds"


def finding_keys(findings):
    from tools.ai.tool_builder.research_result import command_key

    keys = []
    for item in findings or []:
        key = command_key(item)
        if key and key[0]:
            keys.append(key)
    return keys


def normalize_missing(missing):
    return tuple(
        sorted({str(item).strip() for item in (missing or []) if str(item).strip()})
    )


def evaluate_research_progress(
    *,
    satisfies_request,
    missing,
    previous_missing,
    round_finding_keys,
    seen_keys,
    stagnation,
    round_num,
    max_rounds=10,
    max_stagnation=3,
):
    missing_now = normalize_missing(missing)
    missing_before = (
        None if previous_missing is None else normalize_missing(previous_missing)
    )
    seen_keys = set(seen_keys or [])
    round_finding_keys = [key for key in (round_finding_keys or []) if key and key[0]]
    new_keys = [key for key in round_finding_keys if key not in seen_keys]
    has_new_finding = bool(new_keys)
    missing_same = missing_before is not None and missing_now == missing_before
    missing_resolved = (
        missing_before is not None and bool(missing_before) and not missing_now
    )
    duplicate_only = bool(round_finding_keys) and not has_new_finding
    no_finding = not round_finding_keys

    if satisfies_request:
        return _decision(
            IMPLEMENT,
            REASON_FINDINGS_COMPLETE,
            stagnation=0,
            has_new_finding=has_new_finding,
            new_keys=new_keys,
            missing_same=missing_same,
            duplicate_only=duplicate_only,
        )
    if missing_resolved:
        return _decision(
            IMPLEMENT,
            REASON_MISSING_RESOLVED,
            stagnation=0,
            has_new_finding=has_new_finding,
            new_keys=new_keys,
            missing_same=False,
            duplicate_only=duplicate_only,
        )

    progress = has_new_finding or (
        missing_before is not None and not missing_same
    )
    next_stagnation = 0 if progress else stagnation + 1

    if not progress:
        if next_stagnation >= max_stagnation:
            return _decision(
                STOP,
                REASON_STAGNATION,
                stagnation=next_stagnation,
                has_new_finding=False,
                new_keys=[],
                missing_same=missing_same or missing_before is None,
                duplicate_only=duplicate_only or no_finding,
            )
        if round_num >= max_rounds:
            return _decision(
                STOP,
                REASON_MAX_ROUNDS,
                stagnation=next_stagnation,
                has_new_finding=False,
                new_keys=[],
                missing_same=missing_same,
                duplicate_only=duplicate_only or no_finding,
            )
        return _decision(
            CONTINUE,
            REASON_NO_PROGRESS,
            stagnation=next_stagnation,
            has_new_finding=False,
            new_keys=[],
            missing_same=missing_same or missing_before is None,
            duplicate_only=duplicate_only or no_finding,
        )

    if round_num >= max_rounds:
        return _decision(
            STOP,
            REASON_MAX_ROUNDS,
            stagnation=0,
            has_new_finding=has_new_finding,
            new_keys=new_keys,
            missing_same=missing_same,
            duplicate_only=duplicate_only,
        )
    return _decision(
        CONTINUE,
        REASON_NEW_INFORMATION,
        stagnation=0,
        has_new_finding=has_new_finding,
        new_keys=new_keys,
        missing_same=missing_same,
        duplicate_only=False,
    )


def _decision(
    action,
    reason,
    *,
    stagnation,
    has_new_finding,
    new_keys,
    missing_same,
    duplicate_only,
):
    return {
        "action": action,
        "reason": reason,
        "stagnation": stagnation,
        "has_new_finding": has_new_finding,
        "new_keys": new_keys,
        "missing_same": missing_same,
        "duplicate_only": duplicate_only,
    }
