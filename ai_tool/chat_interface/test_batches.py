"""In-process background jobs for the Chat UI small test panel."""
from __future__ import annotations

from threading import Lock, Thread
from typing import Any, Callable, Mapping
import uuid

from ai_tool.agent_test_runner import get_test_case, load_test_cases, run_batch
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.activity_status import snapshot_activity


_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = Lock()


def public_cases() -> list[dict[str, Any]]:
    return [
        {"test_case_id": row["test_case_id"], "name": row.get("name")}
        for row in load_test_cases()
    ]


def _default_execute(model: str | None) -> Callable[[dict[str, Any], str], Mapping[str, Any]]:
    def execute(test_case: dict[str, Any], run_id: str) -> Mapping[str, Any]:
        session = empty_session(f"test-{run_id}")
        diagnostics = {
            "provider_reachable": "UNKNOWN",
            "provider_ready": "UNKNOWN",
            "model_busy": "UNKNOWN",
            "model_selection_started": True,
            "requested_model": model,
            "model_selected": None,
            "model_available": "UNKNOWN",
            "preflight_started": "UNKNOWN",
            "preflight_failed": "UNKNOWN",
            "exception_type": None,
            "exception_message": None,
        }
        try:
            result = dict(
                run_chat_turn(
                    session,
                    str(test_case["prompt"]),
                    model=model,
                    local_review_enabled=True,
                )
            )
        except Exception as exc:  # preserve pre-Agent failure evidence for the recorder
            selected = str(session.get("model") or "").strip() or None
            sandbox_failure = "Dedicated Sandbox bootstrap failed" in str(exc)
            diagnostics.update(
                {
                    "model_selected": selected,
                    "preflight_started": True if sandbox_failure else "UNKNOWN",
                    "preflight_failed": True if sandbox_failure else "UNKNOWN",
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                }
            )
            return {
                "is_error": True,
                "error": f"{type(exc).__name__}: {exc}",
                "answer": "",
                "model": selected,
                "execution_diagnostics": diagnostics,
            }
        diagnostics["model_selected"] = str(
            result.get("model") or session.get("model") or ""
        ).strip() or None
        runtime = result.get("task_runtime") or {}
        lifecycle = result.get("final_llm_lifecycle") or {}
        sandbox_started = bool(runtime.get("sandbox_session"))
        response_received = bool(lifecycle.get("final_llm_response_received"))
        diagnostics.update(
            {
                "provider_reachable": True if response_received else "UNKNOWN",
                "provider_ready": True if response_received else "UNKNOWN",
                "model_available": True if response_received else "UNKNOWN",
                "preflight_started": sandbox_started,
                "preflight_failed": False if sandbox_started else "UNKNOWN",
            }
        )
        result.setdefault("model", diagnostics["model_selected"])
        result.setdefault("execution_diagnostics", diagnostics)
        return result

    return execute


def start_batch_job(
    test_case_id: str | None,
    runs: int,
    *,
    model: str | None = None,
    prompt: str | None = None,
    execute: Callable[[dict[str, Any], str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if prompt is not None:
        text = prompt.strip()
        if not text:
            raise ValueError("test prompt must not be empty")
        test_case = {
            "test_case_id": f"ADHOC-{uuid.uuid4().hex[:10]}",
            "name": "Current User Message",
            "prompt": text,
            "expected": {"tool_required": True},
        }
    else:
        test_case = get_test_case(str(test_case_id or ""))
    resolved_case_id = str(test_case["test_case_id"])
    if runs not in {1, 5, 10}:
        raise ValueError("runs must be one of 1, 5, or 10")
    with _LOCK:
        if any(row.get("status") == "running" for row in _JOBS.values()):
            raise RuntimeError("a test batch is already running")
        job_id = f"tj-{uuid.uuid4().hex[:10]}"
        job = {
            "job_id": job_id,
            "test_case_id": resolved_case_id,
            "runs": runs,
            "model": model,
            "status": "running",
            "current": 0,
            "total": runs,
            "current_run_id": None,
            "run_statuses": [],
            "result": None,
            "error": None,
        }
        _JOBS[job_id] = job

    def update(event: dict[str, Any]) -> None:
        with _LOCK:
            row = _JOBS[job_id]
            row["current"] = event["current"]
            row["current_run_id"] = event["run_id"]
            if event["status"] != "running":
                row["run_statuses"].append(
                    {
                        "index": event["current"],
                        "run_id": event["run_id"],
                        "status": event["status"],
                    }
                )

    def worker() -> None:
        try:
            result = run_batch(
                test_case,
                runs,
                execute or _default_execute(model),
                progress=update,
            )
            with _LOCK:
                _JOBS[job_id]["status"] = "completed"
                _JOBS[job_id]["result"] = result
        except Exception as exc:  # infrastructure failure, not an individual run
            with _LOCK:
                _JOBS[job_id]["status"] = "failed"
                _JOBS[job_id]["error"] = f"{type(exc).__name__}: {exc}"

    Thread(target=worker, name=f"agent-test-{job_id}", daemon=True).start()
    return dict(job)


def batch_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        row = _JOBS.get(job_id)
        result = dict(row) if row else None
    if result and result.get("current_run_id"):
        result["current_activity"] = snapshot_activity(
            f"test-{result['current_run_id']}"
        )
    return result


def reset_jobs_for_test() -> None:
    with _LOCK:
        _JOBS.clear()


__all__ = ["batch_job", "public_cases", "reset_jobs_for_test", "start_batch_job"]
