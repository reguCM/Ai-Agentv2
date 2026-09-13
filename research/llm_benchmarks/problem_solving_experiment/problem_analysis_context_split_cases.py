"""
切り分け実験の入力。traceback / source は fixture から。会話は前回文脈実験の固定文を改変せず使う。
新しい架空 traceback / source / 会話は作らない。
"""

from __future__ import annotations

import json
import traceback

from tests.fixtures.broken_tools import SOURCE_INDEX_ERROR
from research.llm_benchmarks.problem_solving_experiment.problem_analysis_bench import (
    CASES as FAILURE_CASES,
)
from research.llm_benchmarks.problem_solving_experiment.problem_analysis_context_cases import (
    CASES as CONTEXT_CASES,
)


PROMPT_HEADER = """Analyze the problem below.
Do not fix the problem.
Do not use tools."""

CONDITIONS = ("F1", "F2", "F3", "F4", "F5")


def _context_by_letter():
    return {item["letter"]: item for item in CONTEXT_CASES}


def _traceback_for_a():
    namespace = {}
    compiled = compile(SOURCE_INDEX_ERROR, "cpu_status.py", "exec")
    exec(compiled, namespace)
    try:
        namespace["cpu_status"]()
    except IndexError:
        return traceback.format_exc().rstrip()
    return "NOT_RECORDED"


def extras_for(letter):
    ctx = _context_by_letter()[letter]
    if ctx["has_source"]:
        tb = _traceback_for_a()
        source = ctx["source"].rstrip() + "\n"
    else:
        tb = "NOT_RECORDED"
        source = "NOT_RECORDED"
    return {
        "traceback": tb,
        "source": source,
        "conversation": ctx["conversation"],
        "conversation_provenance": "problem_analysis_context_cases.py (previous context experiment fixture, not live chat)",
        "has_source": ctx["has_source"],
    }


def failure_for(letter):
    for item in FAILURE_CASES:
        if item["id"].startswith(letter + "_"):
            return item["failure"], item["id"]
    raise KeyError(letter)


def build_input(letter, condition):
    if condition not in CONDITIONS:
        raise ValueError(condition)
    failure, case_id = failure_for(letter)
    extra = extras_for(letter)
    parts = [PROMPT_HEADER, "", json.dumps(failure, ensure_ascii=False, indent=2)]
    if condition in ("F2", "F4"):
        parts.extend(["", "traceback:", extra["traceback"]])
    if condition in ("F3", "F4"):
        parts.extend(["", "source:", extra["source"].rstrip()])
    if condition == "F5":
        parts.extend(["", "conversation:", extra["conversation"]])
    return {
        "case_id": case_id,
        "letter": letter,
        "condition": condition,
        "failure": failure,
        "prompt": "\n".join(parts) + "\n",
        "extras": {
            "traceback_included": condition in ("F2", "F4"),
            "source_included": condition in ("F3", "F4"),
            "conversation_included": condition == "F5",
            "traceback_recorded": extra["has_source"],
            "source_recorded": extra["has_source"],
            "conversation_provenance": extra["conversation_provenance"],
        },
    }
