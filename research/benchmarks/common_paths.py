"""Shared paths for scripts under research/benchmarks/."""
from __future__ import annotations

from pathlib import Path

BENCHMARKS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BENCHMARKS_ROOT.parents[1]


def bootstrap_repo_root() -> Path:
    """Add repo root to sys.path (for scripts importing tools/ or research/)."""
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return REPO_ROOT
