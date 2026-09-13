from __future__ import annotations

from pathlib import Path

from ai_tool.environment_precondition_checker import evaluate_environment_preconditions
from ai_tool.precondition_contract import STATUS_SATISFIED
from ai_tool.tetris_execution_context import TETRIS_GOLDEN_PATH_EXECUTION_CONTEXT
from ai_tool.tetris_precondition_checker import build_precondition_evaluation_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_golden_path_execution_context_is_separate_from_preconditions() -> None:
    bundle = build_precondition_evaluation_bundle(
        handoff_packet=None,
        repo_root=REPO_ROOT,
        execution_context=TETRIS_GOLDEN_PATH_EXECUTION_CONTEXT,
        include_environment=True,
    )
    assert bundle["execution_context"]["workspace"] == "sandbox"
    assert bundle["execution_context"]["ui_mode"] == "desktop_gui"
    assert "execution_context" not in {row["key"] for row in bundle["preconditions"]}
    assert bundle["policy"]["execution_context_not_equal_precondition"] is True


def test_environment_preconditions_include_python_and_sandbox() -> None:
    items = evaluate_environment_preconditions(repo_root=REPO_ROOT)
    by_key = {item.key: item for item in items}
    assert by_key["python_available"].evaluation.status == STATUS_SATISFIED
    assert by_key["sandbox_writable"].evaluation.status == STATUS_SATISFIED
    assert "pygame_available" in by_key
