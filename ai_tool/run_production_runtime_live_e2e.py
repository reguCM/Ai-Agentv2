#!/usr/bin/env python3
"""Small Production Runtime live-LLM E2E (Phase 0-5 + Decision Change).

Observes naturally selected paths through run_chat_turn with real Ollama.
Tool read failure/success for probe.txt is controlled via wrapper only.
"""
from __future__ import annotations

import json
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
from tools.system.config import get_llm_profile

PROBE_REL_DIR = "local_state/_production_runtime_live_e2e_probe"
PROBE_REL = f"{PROBE_REL_DIR}/probe.txt"
PROBE_LINE = "PROBE-LIVE-RUNTIME-LINE1"
MAX_TURNS = 8
BUDGET_SECONDS = 600.0

LIVE_REQUEST = (
    f"{PROBE_REL} の先頭1行を read_file で確認して報告する。\n"
    "報告形式は次の2通りがともに妥当ですが、どちらを採用するか未決です。\n"
    "A: 原文をそのまま報告する\n"
    "B: VALUE=先頭1行 の形式で報告する\n"
    "事実確認後、既存仕様から一意に決められない場合のみ確認する。"
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _event_types(result: dict[str, Any]) -> list[str]:
    return [str(item.get("type") or "") for item in (result.get("events") or [])]


def _collect_path_observations(result: dict[str, Any]) -> dict[str, Any]:
    events = _event_types(result)
    gap = None
    for item in result.get("events") or []:
        if item.get("type") == "gap_resolution_routed":
            gap = dict(item)
            break
    return {
        "event_types": events,
        "gap_resolution_routed": gap,
        "awaiting_goal_continuation": result.get("awaiting_goal_continuation"),
        "awaiting_boundary_grill": result.get("awaiting_boundary_grill"),
        "awaiting_decision_change_confirmation": result.get(
            "awaiting_decision_change_confirmation"
        ),
        "awaiting_human_grill": result.get("awaiting_human_grill"),
        "awaiting_goal_completion_human": result.get("awaiting_goal_completion_human"),
        "stop_reason": result.get("stop_reason"),
        "mission_id": (result.get("mission_memory") or {}).get("mission_id"),
        "execution_id": (result.get("mission_memory") or {}).get("execution_id"),
    }


def _human_follow_up(session: dict[str, Any], turn_index: int) -> str | None:
    if session.get("awaiting_decision_change_confirmation"):
        return None
    if session.get("awaiting_boundary_grill"):
        return "acceptance_quote_first_lines"
    if session.get("awaiting_goal_completion_human"):
        return "1"
    if session.get("awaiting_human_grill"):
        return "確認済みの調査対象で進めてください。"
    if session.get("awaiting_goal_continuation"):
        return "継続"
    return None


def _setup_probe() -> Path:
    probe_dir = _REPO / PROBE_REL_DIR
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_file = probe_dir / "probe.txt"
    probe_file.write_text(f"{PROBE_LINE}\n", encoding="utf-8")
    return probe_file


def _install_tool_wrapper(tool_state: dict[str, Any]) -> Callable[..., Any]:
    import ai_tool.chat_interface.agent_turn as agent_turn

    original = agent_turn._execute_agent_tool

    def wrapped(name, arguments, **_kwargs):
        path = str((arguments or {}).get("path") or "").replace("\\", "/")
        if name == "read_file" and path.endswith("probe.txt"):
            if not tool_state["allow_probe_read"]:
                return {
                    "ok": False,
                    "status": "failure",
                    "path": path,
                    "error": {
                        "code": "path_not_found",
                        "message": "temporary probe read failure (live e2e)",
                    },
                }
            return {
                "ok": True,
                "status": "success",
                "path": path,
                "content": f"{PROBE_LINE}\n",
                "error": None,
            }
        return original(name, arguments, **_kwargs)

    agent_turn._execute_agent_tool = wrapped
    return original


def _restore_tool_wrapper(original: Callable[..., Any]) -> None:
    import ai_tool.chat_interface.agent_turn as agent_turn

    agent_turn._execute_agent_tool = original


def main() -> int:
    run_id = _utc_stamp() + "_production_runtime_live"
    run_dir = _REPO / "logs" / "_e2e_production_runtime_live" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    live, live_err = ollama_available()
    model = None
    model_err = None
    try:
        model = get_llm_profile().get("model")
    except Exception as exc:  # noqa: BLE001
        model_err = f"{type(exc).__name__}: {exc}"

    summary: dict[str, Any] = {
        "run_id": run_id,
        "experiment": "production_runtime_live_e2e",
        "request": LIVE_REQUEST,
        "ollama_available": live,
        "ollama_error": live_err,
        "configured_model": model,
        "model_config_error": model_err,
        "budget_seconds": BUDGET_SECONDS,
        "status": "NOT_RUN",
        "observed_paths": [],
        "turns": [],
    }

    if not live or not model:
        summary["status"] = "SKIP"
        summary["judgment"] = "NOT_OBSERVED"
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    _setup_probe()
    tool_state = {"allow_probe_read": False}
    original_tool = _install_tool_wrapper(tool_state)

    session = empty_session(f"production-runtime-live-{run_id}")
    save_session(session)

    started = time.perf_counter()
    user_text = LIVE_REQUEST
    turn_records: list[dict[str, Any]] = []
    observed_path_keys: set[str] = set()

    try:
        for turn_index in range(1, MAX_TURNS + 1):
            if time.perf_counter() - started > BUDGET_SECONDS:
                summary["status"] = "BUDGET_EXCEEDED"
                break

            if turn_index > 1 and session.get("awaiting_goal_continuation"):
                tool_state["allow_probe_read"] = True

            turn_started = time.perf_counter()
            result = run_chat_turn(session, user_text, model=model)
            elapsed_ms = max(0, round((time.perf_counter() - turn_started) * 1000))
            obs = _collect_path_observations(result)
            events = obs["event_types"]

            if "gap_resolution_routed" in events:
                gap = obs.get("gap_resolution_routed") or {}
                observed_path_keys.add(f"gap:{gap.get('gap_kind')}:{gap.get('winner')}")
            if "goal_continuation_restored" in events:
                observed_path_keys.add("continuation:restored")
            if "continuation_capability_applied" in events:
                observed_path_keys.add("continuation:capability_applied")
            if "boundary_grill_launched" in events or any(
                e == "boundary_grill" for e in events
            ):
                observed_path_keys.add("boundary_grill:launched")
            if "boundary_grill_answer_applied" in events:
                observed_path_keys.add("boundary_grill:answer_applied")
            if "decision_change_confirmation_launched" in events:
                observed_path_keys.add("decision_change:confirmation_launched")
            if "decision_change_confirmed" in events:
                observed_path_keys.add("decision_change:confirmed")
            if "decision_change_rejected" in events:
                observed_path_keys.add("decision_change:rejected")

            turn_records.append(
                {
                    "turn": turn_index,
                    "user_text": user_text,
                    "elapsed_ms": elapsed_ms,
                    "observation": obs,
                    "answer_preview": str(result.get("answer") or "")[:800],
                }
            )
            (run_dir / f"turn_{turn_index:02d}.json").write_text(
                json.dumps(
                    {
                        "turn": turn_index,
                        "user_text": user_text,
                        "result": {
                            "events": result.get("events"),
                            "gap_resolution": result.get("gap_resolution"),
                            "awaiting_goal_continuation": result.get(
                                "awaiting_goal_continuation"
                            ),
                            "awaiting_boundary_grill": result.get("awaiting_boundary_grill"),
                            "awaiting_decision_change_confirmation": result.get(
                                "awaiting_decision_change_confirmation"
                            ),
                            "mission_memory": result.get("mission_memory"),
                            "answer": result.get("answer"),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            follow_up = _human_follow_up(session, turn_index)
            if follow_up is None and not any(
                session.get(key)
                for key in (
                    "awaiting_goal_continuation",
                    "awaiting_boundary_grill",
                    "awaiting_human_grill",
                    "awaiting_goal_completion_human",
                    "awaiting_decision_change_confirmation",
                )
            ):
                summary["status"] = "COMPLETED"
                break
            if follow_up is None:
                summary["status"] = "PAUSED"
                summary["pause_reason"] = "awaiting_decision_change_confirmation"
                break
            user_text = follow_up
        else:
            if summary.get("status") not in {"BUDGET_EXCEEDED", "PAUSED"}:
                summary["status"] = "MAX_TURNS"
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "ERROR"
        summary["exception_type"] = type(exc).__name__
        summary["exception_message"] = str(exc)
    finally:
        _restore_tool_wrapper(original_tool)

    elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))
    summary["elapsed_ms"] = elapsed_ms
    summary["turns"] = turn_records
    summary["observed_paths"] = sorted(observed_path_keys)
    summary["session_awaiting"] = {
        "goal_continuation": session.get("awaiting_goal_continuation"),
        "boundary_grill": session.get("awaiting_boundary_grill"),
        "decision_change_confirmation": session.get("awaiting_decision_change_confirmation"),
        "human_grill": session.get("awaiting_human_grill"),
        "goal_completion_human": session.get("awaiting_goal_completion_human"),
    }

    path_set = set(summary["observed_paths"])
    checks = {
        "gap_routed": any(p.startswith("gap:") for p in path_set),
        "continuation_or_recovery": any(
            p.startswith("continuation:") or "recovery" in p for p in path_set
        ),
        "boundary_grill_if_needed": "boundary_grill:launched" in path_set
        or "boundary_grill:answer_applied" in path_set
        or not session.get("awaiting_boundary_grill"),
        "human_decision_applied": "boundary_grill:answer_applied" in path_set,
    }
    summary["checks"] = checks
    if summary.get("status") == "COMPLETED" and checks["gap_routed"]:
        summary["judgment"] = "PASS"
    elif summary.get("status") in {"PAUSED", "MAX_TURNS"} and checks["gap_routed"]:
        summary["judgment"] = "PARTIAL_PASS"
    elif summary.get("status") == "ERROR":
        summary["judgment"] = "FAIL"
    else:
        summary["judgment"] = "PARTIAL_PASS" if checks["gap_routed"] else "NOT_OBSERVED"

    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("judgment") in {"PASS", "PARTIAL_PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
