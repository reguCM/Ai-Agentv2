"""
実装層の失敗分類。モデルに依存しない。

ok                     要求を満たす finding だけを使っている
finding_not_used       要求を満たす finding を使っていない
unnecessary_finding    正解に加えて不要な finding も使っている
empty_code             code が空
wrong_command          usable_findings にないコマンドを実装している
"""

import re


EMPTY_CODE = "empty_code"
FINDING_NOT_USED = "finding_not_used"
UNNECESSARY_FINDING = "unnecessary_finding"
WRONG_COMMAND = "wrong_command"
OK = "ok"

SKIP_TOKENS = {
    "noprofile",
    "noninteractive",
    "command",
    "select",
    "select-object",
    "get-ciminstance",
    "get-wmiobject",
    "get-counter",
    "ciminstance",
    "expandproperty",
    "property",
    "powershell",
    "powershell.exe",
    "pwsh",
    "wmic",
    "class",
    "classname",
    "subprocess",
    "check_output",
    "run",
}

FETCH_MARKERS = (
    "powershell",
    "pwsh",
    "wmic",
    "subprocess",
    "Get-CimInstance",
    "Get-WmiObject",
    "Get-Counter",
)


def distinctive_fragments(finding):
    evidence = finding.get("evidence") if isinstance(finding, dict) else {}
    if not evidence:
        evidence = finding or {}
    parts = [str(evidence.get("command") or finding.get("command") or "")]
    parts.extend(
        str(arg)
        for arg in (evidence.get("args") or finding.get("args") or [])
    )
    fragments = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\\%.]{5,}", " ".join(parts)):
        lowered = token.lower().strip("\\")
        if lowered in SKIP_TOKENS:
            continue
        if token not in fragments:
            fragments.append(token)
    return fragments


def primary_usable_finding(research_result):
    for item in (research_result or {}).get("usable_findings") or []:
        evidence = item.get("evidence") or {}
        if evidence.get("command") and evidence.get("sample"):
            return item
        if item.get("command") and item.get("sample"):
            return item
    return None


def finding_id(finding):
    fragments = distinctive_fragments(finding)
    return fragments[0] if fragments else ""


def same_finding(left, right):
    return distinctive_fragments(left) == distinctive_fragments(right)


def expected_finding_list(
    *,
    expected_finding=None,
    expected_findings=None,
    research_result=None,
):
    if expected_findings:
        return [item for item in expected_findings if item]
    if expected_finding:
        return [expected_finding]
    primary = primary_usable_finding(research_result)
    return [primary] if primary else []


def used_findings(code, findings):
    matched = []
    for item in findings or []:
        if uses_finding(code, item):
            matched.append(item)
    return matched


def classify_implementation(
    *,
    code=None,
    payload=None,
    error=None,
    research_result=None,
    expected_finding=None,
    expected_findings=None,
):
    payload = payload if isinstance(payload, dict) else {}
    code = str(code if code is not None else payload.get("code") or "")
    findings = list((research_result or {}).get("usable_findings") or [])
    expected = expected_finding_list(
        expected_finding=expected_finding,
        expected_findings=expected_findings,
        research_result=research_result,
    )
    adopted = bool(expected) and all(uses_finding(code, item) for item in expected)
    used = used_findings(code, findings)
    used_other = [
        finding_id(item)
        for item in used
        if not any(same_finding(item, exp) for exp in expected)
    ]
    missing = [finding_id(item) for item in expected if not uses_finding(code, item)]
    fetch = has_fetch_call(code)

    if error in ("timeout", "no_json") and not code.strip():
        kind = EMPTY_CODE
    elif not code.strip():
        kind = EMPTY_CODE
    elif expected and adopted and used_other:
        kind = UNNECESSARY_FINDING
    elif expected and adopted:
        kind = OK
    elif used:
        kind = FINDING_NOT_USED
    elif fetch:
        kind = WRONG_COMMAND
    else:
        kind = FINDING_NOT_USED

    fragments = []
    for item in expected:
        for token in distinctive_fragments(item):
            if token not in fragments:
                fragments.append(token)

    return {
        "class": kind,
        "code_present": bool(code.strip()),
        "finding_adopted": adopted,
        "used_other": used_other,
        "missing": missing,
        "has_fetch_call": fetch,
        "fragments": fragments,
        "unimplemented": payload.get("unimplemented"),
        "error": error,
    }


def fragment_in_code(code, fragment):
    if not code or not fragment:
        return False
    return (
        re.search(
            r"(?<![A-Za-z0-9_])" + re.escape(fragment) + r"(?![A-Za-z0-9_])",
            code,
        )
        is not None
    )


def uses_finding(code, finding):
    if not code or not finding:
        return False
    fragments = distinctive_fragments(finding)
    if not fragments:
        return False
    return all(fragment_in_code(code, fragment) for fragment in fragments)


def has_fetch_call(code):
    if not code:
        return False
    lowered = code.lower()
    return any(marker.lower() in lowered for marker in FETCH_MARKERS)
