"""Recovery Harness CLI（Live LLM 実測）。"""
from __future__ import annotations

import argparse
import json

from tools.system.context_monitor.recovery_harness import run_harness_batch


def main() -> None:
    parser = argparse.ArgumentParser(description="P2-11 Recovery Harness (Live LLM)")
    parser.add_argument("--runs", type=int, default=3, help="実行回数")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Recovery 候補を明示承認して 32768 再試行",
    )
    args = parser.parse_args()
    report = run_harness_batch(runs=args.runs, approve_recovery=args.approve)
    print(json.dumps(report.get("summary"), ensure_ascii=False, indent=2))
    print(f"Report: {report.get('output_path')}")


if __name__ == "__main__":
    main()
