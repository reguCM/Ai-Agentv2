"""
検証が呼ぶ既存実装の入口。既存ファイルは書き換えない。
copy_fixture は order_live を使うため呼ばない。
"""

from research.llm_benchmarks.judgment_loop_min_experiment.bench import sent_for_tool
from research.llm_benchmarks.judgment_loop_min_experiment.execute import (
    format_execution_block,
    format_file_result,
    format_test_failure,
    run_program,
    run_test,
    split_outcomes,
)
from research.llm_benchmarks.judgment_loop_min_experiment.mapping import classify_mapping
from research.llm_benchmarks.judgment_loop_min_experiment.workspace import (
    apply_patch,
    dispatch,
    dump_result,
    git_diff,
    git_init_workspace,
    read_file,
    workspace_filenames,
)

SUT = {
    "mapping": "research.llm_benchmarks.judgment_loop_min_experiment.mapping.classify_mapping",
    "dispatch": "research.llm_benchmarks.judgment_loop_min_experiment.workspace.dispatch",
    "sent_for_tool": "research.llm_benchmarks.judgment_loop_min_experiment.bench.sent_for_tool",
    "run_test": "research.llm_benchmarks.judgment_loop_min_experiment.execute.run_test",
    "format_test_failure": "research.llm_benchmarks.judgment_loop_min_experiment.execute.format_test_failure",
    "copy_fixture": "not_called",
    "agent": "not_connected",
    "registry": "not_connected",
}
