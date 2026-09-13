"""
ベンチマーク採点。仕様は docs/scoring.md。
モデルに依存しない。PASS と score は分ける。
"""

from tools.system.tool_builder.implementation_classify import (
    EMPTY_CODE,
    FINDING_NOT_USED,
    OK,
    UNNECESSARY_FINDING,
    WRONG_COMMAND,
)


SCORING_VERSION = "1.0"

CAP_PARTIAL_REQUIREMENT = {"id": "partial_requirement", "limit": 69}
CAP_WRONG_COMMAND = {"id": "wrong_command", "limit": 49}
CAP_EXISTING_BROKEN = {"id": "existing_tool_broken", "limit": 29}
CAP_FABRICATED = {"id": "fabricated_or_dangerous", "limit": 19}

PIPELINE_STAGES = (
    "research",
    "judge",
    "implementation",
    "validation",
    "repair",
)


def grade_for(score):
    if score >= 95:
        return "S"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def apply_caps(raw, caps):
    if not caps:
        return raw
    return min(raw, min(item["limit"] for item in caps))


def pipeline_status(*, implementation="skipped", extra=None):
    status = {stage: "skipped" for stage in PIPELINE_STAGES}
    status["implementation"] = implementation
    if extra:
        status.update(extra)
    return status


def overimplementation_points(extra_count):
    if extra_count <= 0:
        return 10
    if extra_count == 1:
        return 8
    if extra_count <= 3:
        return 6
    return 3


def score_implementation(*, classified, error=None, pipeline=None):
    """
    実装層の機械採点 v1.0。
    classified は classify_implementation の戻り値。
    """
    classified = classified or {}
    kind = classified.get("class")
    extras = list(classified.get("used_other") or [])
    adopted = bool(classified.get("finding_adopted"))
    fetch = bool(classified.get("has_fetch_call"))
    caps = []

    if kind == OK:
        breakdown = {
            "requirement": 40,
            "correctness": 30,
            "integration": 20,
            "overimplementation": 10,
        }
        passed = True
        implementation = "pass"
    elif kind == UNNECESSARY_FINDING:
        breakdown = {
            "requirement": 40,
            "correctness": 30,
            "integration": 20,
            "overimplementation": overimplementation_points(len(extras)),
        }
        passed = True
        implementation = "pass"
    elif kind == FINDING_NOT_USED and fetch:
        breakdown = {
            "requirement": 20,
            "correctness": 0,
            "integration": 20,
            "overimplementation": 10,
        }
        caps.append(CAP_PARTIAL_REQUIREMENT)
        passed = False
        implementation = "fail"
    elif kind == FINDING_NOT_USED:
        breakdown = {
            "requirement": 0,
            "correctness": 0,
            "integration": 20,
            "overimplementation": 10,
        }
        passed = False
        implementation = "fail"
    elif kind == WRONG_COMMAND:
        breakdown = {
            "requirement": 0,
            "correctness": 0,
            "integration": 15,
            "overimplementation": 10,
        }
        caps.append(CAP_WRONG_COMMAND)
        passed = False
        implementation = "fail"
    else:
        breakdown = {
            "requirement": 0,
            "correctness": 0,
            "integration": 0,
            "overimplementation": 10,
        }
        passed = False
        implementation = "fail"

    raw = sum(breakdown.values())
    score = apply_caps(raw, caps)
    return {
        "scoring_version": SCORING_VERSION,
        "score": score,
        "grade": grade_for(score),
        "pass": passed,
        "ok": passed,
        "score_breakdown": breakdown,
        "caps": caps,
        "pipeline": pipeline or pipeline_status(implementation=implementation),
        "implementation_class": kind,
        "error": error,
        "finding_adopted": adopted,
    }
