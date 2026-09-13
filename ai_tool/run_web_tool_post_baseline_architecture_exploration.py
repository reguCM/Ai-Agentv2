#!/usr/bin/env python3
"""Run Post-Baseline Architecture Exploration."""
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
from ai_tool.web_tool_post_baseline_architecture_exploration import run_post_baseline_exploration
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_post_baseline_architecture_exploration"
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

    result = run_post_baseline_exploration(
        fetch_live=True, llm_enabled=ok, chat_fn=chat, model=model,
    )
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/experimental/test_read_url_evidence.py",
            "tests/ai_tool/project_audit/test_web_tool_post_baseline_architecture_exploration.py",
            "-q", "--tb=no",
        ],
        cwd=_REPO, capture_output=True, text=True,
    )
    result["pytest_exit"] = proc.returncode
    result["pytest_output"] = proc.stdout + proc.stderr

    (RUN_DIR / "observations.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "selected_option": result.get("selected_option"),
                "stop_reason": result.get("stop_reason"),
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

    print(json.dumps({
        "run_id": RUN_ID,
        "overall": result.get("overall"),
        "selected": result.get("selected_option"),
        "stop": result.get("stop_reason"),
        "pytest": proc.returncode,
    }, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
