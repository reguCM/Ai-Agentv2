#!/usr/bin/env python3
"""NH3 State Safety Boundary experiment runner (research-only).

Does NOT modify production Agent/Tools/Manager/Selector.
Writes results under runs/<id>/nh3_state_safety_boundary/.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "runs" / "20260826_191500" / "nh3_state_safety_boundary"


def main() -> int:
    if not RUN.is_dir():
        print("missing run dir", RUN, file=sys.stderr)
        return 1
    sys.path.insert(0, str(RUN))
    runpy.run_path(str(RUN / "write_cases.py"), run_name="__main__")
    runpy.run_path(str(RUN / "run_experiment.py"), run_name="__main__")
    runpy.run_path(str(RUN / "build_reports.py"), run_name="__main__")
    print("NH3 complete:", RUN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
