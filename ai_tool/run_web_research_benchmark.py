#!/usr/bin/env python3
"""Run Web Research Benchmark — investigation only."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_research_benchmark import run_web_research_benchmark

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_research_benchmark"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_web_research_benchmark()
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/ai_tool/project_audit/test_web_research_benchmark.py",
            "tests/ai_tool/project_audit/test_defensive_core_discovery_policy.py",
            "-q",
            "--tb=no",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    result["pytest_exit"] = proc.returncode
    result["pytest_output"] = proc.stdout + proc.stderr

    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "benchmark_result": result.get("benchmark_result"),
                "decision": result.get("decision"),
                "overall": result.get("overall"),
                "golden": (result.get("golden_baseline") or {}).get("overall"),
                "self_pass_rate": (result.get("self_benchmark") or {}).get("aggregate", {}).get(
                    "tool_layer_pass_rate"
                ),
                "production_changes": result.get("production_changes"),
                "human_review_required": result.get("human_review_required"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "benchmark_result": result.get("benchmark_result"),
                "golden": (result.get("golden_baseline") or {}).get("overall"),
                "self_pass_rate": (result.get("self_benchmark") or {}).get("aggregate", {}).get(
                    "tool_layer_pass_rate"
                ),
                "external": (result.get("external_targets") or {}).get("comparison_mode"),
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 and result.get("overall") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
