"""判断と Mapping を分けて記録し、SUT の Tool を実行する。"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from research.llm_benchmarks.experiment_infrastructure_validation.cases import KNOWN_FILES
from research.llm_benchmarks.experiment_infrastructure_validation.sut import (
    classify_mapping,
    dispatch,
    dump_result,
    format_execution_block,
    format_test_failure,
    git_diff,
    git_init_workspace,
    run_program,
    run_test,
    sent_for_tool,
    split_outcomes,
    workspace_filenames,
)


FIXTURE_SRC = Path(__file__).resolve().parent / "fixtures" / "chain_ready"


def copy_val_workspace(dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        FIXTURE_SRC,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
    )
    return dest


def snapshot_workspace(workspace: Path):
    files = {}
    for name in workspace_filenames(workspace):
        text = (workspace / name).read_text(encoding="utf-8", errors="replace")
        files[name] = {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text": text,
        }
    return {
        "files": files,
        "git_diff": git_diff(workspace),
        "filenames": list(files),
    }


def _normalize_call(tool_name, arguments):
    arguments = dict(arguments or {})
    if tool_name == "run_test":
        arguments = {}
    return {"tool_name": tool_name, "tool_arguments": arguments}


def compare_mapping(expected_calls, mapping):
    chosen = mapping.get("execute")
    actual = None
    if chosen and chosen.get("tool_name"):
        actual = _normalize_call(chosen["tool_name"], chosen.get("tool_arguments"))
    executable = [
        _normalize_call(item["tool_name"], item.get("tool_arguments"))
        for item in (mapping.get("candidates") or [])
        if item.get("execute") and item.get("tool_name")
    ]
    expected = [_normalize_call(item["tool_name"], item.get("tool_arguments")) for item in expected_calls]
    if not expected:
        if actual is None:
            return {
                "mapping_status": "gap_as_expected" if not executable else "unexpected_execute",
                "mapping_match": actual is None,
                "order_preserved": True,
                "actual_call": actual,
                "executable_calls": executable,
            }
        return {
            "mapping_status": "unexpected_execute",
            "mapping_match": False,
            "order_preserved": False,
            "actual_call": actual,
            "executable_calls": executable,
        }
    if len(expected) == 1:
        if actual is None:
            return {
                "mapping_status": "gap",
                "mapping_match": False,
                "order_preserved": False,
                "actual_call": actual,
                "executable_calls": executable,
            }
        match = actual == expected[0]
        return {
            "mapping_status": "correct" if match else "wrong_tool",
            "mapping_match": match,
            "order_preserved": match,
            "actual_call": actual,
            "executable_calls": executable,
        }
    expected_in_exec = all(item in executable for item in expected)
    first_ok = actual == expected[0]
    order_ok = executable[: len(expected)] == expected
    if expected_in_exec and len(executable) == len(expected) and order_ok and first_ok:
        status = "correct_candidates_single_execute"
    elif expected_in_exec and first_ok:
        status = "partial_all_candidates_one_execute"
    elif actual in expected:
        status = "partial_subset"
    elif actual is None:
        status = "gap"
    else:
        status = "wrong_tool"
    return {
        "mapping_status": status,
        "mapping_match": False,
        "order_preserved": order_ok,
        "actual_call": actual,
        "executable_calls": executable,
        "expected_in_executable": expected_in_exec,
    }


def new_session(workspace: Path):
    git_init_workspace(workspace)
    pytest_run = run_test(workspace)
    program_run = run_program(workspace)
    outcomes = split_outcomes(pytest_run, program_run)
    initial_text = (
        format_execution_block("pytest", pytest_run)
        + "\n\n"
        + format_execution_block("python main.py", program_run)
        + "\n"
    )
    return {
        "workspace": workspace,
        "known_files": workspace_filenames(workspace) or list(KNOWN_FILES),
        "files_read": [],
        "files_changed": [],
        "tool_calls": [],
        "test_results": [],
        "next_inputs": [initial_text],
        "messages": [{"role": "user", "content": initial_text}],
        "initial_pytest": pytest_run,
        "initial_program": program_run,
        "initial_outcomes": outcomes,
        "patch_rounds": 0,
    }


def run_fixed_turn(session, turn_id, judgment, expected_calls, *, auto_test_after_patch=True):
    workspace = session["workspace"]
    before = snapshot_workspace(workspace)
    mapping = classify_mapping(judgment, session["known_files"])
    compared = compare_mapping(expected_calls, mapping)
    execute = mapping.get("execute")
    tool_name = None
    tool_arguments = None
    tool_result = None
    next_input = None
    test_result = None
    error = None
    tool_status = "not_executed"
    execution_status = "not_executed"
    return_ok = False

    session["messages"].append({"role": "assistant", "content": judgment})

    if execute and execute.get("tool_name"):
        tool_name = execute["tool_name"]
        tool_arguments = execute.get("tool_arguments") or {}
        result = dispatch(workspace, tool_name, tool_arguments)
        dumped = dump_result(result)
        tool_result = dumped["raw_result"]
        next_input = sent_for_tool(tool_name, result, dumped)
        session["messages"].append({"role": "user", "content": next_input})
        session["next_inputs"].append(next_input)
        session["tool_calls"].append(
            {"turn_id": turn_id, "tool_name": tool_name, "tool_arguments": tool_arguments}
        )
        if isinstance(result, dict) and result.get("error"):
            tool_status = "error"
            execution_status = "error"
            error = result.get("error")
        elif tool_name == "run_test":
            tool_status = "ok"
            execution_status = "ok"
            return_ok = bool(next_input) and "exit_code" in next_input
        elif result.get("ok"):
            tool_status = "ok"
            execution_status = "ok"
            return_ok = bool(next_input)
        else:
            tool_status = "failed"
            execution_status = "failed"
            error = (result or {}).get("error")
        if tool_name == "read_file" and result.get("ok"):
            session["files_read"].append(result.get("path"))
        if tool_name == "apply_patch" and result.get("ok"):
            session["files_changed"].append(result.get("path"))
            session["patch_rounds"] += 1
            if auto_test_after_patch:
                pytest_run = run_test(workspace)
                program_run = run_program(workspace)
                outcomes = split_outcomes(pytest_run, program_run)
                if outcomes["test_pass"]:
                    feedback = (
                        "The tests passed.\n\n"
                        + format_execution_block("pytest", pytest_run)
                        + "\n\n"
                        + format_execution_block("python main.py", program_run)
                        + "\n"
                    )
                else:
                    feedback = format_test_failure(pytest_run, program_run)
                test_result = {
                    "source": "harness_after_patch",
                    "command": pytest_run["command"],
                    "exit_code": pytest_run["exit_code"],
                    "stdout": pytest_run.get("stdout"),
                    "stderr": pytest_run.get("stderr"),
                    "traceback": pytest_run.get("traceback") or program_run.get("traceback"),
                    "test_pass": outcomes["test_pass"],
                    "pytest": pytest_run,
                    "python_main": program_run,
                    "sent_to_next_judgment": feedback,
                    **outcomes,
                }
                session["messages"].append({"role": "user", "content": feedback})
                session["next_inputs"].append(feedback)
                session["test_results"].append(test_result)
                return_ok = return_ok and bool(feedback)
    else:
        tool_status = "not_mapped"
        execution_status = "not_mapped"

    after = snapshot_workspace(workspace)
    record = {
        "step_id": f"turn_{turn_id}",
        "turn_id": turn_id,
        "input": session["messages"][-3]["content"] if len(session["messages"]) >= 3 else session["next_inputs"][0],
        "judgment": judgment,
        "judgment_status": "fixed_assumed_correct",
        "mapping_output": mapping.get("mapping_output"),
        "mapping_candidates": mapping.get("candidates"),
        "mapping_status": compared["mapping_status"],
        "mapping_match": compared["mapping_match"],
        "order_preserved": compared["order_preserved"],
        "expected_calls": expected_calls,
        "actual_call": compared["actual_call"],
        "executable_calls": compared["executable_calls"],
        "tool_name": tool_name,
        "tool_arguments": tool_arguments,
        "tool_result": tool_result,
        "tool_status": tool_status,
        "execution_status": execution_status,
        "next_judgment_input": next_input,
        "return_ok": return_ok,
        "workspace_before": {"filenames": before["filenames"], "git_diff": before["git_diff"]},
        "workspace_after": {"filenames": after["filenames"], "git_diff": after["git_diff"]},
        "workspace_file_hashes_before": {name: item["sha256"] for name, item in before["files"].items()},
        "workspace_file_hashes_after": {name: item["sha256"] for name, item in after["files"].items()},
        "test_result": test_result,
        "error": error,
        "files_read_so_far": list(session["files_read"]),
        "files_changed_so_far": list(session["files_changed"]),
        "tool_calls_so_far": list(session["tool_calls"]),
    }
    return record
