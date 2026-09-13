#!/usr/bin/env python3
"""S2 — emit TEST_SAFETY_EVALUATION packet (READ-ONLY; no Gate)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_evaluation.schema.json"
DEFAULT_P2A = REPO_ROOT / "tools" / "test_safety" / "reference_cases" / "p2a_development_policy_regression.json"

from test_safety.validator import (  # noqa: E402
    evaluate_test_plan,
    load_reference_case,
    validate_packet_schema,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test Safety Validator S2 (READ-ONLY)")
    parser.add_argument("--reference-case", type=Path, default=None)
    parser.add_argument("--plan-json", type=Path, default=None, help="JSON file with test_plan object")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--p2a", action="store_true", help=f"Use {DEFAULT_P2A.name}")
    args = parser.parse_args(argv)

    host_notes: list[str] = []
    reference_id: str | None = None
    if args.p2a or (args.reference_case is None and args.plan_json is None):
        ref_path = args.reference_case or DEFAULT_P2A
        ref = load_reference_case(ref_path)
        reference_id = str(ref.get("reference_case_id") or "")
        plan = dict(ref["test_plan"])
        host_notes = list(ref.get("host_process_notes") or [])
    elif args.reference_case:
        ref = load_reference_case(args.reference_case)
        reference_id = str(ref.get("reference_case_id") or "")
        plan = dict(ref["test_plan"])
        host_notes = list(ref.get("host_process_notes") or [])
    elif args.plan_json:
        raw = json.loads(args.plan_json.read_text(encoding="utf-8"))
        plan = raw.get("test_plan") if "test_plan" in raw else raw
    else:
        parser.error("provide --p2a, --reference-case, or --plan-json")

    packet = evaluate_test_plan(
        plan,
        repo_root=args.repo_root.resolve(),
        host_process_notes=host_notes,
        reference_case_id=reference_id,
    )
    validate_packet_schema(packet, args.schema)
    text = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
