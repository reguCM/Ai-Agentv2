#!/usr/bin/env python3
"""Run Web Tool Search Hardening probe (read-only design phase)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_search_hardening_probe import run_search_hardening_probe

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_search_hardening_probe"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Web Tool Search Hardening probe - starting ({RUN_ID})")

    result = run_search_hardening_probe()
    result["run_id"] = RUN_ID
    result["git_head"] = _git_head()

    probes = result["probe_queries"]
    serializable = result.copy()
    serializable["probe_queries"] = [p.to_dict() for p in probes]

    (RUN_DIR / "probe_results.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "osaka_comparison.json").write_text(
        json.dumps(result["osaka_variant_comparison"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "ddg_raw_matrix.json").write_text(
        json.dumps(result["duckduckgo_raw_matrix"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "success_criteria.json").write_text(
        json.dumps(result["success_criteria_mapping"], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/project_audit/test_web_tool_search_hardening_design.py", "-q"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest_output.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    summary = {
        "run_id": RUN_ID,
        "osaka_comparison": result["osaka_variant_comparison"],
        "success_criteria": result["success_criteria_mapping"],
        "pytest_exit": proc.returncode,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
