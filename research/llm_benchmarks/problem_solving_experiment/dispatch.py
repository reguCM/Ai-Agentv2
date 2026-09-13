"""実験 Tool 実行。本番 execute_tool / Registry には接続しない。"""

from __future__ import annotations

from research.llm_benchmarks.problem_solving_experiment.catalog import by_name


def dispatch(name, arguments=None):
    arguments = arguments or {}
    tools = by_name()
    item = tools.get(name)
    if item is None:
        return {"ok": False, "error": f"unknown_experiment_tool:{name}"}
    handler = item["handler"]
    try:
        return handler(**arguments)
    except TypeError as exc:
        return {"ok": False, "error": f"TypeError:{exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
