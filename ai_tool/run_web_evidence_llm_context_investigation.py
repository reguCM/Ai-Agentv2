#!/usr/bin/env python3
"""Run Web Evidence → LLM Context Architecture Investigation."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_evidence_llm_context_investigation import (
    run_web_evidence_llm_context_investigation,
)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_evidence_llm_context_investigation"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_web_evidence_llm_context_investigation(fetch_live_baseline=False)
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_web_evidence_llm_context_investigation.py",
            "tests/ai_tool/project_audit/test_web_tool_success_class_accuracy_evaluation.py",
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
                "decision": result.get("decision"),
                "stop_raw_sufficient": result.get("stop_raw_sufficient"),
                "best_format_proxy": result.get("best_format_proxy"),
                "aggregate": (result.get("investigation_a_format_comparison") or {}).get("aggregate"),
                "production_changes": result.get("production_changes"),
                "human_review_required": result.get("human_review_required"),
                "overall": result.get("overall"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "architecture_options.json").write_text(
        json.dumps(result.get("architecture_options") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "core_capability_discovery.json").write_text(
        json.dumps(result.get("core_capability_discovery") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    agg = (result.get("investigation_a_format_comparison") or {}).get("aggregate") or {}
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "decision": result.get("decision"),
                "stop_raw_sufficient": result.get("stop_raw_sufficient"),
                "best_format_proxy": result.get("best_format_proxy"),
                "format_accuracy": {k: v.get("accuracy") for k, v in agg.items()},
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
