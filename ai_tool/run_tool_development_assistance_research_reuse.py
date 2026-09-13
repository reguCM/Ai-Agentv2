#!/usr/bin/env python3
"""Run Phase E — Research Reuse & Hierarchical Capability Discovery."""
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
from ai_tool.experimental.development_assistance.research_reuse_harness import run_phase_e
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_tool_development_assistance_research_reuse"
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
        model = str(get_llm_profile("qwen3_8b").get("model") or "qwen3:8b")
        chat = live_chat_fn()
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        llm_mod._client = None

    result = run_phase_e(chat_fn=chat, model=model, llm_enabled=ok)
    result["run_id"] = RUN_ID
    result["llm_enabled"] = ok

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/ai_tool/project_audit/test_tool_development_assistance_poc.py",
            "tests/ai_tool/project_audit/test_tool_development_assistance_decision_support.py",
            "tests/ai_tool/project_audit/test_tool_development_assistance_research_reuse.py",
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
                "pass_count": result.get("pass_count"),
                "research_reuse_summary": result.get("research_reuse_summary"),
                "search_reduction": result.get("search_reduction"),
                "final_questions": result.get("final_questions"),
                "standard_workflow_recommended": result.get("standard_workflow_recommended"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Phase E Research Reuse: {result.get('pass_count')}/{result.get('total')} PASS")
    print(f"Decision: {result.get('decision')}")
    print(f"Search reduction: {result.get('search_reduction')}")
    print(f"Run dir: {RUN_DIR}")
    return 0 if result.get("pass_count") == result.get("total") and proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
