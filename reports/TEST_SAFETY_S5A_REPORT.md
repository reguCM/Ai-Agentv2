# Test Safety — S5a Authoritative Authorization Binding Report

**Status:** S5a complete. **Execution NOT_CONNECTED** (no pytest block, no runner wedge).

## Deliverables

| Item | Path |
|------|------|
| Plan fingerprint | `tools/test_safety/plan_fingerprint.py` |
| Authorization binder | `tools/test_safety/authorization.py` |
| Schema | `registry/schema/test_safety_authorization.schema.json` |
| Tests | `tests/tools/test_test_safety_authorization.py` |

## Fingerprint definition (from validator inputs)

Canonical material (`fingerprint_material_from_plan`):

| Field | Validator usage |
|-------|-----------------|
| `commands` | Required; normalized strip |
| `declared_primary_risk_level` | Optional override in `evaluate_test_plan` |
| `declared_dimensions` | Merged keys in `DIMENSION_KEYS` only |
| `declared_write_scope` | `_apply_declared_write_scope` |

**Excluded:** `plan_id`, `description`, `notes`, `host_process_notes`, `readonly_observations`, timestamps, warnings order.

Hash: `SHA-256` of `json.dumps(material, sort_keys=True, separators=(",", ":"))`.

## Authorization conditions

**AUTHORIZED** when all hold:

- Valid `TEST_SAFETY_EVALUATION` + valid `TEST_SAFETY_SHADOW_GATE`
- `gate_decision == PASS`
- `human_approval_required == false` (execution safety binding; approval is S5b+ runtime)
- `evaluation_ref` (packet) matches gate `evaluation_ref`
- `compute_plan_fingerprint(current_plan) == fingerprint(evaluation.test_plan)`
- `action_id` present; optional `expected_action_id` / `expected_evaluation_ref` checks pass

**DENIED** otherwise (not TEST_FAILED).

## Denial reason codes

`GATE_BLOCKED`, `MISSING_EVALUATION`, `INVALID_EVALUATION`, `INVALID_GATE_PACKET`, `UNKNOWN_SCHEMA_VERSION`, `ACTION_ID_MISMATCH`, `PLAN_FINGERPRINT_MISMATCH`, `EVALUATION_REF_MISMATCH`, `STALE_EVALUATION`, `HUMAN_APPROVAL_REQUIRED`

## Responsibility separation

- Validator → facts
- `decide_gate_from_evaluation` → PASS/BLOCKED (unchanged)
- `bind_test_safety_authorization` → binding only (no pytest)
- Executor → NOT_CONNECTED

## Exactly-once identity (S5a)

`authorization_binding_key = SHA-256(action_id + plan_fingerprint + canonical evaluation_ref)`

Stable for same triple; distinct across `action_id`.

## Tests

Module preflight: synthetic LEVEL_1 plan → shadow PASS.

Cases A–K + binding key stability: **13 passed** (with full test_safety suite **31 passed**).

```bash
python -m pytest tests/tools/test_test_safety_authorization.py tests/tools/test_test_safety_shadow_gate.py tests/tools/test_test_safety_validator.py -q
```

## Not in S5a

Runner wedge, pytest blocking, CI, Task Runtime, postflight execution, Human Approval UI.

## Final Verdict

```text
S5A_AUTHORIZATION_BINDING:
READY

STALE_PASS_PROTECTION:
PASS

ACTION_ID_BINDING:
PASS

EVALUATION_BINDING:
PASS

PLAN_FINGERPRINT:
STABLE

REQUIRED_POSTFLIGHT_PRESERVED:
true

EXECUTION_AUTHORITY:
NOT_CONNECTED

READY_FOR_S5B_RUNNER_WEDGE:
true
```

S5b requires **Human Review**; do not auto-start.
