"""P2-11 Recovery Strategy 比較 CLI。"""
from __future__ import annotations

import argparse
import json

from tools.system.context_monitor.strategy_compare import run_compare_batch


def main() -> None:
    parser = argparse.ArgumentParser(description="P2-11 Recovery Strategy 比較実験")
    parser.add_argument("--runs", type=int, default=1, help="比較サイクル数")
    args = parser.parse_args()
    report = run_compare_batch(runs=args.runs)
    print(json.dumps(report.get("evaluation"), ensure_ascii=False, indent=2))
    print(f"Report: {report.get('output_path')}")


if __name__ == "__main__":
    main()
