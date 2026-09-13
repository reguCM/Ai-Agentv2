"""Tetris Golden Path execution context v0 (PROVISIONAL).

Execution context describes the intended run environment. It is NOT a precondition.
Preconditions are evaluated separately by system checkers.
"""
from __future__ import annotations

from typing import Any

CONTEXT_VERSION = "0.1"
EXECUTION_CONTEXT_FILENAME = "execution_context.json"

TETRIS_GOLDEN_PATH_EXECUTION_CONTEXT: dict[str, Any] = {
    "context_version": CONTEXT_VERSION,
    "golden_path": True,
    "composition_id": "tetris-sandbox-e2e",
    "target_os": "windows",
    "runtime": "python",
    "ui_mode": "desktop_gui",
    "input_method": "keyboard",
    "dependency_policy": "pygame_allowed",
    "workspace": "sandbox",
    "environment_policy": "VERIFY_ONLY",
    "policy": {
        "execution_context_not_equal_precondition": True,
        "llm_may_read_but_not_mutate": True,
        "environment_policy": "VERIFY_ONLY",
        "verify_only_no_auto_mutation": True,
    },
}


def build_tetris_golden_path_execution_context(**overrides: Any) -> dict[str, Any]:
    context = dict(TETRIS_GOLDEN_PATH_EXECUTION_CONTEXT)
    context.update(overrides)
    return context


__all__ = [
    "CONTEXT_VERSION",
    "EXECUTION_CONTEXT_FILENAME",
    "TETRIS_GOLDEN_PATH_EXECUTION_CONTEXT",
    "build_tetris_golden_path_execution_context",
]
