"""Standalone runner for Capability Routing Lab v0."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_tool.capability_routing_lab import run_capability_routing_lab


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Capability Routing Lab v0")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/capability_routing_lab"),
    )
    args = parser.parse_args()
    summary = run_capability_routing_lab(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
