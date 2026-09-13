"""S9 — Test Action Runtime Bridge (routing only; reuses S7a safety stack)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from test_safety.runner_wedge import ConsumedAuthorizationRegistry
from test_safety.safety_resolution import run_explicit_test_with_auto_resolution

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_shadow_gate.schema.json"
RUNS_DIR = REPO_ROOT / "runs" / "test_safety_explicit"


def _safe_action_filename(action_id: str) -> str:
    token = re.sub(r"[^\w\-]+", "_", str(action_id or "").strip())
    return token or "unknown_action"


def persist_explicit_run_packet(
    outcome: Mapping[str, Any],
    *,
    action_id: str,
    runs_dir: Path | None = None,
) -> Path:
    target_dir = runs_dir or RUNS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{_safe_action_filename(action_id)}.json"
    path.write_text(json.dumps(dict(outcome), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def bridge_test_execution(
    *,
    action_id: str,
    test_plan: Mapping[str, Any],
    repo_root: Path | None = None,
    authorization_packet: Mapping[str, Any] | None = None,
    consumed_registry: ConsumedAuthorizationRegistry | None = None,
    persist: bool = True,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Thin wrapper around run_explicit_test_with_auto_resolution.
    Does not implement validator/gate/authorization logic.
    """
    root = repo_root or REPO_ROOT
    outcome = run_explicit_test_with_auto_resolution(
        action_id=str(action_id),
        current_plan=dict(test_plan),
        authorization_packet=authorization_packet,
        repo_root=root,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
        consumed_registry=consumed_registry or ConsumedAuthorizationRegistry(),
    )
    run_path: Path | None = None
    if persist:
        run_path = persist_explicit_run_packet(
            outcome,
            action_id=str(action_id),
            runs_dir=runs_dir,
        )
    if run_path is not None:
        outcome = dict(outcome)
        outcome["persisted_run_path"] = str(run_path)
    return outcome


def build_llm_tool_summary(outcome: Mapping[str, Any]) -> dict[str, Any]:
    """Structured summary for tool result / Evidence — not full packet."""
    resolution = dict(outcome.get("resolution") or {})
    runner = dict(outcome.get("runner_evidence") or {})
    exec_result = dict(runner.get("execution_result") or {})
    return {
        "resolution_result": resolution.get("resolution_result"),
        "gate_decision": resolution.get("gate_decision"),
        "executor_called": outcome.get("executor_called"),
        "test_failed": outcome.get("test_failed"),
        "run_closed": outcome.get("run_closed"),
        "closure_reason": runner.get("closure_reason"),
        "execution_ok": exec_result.get("ok"),
        "returncode": exec_result.get("returncode"),
        "stdout_tail": (exec_result.get("stdout_tail") or "")[-1500:],
        "stderr_tail": (exec_result.get("stderr_tail") or "")[-800:],
        "persisted_run_path": outcome.get("persisted_run_path"),
        "action_id": resolution.get("action_id") or runner.get("action_id"),
    }


def safety_run_closure_predicate(outcome: Mapping[str, Any]) -> bool:
    runner = outcome.get("runner_evidence") or {}
    return bool(
        outcome.get("executor_called")
        and not outcome.get("test_failed")
        and runner.get("run_closed") is True
    )
