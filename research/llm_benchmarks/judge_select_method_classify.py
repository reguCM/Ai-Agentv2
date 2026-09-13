"""
複数候補から正しい取得方法を選べるかの機械検査。LLM は呼ばない。

Judge の satisfies_request=true + proposed_decisions から、
要求を満たす候補（A/B）だけを採用し、
満たさない候補（C/D/E）を含めていないかを見る。
"""

from tools.ai.tool_builder.research_judge import normalize_judgment


GRADE_CORRECT = "CORRECT"
GRADE_OVER_ACCEPT = "OVER_ACCEPT"
GRADE_WRONG_REJECT = "WRONG_REJECT"
GRADE_FAIL = "FAIL"


def _norm(text):
    return str(text or "").strip().lower()


def finding_labels(research_result):
    labels = {}
    for item in (research_result or {}).get("usable_findings") or []:
        label = item.get("_test_label")
        if label:
            labels[label] = item
    return labels


def sample_fingerprint(finding):
    evidence = finding.get("evidence") or finding
    sample = evidence.get("sample") or []
    command = str(evidence.get("command") or "").lower()
    args = " ".join(str(arg) for arg in (evidence.get("args") or []))
    return (command, _norm(args), tuple(str(item) for item in sample))


def match_finding_to_label(reason, decisions, findings_by_label):
    import re

    mentions = {}
    haystack = _norm(reason)
    for label, finding in findings_by_label.items():
        evidence = finding.get("evidence") or finding
        sample = evidence.get("sample") or []
        args = " ".join(str(arg) for arg in (evidence.get("args") or []))
        for token in sample:
            tok = _norm(token)
            if not tok or len(tok) < 3:
                continue
            pattern = r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])"
            if re.search(pattern, haystack):
                mentions[label] = mentions.get(label, 0) + 1
        for fragment in _extract_distinctive(args):
            if _norm(fragment) in haystack:
                mentions[label] = mentions.get(label, 0) + 1
    return mentions


def _extract_distinctive(args_text):
    import re

    fragments = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{8,}", args_text):
        low = token.lower()
        if low not in (
            "noprofile",
            "noninteractive",
            "command",
            "powershell",
            "select",
        ):
            fragments.append(token)
    return fragments


def inspect_judge_select_method(
    payload,
    error=None,
    *,
    case=None,
):
    case = case or {}
    candidates = case.get("candidates") or {}
    research = case.get("research_result") or {}
    labels = finding_labels(research)

    judgment = normalize_judgment(payload)
    json_ok = error not in ("timeout", "no_json") and isinstance(payload, dict)
    accepted = bool(judgment.get("satisfies_request"))
    reason = judgment.get("reason") or ""
    missing = list(judgment.get("missing") or [])
    decisions = judgment.get("proposed_decisions") or []

    should_accept = {
        label
        for label, meta in candidates.items()
        if meta.get("satisfies")
    }
    should_reject = {
        label
        for label, meta in candidates.items()
        if not meta.get("satisfies")
    }

    mentions = match_finding_to_label(reason, decisions, labels)
    accepted_labels = set()
    rejected_labels = set()
    for label in labels:
        if label in mentions and accepted:
            accepted_labels.add(label)
        elif label not in mentions and not accepted:
            rejected_labels.add(label)

    over_accepted = accepted_labels & should_reject

    if not json_ok:
        grade = GRADE_FAIL
    elif not accepted:
        if should_accept:
            grade = GRADE_WRONG_REJECT
        else:
            grade = GRADE_CORRECT
    elif over_accepted:
        grade = GRADE_OVER_ACCEPT
    else:
        grade = GRADE_CORRECT

    correct_accept = bool(accepted and not over_accepted)
    no_wrong = not bool(over_accepted)

    return {
        "ok": grade == GRADE_CORRECT,
        "grade": grade,
        "json_ok": json_ok,
        "accepted": accepted,
        "correct_accept": correct_accept,
        "no_wrong_accept": no_wrong,
        "reason": reason,
        "missing": missing,
        "decisions": decisions,
        "mentions": mentions,
        "accepted_labels": sorted(accepted_labels),
        "rejected_labels": sorted(rejected_labels),
        "should_accept": sorted(should_accept),
        "should_reject": sorted(should_reject),
        "error": error,
    }
