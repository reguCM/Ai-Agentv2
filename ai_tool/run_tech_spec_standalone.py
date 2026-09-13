#!/usr/bin/env python3
"""Run tech-spec generation alone with the Tetris PRD fixture."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.dev_skill_pipeline import _generate_tech_spec, load_registry
from ai_tool.run_tech_spec_diagnose import TETRIS_PRD
from tools.system.config import get_llm_profile


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_tech_spec_standalone"
    run_dir = _REPO / "logs" / "_tech_spec_standalone" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    model = str(get_llm_profile().get("model") or "")
    registry = load_registry()
    payload = _generate_tech_spec(model=model, prd=TETRIS_PRD, registry=registry, chat_fn=None)
    out = {
        "run_id": run_id,
        "model": model,
        "status": "ok",
        "keys": sorted(payload.keys()),
        "payload": payload,
    }
    (run_dir / "tech_spec_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
