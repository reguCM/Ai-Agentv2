#!/usr/bin/env python3
"""Run Web Tool Autonomous Improvement selection iteration."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import live_chat_fn, ollama_available
from ai_tool.web_tool_autonomous_improvement import run_autonomous_improvement
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_autonomous_improvement"
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
        profile = get_llm_profile("qwen3_8b")
        model = str(profile.get("model") or "")
        chat = live_chat_fn()
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        llm_mod._client = None

    result = run_autonomous_improvement(
        fetch_live=True,
        llm_enabled=ok,
        chat_fn=chat,
        model=model,
    )
    result["run_id"] = RUN_ID

    (RUN_DIR / "observations.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "selected_option": result.get("selected_option"),
                "stop_reason": result.get("stop_reason"),
                "overall": result.get("overall"),
                "production_changes": result.get("production_changes"),
                "human_intervention_count": result.get("human_intervention_count"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "before_after.json").write_text(
        json.dumps(
            {
                "pre_d37e343_osaka_e2e": "FAIL (extraction + env)",
                "post_d37e343_osaka_e2e": result.get("probes", {}).get("live_mirror_e2e", {}),
                "golden": result.get("probes", {}).get("golden", {}).get("overall"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({"run_id": RUN_ID, "overall": result.get("overall"), "stop": result.get("stop_reason")}, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
