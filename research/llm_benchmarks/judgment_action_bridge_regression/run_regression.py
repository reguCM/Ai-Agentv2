"""一次資料を results/<timestamp>/ へ保存する。LLM は呼ばない。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.judgment_action_bridge_regression.bridge import process
from research.llm_benchmarks.judgment_action_bridge_regression.fixed_inputs import (
    CASE_A_READ_HELPER,
    CASE_B_PATCH_NO_FILE,
    CASE_C_OPEN_MODIFY_RUN,
    CASE_D_RUN_TEST_AGAIN,
    CASE_E_FENCE_TOKENS,
    CYCLE_TEXTS,
    GEMMA_SOURCE,
    GEMMA_T4_RAW,
    GEMMA_T5_RAW,
    KNOWN,
    MULTI_READ_THEN_TEST,
    READY_NOT_READ,
    RUN_THE_TESTS_AGAIN,
    SEARCH_FIELD_COUNT,
)
from research.llm_benchmarks.judgment_action_bridge_regression.old_mapping import (
    old_mapping_select,
)
from research.llm_benchmarks.judgment_action_bridge_regression.tool_adapter import (
    copy_fixture,
    git_init_workspace,
)


OUT_ROOT = Path("research/llm_benchmarks/judgment_action_bridge_regression/results")


def _dump_process(parsed):
    return {
        "input_text": parsed["input_text"],
        "clauses": parsed["clauses"],
        "mapping_status": parsed["mapping_status"],
        "flags": parsed["flags"],
        "action_candidates": parsed["action_candidates"],
        "selected_actions": parsed["selected_actions"],
        "steps": [
            {
                "step_id": item["step_id"],
                "parsed_intent": item["parsed_intent"],
                "tool_name": item["tool_name"],
                "tool_arguments": item["tool_arguments"],
                "execution_status": item["execution_status"],
                "next_input": item["next_input"],
                "execution_success": item["execution_success"],
                "result_return_success": item["result_return_success"],
                "tool_result": item["tool_result"],
            }
            for item in parsed["steps"]
        ],
    }


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = OUT_ROOT / stamp
    dest.mkdir(parents=True, exist_ok=True)
    cases = {
        "A_read_helper": CASE_A_READ_HELPER,
        "B_patch_no_file": CASE_B_PATCH_NO_FILE,
        "C_open_modify_run": CASE_C_OPEN_MODIFY_RUN,
        "D_run_test_again": CASE_D_RUN_TEST_AGAIN,
        "E_fence_tokens": CASE_E_FENCE_TOKENS,
        "search_field_count": SEARCH_FIELD_COUNT,
        "multi_read_then_test": MULTI_READ_THEN_TEST,
        "ready_not_read": READY_NOT_READ,
        "run_the_tests_again": RUN_THE_TESTS_AGAIN,
        "gemma_t4": GEMMA_T4_RAW,
        "gemma_t5": GEMMA_T5_RAW,
    }
    comparison = []
    for name, text in cases.items():
        old = old_mapping_select(text, KNOWN)
        parsed = process(text, KNOWN)
        comparison.append(
            {
                "case": name,
                "text": text,
                "old_mapping": {
                    "mapping_status": old["mapping_status"],
                    "selected_actions": old["selected_actions"],
                },
                "new_bridge": _dump_process(parsed),
            }
        )
    cycle_ws = copy_fixture(dest / "cycle_workspace")
    git_init_workspace(cycle_ws)
    cycle = []
    for text in CYCLE_TEXTS:
        parsed = process(text, KNOWN, workspace=cycle_ws, execute=True)
        cycle.append(_dump_process(parsed))
    gemma_ws = copy_fixture(dest / "gemma_t5_workspace")
    git_init_workspace(gemma_ws)
    gemma_t5 = process(GEMMA_T5_RAW, KNOWN, workspace=gemma_ws, execute=True)
    payload = {
        "experiment_id": "judgment_action_bridge_regression",
        "at": datetime.now(timezone.utc).isoformat(),
        "native_tools": False,
        "llm_used": False,
        "gemma_source": GEMMA_SOURCE,
        "comparison": comparison,
        "cycle": cycle,
        "gemma_t5_executed": _dump_process(gemma_t5),
        "cycle_config_after": (cycle_ws / "config.py").read_text(encoding="utf-8"),
        "cycle_final_pytest_exit": cycle[-1]["steps"][-1]["tool_result"]["exit_code"]
        if cycle and cycle[-1]["steps"]
        else None,
    }
    (dest / "run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(dest)


if __name__ == "__main__":
    main()
