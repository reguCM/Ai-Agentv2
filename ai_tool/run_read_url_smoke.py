#!/usr/bin/env python3
"""Record real-web smoke test run for local:read_url_text (experimental)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.read_url.smoke_runner import run_smoke_suite

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_read_url_real_web_smoke"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    suite = run_smoke_suite(RUN_DIR)
    print(json.dumps({"run_dir": str(RUN_DIR), "summary": suite["summary"]}, ensure_ascii=False, indent=2))
    return 0 if suite["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
