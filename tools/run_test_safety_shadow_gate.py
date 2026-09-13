#!/usr/bin/env python3
"""S3 — Shadow Gate from TEST_SAFETY_EVALUATION (non-authoritative; no pytest stop)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO_ROOT / "registry" / "schema" / "test_safety_shadow_gate.schema.json"
REF_DIR = REPO_ROOT / "tools" / "test_safety" / "reference_cases"

from test_safety.comparison import build_comparison_evidence  # noqa: E402
from test_safety.shadow_gate import evaluate_shadow_gate, validate_shadow_gate_schema  # noqa: E402
from test_safety.validator import evaluate_test_plan, load_reference_case, validate_packet_schema  # noqa: E402


def _run_reference_case(
    ref_path: Path,
    *,
    repo_root: Path,
    eval_schema: Path,
    gate_schema: Path,
) -> dict:
    ref = load_reference_case(ref_path)
    case_id = str(ref.get("reference_case_id") or ref_path.stem)
    packet = evaluate_test_plan(
        ref["test_plan"],
        repo_root=repo_root,
        host_process_notes=list(ref.get("host_process_notes") or []),
        reference_case_id=case_id,
    )
    validate_packet_schema(packet, eval_schema)
    gate = evaluate_shadow_gate(packet, schema_path=eval_schema, reference_case_id=case_id)
    validate_shadow_gate_schema(gate, gate_schema)
    expectation = dict(ref.get("expectation") or {})
    return build_comparison_evidence(
        reference_case_id=case_id,
        validator_result=packet,
        shadow_gate_packet=gate,
        expectation=expectation,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test Safety Shadow Gate S3")
    parser.add_argument("--evaluation-json", type=Path, default=None)
    parser.add_argument("--reference-case", type=Path, default=None)
    parser.add_argument("--all-references", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--eval-schema", type=Path, default=EVAL_SCHEMA)
    parser.add_argument("--gate-schema", type=Path, default=GATE_SCHEMA)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.all_references:
        evidence_list = []
        for ref_path in sorted(REF_DIR.glob("*.json")):
            evidence_list.append(
                _run_reference_case(
                    ref_path,
                    repo_root=args.repo_root.resolve(),
                    eval_schema=args.eval_schema,
                    gate_schema=args.gate_schema,
                )
            )
        payload = {"reference_evidence": evidence_list, "execution_authoritative": False}
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"Wrote {args.out}", file=sys.stderr)
        else:
            print(text, end="")
        return 0

    if args.evaluation_json:
        packet = json.loads(args.evaluation_json.read_text(encoding="utf-8"))
        gate = evaluate_shadow_gate(packet, schema_path=args.eval_schema)
        validate_shadow_gate_schema(gate, args.gate_schema)
        text = json.dumps(gate, indent=2, ensure_ascii=False) + "\n"
    elif args.reference_case:
        evidence = _run_reference_case(
            args.reference_case,
            repo_root=args.repo_root.resolve(),
            eval_schema=args.eval_schema,
            gate_schema=args.gate_schema,
        )
        text = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    else:
        parser.error("provide --evaluation-json, --reference-case, or --all-references")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
