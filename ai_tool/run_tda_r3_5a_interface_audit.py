#!/usr/bin/env python3
"""R3.5-A：Local Agent 窓口・処理経路の静的監査。Production は変更しない。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_r35a_interface_audit import (
    run_r35a_interface_audit,
)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_r3_5a_interface_audit"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_r35a_interface_audit()
    result["run_id"] = RUN_ID
    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "run_id": RUN_ID,
        "judgment": result["judgment"],
        "judgment_ja": result["judgment_ja"],
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_changed": False,
        "agent_imports_tda": result["agent_imports_tda"],
        "r3_calls_real_llm": result["r3_calls_real_llm"],
        "registry_agent_tools": result["registry_visibility"]["agent"],
        "file_tools_in_agent_registry": result["file_tools_in_agent_registry"],
        "problem_count": len(result["problems"]),
    }
    (RUN_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote {RUN_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
