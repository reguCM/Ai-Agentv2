# Test Safety — S3 Shadow Gate Report

**Status:** S3 Shadow Gate complete. **Non-authoritative** (`execution_authoritative=false`). No pytest stop, no CI, no Human Approval Runtime.

## Architecture

| Layer | Responsibility |
|-------|----------------|
| Validator (`tools/test_safety/validator.py`) | Risk state: LEVEL, dimensions, `relevant_unknowns`, evaluator `warnings` |
| Shadow Gate (`tools/test_safety/shadow_gate.py`) | `PASS` \| `BLOCKED` from evaluation packet only |
| Comparison (`tools/test_safety/comparison.py`) | Human expectation vs shadow; mismatch taxonomy |

`recommended_gate_decision` on the evaluation packet remains an **advisory mirror** of the same gate rules (single implementation in `shadow_gate`).

## Schemas

- Evaluation (S2): `registry/schema/test_safety_evaluation.schema.json`
- Shadow Gate (S3): `registry/schema/test_safety_shadow_gate.schema.json`

## Gate rules (summary)

- **PASS** candidates: controlled `LEVEL_1` / `LEVEL_2` when no blockers
- **BLOCK**: relevant `UNKNOWN` not verifiable; prohibited side effects (e.g. `credentials=PRESENT`); uncontrolled L3 live resources; external/uncontrolled network policy blockers
- **Warnings**: separate array; warnings alone do not block
- **Fail-safe**: missing / invalid evaluation → `BLOCKED`, `gate_reason=INVALID_OR_UNVERIFIED_EVALUATION`
- **Postflight**: `required_postflight.postflight_git_check_required` copied from evaluation heuristics (not executed in S3)

## Reference cases (6/6 match)

| Case | ID | Shadow | Human | Notes |
|------|-----|--------|-------|-------|
| A | `p2a_development_policy_regression` | PASS | PASS | warnings; postflight git |
| B | `pure_unit` | PASS | PASS | no warnings |
| C | `relevant_unknown_gpu` | BLOCKED | BLOCKED | relevant GPU UNKNOWN |
| D | `irrelevant_unknown_ollama` | PASS | PASS | irrelevant host note → warning |
| E | `intentional_repo_write` | PASS | PASS | declared repo write + postflight |
| F | `external_uncontrolled` | BLOCKED | BLOCKED | human_approval_required=true |

Evidence: `reports/test_safety_shadow_gate_<case>.json`, aggregate `reports/test_safety_shadow_gate_all_references.json`.

## Tests

```bash
python -m pytest tests/tools/test_test_safety_validator.py tests/tools/test_test_safety_shadow_gate.py -q
```

S3 module preflight: synthetic L1 plan → shadow PASS before case tests run.

## CLI

```bash
$env:PYTHONPATH=".;tools"
python tools/run_test_safety_shadow_gate.py --reference-case tools/test_safety/reference_cases/pure_unit.json --out reports/test_safety_shadow_gate_pure_unit.json
python tools/run_test_safety_shadow_gate.py --all-references --out reports/test_safety_shadow_gate_all_references.json
```

## Not in S3

- pytest / shell execution blocking
- CI gate
- Agent Runtime RequiredFirstAction
- Human Approval UI
- `development_policy.json` changes
- Stage7 / Git Governance / P2b

## Final verdict

```text
S3_SHADOW_GATE:
READY

FALSE_PASS_COUNT:
0

FALSE_BLOCK_COUNT:
0

REFERENCE_CASE_MATCH:
6/6

EXECUTION_AUTHORITY:
SHADOW_ONLY

READY_FOR_RUNTIME_GATE_DESIGN:
true
```

Runtime Gate design and CI connection require **Human Review**; do not auto-connect.
