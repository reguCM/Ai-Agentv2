"""Runtime bridge for bounded workspace read_file and LLM transport safety."""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

# General initial read budget for Runtime-owned read_file actions (not read_file defaults).
READ_FILE_INITIAL_LINE_LIMIT = 50
# Keep tool-role payloads under the observed Ollama/Gemma4 cliff (~5k chars).
READ_FILE_LLM_CONTEXT_CHAR_BUDGET = 4000
READ_FILE_MAX_CONTINUATION_PAGES = 64
RUN_TEST_PLAN_STDOUT_TAIL_CHARS = 1500
RUN_TEST_PLAN_STDERR_TAIL_CHARS = 800


def runtime_initial_read_arguments(
    path: str,
    *,
    offset: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Bounded first-page arguments for Runtime capability / bridge actions."""
    arguments: dict[str, Any] = {"path": path}
    if offset is not None:
        arguments["offset"] = int(offset)
    if limit is not None:
        arguments["limit"] = int(limit)
        return arguments
    if offset is None:
        arguments["offset"] = 1
        arguments["limit"] = READ_FILE_INITIAL_LINE_LIMIT
    return arguments


def runtime_continuation_read_arguments(
    path: str,
    *,
    next_offset: int,
    limit: int | None = None,
) -> dict[str, Any]:
    return runtime_initial_read_arguments(
        path,
        offset=int(next_offset),
        limit=limit or READ_FILE_INITIAL_LINE_LIMIT,
    )


def read_file_observation_complete(
    *,
    supported: Mapping[str, str],
    completion_conditions: Iterable[str],
    generic_observation_completes: bool,
    source_result: Mapping[str, Any] | None,
) -> bool:
    """True when the current Task does not need another read_file page."""
    conditions = [str(item) for item in completion_conditions if str(item).strip()]
    if conditions and supported and all(condition in supported for condition in conditions):
        return True
    if conditions == ["relevant evidence observed"] and generic_observation_completes:
        return True
    if isinstance(source_result, Mapping) and not source_result.get("has_more"):
        return True
    return False


def _line_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    lines = result.get("lines")
    if not isinstance(lines, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in lines:
        if isinstance(item, Mapping):
            rows.append(dict(item))
    return rows


def _shrink_read_file_result_for_llm(result: Mapping[str, Any]) -> dict[str, Any]:
    rows = _line_rows(result)
    kept: list[dict[str, Any]] = []
    for row in rows:
        candidate_rows = kept + [row]
        candidate = _partial_read_file_payload(result, candidate_rows, guard_warning=False)
        if len(json.dumps(candidate, ensure_ascii=False, indent=2)) > READ_FILE_LLM_CONTEXT_CHAR_BUDGET:
            break
        kept = candidate_rows
    if not kept and rows:
        first = dict(rows[0])
        text = str(first.get("text") or "")
        first["text"] = text[: max(0, READ_FILE_LLM_CONTEXT_CHAR_BUDGET // 4)]
        kept = [first]
    shrunk = _partial_read_file_payload(result, kept, guard_warning=True)
    return shrunk


def _partial_read_file_payload(
    result: Mapping[str, Any],
    kept_rows: list[dict[str, Any]],
    *,
    guard_warning: bool,
) -> dict[str, Any]:
    shrunk = dict(result)
    start_line = int(result.get("offset") or 1)
    end_line = start_line + len(kept_rows) - 1 if kept_rows else start_line - 1
    total_lines = int(result.get("total_lines") or end_line)
    original_has_more = bool(result.get("has_more"))
    shrunk["lines"] = kept_rows
    shrunk["returned_lines"] = len(kept_rows)
    shrunk["truncated"] = True
    shrunk["has_more"] = original_has_more or end_line < total_lines
    shrunk["next_offset"] = end_line + 1 if shrunk["has_more"] else None
    if guard_warning:
        warnings = list(shrunk.get("warnings") or [])
        warnings.append(
            {
                "code": "llm_context_guard",
                "message": (
                    "Tool Result exceeded LLM transport budget; partial content retained "
                    "with continuation metadata."
                ),
            }
        )
        shrunk["warnings"] = warnings
    return shrunk


def _shrink_run_test_plan_result_for_llm(result: Mapping[str, Any]) -> dict[str, Any]:
    """LLM transport only — full TEST_SAFETY_EXPLICIT_RUN stays in runs/ and Runtime."""
    summary = result.get("test_safety_summary")
    if not isinstance(summary, Mapping):
        summary = {}
    stdout_tail = str(summary.get("stdout_tail") or "")[-RUN_TEST_PLAN_STDOUT_TAIL_CHARS:]
    stderr_tail = str(summary.get("stderr_tail") or "")[-RUN_TEST_PLAN_STDERR_TAIL_CHARS:]
    short_summary = str(
        summary.get("resolution_result")
        or summary.get("closure_reason")
        or result.get("message")
        or ""
    )[:500]
    llm_view: dict[str, Any] = {
        "action_id": summary.get("action_id"),
        "packet_path": summary.get("persisted_run_path"),
        "resolution_result": summary.get("resolution_result"),
        "executor_called": summary.get("executor_called"),
        "test_failed": summary.get("test_failed"),
        "run_closed": summary.get("run_closed"),
        "closure_reason": summary.get("closure_reason"),
        "summary": short_summary,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    if result.get("test_safety_duplicate_suppressed"):
        llm_view["duplicate_suppressed"] = True
    return {
        "ok": result.get("ok"),
        "status": result.get("status"),
        "test_safety_llm_view": llm_view,
    }


def prepare_tool_result_for_llm(tool_name: str, result: Any) -> Any:
    """Safety guard: bounded payloads for read_file and run_test_plan LLM transport."""
    if tool_name == "run_test_plan" and isinstance(result, Mapping):
        return _shrink_run_test_plan_result_for_llm(result)
    if tool_name != "read_file" or not isinstance(result, Mapping):
        return result
    if str(result.get("status") or "") not in {"success", "partial"}:
        return result
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if len(serialized) <= READ_FILE_LLM_CONTEXT_CHAR_BUDGET:
        return result
    return _shrink_read_file_result_for_llm(result)


def read_file_llm_delivery(result: Mapping[str, Any]) -> dict[str, Any]:
    """Continuation metadata aligned with what prepare_tool_result_for_llm() presents."""
    guarded = prepare_tool_result_for_llm("read_file", result)
    rows = _line_rows(guarded if isinstance(guarded, Mapping) else result)
    first_line = int(rows[0].get("line") or 0) if rows else None
    last_line = int(rows[-1].get("line") or 0) if rows else None
    guard_applied = guarded is not result
    payload = guarded if isinstance(guarded, Mapping) else result
    return {
        "presented_line_start": first_line,
        "presented_line_end": last_line,
        "presented_line_count": len(rows),
        "has_more": bool(payload.get("has_more")),
        "next_offset": payload.get("next_offset"),
        "guard_applied": guard_applied,
    }
