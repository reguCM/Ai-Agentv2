#!/usr/bin/env python3
"""NH7 observation-to-fingerprint runner (research-only)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

RUN = (
    Path(__file__).resolve().parent
    / "runs"
    / "20260827_143100"
    / "nh7_observation_to_fingerprint"
)


def main() -> int:
    if not RUN.is_dir():
        print("missing", RUN, file=sys.stderr)
        return 1
    sys.path.insert(0, str(RUN))
    runpy.run_path(str(RUN / "build_inputs.py"), run_name="__main__")
    runpy.run_path(str(RUN / "run_experiment.py"), run_name="__main__")
    runpy.run_path(str(RUN / "build_reports.py"), run_name="__main__")
    print("NH7 complete:", RUN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
