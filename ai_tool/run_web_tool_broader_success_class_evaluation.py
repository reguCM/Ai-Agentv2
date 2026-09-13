#!/usr/bin/env python3
"""Run Broader Success-Class Evaluation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import live_chat_fn, ollama_available
from ai_tool.web_tool_broader_success_class_evaluation import run_broader_success_class_evaluation
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_broader_success_class_evaluation"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    ok, _ = ollama_available()
    chat = None
    model = ""
    if ok:
        prev = os.environ.get("AI_AGENT_MODEL")
        os.environ["AI_AGENT_MODEL"] = "qwen3_8b"
        import tools.system.llm as llm_mod

        llm_mod._client = None
        model = str(get_llm_profile("qwen3_8b").get("model") or "")
        chat = live_chat_fn()
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        llm_mod._client = None

    result = run_broader_success_class_evaluation(
        include_live=True,
        llm_enabled=ok,
        chat_fn=chat,
        model=model,
    )
    result["run_id"] = RUN_ID
    result["llm_enabled"] = ok
    result["model"] = model if ok else "mock-only"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_web_tool_broader_success_class_evaluation.py",
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
                "selected_option": result.get("selected_option"),
                "mechanical_answer": result.get("mechanical_answer"),
                "failure_rates": result.get("failure_rates"),
                "production_changes": result.get("production_changes"),
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
    rates = result.get("failure_rates") or {}
    (RUN_DIR / "diagnosis.json").write_text(
        json.dumps(
            {
                "confirmed_causes": result.get("confirmed_causes"),
                "hypotheses": result.get("hypotheses"),
                "unknowns": result.get("unknowns"),
                "web_vs_llm": {
                    "web_failure_count": rates.get("web_failure_count"),
                    "llm_failure_count": rates.get("llm_failure_count"),
                    "web_failure_cases": rates.get("web_failure_cases"),
                    "llm_failure_cases": rates.get("llm_failure_cases"),
                },
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
                "decision": result.get("decision"),
                "accuracy": (result.get("failure_rates") or {}).get("accuracy_rate"),
                "selected": result.get("selected_option"),
                "mechanical": result.get("mechanical_answer"),
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 and result.get("overall") != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
