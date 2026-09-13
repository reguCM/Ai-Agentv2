"""Copy Completion Gap workspace into this experiment. Import-path rewrite only."""
from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_PKG = "research.grill_observation_v0.completion_gap_v0"
DEST_PKG = "research.grill_observation_v0.medium_task_reality_v0"
SOURCE = ROOT / "research" / "grill_observation_v0" / "completion_gap_v0"


def _copy_rewritten(src: Path, dest: Path) -> None:
    text = src.read_text(encoding="utf-8")
    text = text.replace(SOURCE_PKG, DEST_PKG)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def seed_workspace() -> dict[str, list[str]]:
    copied: list[str] = []
    ws_src = SOURCE / "workspace"
    ws_dst = HERE / "workspace"
    tests_src = SOURCE / "tests"
    tests_dst = HERE / "tests"
    if ws_dst.exists():
        shutil.rmtree(ws_dst)
    if tests_dst.exists():
        shutil.rmtree(tests_dst)
    ws_dst.mkdir(parents=True)
    tests_dst.mkdir(parents=True)
    for src in sorted(ws_src.glob("*.py")):
        dest = ws_dst / src.name
        _copy_rewritten(src, dest)
        copied.append(f"workspace/{src.name}")
    for src in sorted(tests_src.glob("*.py")):
        dest = tests_dst / src.name
        _copy_rewritten(src, dest)
        copied.append(f"tests/{src.name}")
    (ws_dst / "__init__.py").write_text(
        '"""Experiment workspace package for Medium Task Reality Loop v0."""\n',
        encoding="utf-8",
    )
    return {"copied": copied, "source": str(SOURCE), "rewrite": f"{SOURCE_PKG} -> {DEST_PKG}"}
