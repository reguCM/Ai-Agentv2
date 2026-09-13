"""PROJECT_AGENT execute_tool hook for v2.2.1 destructive local git commands."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from tools.git_guard.agent_local_op_bridge import (
    block_tool_result_from_gate,
    gate_agent_shell_command,
    need_human_tool_result_from_gate,
)

T = TypeVar("T")


def agent_git_local_gate_enabled() -> bool:
    raw = (os.environ.get("AI_AGENT_GIT_LOCAL_GATE") or "on").strip().lower()
    return raw not in ("0", "off", "false", "disable", "disabled")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def extract_shell_command(tool_name: str, arguments: dict[str, Any]) -> str | None:
    for key in ("command", "cmd", "shell_command", "git_command"):
        val = arguments.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    if tool_name in ("run_command", "execute_shell", "shell"):
        val = arguments.get("command") or arguments.get("cmd")
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def apply_git_local_pre_execution_gate(
    tool_name: str,
    arguments: dict[str, Any],
    execute: Callable[[], T],
    *,
    repo: Path | None = None,
    human_decision_emit: Callable[[dict[str, Any]], None] | None = None,
) -> T | dict[str, Any]:
    """
    If arguments carry a destructive local git command, run v2.2 evaluator before execute().
    Otherwise call execute() once with no extra gate.
    """
    if not agent_git_local_gate_enabled():
        return execute()

    cmd = extract_shell_command(tool_name, arguments)
    if not cmd:
        return execute()

    result, gate_record = gate_agent_shell_command(
        repo or repo_root(),
        cmd,
        execute,
        human_decision_emit=human_decision_emit,
    )
    evaluation = gate_record.get("evaluation") or {}
    decision = str(evaluation.get("decision") or "").upper()

    if result is not None:
        return result
    if gate_record.get("blocked") or decision == "BLOCK":
        return block_tool_result_from_gate(tool_name, arguments, gate_record)
    return need_human_tool_result_from_gate(tool_name, arguments, gate_record)
