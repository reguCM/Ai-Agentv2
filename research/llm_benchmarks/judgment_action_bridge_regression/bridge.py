"""
LLM text → parser → validator → executor → tool_adapter。
既存 bridge / Mapping / 本番には接続しない。LLM は呼ばない。
"""

from __future__ import annotations

from research.llm_benchmarks.judgment_action_bridge_regression.action_executor import (
    execute_actions,
    prepare_actions,
)
from research.llm_benchmarks.judgment_action_bridge_regression.action_parser import parse_actions
from research.llm_benchmarks.judgment_action_bridge_regression.action_validator import (
    validate_actions,
)
from research.llm_benchmarks.judgment_action_bridge_regression.tool_adapter import (
    workspace_filenames,
)


def process(text, known_files, workspace=None, execute=False):
    actions, fences, clauses = parse_actions(text, known_files)
    exists = None
    if workspace is not None:
        names = workspace_filenames(workspace)
        exists = {name: True for name in names}
        for name in known_files or []:
            posix = str(name).replace("\\", "/")
            if posix not in exists and posix.split("/")[-1] not in {
                item.split("/")[-1] for item in names
            }:
                exists[posix] = False
    validated = validate_actions(actions, known_files, workspace_exists=exists)
    prepared = prepare_actions(validated, workspace if execute else None)
    executable = [item for item in prepared if item.get("execute") and item.get("tool_name")]
    steps = []
    next_inputs = []
    if execute and workspace is not None:
        steps, next_inputs = execute_actions(workspace, prepared)
    flags = _flags(prepared, steps)
    return {
        "input_text": text,
        "judgment_received": bool(text and str(text).strip()),
        "clauses": clauses,
        "fences": fences,
        "action_candidates": prepared,
        "selected_actions": executable,
        "steps": steps,
        "next_inputs": next_inputs,
        "mapping_status": _mapping_status(prepared, executable),
        "flags": flags,
    }


def _mapping_status(prepared, executable):
    if executable:
        return "selected"
    statuses = {item.get("status") for item in prepared}
    if "ambiguous" in statuses:
        return "ambiguous"
    if "unknown_target" in statuses:
        return "unknown_target"
    if "missing_file" in statuses:
        return "missing_file"
    return "unresolved"


def _flags(prepared, steps):
    parse_success = any(
        item.get("intent") not in (None, "AMBIGUOUS") or item.get("status") == "ambiguous"
        for item in prepared
    )
    validation_success = all(item.get("validation_success", True) for item in prepared)
    executed = [item for item in steps if item.get("tool_name")]
    execution_success = bool(executed) and all(
        item.get("execution_success") for item in executed
    )
    result_return_success = bool(executed) and all(
        item.get("result_return_success") for item in executed
    )
    intents = [item.get("intent") for item in prepared]
    orders = [item.get("order") for item in prepared if item.get("order")]
    sequence_success = orders == sorted(orders) if orders else True
    return {
        "parse_success": parse_success,
        "validation_success": validation_success,
        "execution_success": execution_success,
        "result_return_success": result_return_success,
        "sequence_success": sequence_success,
        "intents": intents,
        "executable_tools": [item.get("tool_name") for item in prepared if item.get("execute")],
    }
