"""Library entry — delegates to run directory."""

from __future__ import annotations

import importlib.util
from pathlib import Path

RUN = (
    Path(__file__).resolve().parents[2]
    / "runs"
    / "20260828_131500"
    / "nh13_7_mechanical_glossary_selection"
    / "run_experiment.py"
)


def main() -> int:
    spec = importlib.util.spec_from_file_location("nh13_7_run", RUN)
    if spec is None or spec.loader is None:
        raise RuntimeError(RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
