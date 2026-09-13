"""Tool Result Contract v1 validation and legacy normalization.

The validator is intentionally strict for new producers.  The normalizer is a
tolerant, non-mutating boundary adapter for results emitted by legacy tools.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


TOOL_RESULT_STATUSES = frozenset({"success", "partial", "failure"})


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_count_summary(
    name: str, value: object, issues: list[str]
) -> None:
    if not isinstance(value, Mapping):
        issues.append(f"{name} must be an object")
        return

    if "total" not in value:
        issues.append(f"{name}.total is required")
    else:
        total = value["total"]
        if type(total) is not int or total < 0:
            issues.append(f"{name}.total must be a non-negative integer")

    if "reasons" not in value:
        issues.append(f"{name}.reasons is required")
    elif not isinstance(value["reasons"], Mapping):
        issues.append(f"{name}.reasons must be an object")
    else:
        for reason, count in value["reasons"].items():
            if not _is_nonempty_string(reason):
                issues.append(f"{name}.reasons keys must be non-empty strings")
            if type(count) is not int or count < 0:
                issues.append(
                    f"{name}.reasons[{reason!r}] must be a non-negative integer"
                )


def validate_tool_result_v1(result: object) -> list[str]:
    """Return every detected Tool Result Contract v1 violation.

    An empty list means the value is valid.  The function does not mutate the
    input and deliberately rejects legacy string errors.
    """

    if not isinstance(result, Mapping):
        return ["result must be an object"]

    issues: list[str] = []
    for field in ("ok", "status", "error", "warnings"):
        if field not in result:
            issues.append(f"{field} is required")

    ok = result.get("ok")
    status = result.get("status")
    error = result.get("error")
    warnings = result.get("warnings")

    if "ok" in result and type(ok) is not bool:
        issues.append("ok must be a boolean")

    valid_status = isinstance(status, str) and status in TOOL_RESULT_STATUSES
    if "status" in result and not valid_status:
        issues.append("status must be one of: success, partial, failure")

    if "warnings" in result:
        if not isinstance(warnings, list):
            issues.append("warnings must be a list")
        else:
            for index, warning in enumerate(warnings):
                if not isinstance(warning, Mapping):
                    issues.append(f"warnings[{index}] must be an object")
                    continue
                if not _is_nonempty_string(warning.get("code")):
                    issues.append(f"warnings[{index}].code must be a non-empty string")
                if not _is_nonempty_string(warning.get("message")):
                    issues.append(
                        f"warnings[{index}].message must be a non-empty string"
                    )

    if valid_status:
        if status in {"success", "partial"}:
            if ok is not True:
                issues.append(f"status={status} requires ok=true")
            if error is not None:
                issues.append(f"status={status} requires error=null")
        else:
            if ok is not False:
                issues.append("status=failure requires ok=false")
            if not isinstance(error, Mapping):
                issues.append("status=failure requires error to be an object")
            else:
                if not _is_nonempty_string(error.get("code")):
                    issues.append("error.code must be a non-empty string")
                if not _is_nonempty_string(error.get("message")):
                    issues.append("error.message must be a non-empty string")

    for field in ("truncated", "has_more"):
        if field in result and type(result[field]) is not bool:
            issues.append(f"{field} must be a boolean")

    if "next_offset" in result:
        value = result["next_offset"]
        if value is not None and type(value) is not int:
            issues.append("next_offset must be an integer or null")

    for field in ("next_cursor", "resume_token"):
        if field in result:
            value = result[field]
            if value is not None and not isinstance(value, (str, Mapping)):
                issues.append(f"{field} must be a string, object, or null")

    for field in ("excluded", "skipped"):
        if field in result:
            _validate_count_summary(field, result[field], issues)

    return issues


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _normalize_warnings(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[dict[str, Any]] = []
    for item in items:
        if (
            isinstance(item, Mapping)
            and _is_nonempty_string(item.get("code"))
            and _is_nonempty_string(item.get("message"))
        ):
            normalized.append(deepcopy(dict(item)))
        elif _is_nonempty_string(item):
            normalized.append(_warning("legacy_warning", item.strip()))
        else:
            normalized.append(
                _warning("legacy_warning", "Legacy warning had no usable message")
            )
    return normalized


def _structured_error(value: object) -> dict[str, Any]:
    if (
        isinstance(value, Mapping)
        and _is_nonempty_string(value.get("code"))
        and _is_nonempty_string(value.get("message"))
    ):
        return deepcopy(dict(value))
    if _is_nonempty_string(value):
        return {"code": "legacy_error", "message": value.strip()}
    return {
        "code": "legacy_failure",
        "message": "Legacy Tool Result reported failure without a usable error",
    }


def _ambiguous_error(reason: str) -> dict[str, str]:
    return {"code": "ambiguous_legacy_result", "message": reason}


def normalize_tool_result(
    result: Mapping[str, Any], *, tool_name: str | None = None
) -> dict[str, Any]:
    """Convert a legacy result to a strict v1 result without mutating it.

    Unknown or contradictory legacy signals become an explicit failure; they
    are never silently interpreted as success.  ``tool_name`` is only used for
    narrowly documented legacy semantics, not broad per-tool inference.
    """

    if not isinstance(result, Mapping):
        raise TypeError("result must be an object")

    output: dict[str, Any] = deepcopy(dict(result))
    if not validate_tool_result_v1(output):
        return output

    warnings = _normalize_warnings(output.get("warnings"))
    raw_ok = output.get("ok")
    has_ok = "ok" in output and type(raw_ok) is bool
    raw_status = output.get("status")
    status_aliases = {
        "success": "success",
        "ok": "success",
        "partial": "partial",
        "failure": "failure",
        "failed": "failure",
        "error": "failure",
        "unavailable": "failure",
    }
    mapped_status = (
        status_aliases.get(raw_status.lower()) if isinstance(raw_status, str) else None
    )
    raw_error = output.get("error")

    # get_system_summary historically used ok=false for a usable partial result.
    if tool_name == "get_system_summary" and mapped_status == "partial":
        output.update(ok=True, status="partial", error=None)
        warnings.append(
            _warning(
                "legacy_partial",
                "Legacy get_system_summary partial result used ok=false",
            )
        )
    elif has_ok and raw_ok is False:
        output.update(ok=False, status="failure", error=_structured_error(raw_error))
    elif has_ok and raw_ok is True:
        if raw_error is None and mapped_status in (None, "success", "partial"):
            output.update(ok=True, status=mapped_status or "success", error=None)
        elif raw_error is not None and output.get("truncated") is True:
            message = (
                raw_error.strip()
                if _is_nonempty_string(raw_error)
                else "Legacy partial result included error details"
            )
            warnings.append(_warning("legacy_partial", message))
            output.update(ok=True, status="partial", error=None)
        else:
            output.update(
                ok=False,
                status="failure",
                error=_ambiguous_error(
                    "Legacy result contained contradictory success and error signals"
                ),
            )
    elif mapped_status == "failure" or (mapped_status is None and raw_error is not None):
        output.update(ok=False, status="failure", error=_structured_error(raw_error))
    elif mapped_status in {"success", "partial"} and raw_error is None:
        output.update(ok=True, status=mapped_status, error=None)
    else:
        output.update(
            ok=False,
            status="failure",
            error=_ambiguous_error(
                "Legacy result did not contain an unambiguous outcome"
            ),
        )

    output["warnings"] = warnings
    return output


__all__ = [
    "TOOL_RESULT_STATUSES",
    "normalize_tool_result",
    "validate_tool_result_v1",
]
