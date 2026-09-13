"""実験1–8。既存結果は読むだけ。既存実験コードは変更しない。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.mapping_harness_validation.observe import (
    KNOWN_ORDER_LIVE,
    compare_expected,
    map_text,
)
from research.llm_benchmarks.mapping_harness_validation.pipeline import (
    copy_val_workspace,
    execute_mapped,
    return_test_failure_text,
)


OUT_DIR = Path("research/llm_benchmarks/mapping_harness_validation/results")
PAST_GEMMA = Path(
    "research/llm_benchmarks/judgment_loop_min_experiment/results/"
    "20260901T024054Z/gemma3_12b/run.json"
)
PAST_QWEN = Path(
    "research/llm_benchmarks/judgment_loop_min_experiment/results/"
    "20260901T024054Z/qwen3_14b/run.json"
)

FIXED = [
    {
        "id": "inspect_helper",
        "text": "I need to inspect helper.py before making a change.",
        "expected_tool": "read_file",
        "expected_args": {"path": "helper.py"},
    },
    {
        "id": "inspect_main",
        "text": "I need to inspect main.py.",
        "expected_tool": "read_file",
        "expected_args": {"path": "main.py"},
    },
    {
        "id": "inspect_config",
        "text": "I need to inspect config.py.",
        "expected_tool": "read_file",
        "expected_args": {"path": "config.py"},
    },
    {
        "id": "run_pytest",
        "text": "I need to run pytest again.",
        "expected_tool": "run_test",
        "expected_args": {},
    },
    {
        "id": "apply_helper",
        "text": (
            "I need to apply a patch to helper.py.\n"
            "helper.py\n"
            "```python\nVALUE = 8\n```\n"
        ),
        "expected_tool": "apply_patch",
        "expected_args": {"path": "helper.py", "content": "VALUE = 8\n"},
    },
]

MULTI = """The error is caused by an invalid index.

I need to inspect helper.py.

After that I may need to run the tests again.

The likely fix is to change the index.
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_turn_raw(path: Path, turn_id):
    payload = json.loads(path.read_text(encoding="utf-8"))
    for turn in payload.get("turns") or []:
        if turn.get("turn_id") == turn_id:
            return turn.get("raw_output") or ""
    return ""


def experiment_1_and_2():
    rows = []
    for case in FIXED:
        observed = map_text(case["text"])
        compared = compare_expected(observed, case["expected_tool"], case["expected_args"])
        rows.append(
            {
                "case_id": case["id"],
                "judgment": case["text"],
                **observed,
                **compared,
                "judgment_correct": "NOT_APPLICABLE_FIXED_TEXT",
                "extraction_correct": observed["extraction_step_exists"] is False
                and compared["mapping_match"],
                "mapping_correct": compared["mapping_match"],
            }
        )
    return rows


def experiment_3_and_4():
    rows = []
    for label, path in (("gemma_turn1", PAST_GEMMA), ("qwen_turn1", PAST_QWEN)):
        raw = _load_turn_raw(path, 1)
        observed = map_text(raw)
        rows.append(
            {
                "case_id": label,
                "source": str(path),
                "judgment_correct": "NOT_EVALUATED_HERE",
                **observed,
                "expected_tool": "read_file",
                "actual_tool": observed["tool_name"],
                "mapping_match": observed["tool_name"] == "read_file",
            }
        )
    return rows


def experiment_5():
    observed = map_text(MULTI)
    return {
        "raw_llm_output": MULTI,
        **observed,
        "now_vs_later_distinguished": False,
        "note": "inspect helper.py と run the tests again が同一入力に共存する。現行 Mapping は全文を走査する。",
        "expected_immediate": "read_file",
        "actual_tool": observed["tool_name"],
        "mapping_match": observed["tool_name"] == "read_file",
    }


def experiment_6_and_7(workspace: Path):
    mapped = {
        "tool": "read_file",
        "path": "helper.py",
    }
    executed = execute_mapped(workspace, "read_file", {"path": "helper.py"})
    execution_match = (
        executed["dispatched_name"] == "read_file"
        and executed["tool_arguments"] == {"path": "helper.py"}
        and (executed["tool_result"] or {}).get("ok") is True
        and "VALUE = 7" in ((executed["tool_result"] or {}).get("text") or "")
        and "You asked to inspect helper.py" in executed["next_llm_input"]
        and "VALUE = 7" in executed["next_llm_input"]
    )
    pytest_run = {
        "exit_code": 1,
        "stdout": "AssertionError: store",
        "stderr": "",
        "traceback": "Traceback (most recent call last):\nIndexError\n",
        "command": ["pytest"],
    }
    program_run = {
        "command": ["python", "main.py"],
        "exit_code": 0,
        "stdout": "{}",
        "stderr": "",
        "traceback": "",
    }
    returned = return_test_failure_text(pytest_run, program_run)
    return {
        "mapping_result_fixed": mapped,
        "execution": executed,
        "execution_match": execution_match,
        "execution_correct": execution_match,
        "return_correct": (
            returned["has_exit_code"]
            and returned["has_stdout"]
            and returned["has_traceback"]
            and not returned["directs_other_file"]
        ),
        "test_return": returned,
    }


def experiment_8_fixed_pipeline(workspace: Path):
    text = "I need to inspect helper.py before making a change."
    observed = map_text(text, ["helper.py", "main.py", "tests/test_main.py"])
    compared = compare_expected(observed, "read_file", {"path": "helper.py"})
    executed = None
    execution_match = False
    if compared["mapping_match"]:
        executed = execute_mapped(workspace, observed["tool_name"], observed["tool_arguments"])
        execution_match = (
            executed["dispatched_name"] == "read_file"
            and "VALUE = 7" in executed["next_llm_input"]
        )
    return {
        "raw_llm_output": text,
        **observed,
        **compared,
        "tool_result": None if executed is None else executed["tool_result"],
        "next_llm_input": None if executed is None else executed["next_llm_input"],
        "execution_match": execution_match,
        "minimum_success": compared["mapping_match"] and execution_match,
    }


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    workspace = copy_val_workspace(root / "workspace")
    payload = {
        "experiment_id": "mapping_harness_validation",
        "at": _now(),
        "sut": "research.llm_benchmarks.judgment_loop_min_experiment.mapping.classify_mapping",
        "extraction_layer": "NOT_IMPLEMENTED",
        "experiment_1_2_fixed_judgments": experiment_1_and_2(),
        "experiment_3_4_past_llm": experiment_3_and_4(),
        "experiment_5_multiple_actions": experiment_5(),
        "experiment_6_7_execution_return": experiment_6_and_7(workspace),
        "experiment_8_fixed_pipeline": experiment_8_fixed_pipeline(workspace),
        "experiment_8_llm": "NOT_RUN_IN_THIS_FUNCTION",
    }
    save_json(root / "run.json", payload)
    print(f"wrote {root}", flush=True)
    e12 = payload["experiment_1_2_fixed_judgments"]
    print(
        "fixed_match="
        + str(all(item["mapping_match"] for item in e12)),
        flush=True,
    )
    print(
        "gemma_actual="
        + str(payload["experiment_3_4_past_llm"][0]["actual_tool"]),
        flush=True,
    )
    print(
        "multi_actual="
        + str(payload["experiment_5_multiple_actions"]["actual_tool"]),
        flush=True,
    )
    print(
        "pipeline_ok="
        + str(payload["experiment_8_fixed_pipeline"]["minimum_success"]),
        flush=True,
    )
    return root


if __name__ == "__main__":
    main()
