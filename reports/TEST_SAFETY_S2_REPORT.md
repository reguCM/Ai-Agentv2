# Test Safety — S2 Validator Prototype Report

**Status:** S2 prototype complete (READ-ONLY; **no Gate**, **no CI**, **no `development_policy.json` change**).

## Deliverables

| Item | Path |
|------|------|
| Evaluation packet schema | `registry/schema/test_safety_evaluation.schema.json` |
| Validator | `tools/test_safety/validator.py` |
| P2a reference case | `tools/test_safety/reference_cases/p2a_development_policy_regression.json` |
| CLI | `tools/run_test_safety_validator.py` (`--p2a`) |
| Tests | `tests/tools/test_test_safety_validator.py` |

## Human decisions applied (S1)

- **Risk:** `LEVEL_1` / `LEVEL_2` / `LEVEL_3` primary + optional `also_applies_risk_levels`
- **Dimensions:** 12-axis `NONE|CONTROLLED|PRESENT|UNKNOWN`
- **No** combinatorial risk enum; **no** new policy contract; **no** manifest extension
- **Repository write:** declared scope → warnings + dimension bump (not blanket forbid)
- **Postflight git:** flag `postflight_git_check_required` (not executed in S2)
- **Gate:** `recommended_gate_decision` is **advisory only**
- **Human approval:** `human_approval_required` flag only (no runtime)

## P2a reference evaluation (expected)

- `primary_risk_level`: LEVEL_2
- `llm`: NONE; `network`: CONTROLLED
- `recommended_gate_decision`: PASS
- `human_approval_required`: false
- `postflight_git_check_required`: true (declared repo session write + integration)
- Host ollama / unknown python → warnings / relevant_unknown with **no** gate block

## Usage

```bash
PYTHONPATH=.;tools python tools/run_test_safety_validator.py --p2a \
  --out reports/test_safety_evaluation_p2a.json
```

## Not in S2

- Execution Gate / blocking pytest
- CI integration
- Shadow gate / negative gate test suite (S3+)
- Postflight git diff execution
- Human Approval UI

## Next (Human; do not auto-start)

**S3 — Shadow Gate** (evaluate packet vs actual run; still no CI)
