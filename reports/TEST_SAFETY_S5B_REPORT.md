# Test Safety — S5b Explicit Runner Wedge Report

**Status:** S5b complete. **General runtime / CI NOT_CONNECTED.**

## Pre-implementation READ-ONLY: explicit test execution entries

| Entry | Role | Safety (pre-S5b) |
|-------|------|------------------|
| Shell / CI `python -m pytest` | Primary dev test execution | None |
| `tools/run_test_safety_validator.py` | Evaluation only | No pytest |
| `tools/run_test_safety_shadow_gate.py` | Shadow gate evidence | No pytest |
| `ai_tool/run_agent_test_batch.py` | Local Agent **chat** batch | Not TEST_EXECUTION pytest |
| `ai_tool/agent_test_runner.py` | Agent turn recording / grading | subprocess for **git metadata** only |

**S5b wedge (new):** `tools/test_safety/runner_wedge.py` + `tools/run_authorized_test_plan.py` — **only** path that uses authoritative authorization before executor.

## Responsibility chain (implemented)

```text
Validator → Gate → Authorization Binder → Runner Wedge (verify) → Executor (pytest/subprocess)
```

Gate and Binder do **not** invoke pytest.

## Components

| Item | Path |
|------|------|
| Runner wedge | `tools/test_safety/runner_wedge.py` |
| CLI | `tools/run_authorized_test_plan.py` |
| Tests | `tests/tools/test_test_safety_runner_wedge.py` |

### `execute_authorized_test_plan`

1. `verify_authorization_for_execution(action_id, current_plan)`
2. If not `AUTHORIZED` → `SAFETY_AUTHORIZATION_FAILURE`, `executor_called=false`, `test_failed=false`
3. `ConsumedAuthorizationRegistry` — second spawn → `EXECUTION_ALREADY_CONSUMED`, executor not called
4. Else call injected `executor` (default: `default_pytest_executor` with argv normalization)

### Evidence packet (`TEST_SAFETY_RUNNER_EVIDENCE`)

`action_id`, `plan_fingerprint`, `evaluation_ref`, `authorization_id`, `authorization`, `execution_verification`, `executor_called`, `execution_result`, `required_postflight`, `run_closed`, `postflight_completed`, `execution_connected=true`, `general_runtime_connected=false`

`run_closed=false` when `postflight_git_check_required=true` (S5c will strengthen closure).

## S5b-1 (fake executor)

| Case | Result |
|------|--------|
| A AUTHORIZED | executor called once |
| B DENIED (BLOCKED gate) | never called |
| C stale plan | never called |
| D wrong action_id | never called |
| E invalid auth packet | never called |
| F external / blocked auth | never called |
| G postflight | preserved; `run_closed=false` |
| Exactly-once | second call `EXECUTION_ALREADY_CONSUMED` |

## S5b-2 (controlled real pytest)

Single authorized path:

`LEVEL_1` → `test_h_deterministic_fingerprint` — PASS → AUTHORIZED → verify → real pytest **ok**.

## Test Safety Preflight

S5b test module: synthetic LEVEL_1 preflight before cases; skips if BLOCKED.

## Regression

```bash
python -m pytest tests/tools/test_test_safety_*.py -q
```

**40 passed** (authorization + runner + shadow + validator).

## Not in S5b

CI, `_execute_agent_tool`, chat runtime, Human Approval UI, postflight execution, P2b.

## Final Verdict

```text
S5B_RUNNER_WEDGE:
READY

AUTHORIZED_EXECUTION:
PASS

DENIED_EXECUTION_BLOCK:
PASS

STALE_EXECUTION_BLOCK:
PASS

EXECUTOR_EXACTLY_ONCE:
PASS

REAL_CONTROLLED_TEST:
PASS

GENERAL_RUNTIME_AUTHORITY:
NOT_CONNECTED

READY_FOR_S5C:
true
```

S5c requires **Human Review**; do not auto-start.
