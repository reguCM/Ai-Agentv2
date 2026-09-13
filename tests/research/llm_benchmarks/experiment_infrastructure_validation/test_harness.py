from research.llm_benchmarks.experiment_infrastructure_validation.cases import (
    FULL_CONFIG,
    KNOWN_FILES,
    MAPPING_CASES,
    PARTIAL_CONFIG,
)
from research.llm_benchmarks.experiment_infrastructure_validation.harness import (
    compare_mapping,
    copy_val_workspace,
    new_session,
    run_fixed_turn,
)
from research.llm_benchmarks.experiment_infrastructure_validation.sut import (
    apply_patch,
    classify_mapping,
    run_test,
    split_outcomes,
    run_program,
)


def test_fixture_two_stage_failure(tmp_path):
    workspace = copy_val_workspace(tmp_path / "ws")
    session = new_session(workspace)
    assert session["initial_outcomes"]["test_pass"] is False
    apply_patch(workspace, "config.py", PARTIAL_CONFIG)
    pytest_run = run_test(workspace)
    program_run = run_program(workspace)
    assert split_outcomes(pytest_run, program_run)["test_pass"] is False
    apply_patch(workspace, "config.py", FULL_CONFIG)
    pytest_run = run_test(workspace)
    program_run = run_program(workspace)
    assert split_outcomes(pytest_run, program_run)["test_pass"] is True


def test_mapping_case1_helper_confirm():
    case = MAPPING_CASES[0]
    mapping = classify_mapping(case["judgment"], KNOWN_FILES)
    compared = compare_mapping(case["expected_calls"], mapping)
    assert compared["actual_call"]["tool_name"] == "read_file"
    assert compared["actual_call"]["tool_arguments"]["path"] == "helper.py"


def test_state_keeps_previous_read(tmp_path):
    workspace = copy_val_workspace(tmp_path / "ws")
    session = new_session(workspace)
    first = run_fixed_turn(session, 1, "helper.py を確認する", [{"tool_name": "read_file", "tool_arguments": {"path": "helper.py"}}])
    second = run_fixed_turn(session, 2, "config.py を確認する", [{"tool_name": "read_file", "tool_arguments": {"path": "config.py"}}])
    assert first["files_read_so_far"] == ["helper.py"]
    assert "helper.py" in second["files_read_so_far"]
    assert "config.py" in second["files_read_so_far"]


def test_patch_does_not_change_other_files(tmp_path):
    workspace = copy_val_workspace(tmp_path / "ws")
    new_session(workspace)
    helper = (workspace / "helper.py").read_text(encoding="utf-8")
    apply_patch(workspace, "config.py", FULL_CONFIG)
    assert (workspace / "helper.py").read_text(encoding="utf-8") == helper
    assert (workspace / "config.py").read_text(encoding="utf-8") == FULL_CONFIG
