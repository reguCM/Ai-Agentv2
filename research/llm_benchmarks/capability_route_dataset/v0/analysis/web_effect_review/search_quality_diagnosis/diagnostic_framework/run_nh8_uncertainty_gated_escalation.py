#!/usr/bin/env python3
"""NH8 uncertainty-gated escalation runner (research-only)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUN = (
    Path(__file__).resolve().parent
    / "runs"
    / "20260827_145000"
    / "nh8_uncertainty_gated_escalation"
)


def run_py(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "main"):
        mod.main()


def main() -> int:
    if not RUN.is_dir():
        print("missing", RUN, file=sys.stderr)
        return 1
    sys.path.insert(0, str(RUN))
    run_py(RUN / "build_inputs.py")
    run_py(RUN / "run_experiment.py")
    run_py(RUN / "build_reports.py")
    print("NH8 complete:", RUN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
