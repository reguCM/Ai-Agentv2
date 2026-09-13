#!/usr/bin/env python3
"""S7a — explicit test plan runner with automatic safety resolution (TEST_EXECUTION only)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_shadow_gate.schema.json"

from test_safety.runner_wedge import ConsumedAuthorizationRegistry, prepare_evaluation_and_authorization  # noqa: E402
from test_safety.safety_resolution import run_explicit_test_with_auto_resolution  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authorized test plan runner (S5b wedge)")
    parser.add_argument("--plan-json", type=Path, required=True, help="JSON file with test_plan object")
    parser.add_argument("--action-id", default="CLI-TEST-1")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-bind-only", action="store_true", help="Evaluate+bind only; do not execute")
    parser.add_argument(
        "--authorization-json",
        type=Path,
        default=None,
        help="Optional pre-bound TEST_SAFETY_AUTHORIZATION packet (skips auto resolution when valid)",
    )
    args = parser.parse_args(argv)

    raw = json.loads(args.plan_json.read_text(encoding="utf-8"))
    plan = raw.get("test_plan") if isinstance(raw, dict) and "test_plan" in raw else raw
    if not isinstance(plan, dict):
        parser.error("plan-json must contain a test_plan object")

    evaluation, gate, authorization = prepare_evaluation_and_authorization(
        plan,
        action_id=args.action_id,
        repo_root=REPO_ROOT,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
    )
    if args.dry_bind_only:
        payload = {
            "evaluation": evaluation,
            "gate": gate,
            "authorization": authorization,
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    pre_auth = None
    if args.authorization_json:
        pre_auth = json.loads(args.authorization_json.read_text(encoding="utf-8"))

    outcome = run_explicit_test_with_auto_resolution(
        action_id=args.action_id,
        current_plan=plan,
        authorization_packet=pre_auth,
        repo_root=REPO_ROOT,
        eval_schema_path=EVAL_SCHEMA,
        gate_schema_path=GATE_SCHEMA,
        consumed_registry=ConsumedAuthorizationRegistry(),
    )
    text = json.dumps(outcome, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    runner = outcome.get("runner_evidence") or {}
    exec_result = runner.get("execution_result") or {}
    return 0 if outcome.get("executor_called") and exec_result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
