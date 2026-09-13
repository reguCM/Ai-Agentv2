#!/usr/bin/env python3
"""Phase 1 experiment: local read_url_text vs MCP Fetch (isolated; not agent-integrated)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.mcp_fetch_comparison.runner import run_comparison

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_mcp_fetch_comparison"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    result = run_comparison(RUN_DIR)
    print(json.dumps({"run_dir": str(RUN_DIR), "cases": len(result["cases"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
