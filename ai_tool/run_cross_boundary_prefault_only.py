#!/usr/bin/env python3
"""Run Tetris prefault after deterministic precondition evaluation (no full E2E)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.e2e_cross_boundary_prefault import run_cross_boundary_prefault
from ai_tool.precondition_contract import preconditions_to_dicts
from ai_tool.tetris_execution_context import (
    EXECUTION_CONTEXT_FILENAME,
    build_tetris_golden_path_execution_context,
)
from ai_tool.tetris_precondition_checker import (
    build_precondition_evaluation_bundle,
    evaluate_all_tetris_preconditions,
    load_handoff_artifact,
)
from tools.system.config import get_llm_profile


def _latest_pipeline_smoke_dir(repo_root: Path) -> Path | None:
    root = repo_root / "logs" / "_e2e_pipeline_smoke"
    if not root.is_dir():
        return None
    candidates = sorted(
        [path for path in root.iterdir() if path.is_dir()],
        key=lambda path: path.name,
        reverse=True,
    )
    for candidate in candidates:
        if (candidate / "design" / "handoff.json").is_file() or (candidate / "handoff.json").is_file():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Tetris prefault with deterministic preconditions")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Pipeline run dir containing design/handoff.json (default: latest pipeline smoke)",
    )
    args = parser.parse_args()

    artifact_dir = args.artifact_dir or _latest_pipeline_smoke_dir(_REPO)
    if artifact_dir is None:
        print("No artifact dir with handoff.json found", file=sys.stderr)
        return 2

    handoff_packet, handoff_path = load_handoff_artifact(artifact_dir)
    execution_context = build_tetris_golden_path_execution_context()
    precondition_items = evaluate_all_tetris_preconditions(
        handoff_packet=handoff_packet,
        repo_root=_REPO,
        include_environment=True,
    )
    precondition_evaluation = build_precondition_evaluation_bundle(
        handoff_packet=handoff_packet,
        repo_root=_REPO,
        handoff_path=str(handoff_path),
        execution_context=execution_context,
        include_environment=True,
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_prefault_only"
    run_dir = _REPO / "logs" / "_e2e_prefault" / run_id
    (run_dir / EXECUTION_CONTEXT_FILENAME).write_text(
        json.dumps(execution_context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    model = str(get_llm_profile().get("model") or "")
    result = run_cross_boundary_prefault(
        run_dir=run_dir,
        model=model,
        composition_id="tetris-sandbox-e2e",
        preconditions=preconditions_to_dicts(precondition_items),
        precondition_evaluation=precondition_evaluation,
        handoff_packet=handoff_packet,
        execution_context=execution_context,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"artifact_dir={artifact_dir}")
    print(f"run_dir={run_dir}")
    return 0 if result.get("llm_status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
