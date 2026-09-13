from research.llm_benchmarks.judgment_layer_llm_connection_experiment.bridge import parse_judgment
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.execute import run_scripted
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.failure_cases import (
    FAIL1,
    FAIL2,
    FAIL3,
    FAIL4,
    FAIL5,
    KNOWN,
)
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.naive import naive_select
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.workspace import (
    copy_fixture,
    git_init_workspace,
    run_program,
    run_test,
)


def _names(parsed):
    return [item["tool_name"] for item in parsed["selected_actions"]]


def test_naive_fail1_cannot_see_confirm():
    naive = naive_select(FAIL1, KNOWN)
    assert naive["selected_actions"] == []
    assert naive["mapping_status"] == "unrecognized"


def test_naive_fail2_cannot_see_run_again():
    naive = naive_select(FAIL2, KNOWN)
    assert naive["selected_actions"] == []


def test_naive_fail3_does_not_keep_both_actions():
    naive = naive_select(FAIL3, KNOWN)
    names = [item["tool_name"] for item in naive["selected_actions"]]
    assert names != ["read_file", "run_test"]
    assert len(names) <= 1


def test_naive_fail4_fence_tokens_trigger():
    naive = naive_select(FAIL4, KNOWN)
    names = [item["tool_name"] for item in naive["selected_actions"]]
    assert "apply_patch" in names or "run_test" in names


def test_naive_fail5_only_one_tool():
    naive = naive_select("helper.pyを読む。config.pyを読む。", KNOWN)
    assert len(naive["selected_actions"]) == 1
    assert naive["selected_actions"][0]["tool_name"] == "read_file"


def test_bridge_fail1_confirm_helper():
    parsed = parse_judgment(FAIL1, KNOWN)
    assert _names(parsed)[0] == "read_file"
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "helper.py"


def test_bridge_fail2_run_test_again():
    parsed = parse_judgment(FAIL2, KNOWN)
    assert _names(parsed) == ["run_test"]


def test_bridge_fail3_both_in_order():
    parsed = parse_judgment(FAIL3, KNOWN)
    assert _names(parsed) == ["read_file", "run_test"]


def test_bridge_fail4_ignores_fence_tokens():
    parsed = parse_judgment(FAIL4, KNOWN)
    assert _names(parsed) == ["read_file"]
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "helper.py"


def test_bridge_fail5_two_reads():
    parsed = parse_judgment(FAIL5, KNOWN)
    paths = [item["tool_arguments"]["path"] for item in parsed["selected_actions"]]
    assert paths == ["helper.py", "config.py"]


def test_bridge_ambiguous_stops():
    parsed = parse_judgment("もう少し調べる必要がある", KNOWN)
    assert parsed["selected_actions"] == []
    assert parsed["mapping_status"] in ("needs_clarification", "mapping_gap")


def test_real_failure_to_tool(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    pytest_run = run_test(workspace)
    program_run = run_program(workspace)
    assert pytest_run["exit_code"] != 0
    assert program_run["exit_code"] != 0
    parsed = parse_judgment("helper.pyを確認したい。", KNOWN)
    steps = run_scripted(workspace, parsed["selected_actions"])
    assert steps[0]["execution_status"] == "ok"
    assert "load_items" in steps[0]["next_input"]
