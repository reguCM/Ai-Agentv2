"""実験 Tool の単体確認。Ollama は使わない。本番経路は変更しない。"""

from __future__ import annotations

import json
from pathlib import Path

from research.llm_benchmarks.problem_solving_experiment import adapters
from research.llm_benchmarks.problem_solving_experiment.dispatch import dispatch


def _ok(result):
    if not isinstance(result, dict):
        return False
    if result.get("help_requested"):
        return True
    if result.get("error") == "pdf_library_not_installed":
        return True
    if "ok" in result:
        return result.get("ok") is True or result.get("error") == "pdf_library_not_installed"
    if result.get("status") in ("ok", "pass", "partial", "unavailable"):
        return True
    if "lines" in result or "matches" in result or "entries" in result:
        return result.get("error") is None or result.get("ok") is True
    if "diff" in result or "diff_stat" in result:
        return bool(result.get("ok"))
    return False


def main():
    adapters.set_session(
        tool_name="cpu_status",
        source="def cpu_status():\n    return {'status': rows[2]}\n",
        test_result={
            "status": "fail",
            "error_type": "IndexError",
            "error": "list index out of range",
            "traceback": "Traceback (smoke)\n",
        },
        validation={"status": "fail", "errors": ["runtime"], "warning_items": []},
    )
    checks = [
        ("get_current_failure", {}),
        ("read_file", {"path": "registry/tools.json", "offset": 1, "limit": 5}),
        ("search_files", {"query": "def cpu_status", "path": "tools/system/cpu", "glob": "*.py"}),
        ("list_files", {"path": "tools/system/cpu", "recursive": False}),
        ("get_execution_environment", {}),
        ("get_gpu_status", {}),
        ("get_gpu_processes", {}),
        ("read_git_diff", {}),
        ("request_human_help", {"reason": "smoke", "questions": ["ok?"]}),
        (
            "experiment_test_source",
            {
                "source": "def cpu_status():\n    rows = ['a']\n    return {'status': rows[2]}\n"
            },
        ),
        ("read_pdf", {"path": "registry/tools.json"}),
    ]
    rows = []
    for name, args in checks:
        result = dispatch(name, args)
        rows.append(
            {
                "name": name,
                "callable": True,
                "ok_or_expected": _ok(result)
                or (
                    name == "read_pdf" and isinstance(result, dict)
                )
                or (
                    name == "experiment_test_source"
                    and isinstance(result, dict)
                    and result.get("error_type") == "IndexError"
                ),
                "result_keys": sorted(result.keys()) if isinstance(result, dict) else type(result).__name__,
                "error": (result or {}).get("error") if isinstance(result, dict) else None,
            }
        )
        print(f"{name}: error={rows[-1]['error']} keys={rows[-1]['result_keys']}")
    out = Path("research/llm_benchmarks/problem_solving_experiment/smoke_result.json")
    out.write_text(json.dumps({"checks": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    failed = [r for r in rows if not r["ok_or_expected"] and r["name"] not in ("read_pdf",)]
    # GPU may be unavailable; still callable
    hard = []
    for r in rows:
        if r["name"] in ("get_gpu_status", "get_gpu_processes"):
            continue
        if r["name"] == "read_pdf":
            continue
        if r["name"] == "read_git_diff":
            continue
        if not r["ok_or_expected"]:
            hard.append(r["name"])
    if hard:
        raise SystemExit("smoke failed: " + ",".join(hard))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
