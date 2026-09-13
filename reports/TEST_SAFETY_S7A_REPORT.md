# Test Safety — S7a Automatic Safety Resolution Report

**Status:** S7a complete. **General runtime NOT_CONNECTED.**

## Deliverables

| Item | Path |
|------|------|
| Resolution layer | `tools/test_safety/safety_resolution.py` |
| Runner integration | `run_explicit_test_with_auto_resolution()` |
| CLI | `tools/run_authorized_test_plan.py` (auto-resolution default; `--authorization-json` optional) |
| Tests | `tests/tools/test_test_safety_resolution.py` |

## Lifecycle (implemented)

```text
Original Test Action (action_id + test_plan)
  → authorization_is_valid?
      YES → resolution SKIPPED → execute_authorized_test_plan (verify + S5b/c)
      NO  → automatic resolve_test_safety (max 1 attempt)
          → RESOLVED → same action/plan → runner wedge
          → BLOCKED / AWAITING_HUMAN_APPROVAL / ERROR / UNRESOLVED → executor NOT_CALLED
```

- No LLM re-plan; `original_action_preserved` checked via fingerprint + action_id.
- Defense in depth: runner still runs `verify_authorization_for_execution`.

## Reused components (not reimplemented)

`evaluate_test_plan`, `evaluate_shadow_gate`, `decide_gate_from_evaluation` (via gate), `bind_test_safety_authorization`, `verify_authorization_for_execution`, `execute_authorized_test_plan`, postflight/closure.

## Resolution evidence fields

`authorization_present_before`, `resolution_attempted`, `resolution_attempt_count`, `resolution_result`, `evaluation_ref`, `gate_decision`, `authorization_id`, `original_action_preserved`, `executor_called` (on merged run).

`ResolutionRunState`: in-run only (S6.1); `max_automatic_attempts = 1`.

## Tests

| Case | Result |
|------|--------|
| A valid auth → SKIPPED, executor once | PASS |
| B missing → RESOLVED, executor once | PASS |
| C BLOCKED | PASS |
| D AWAITING_HUMAN_APPROVAL | PASS |
| E validator error | PASS |
| F binder denied | PASS |
| G stale auth → re-resolve | PASS |
| H/I identity preserved | PASS |
| J second auto attempt UNRESOLVED | PASS |
| K tampered plan at runner → DENIED | PASS |
| S7a2 controlled real pytest | PASS |

```bash
python -m pytest tests/tools/test_test_safety_*.py -q
```

**63 passed** (full test_safety glob).

## Not connected

Chat, orchestrator, `_execute_agent_tool`, shell, CI, pending store, Human Approval UI, P2b.

## Final Verdict

```text
S7A_AUTOMATIC_SAFETY_RESOLUTION:
READY

MISSING_AUTH_DETECTION:
PASS

AUTO_SAFETY_EVALUATION:
PASS

ORIGINAL_ACTION_PRESERVATION:
PASS

AUTO_RESOLUTION_ATTEMPTS:
1 (max enforced)

BLOCKED_EXECUTION_PREVENTION:
PASS

FAIL_SAFE:
PASS

RUNNER_FINAL_VERIFICATION:
PASS

CONTROLLED_REAL_TEST:
PASS

GENERAL_RUNTIME:
NOT_CONNECTED

READY_FOR_NEXT_DESIGN:
true
```

Next expansion requires **Human Review**; do not auto-connect general runtime.
