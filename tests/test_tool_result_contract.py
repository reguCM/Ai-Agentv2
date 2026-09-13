from copy import deepcopy

import pytest

from tools.system.tool_result_contract import (
    normalize_tool_result,
    validate_tool_result_v1,
)


def valid_result(**overrides):
    result = {"ok": True, "status": "success", "error": None, "warnings": []}
    result.update(overrides)
    return result


@pytest.mark.parametrize(
    "result",
    [
        valid_result(),
        valid_result(status="partial", truncated=True),
        valid_result(
            ok=False,
            status="failure",
            error={"code": "tool_failed", "message": "failed"},
        ),
        valid_result(warnings=[{"code": "notice", "message": "notice"}]),
        valid_result(next_offset=None, next_cursor="cursor", resume_token={"id": 1}),
        valid_result(excluded={"total": 2, "reasons": {"policy": 2}}),
        valid_result(skipped={"total": 0, "reasons": {}}),
    ],
)
def test_validator_accepts_valid_results(result):
    assert validate_tool_result_v1(result) == []


@pytest.mark.parametrize("missing", ["ok", "status", "error", "warnings"])
def test_validator_requires_core_fields(missing):
    result = valid_result()
    del result[missing]
    assert f"{missing} is required" in validate_tool_result_v1(result)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ([], "result must be an object"),
        (valid_result(ok=1), "ok must be a boolean"),
        (valid_result(status="unknown"), "status must be one of"),
        (valid_result(ok=False), "status=success requires ok=true"),
        (valid_result(error="legacy"), "status=success requires error=null"),
        (valid_result(status="partial", error={}), "status=partial requires error=null"),
        (valid_result(status="failure", ok=True), "status=failure requires ok=false"),
        (
            valid_result(status="failure", ok=False, error="legacy"),
            "status=failure requires error to be an object",
        ),
        (
            valid_result(status="failure", ok=False, error={"message": "failed"}),
            "error.code must be a non-empty string",
        ),
        (
            valid_result(status="failure", ok=False, error={"code": "failed"}),
            "error.message must be a non-empty string",
        ),
        (valid_result(warnings="warning"), "warnings must be a list"),
        (valid_result(warnings=["warning"]), "warnings[0] must be an object"),
        (
            valid_result(warnings=[{"code": "", "message": "warning"}]),
            "warnings[0].code must be a non-empty string",
        ),
        (
            valid_result(warnings=[{"code": "warning", "message": ""}]),
            "warnings[0].message must be a non-empty string",
        ),
        (valid_result(truncated=1), "truncated must be a boolean"),
        (valid_result(has_more=None), "has_more must be a boolean"),
        (valid_result(next_offset=True), "next_offset must be an integer or null"),
        (valid_result(next_cursor=1), "next_cursor must be a string, object, or null"),
        (valid_result(resume_token=[]), "resume_token must be a string, object, or null"),
        (valid_result(excluded=[]), "excluded must be an object"),
        (valid_result(skipped={"reasons": {}}), "skipped.total is required"),
        (valid_result(skipped={"total": 0}), "skipped.reasons is required"),
        (
            valid_result(excluded={"total": -1, "reasons": {}}),
            "excluded.total must be a non-negative integer",
        ),
        (
            valid_result(excluded={"total": 1, "reasons": {"policy": -1}}),
            "excluded.reasons['policy'] must be a non-negative integer",
        ),
    ],
)
def test_validator_rejects_invalid_results(result, expected):
    assert any(expected in issue for issue in validate_tool_result_v1(result))


def test_validator_reports_multiple_violations():
    issues = validate_tool_result_v1(
        {"ok": "yes", "status": "failure", "error": {}, "warnings": [None]}
    )
    assert len(issues) >= 4


def test_normalizer_legacy_success():
    assert normalize_tool_result({"ok": True, "error": None}) == valid_result()


def test_normalizer_legacy_string_failure():
    result = normalize_tool_result({"ok": False, "error": "disk full"})
    assert result["status"] == "failure"
    assert result["error"] == {"code": "legacy_error", "message": "disk full"}
    assert validate_tool_result_v1(result) == []


def test_normalizer_legacy_truncated_success_is_partial():
    result = normalize_tool_result(
        {"ok": True, "truncated": True, "error": "more results available"}
    )
    assert result["status"] == "partial"
    assert result["error"] is None
    assert result["warnings"][0]["code"] == "legacy_partial"


def test_normalizer_preserves_v1_meaning():
    source = valid_result(data={"value": 1})
    assert normalize_tool_result(source) == source


def test_normalizer_is_non_mutating():
    source = {"ok": False, "error": {"code": "x", "message": "y"}, "data": []}
    before = deepcopy(source)
    normalize_tool_result(source)
    assert source == before


@pytest.mark.parametrize("source", [{}, {"value": 1}, {"status": "mystery"}])
def test_normalizer_ambiguous_result_is_never_success(source):
    result = normalize_tool_result(source)
    assert result["ok"] is False
    assert result["status"] == "failure"
    assert result["error"]["code"] == "ambiguous_legacy_result"
    assert validate_tool_result_v1(result) == []


def test_normalizer_preserves_structured_failure():
    error = {"code": "timeout", "message": "timed out", "retryable": True}
    result = normalize_tool_result({"ok": False, "error": error})
    assert result["error"] == error


def test_normalizer_converts_legacy_warning_strings():
    result = normalize_tool_result({"ok": True, "error": None, "warnings": ["slow"]})
    assert result["warnings"] == [{"code": "legacy_warning", "message": "slow"}]


def test_normalizer_corrects_known_system_summary_partial_semantics():
    result = normalize_tool_result(
        {"ok": False, "status": "partial", "error": None, "sections": {}},
        tool_name="get_system_summary",
    )
    assert result["ok"] is True
    assert result["status"] == "partial"
    assert result["warnings"][0]["code"] == "legacy_partial"
    assert validate_tool_result_v1(result) == []


def test_normalizer_contradictory_success_is_explicit_failure():
    result = normalize_tool_result({"ok": True, "error": "unexpected"})
    assert result["status"] == "failure"
    assert result["error"]["code"] == "ambiguous_legacy_result"


def test_normalizer_rejects_non_object_input():
    with pytest.raises(TypeError):
        normalize_tool_result([])  # type: ignore[arg-type]
