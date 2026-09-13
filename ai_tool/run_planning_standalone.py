#!/usr/bin/env python3
"""Run planning-and-task-breakdown and goal-handoff build in isolation."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.dev_skill_pipeline import (
    _generate_plan,
    build_handoff_packet,
    load_registry,
    validate_handoff_packet,
)
from tools.system.config import get_llm_profile

SAMPLE_TECH_SPEC = {
    "summary": "Single-file console Tetris in Dedicated Sandbox",
    "modules": ["tetris/main.py"],
    "sequencing": ["create file"],
    "sandbox_constraints": "Dedicated Sandbox only",
    "implementation_tasks": [
        {"id": 1, "title": "Core loop", "acceptance": ["runs"], "size": "S"},
    ],
}


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_planning_standalone"
    run_dir = _REPO / "logs" / "_planning_standalone" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    model = str(get_llm_profile().get("model") or "")
    registry = load_registry()
    plan = _generate_plan(
        model=model,
        tech_spec=SAMPLE_TECH_SPEC,
        registry=registry,
        chat_fn=None,
    )
    packet = build_handoff_packet(
        initial_request="テトリスを作って",
        prd={"title": "Tetris", "acceptance_criteria": ["tetris/main.py exists"]},
        prd_rel="design/prd.md",
        tech_spec_rel="design/tech-spec.md",
        plan_rel="design/plan.md",
        todo_rel="design/todo.md",
        tech_spec=SAMPLE_TECH_SPEC,
        plan=plan,
        skill_steps=["write-prd", "tech-spec", "planning-and-task-breakdown"],
    )
    errors = validate_handoff_packet(packet)
    out = {
        "run_id": run_id,
        "model": model,
        "plan_keys": sorted(plan.keys()),
        "task_ids": [task["id"] for task in packet.get("implementation_tasks") or []],
        "handoff_valid": not errors,
        "handoff_errors": errors,
    }
    (run_dir / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "handoff.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
