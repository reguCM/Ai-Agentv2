"""workspace 複製。本番 Registry には接続しない。"""

from __future__ import annotations

import shutil
from pathlib import Path


FIXTURE_SRC = Path(__file__).resolve().parent / "fixtures" / "lane_bay"


def copy_fixture(dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        FIXTURE_SRC,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
    )
    return dest
