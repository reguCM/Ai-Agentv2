"""LLM なしで基盤を実測する。既存実験・本番 Agent には接続しない。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.experiment_infrastructure_validation.cases import (
    FULL_CONFIG,
    KNOWN_FILES,
    MAPPING_CASES,
    MISMAPPING_CASES,
    MULTI_TURN,
    PARTIAL_CONFIG,
    RETURN_CASE,
    SNIPPET_CONFIG,
    SOLVE_LOOP,
    UNKNOWN_TOOL_JUDGMENT,
)
from research.llm_benchmarks.experiment_infrastructure_validation.harness import (
    compare_mapping,
    copy_val_workspace,
    new_session,
    run_fixed_turn,
    snapshot_workspace,
)
from research.llm_benchmarks.experiment_infrastructure_validation.sut import (
    SUT,
    apply_patch,
    classify_mapping,
    dispatch,
    dump_result,
    format_test_failure,
    git_diff,
    run_program,
    run_test,
    sent_for_tool,
    split_outcomes,
)


OUT_DIR = Path("research/llm_benchmarks/experiment_infrastructure_validation/results")


def _now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _classify_mapping_case(case, compared):
    if not case.get("expected_calls"):
        if compared["mapping_status"] == "gap_as_expected":
            return "no_mechanical_target"
        return "unexpected_execute"
    if compared["mapping_match"]:
        return "judgment_ok_mapping_ok"
    if compared["mapping_status"].startswith("partial"):
        return "judgment_ok_mapping_partial"
    return "judgment_ok_mapping_failed"


def mapping_only(case):
    mapping = classify_mapping(case["judgment"], KNOWN_FILES)
    compared = compare_mapping(case["expected_calls"], mapping)
    return {
        "step_id": case["id"],
        "turn_id": None,
        "input": case["judgment"],
        "judgment": case["judgment"],
        "judgment_status": "fixed_assumed_correct",
        "mapping_output": mapping.get("mapping_output"),
        "mapping_candidates": mapping.get("candidates"),
        "mapping_status": compared["mapping_status"],
        "mapping_match": compared["mapping_match"],
        "order_preserved": compared["order_preserved"],
        "expected_calls": case["expected_calls"],
        "actual_call": compared["actual_call"],
        "executable_calls": compared["executable_calls"],
        "tool_name": None if compared["actual_call"] is None else compared["actual_call"]["tool_name"],
        "tool_arguments": None if compared["actual_call"] is None else compared["actual_call"]["tool_arguments"],
        "tool_result": None,
        "workspace_before": None,
        "workspace_after": None,
        "test_result": None,
        "error": None,
        "note": case.get("note"),
        "classification": _classify_mapping_case(case, compared),
    }


def run_mapping_section():
    return {
        "required_cases": [mapping_only(case) for case in MAPPING_CASES],
        "mismapping_cases": [mapping_only(case) for case in MISMAPPING_CASES],
        "unknown_tool_judgment": mapping_only(UNKNOWN_TOOL_JUDGMENT),
    }


def run_return_and_turns(root: Path):
    workspace = copy_val_workspace(root / "workspace_return")
    session = new_session(workspace)
    returned = run_fixed_turn(
        session,
        1,
        RETURN_CASE["judgment"],
        RETURN_CASE["expected_calls"],
    )
    helper_text = (workspace / "helper.py").read_text(encoding="utf-8")
    next_input = returned.get("next_judgment_input") or ""
    returned["failure_c"] = {
        "name": "tool_ok_but_result_not_returned",
        "observed": not (
            returned["tool_status"] == "ok"
            and "from config import FIELD_COUNT" in next_input
            and helper_text in next_input
        ),
        "next_input_has_source": "from config import FIELD_COUNT" in next_input,
    }

    workspace_multi = copy_val_workspace(root / "workspace_multi")
    session_multi = new_session(workspace_multi)
    turns = []
    for item in MULTI_TURN:
        turns.append(
            run_fixed_turn(
                session_multi,
                item["turn_id"],
                item["judgment"],
                item["expected_calls"],
            )
        )
    state_ok = session_multi["files_read"][:2] == ["helper.py", "config.py"] or (
        "helper.py" in session_multi["files_read"] and "config.py" in session_multi["files_read"]
    )
    turn1_lost = turns[0]["files_read_so_far"] == ["helper.py"] and (
        "helper.py" not in turns[1]["files_read_so_far"]
    )
    return {
        "initial_failure": {
            "command": session["initial_pytest"]["command"],
            "exit_code": session["initial_pytest"]["exit_code"],
            "stdout": session["initial_pytest"]["stdout"],
            "stderr": session["initial_pytest"]["stderr"],
            "traceback": session["initial_pytest"]["traceback"],
            "test_pass": session["initial_outcomes"]["test_pass"],
        },
        "return_path": returned,
        "multi_turn": turns,
        "state_after_multi": {
            "files_read": session_multi["files_read"],
            "files_changed": session_multi["files_changed"],
            "tool_calls": session_multi["tool_calls"],
            "test_results_count": len(session_multi["test_results"]),
            "next_inputs_count": len(session_multi["next_inputs"]),
            "turn1_helper_retained_in_turn2": "helper.py" in turns[1]["files_read_so_far"],
            "turn1_information_lost": turn1_lost,
            "exploration_changed": state_ok,
        },
    }


def run_solve_loop(root: Path):
    workspace = copy_val_workspace(root / "workspace_solve")
    session = new_session(workspace)
    turns = []
    for item in SOLVE_LOOP:
        turns.append(
            run_fixed_turn(
                session,
                item["turn_id"],
                item["judgment"],
                item["expected_calls"],
            )
        )
    last_tests = [item["test_result"] for item in turns if item.get("test_result")]
    first_patch_test = last_tests[0] if last_tests else None
    second_patch_test = last_tests[1] if len(last_tests) > 1 else None
    failure_d = True
    if first_patch_test:
        sent = first_patch_test.get("sent_to_next_judgment") or ""
        failure_d = not (
            str(first_patch_test.get("exit_code")) in sent
            and (first_patch_test.get("stdout") or "") in sent
            and first_patch_test.get("test_pass") is False
        )
    return {
        "turns": turns,
        "files_read": session["files_read"],
        "files_changed": session["files_changed"],
        "patch_rounds": session["patch_rounds"],
        "first_patch_test": first_patch_test,
        "second_patch_test": second_patch_test,
        "success3": bool(
            first_patch_test
            and first_patch_test.get("test_pass") is False
            and second_patch_test
            and second_patch_test.get("test_pass") is True
            and "config.py" in session["files_read"]
            and "helper.py" in session["files_read"]
        ),
        "failure_d_test_result_not_returned": failure_d,
        "failure_f_cannot_repatch": not (
            session["patch_rounds"] >= 2 and second_patch_test is not None
        ),
        "failure_g_cannot_change_file": not (
            "helper.py" in session["files_read"] and "config.py" in session["files_read"]
        ),
    }


def run_patch_safety(root: Path):
    workspace = copy_val_workspace(root / "workspace_patch")
    session = new_session(workspace)
    before = snapshot_workspace(workspace)
    helper_before = before["files"]["helper.py"]["text"]
    main_before = before["files"]["main.py"]["text"]
    config_before = before["files"]["config.py"]["text"]
    result = apply_patch(workspace, "config.py", PARTIAL_CONFIG)
    after = snapshot_workspace(workspace)
    only_config_changed = (
        after["files"]["config.py"]["text"] == PARTIAL_CONFIG
        and after["files"]["helper.py"]["text"] == helper_before
        and after["files"]["main.py"]["text"] == main_before
    )
    pytest_partial = run_test(workspace)
    program_partial = run_program(workspace)
    outcomes_partial = split_outcomes(pytest_partial, program_partial)
    result2 = apply_patch(workspace, "config.py", FULL_CONFIG)
    pytest_full = run_test(workspace)
    program_full = run_program(workspace)
    outcomes_full = split_outcomes(pytest_full, program_full)
    from research.llm_benchmarks.judgment_loop_min_experiment import workspace as sut_workspace
    from research.llm_benchmarks.experiment_infrastructure_validation.sut import git_init_workspace

    snippet_ws = copy_val_workspace(root / "workspace_snippet")
    git_init_workspace(snippet_ws)
    apply_patch(snippet_ws, "config.py", SNIPPET_CONFIG)
    snippet_after = (snippet_ws / "config.py").read_text(encoding="utf-8")
    imports_gone = "READY" not in snippet_after
    missing = dispatch(workspace, "read_file", {"path": "missing.py"})
    unknown = dispatch(workspace, "not_a_real_tool", {})
    dumped_missing = dump_result(missing)
    next_missing = sent_for_tool("read_file", missing, dumped_missing)
    rollback_api = hasattr(sut_workspace, "rollback")
    return {
        "target_only_changed": only_config_changed,
        "config_before": config_before,
        "config_after_partial": after["files"]["config.py"]["text"],
        "partial_test_pass": outcomes_partial["test_pass"],
        "partial_exit_code": pytest_partial["exit_code"],
        "full_test_pass": outcomes_full["test_pass"],
        "full_exit_code": pytest_full["exit_code"],
        "encoding": "utf-8",
        "newline_partial_ok": after["files"]["config.py"]["text"] == PARTIAL_CONFIG,
        "snippet_overwrite_wipes_rest": imports_gone,
        "snippet_after": snippet_after,
        "rollback_implemented": rollback_api,
        "repatch_after_failure": outcomes_full["test_pass"] is True,
        "apply_ok": result.get("ok") is True and result2.get("ok") is True,
        "failure_b_missing_file": {
            "tool_exists": True,
            "file_exists": False,
            "result": missing,
            "next_input": next_missing,
        },
        "failure_b_unknown_tool": unknown,
        "git_diff_after_full": git_diff(workspace),
        "helper_untouched": after["files"]["helper.py"]["text"] == helper_before,
        "main_untouched": after["files"]["main.py"]["text"] == main_before,
        "direct_test_return_after_partial_patch": _test_return_fields(
            pytest_partial, program_partial, outcomes_partial
        ),
    }


def _test_return_fields(pytest_run, program_run, outcomes):
    sent = format_test_failure(pytest_run, program_run)
    return {
        "command": pytest_run["command"],
        "exit_code": pytest_run["exit_code"],
        "stdout_present": bool(pytest_run.get("stdout")),
        "stderr_present": pytest_run.get("stderr") is not None,
        "traceback": pytest_run.get("traceback") or program_run.get("traceback"),
        "test_pass": outcomes["test_pass"],
        "sent_to_next_judgment": sent,
        "sent_has_exit_code": str(pytest_run["exit_code"]) in sent,
        "sent_has_stdout": (pytest_run.get("stdout") or "") in sent,
        "not_only_test_failure_label": "The test still fails." in sent
        and (pytest_run.get("stdout") or "") in sent,
    }


def summarize(payload):
    mapping = payload["mapping"]
    required = mapping["required_cases"]
    case1 = next(item for item in required if item["step_id"] == "case1_confirm_helper")
    ret = payload["return_and_turns"]["return_path"]
    success1 = case1["mapping_match"] and ret["tool_status"] == "ok" and ret["return_ok"]
    success2 = payload["return_and_turns"]["state_after_multi"]["exploration_changed"]
    success3 = payload["solve_loop"]["success3"]
    mapping_problem_ids = [
        item["step_id"]
        for item in required + mapping["mismapping_cases"]
        if item["classification"] in ("judgment_ok_mapping_failed", "judgment_ok_mapping_partial")
    ]
    failures = {
        "A_judgment_ok_mapping_wrong": mapping_problem_ids,
        "B_unknown_tool_error": payload["patch_safety"]["failure_b_unknown_tool"].get("error"),
        "C_tool_ok_no_return": payload["return_and_turns"]["return_path"]["failure_c"]["observed"],
        "D_test_not_returned_via_mapping_loop": payload["solve_loop"]["failure_d_test_result_not_returned"],
        "D_test_not_returned_via_direct_patch": not payload["patch_safety"][
            "direct_test_return_after_partial_patch"
        ]["not_only_test_failure_label"],
        "E_patch_not_in_workspace": not payload["patch_safety"]["target_only_changed"],
        "F_cannot_repatch_via_mapping_loop": payload["solve_loop"]["failure_f_cannot_repatch"],
        "F_cannot_repatch_via_direct_dispatch": not payload["patch_safety"]["repatch_after_failure"],
        "G_cannot_change_file": payload["solve_loop"]["failure_g_cannot_change_file"],
    }
    return {
        "success1_fixed_judgment_tool_result": success1,
        "success2_next_judgment_other_tool": success2,
        "success3_failure_repatch_pass": success3,
        "failures": failures,
    }


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": "experiment_infrastructure_validation",
        "at": _now(),
        "llm_used": False,
        "sut": SUT,
        "fixture": "fixtures/chain_ready",
        "mapping": run_mapping_section(),
        "return_and_turns": run_return_and_turns(root),
        "solve_loop": run_solve_loop(root),
        "patch_safety": run_patch_safety(root),
    }
    payload["summary"] = summarize(payload)
    save_json(root / "run.json", payload)
    print(f"wrote {root}", flush=True)
    print(json.dumps(payload["summary"], ensure_ascii=False), flush=True)
    return root


if __name__ == "__main__":
    main()
