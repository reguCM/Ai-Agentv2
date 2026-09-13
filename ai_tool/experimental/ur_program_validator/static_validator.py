"""Static URScript validator — specification-backed, not LLM."""
from __future__ import annotations

import re
from typing import Any

from ai_tool.experimental.ur_program_validator.models import (
    IssueKind,
    ValidationIssue,
    ValidationResult,
    VerificationStatus,
)
from ai_tool.experimental.ur_program_validator.spec_catalog import SpecCatalog
from ai_tool.experimental.ur_program_validator.version_context import VersionContext, function_available

_CALL_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
_PYTHON_LIKE = {"print", "pandas", "read_csv", "import", "def", "len", "range"}
_BUILTIN_ALLOW = {
    "get_actual_joint_positions",
    "get_actual_tcp_pose",
    "get_inverse_kin",
    "pose_trans",
    "p",
}

# Scope: validator does NOT check real-robot safety (explicit boundary)
NOT_VALIDATED = [
    "real_robot_safety",
    "collision_avoidance",
    "physical_io_wiring",
    "tcp_calibration_accuracy",
    "workpiece_grip",
    "actual_cycle_time",
]


def _worst_status(statuses: list[VerificationStatus]) -> VerificationStatus:
    order = {"FAIL": 0, "WARNING": 1, "UNKNOWN": 2, "PASS": 3}
    if not statuses:
        return "PASS"
    return min(statuses, key=lambda s: order[s])


def validate_script(
    script: str,
    catalog: SpecCatalog,
    *,
    version_ctx: VersionContext | None = None,
) -> ValidationResult:
    """Static validation against spec catalog — PASS/FAIL/WARNING/UNKNOWN."""
    ctx = version_ctx or VersionContext(
        robot=catalog.robot,
        polyscope_version=catalog.polyscope_version,
        urscript_version=catalog.urscript_version,
    )
    issues: list[ValidationIssue] = []

    lines = script.splitlines()
    if not any("def " in ln for ln in lines):
        issues.append(
            ValidationIssue(
                IssueKind.SYNTAX,
                "WARNING",
                "No 'def program' observed — URScript programs typically use def/end",
                line=1,
            )
        )

    open_parens = script.count("(") - script.count(")")
    if open_parens != 0:
        issues.append(
            ValidationIssue(
                IssueKind.SYNTAX,
                "FAIL",
                f"Unbalanced parentheses (delta={open_parens})",
                line=0,
            )
        )

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("def "):
            continue
        for m in _CALL_RE.finditer(line):
            fname = m.group(1)
            if fname in catalog.keywords or fname == "def" or fname in _BUILTIN_ALLOW:
                continue

            if fname in _PYTHON_LIKE or fname.startswith("pandas"):
                issues.append(
                    ValidationIssue(
                        IssueKind.PYTHON_CONFUSION,
                        "FAIL",
                        f"'{fname}' looks like Python — not observed in URScript catalog",
                        line=i,
                        function=fname,
                    )
                )
                continue

            spec = catalog.functions.get(fname)
            if not spec:
                issues.append(
                    ValidationIssue(
                        IssueKind.UNKNOWN_FUNCTION,
                        "FAIL",
                        f"Function '{fname}' not in specification catalog for target version",
                        line=i,
                        function=fname,
                    )
                )
                continue

            avail, avail_detail = function_available(spec, ctx)
            if avail == "deprecated":
                issues.append(
                    ValidationIssue(
                        IssueKind.VERSION,
                        "WARNING",
                        f"'{fname}': {avail_detail}",
                        line=i,
                        function=fname,
                    )
                )
            elif avail == "unavailable":
                issues.append(
                    ValidationIssue(
                        IssueKind.VERSION,
                        "FAIL",
                        f"'{fname}': {avail_detail}",
                        line=i,
                        function=fname,
                    )
                )

            args = _count_args(line, line.index("(", m.end() - 1))
            if args < spec.min_args:
                issues.append(
                    ValidationIssue(
                        IssueKind.ARG_COUNT,
                        "FAIL",
                        f"'{fname}' expects at least {spec.min_args} args, got {args}",
                        line=i,
                        function=fname,
                    )
                )
            elif args > spec.max_args:
                issues.append(
                    ValidationIssue(
                        IssueKind.ARG_COUNT,
                        "FAIL",
                        f"'{fname}' expects at most {spec.max_args} args, got {args}",
                        line=i,
                        function=fname,
                    )
                )

            if "True" in line or "False" in line:
                issues.append(
                    ValidationIssue(
                        IssueKind.TYPE,
                        "WARNING",
                        "Python-style boolean may not be valid URScript literal",
                        line=i,
                        function=fname,
                    )
                )

    statuses = [i.status for i in issues]
    overall = _worst_status(statuses) if issues else "PASS"

    return ValidationResult(
        status=overall,
        issues=issues,
        version_context=ctx.to_dict(),
        provenance=catalog.provenance,
        not_validated=list(NOT_VALIDATED),
    )


def _count_args(line: str, open_paren_idx: int) -> int:
    """Count comma-separated args for call starting at open_paren_idx."""
    depth = 0
    start = open_paren_idx + 1
    end = len(line)
    for j in range(start, len(line)):
        c = line[j]
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                end = j
                break
            depth -= 1
    inner = line[start:end].strip()
    if not inner:
        return 0
    commas = 0
    depth = 0
    for c in inner:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "," and depth == 0:
            commas += 1
    return commas + 1


def suggest_fixes(result: ValidationResult, catalog: SpecCatalog) -> list[dict[str, Any]]:
    """Fix suggestions with provenance — not mechanical truth."""
    suggestions: list[dict[str, Any]] = []
    for issue in result.issues:
        if issue.kind == IssueKind.UNKNOWN_FUNCTION and issue.function:
            # Only officially verified if similar name in catalog
            verified = None
            for name in catalog.functions:
                if name.startswith(issue.function[:3]) and name != issue.function:
                    verified = name
                    break
            if verified:
                suggestions.append(
                    {
                        "original": issue.function,
                        "suggestion": verified,
                        "provenance": "officially_verified",
                        "rationale": f"'{verified}' exists in catalog; '{issue.function}' does not",
                    }
                )
            else:
                suggestions.append(
                    {
                        "original": issue.function,
                        "suggestion": "",
                        "provenance": "unknown",
                        "rationale": "No verified alternative in catalog — do not trust LLM guess alone",
                    }
                )
    return suggestions
