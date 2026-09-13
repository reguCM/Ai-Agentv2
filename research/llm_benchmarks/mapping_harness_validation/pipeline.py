"""SUT の Tool 実行と返却形式。既存実験ファイルは書き換えない。"""

from __future__ import annotations

import shutil
from pathlib import Path

from research.llm_benchmarks.judgment_loop_min_experiment.bench import sent_for_tool
from research.llm_benchmarks.judgment_loop_min_experiment.execute import format_test_failure
from research.llm_benchmarks.judgment_loop_min_experiment.workspace import (
    dispatch,
    dump_result,
)


VAL_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "val_read"


def copy_val_workspace(dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        VAL_FIXTURE,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
    )
    return dest


def execute_mapped(workspace: Path, tool_name, tool_arguments):
    result = dispatch(workspace, tool_name, tool_arguments or {})
    dumped = dump_result(result)
    next_input = sent_for_tool(tool_name, result, dumped)
    return {
        "tool_name": tool_name,
        "tool_arguments": tool_arguments or {},
        "tool_result": dumped["raw_result"],
        "tool_sent_result": dumped["sent_tool_result"],
        "next_llm_input": next_input,
        "execution_match": result.get("ok") is True or "exit_code" in result,
        "dispatched_name": tool_name,
    }


def return_test_failure_text(pytest_run, program_run):
    text = format_test_failure(pytest_run, program_run)
    return {
        "next_llm_input": text,
        "has_exit_code": f"Exit code:\n{pytest_run['exit_code']}" in text,
        "has_stdout": (pytest_run.get("stdout") or "") in text,
        "has_stderr": True,
        "has_traceback": "Traceback:" in text,
        "directs_other_file": "別ファイル" in text or "inspect helper" in text.lower(),
    }
