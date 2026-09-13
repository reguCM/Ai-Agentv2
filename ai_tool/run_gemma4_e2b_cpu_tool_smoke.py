#!/usr/bin/env python3
"""CPU Tool Calling smoke for gemma4:e2b via Production run_chat_turn (read-only)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import ollama_available
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session, save_session
from tools.system.llm import chat as ollama_chat

MODEL = "gemma4:e2b"
EXECUTION_PROFILE = "fast_tool"

CASES = [
    {
        "id": "case1_list_files",
        "prompt": "作業フォルダのファイル一覧を確認して",
        "expect_tools": ["list_files"],
        "allow_prefix": True,
    },
    {
        "id": "case2_read_project_spec",
        "prompt": "PROJECT_SPEC.mdを読んで最初の目的を要約して",
        "expect_tools": ["read_file"],
        "allow_prefix": True,
    },
    {
        "id": "case3_missing_file_recovery",
        "prompt": "local_state/_cpu_smoke_missing_probe/this_file_does_not_exist.md を read_file で読んで要約して",
        "expect_tools": ["read_file"],
        "allow_prefix": False,
    },
]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ollama_ps() -> str:
    proc = subprocess.run(
        ["ollama", "ps"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return (proc.stdout or proc.stderr or "").strip()


def _nvidia_smi() -> str | None:
    if not shutil_which("nvidia-smi"):
        return None
    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "").strip() or None
    return (proc.stdout or "").strip()


def shutil_which(cmd: str) -> bool:
    from shutil import which

    return which(cmd) is not None


def build_cpu_chat_fn(recorder: list[dict[str, Any]]) -> Callable[..., Any]:
    def _chat(**kwargs: Any) -> Any:
        payload = dict(kwargs)
        payload["model"] = MODEL
        payload["execution_profile"] = EXECUTION_PROFILE
        payload["think"] = False
        options = dict(payload.get("options") or {})
        options["num_gpu"] = 0
        payload["options"] = options
        started = time.perf_counter()
        response = ollama_chat(**payload)
        elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))
        message = getattr(response, "message", None)
        content = str(getattr(message, "content", None) or "")
        thinking = str(getattr(message, "thinking", None) or "")
        tool_calls = getattr(message, "tool_calls", None) or []
        dumped: dict[str, Any] = {}
        if hasattr(response, "model_dump"):
            dumped = response.model_dump()
        recorder.append(
            {
                "elapsed_ms": elapsed_ms,
                "execution_profile": EXECUTION_PROFILE,
                "think": False,
                "num_gpu": 0,
                "tool_calls_returned": len(tool_calls),
                "content_length": len(content),
                "thinking_length": len(thinking),
                "empty_response": not content.strip(),
                "eval_count": dumped.get("eval_count"),
                "prompt_eval_count": dumped.get("prompt_eval_count"),
                "done_reason": dumped.get("done_reason"),
                "native_tool_names": [
                    getattr(getattr(tc, "function", None), "name", None) for tc in tool_calls
                ],
            }
        )
        return response

    return _chat


def _retry_count(events: list[dict[str, Any]]) -> int:
    keys = (
        "followup_conversion_retry",
        "empty_response_retry",
        "llm_retry",
        "recovery",
    )
    return sum(1 for item in events if str(item.get("type") or "") in keys)


def _goal_status(task_runtime: dict[str, Any] | None) -> str:
    if not task_runtime:
        return "NOT_OBSERVED"
    goals = task_runtime.get("goals") or []
    for row in goals:
        if str(row.get("goal_id") or "") == "G1":
            return str(row.get("status") or "unknown")
    if goals:
        return str(goals[0].get("status") or "unknown")
    return "NOT_OBSERVED"


def _tool_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in result.get("tools") or []:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _analyze_case(case: dict[str, Any], result: dict[str, Any], llm_records: list[dict[str, Any]]) -> dict[str, Any]:
    tools = _tool_rows(result)
    tool_names = [str(item.get("name") or "") for item in tools]
    tool_sequence = tool_names
    events = [dict(item) for item in (result.get("events") or []) if isinstance(item, dict)]
    timing = dict(result.get("timing_breakdown") or {})
    lifecycle = dict(result.get("final_llm_lifecycle") or {})
    report = dict(result.get("runtime_status_report") or {})

    tool_details = []
    for item in tools:
        args = item.get("arguments") or {}
        status = str(item.get("status") or "")
        ok = status == "success" or item.get("ok") is True
        tool_details.append(
            {
                "name": item.get("name"),
                "arguments": args,
                "status": status,
                "ok": ok,
                "argument_valid": isinstance(args, dict) and bool(args) if item.get("name") in {"list_files", "read_file"} else True,
            }
        )

    expect = case.get("expect_tools") or []
    if case.get("allow_prefix"):
        tool_match = any(name in tool_names for name in expect)
    else:
        tool_match = tool_names == expect or (expect and expect[0] in tool_names)

    recovery_observed = any(
        item.get("type")
        in {
            "recovery",
            "gap_resolution_routed",
            "incomplete_goal_guard",
            "execution_end_status",
            "tool",
        }
        for item in events
    )
    failure_not_success = True
    for item in tool_details:
        if item["name"] == "read_file" and case["id"] == "case3_missing_file_recovery":
            failure_not_success = not item["ok"]

    eval_total = sum(int(row.get("eval_count") or 0) for row in llm_records)
    thinking_total = sum(int(row.get("thinking_length") or 0) for row in llm_records)

    judgment = "PASS"
    notes: list[str] = []
    if not tool_match and case["id"] != "case3_missing_file_recovery":
        judgment = "PARTIAL_PASS"
        notes.append(f"expected tool subset {expect}, got {tool_sequence}")
    if case["id"] == "case1_list_files" and "list_files" not in tool_names:
        judgment = "FAIL"
    if case["id"] == "case2_read_project_spec" and "read_file" not in tool_names:
        judgment = "FAIL"
    if case["id"] == "case3_missing_file_recovery":
        if "read_file" not in tool_names:
            judgment = "FAIL"
            notes.append("read_file not called")
        elif failure_not_success and recovery_observed:
            judgment = "PASS"
        elif failure_not_success:
            judgment = "PARTIAL_PASS"
            notes.append("failure observed but recovery path weak")
        else:
            judgment = "FAIL"
            notes.append("missing file treated as success")

    return {
        "case_id": case["id"],
        "prompt": case["prompt"],
        "judgment": judgment,
        "notes": notes,
        "total_duration_ms": timing.get("total_turn_ms"),
        "llm_call_count": len(llm_records),
        "tool_call_count": len(tool_names),
        "tool_sequence": tool_sequence,
        "tool_details": tool_details,
        "success": result.get("error") is None and not result.get("is_error"),
        "error": result.get("error"),
        "empty_response": bool(lifecycle.get("final_llm_response_empty")),
        "retry_count": _retry_count(events),
        "eval_count_total": eval_total,
        "thinking_length_total": thinking_total,
        "final_goal_status": _goal_status(result.get("task_runtime")),
        "stop_reason": (result.get("runtime_status_report") or {}).get("reason_code"),
        "recovery_observed": recovery_observed,
        "runtime_status_report": report,
        "llm_records": llm_records,
        "answer_excerpt": str(result.get("answer") or "")[:400],
    }


def main() -> int:
    run_id = _utc_stamp() + "_gemma4_e2b_cpu_tool_smoke"
    run_dir = _REPO / "logs" / "_cpu_tool_smoke" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    live, live_err = ollama_available()
    summary: dict[str, Any] = {
        "run_id": run_id,
        "model": MODEL,
        "execution_profile": EXECUTION_PROFILE,
        "think": False,
        "num_gpu": 0,
        "ollama_available": live,
        "ollama_error": live_err,
        "ollama_ps_before": _ollama_ps(),
        "nvidia_smi_before": _nvidia_smi(),
        "cases": [],
    }

    if not live:
        summary["status"] = "SKIP"
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    list_proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15, check=False)
    if MODEL not in (list_proc.stdout or ""):
        summary["status"] = "SKIP"
        summary["model_missing"] = MODEL
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    for index, case in enumerate(CASES, 1):
        llm_records: list[dict[str, Any]] = []
        chat_fn = build_cpu_chat_fn(llm_records)
        session = empty_session(f"cpu-smoke-{case['id']}-{run_id}")
        save_session(session)
        started = time.perf_counter()
        try:
            result = run_chat_turn(session, case["prompt"], chat_fn=chat_fn, model=MODEL)
        except Exception as exc:  # noqa: BLE001
            result = {
                "error": f"{type(exc).__name__}: {exc}",
                "events": [],
                "tools": [],
                "timing_breakdown": {"total_turn_ms": max(0, round((time.perf_counter() - started) * 1000))},
            }
        if result.get("timing_breakdown") is None:
            result["timing_breakdown"] = {
                "total_turn_ms": max(0, round((time.perf_counter() - started) * 1000))
            }
        analyzed = _analyze_case(case, result, llm_records)
        analyzed["wall_ms"] = max(0, round((time.perf_counter() - started) * 1000))
        summary["cases"].append(analyzed)
        (run_dir / f"{case['id']}.json").write_text(
            json.dumps({"result": {k: v for k, v in result.items() if k != "events"}, "analysis": analyzed}, ensure_ascii=False, indent=2, default=str)
            + "\n",
            encoding="utf-8",
        )

    summary["ollama_ps_after"] = _ollama_ps()
    summary["nvidia_smi_after"] = _nvidia_smi()
    summary["status"] = "DONE"
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
