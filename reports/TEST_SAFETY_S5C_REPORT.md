# Test Safety — S5c Postflight Lifecycle / Run Closure Report

**Status:** S5c complete. No new execution entry points. CI / chat / general runtime **NOT_CONNECTED**.

## Principle

```text
pytest PASS  ≠  Safety Run CLOSED
```

Closure requires execution completed **and** all `required_postflight` from authorization satisfied **and** no unresolved postflight safety failure.

## Components

| Item | Path |
|------|------|
| Git snapshot (read-only) | `tools/test_safety/git_snapshot.py` |
| Postflight + closure | `tools/test_safety/postflight.py` |
| Runner integration | `tools/test_safety/runner_wedge.py` (`RUNNER_ID` s5c) |
| Schema | `registry/schema/test_safety_postflight.schema.json` |
| Tests | `tests/tools/test_test_safety_postflight_lifecycle.py` |

Validator `_git_readonly_snapshot` now delegates to `git_worktree_snapshot` (porcelain available for postflight).

## Postflight result (minimal)

```json
{
  "postflight_status": "PASS | INCOMPLETE | FAILED",
  "required_checks": ["git_repository_state"],
  "completed_checks": [...],
  "warnings": [...],
  "unexpected_changes": [...]
}
```

Requirements are taken **only** from `required_postflight` on authorization (no re-inference).

### Git postflight

- Baseline snapshot before executor (when `repo_root` + `postflight_git_check_required`)
- After snapshot compared via porcelain lines
- `declared_write_scope` on plan: paths under declared `runs/` etc. are not `unexpected_changes`
- Undeclared source paths → `FAILED` / closure blocked

### Closure (`evaluate_run_closure`)

| Case | `run_closed` | `closure_reason` (examples) |
|------|--------------|-----------------------------|
| No git postflight required | true (after exec) | `NO_REQUIRED_POSTFLIGHT` |
| Git required, not run | false | `POSTFLIGHT_INCOMPLETE` |
| Git postflight PASS | true | `ALL_REQUIRED_POSTFLIGHT_PASS` |
| pytest FAIL, postflight PASS | true | `ALL_REQUIRED_POSTFLIGHT_PASS` (`test_failed` still true) |
| Unexpected changes | false | `POSTFLIGHT_FAILED` / `UNEXPECTED_REPOSITORY_CHANGES` |
| Authorization denied | false | `SAFETY_AUTHORIZATION_NOT_EXECUTED` (no postflight after exec) |

`execution_consumed` vs `run_closed` are separate (authorization consumed; run may stay OPEN until postflight).

## Runner evidence fields (added)

`postflight_result`, `closure_reason`, `postflight_completed`, `execution_consumed`

## Negative cases (S5c tests)

| Case | Status |
|------|--------|
| A No postflight → CLOSED | PASS |
| B Git required, not run → NOT_CLOSED | PASS |
| C Git postflight PASS → CLOSED | PASS |
| D Exec FAIL, postflight PASS → run CLOSED, test_failed | PASS |
| E Unexpected mutation → NOT_CLOSED | PASS |
| F DENIED → no executor, not test_failed | PASS |
| G Exactly-once | PASS |

Plus unit tests for `compare_git_postflight` and declared scope matching.

## Regression

```bash
python -m pytest tests/tools/test_test_safety_*.py -q
```

**51 passed**

## Not in S5c

CI, shell-wide gate, chat runtime, Human Approval UI, automatic safety resolution, destructive git fixtures on real repo.

## Final Verdict

```text
S5C_POSTFLIGHT_LIFECYCLE:
READY

REQUIRED_POSTFLIGHT_ENFORCEMENT:
PASS

RUN_CLOSURE:
PASS

UNEXPECTED_MUTATION_DETECTION:
PASS

TEST_RESULT_VS_CLOSURE_SEPARATION:
PASS

READY_FOR_AUTOMATIC_SAFETY_RESOLUTION_DESIGN:
true
```

Next phase requires **Human Review**; do not auto-advance.
