"""
Proposal 生成の機械検査。LLM は呼ばない。

LLM が返した proposal が、Implementation に必要な
module/function/category/output を持っているかを検査する。
"""

import re


GRADE_COMPLETE = "COMPLETE"
GRADE_INCOMPLETE = "INCOMPLETE"
GRADE_FAIL = "FAIL"

REQUIRED_KEYS = ("name", "category", "module", "function", "output")


def inspect_proposal(payload, error=None, *, case=None):
    case = case or {}
    expected = case.get("expected") or {}

    if error in ("timeout", "no_json") or not isinstance(payload, dict):
        return _fail(error or "no_json")

    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        return _fail("no_proposals")

    proposal = proposals[0]
    checks = {}
    missing_keys = []

    for key in REQUIRED_KEYS:
        val = proposal.get(key)
        present = bool(val) if isinstance(val, str) else bool(val)
        checks[key] = present
        if not present:
            missing_keys.append(key)

    if expected.get("category"):
        checks["category_match"] = (
            str(proposal.get("category") or "").lower()
            == expected["category"].lower()
        )
    if expected.get("subcategory_contains"):
        checks["subcategory_match"] = (
            expected["subcategory_contains"].lower()
            in str(proposal.get("subcategory") or "").lower()
        )
    if expected.get("module_pattern"):
        mod = str(proposal.get("module") or "")
        checks["module_pattern"] = bool(
            re.match(expected["module_pattern"], mod)
        )
    if expected.get("output_includes"):
        output = proposal.get("output") or []
        checks["output_includes"] = expected["output_includes"] in output
    if expected.get("function_present"):
        checks["function_present"] = bool(
            str(proposal.get("function") or "").strip()
        )
    if expected.get("name_present"):
        checks["name_present"] = bool(
            str(proposal.get("name") or "").strip()
        )

    all_ok = not missing_keys and all(checks.values())
    grade = GRADE_COMPLETE if all_ok else GRADE_INCOMPLETE

    return {
        "ok": all_ok,
        "grade": grade,
        "checks": checks,
        "missing_keys": missing_keys,
        "proposal_name": proposal.get("name"),
        "module": proposal.get("module"),
        "function": proposal.get("function"),
        "category": proposal.get("category"),
        "subcategory": proposal.get("subcategory"),
        "output": proposal.get("output"),
        "error": error,
    }


def _fail(error):
    return {
        "ok": False,
        "grade": GRADE_FAIL,
        "checks": {},
        "missing_keys": list(REQUIRED_KEYS),
        "proposal_name": None,
        "module": None,
        "function": None,
        "category": None,
        "subcategory": None,
        "output": None,
        "error": error,
    }
