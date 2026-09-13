"""Standalone runner for revalidation Lab-0 (production non-connected)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.revalidation_lab_harness import PRIMARY_LOCAL_MODEL, run_lab0, seed_lab0_handoff_orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run revalidation Lab-0 harness")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/revalidation_lab0"),
        help="Directory for JSONL observations and summary",
    )
    parser.add_argument(
        "--model",
        default=PRIMARY_LOCAL_MODEL,
        help="Primary local model id (Lab-0 does not use stronger model)",
    )
    args = parser.parse_args()
    store = MissionMemoryStore(args.output_dir / "mission_memory")
    orchestrator = seed_lab0_handoff_orchestrator(store)
    summary = run_lab0(orchestrator, output_dir=args.output_dir, model=args.model)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
