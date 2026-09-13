from __future__ import annotations

import argparse
import json

from ai_tool.agent_test_runner import get_test_case, run_batch
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded Local Agent test batch")
    parser.add_argument("--case", default="P216-GIT-PLAN")
    parser.add_argument("--runs", type=int, choices=(1, 5, 10), default=1)
    parser.add_argument("--model")
    args = parser.parse_args()
    test_case = get_test_case(args.case)

    def execute(case, run_id):
        return run_chat_turn(
            empty_session(f"test-{run_id}"),
            case["prompt"],
            model=args.model,
        )

    result = run_batch(test_case, args.runs, execute)
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
    print(f"Report: {result['output_directory']}/aggregate.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
