#!/usr/bin/env python3
"""Run Web Tool Extraction Normalization Experiment."""
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
from ai_tool.web_tool_extraction_normalization_experiment import run_extraction_normalization_experiment
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_extraction_normalization_experiment"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
PROFILE = "qwen3_8b"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Extraction Normalization Experiment - starting ({RUN_ID})")

    ok, _ = ollama_available()
    llm_enabled = ok
    chat = None
    model = ""
    if llm_enabled:
        prev = os.environ.get("AI_AGENT_MODEL")
        os.environ["AI_AGENT_MODEL"] = PROFILE
        import tools.system.llm as llm_mod

        llm_mod._client = None
        profile = get_llm_profile(PROFILE)
        model = str(profile.get("model") or "")
        chat = live_chat_fn()
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        llm_mod._client = None

    result = run_extraction_normalization_experiment(
        fetch_live=True,
        llm_enabled=llm_enabled,
        chat_fn=chat,
        model=model,
    )
    result["run_id"] = RUN_ID

    (RUN_DIR / "observations.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "golden_transactions.json").write_text(
        json.dumps(result.get("golden_transactions") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "overall": result.get("overall"),
                "best_candidate": result.get("best_candidate"),
                "stop": result.get("stop"),
                "git_head": result.get("git_head"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "decision_log.json").write_text(
        json.dumps(result.get("decision_log") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "proposed_changes.json").write_text(
        json.dumps(result.get("proposed_production_changes") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "human_review_packet.json").write_text(
        json.dumps(result.get("human_review_packet") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "llm_utilization.json").write_text(
        json.dumps(result.get("llm_utilization") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/ai_tool/experimental/test_extraction_prototype.py",
            "tests/ai_tool/project_audit/test_web_tool_extraction_normalization_experiment.py",
            "-q",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "best_candidate": result.get("best_candidate"),
                "llm_enabled": llm_enabled,
                "pytest_exit": proc.returncode,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
