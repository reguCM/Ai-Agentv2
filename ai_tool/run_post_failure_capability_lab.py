"""Standalone runner for Post-Failure Hard Capability Fallback Lab."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_tool.post_failure_capability_lab import run_post_failure_capability_lab


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Post-Failure Hard Capability Fallback Lab",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/post_failure_capability_lab"),
    )
    args = parser.parse_args()
    summary = run_post_failure_capability_lab(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
