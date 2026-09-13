#!/usr/bin/env python3
"""NH5 Selector selection simulation runner (research-only). No production changes."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

RUN = (
    Path(__file__).resolve().parent
    / "runs"
    / "20260827_134500"
    / "nh5_selector_selection_experiment"
)


def main() -> int:
    if not RUN.is_dir():
        print("missing", RUN, file=sys.stderr)
        return 1
    sys.path.insert(0, str(RUN))
    runpy.run_path(str(RUN / "write_cases.py"), run_name="__main__")
    runpy.run_path(str(RUN / "run_experiment.py"), run_name="__main__")
    print("NH5 complete:", RUN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
