#!/usr/bin/env python3
"""Run Web Evidence → Live LLM Context Format Shootout."""
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
from ai_tool.web_evidence_live_llm_context_shootout import run_web_evidence_live_llm_context_shootout
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_evidence_live_llm_context_shootout"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    ok, ollama_err = ollama_available()
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

    result = run_web_evidence_live_llm_context_shootout(
        chat_fn=chat,
        model=model,
        llm_enabled=ok,
        fetch_live_baseline=False,
    )
    result["run_id"] = RUN_ID
    if not ok:
        result["ollama_error"] = ollama_err

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_web_evidence_live_llm_context_shootout.py",
            "tests/ai_tool/project_audit/test_web_evidence_llm_context_investigation.py",
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
        json.dumps(result.get("decision_log") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "aggregate_by_format.json").write_text(
        json.dumps(result.get("aggregate_by_format") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "core_capability_discovery.json").write_text(
        json.dumps(result.get("core_capability_discovery") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    agg = result.get("aggregate_by_format") or {}
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "decision": (result.get("decision_log") or {}).get("decision"),
                "llm_enabled": ok,
                "model": model if ok else "skipped",
                "context_format_effect_confirmed": result.get("context_format_effect_confirmed"),
                "accuracy_spread": result.get("accuracy_spread"),
                "format_accuracy": {k: v.get("accuracy") for k, v in agg.items() if isinstance(v, dict)},
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
