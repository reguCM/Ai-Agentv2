"""検証観測。SUT の Mapping は変更しない。抽出ステップが無いことを記録する。"""

from __future__ import annotations

import re

from research.llm_benchmarks.judgment_loop_min_experiment import mapping as sut_mapping


KNOWN_ORDER_LIVE = [
    "main.py",
    "helper.py",
    "config.py",
    "store.py",
    "tests/test_main.py",
]


def observe_pattern_hits(text):
    hits = []
    patterns = {
        "INSPECT": sut_mapping.INSPECT,
        "TEST_HINT": sut_mapping.TEST_HINT,
        "PROGRAM_HINT": sut_mapping.PROGRAM_HINT,
        "LIST_HINT": sut_mapping.LIST_HINT,
        "WRITE_HINT": sut_mapping.WRITE_HINT,
        "ORIGIN_HINT": sut_mapping.ORIGIN_HINT,
    }
    for name, regex in patterns.items():
        for match in regex.finditer(text or ""):
            hits.append(
                {
                    "pattern": name,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "window": (text or "")[max(0, match.start() - 40) : match.end() + 40],
                }
            )
    return sorted(hits, key=lambda item: item["start"])


def map_text(text, known_files=None):
    known = known_files or KNOWN_ORDER_LIVE
    mapping = sut_mapping.classify_mapping(text, known)
    execute = mapping.get("execute")
    return {
        "extraction_step_exists": False,
        "extraction_note": "現行ハーネスは抽出層が無く、raw_output 全体を Mapping に渡す。",
        "raw_llm_output": text,
        "extracted_candidates": mapping.get("candidates"),
        "selected_judgment": execute,
        "mapping_input": text,
        "mapping_output": mapping.get("mapping_output"),
        "tool_name": None if execute is None else execute.get("tool_name"),
        "tool_arguments": None if execute is None else execute.get("tool_arguments"),
        "pattern_hits": observe_pattern_hits(text),
        "candidate_count": len(mapping.get("candidates") or []),
        "executable_count": len([item for item in (mapping.get("candidates") or []) if item.get("execute")]),
        "adopt_reason": None if execute is None else execute.get("reason"),
        "mapping_status": mapping.get("mapping_status"),
        "mapping": mapping,
    }


def compare_expected(observed, expected_tool, expected_args=None):
    actual_tool = observed.get("tool_name")
    actual_args = observed.get("tool_arguments")
    args_ok = True
    if expected_args is not None:
        args_ok = actual_args == expected_args
    match = actual_tool == expected_tool and args_ok
    return {
        "expected_tool": expected_tool,
        "actual_tool": actual_tool,
        "expected_arguments": expected_args,
        "actual_arguments": actual_args,
        "mapping_match": match,
    }
