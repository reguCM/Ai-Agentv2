#!/usr/bin/env python3
"""Run Tool Development Assistance Capability Discovery (Phase C)."""
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
from ai_tool.experimental.development_assistance.capability_discovery import run_capability_discovery
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_tool_development_assistance_capability_discovery"
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

    result = run_capability_discovery(
        chat_fn=chat,
        model=model,
        llm_enabled=ok,
        fetch_live_baseline=False,
    )
    result["run_id"] = RUN_ID
    result["llm_enabled"] = ok

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_tool_development_assistance_capability_discovery.py",
            "tests/ai_tool/project_audit/test_tool_development_assistance_poc.py",
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
                "c3_candidate": result.get("c3_candidate"),
                "c3_implemented": result.get("c3_implemented"),
                "lifecycle_summary": result.get("lifecycle_summary"),
                "catalog_evaluation": result.get("catalog_evaluation"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "decision": result.get("decision"),
                "observation_count": result.get("observation_count"),
                "lifecycle_summary": result.get("lifecycle_summary"),
                "c3_candidate": (result.get("c3_candidate") or {}).get("c3_name"),
                "c3_implemented": result.get("c3_implemented"),
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
