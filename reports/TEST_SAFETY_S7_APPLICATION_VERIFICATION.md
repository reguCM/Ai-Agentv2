# Test Safety — S7 Application Verification

**Date:** 2026-09-12  
**Mode:** READ-ONLY (no code, policy, runtime, runner, or registry changes)  
**Purpose:** Independently confirm that the S2–S7a stack is **applied on the Explicit Test Runner production path**, not only documented or unit-tested in isolation.

**Target commits:**

| SHA | Message |
|-----|---------|
| `8789b69` | `test-safety: S2-S7a authoritative stack` |
| `5f59bea` | `docs: test safety architecture and human decisions` |

**Supplementary evidence:** `reports/TEST_SAFETY_DOGFOOD_EXPLICIT_RUN.json` (`DOGFOOD-S2-S7A-2026-09-12`). Dogfood fields were cross-checked against code paths; prior phase reports alone were **not** used as proof of application.

---

## 1. Intended chain (Explicit Runner)

```text
Test Plan
  → Automatic Safety Resolution (S7a)
  → Validator (S2)
  → Shadow Gate (S3)
  → Authorization binding (S5a)
  → Runner verification (S5b)
  → Execution (subprocess / pytest)
  → Postflight (S5c)
  → Run closure (S5c)
```

**Authoritative CLI entry:** `tools/run_authorized_test_plan.py` → `run_explicit_test_with_auto_resolution()` → `execute_authorized_test_plan()`.

---

## 2. Verification chain (code connectivity)

| Step | Rating | Evidence |
|------|--------|----------|
| `run_authorized_test_plan.py` → `run_explicit_test_with_auto_resolution()` | **CONNECTED** | Default path L61–68. `--dry-bind-only` evaluates only; does not enter execution chain (intentional preview). |
| Authorization presence / validity | **CONNECTED** | `resolve_test_safety` → `authorization_is_valid` → `verify_authorization_for_execution`. |
| `resolve_test_safety()` | **CONNECTED** | Missing/invalid auth triggers at most one `prepare_evaluation_and_authorization` cycle. |
| Validator | **CONNECTED** | `prepare_evaluation_and_authorization` → `evaluate_test_plan`. |
| Gate | **CONNECTED** | → `evaluate_shadow_gate`. |
| Authorization binding | **CONNECTED** | → `bind_test_safety_authorization`. |
| Same original action (action_id + fingerprint) | **CONNECTED** | `fp_before` / `fp_after`, `original_action_preserved` in resolution evidence. |
| `execute_authorized_test_plan()` | **CONNECTED** | Called only when resolution is `RESOLVED` or `SKIPPED`; otherwise early return with `executor_called: false`. |
| `verify_authorization_for_execution()` at runner | **CONNECTED** | First step inside `execute_authorized_test_plan` (runner wedge). |
| Executor | **CONNECTED** | After `AUTHORIZED` verify and successful `ConsumedAuthorizationRegistry.consume(binding_key)`. |
| Postflight | **CONNECTED** | `run_required_postflight`. |
| `evaluate_run_closure()` | **CONNECTED** | After execution; `pytest` outcome and `run_closed` are separate fields. |

**Note (non-bypass redundancy):** On the default CLI path, `main()` also calls `prepare_evaluation_and_authorization` once before `run_explicit_test_with_auto_resolution`, but **discards** the result (L37–43). This is redundant evaluation only; it does not reach the executor.

---

## 3. Rule application

### Missing authorization

- **Requirement:** No direct path from missing auth to executor inside the explicit runner.
- **Result:** **PASS.** `run_explicit_test_with_auto_resolution` returns without calling `execute_authorized_test_plan` unless `RESOLVED` or `SKIPPED`. `default_pytest_executor` is only invoked from `execute_authorized_test_plan` after verification and consume.
- **Tests:** `test_test_safety_resolution.py` (missing → RESOLVED; BLOCKED/error paths).

### BLOCKED gate

- **Requirement:** Executor not called; not treated as `test_failed`.
- **Result:** **PASS.** Resolution `RESOLUTION_BLOCKED`; runner denied path sets `test_failed: false`, `executor_called: false`.
- **Tests:** `test_c_missing_blocked_executor_never_called`, `test_s5b1_b_denied_never_calls_executor`, `test_f_denied_no_executor_not_test_failed`.

### Human approval required

- **Requirement:** Executor not called; distinguishable in evidence.
- **Result:** **PASS.** `RESOLUTION_AWAITING_HUMAN_APPROVAL` vs `RESOLUTION_BLOCKED`.
- **Tests:** `test_d_human_approval_executor_never_called`, binder `DENY_HUMAN_APPROVAL_REQUIRED`.

### Stale authorization (action / fingerprint / verify denial)

- **Requirement:** Runner final verification rejects mismatch.
- **Result:** **PASS.** `verify_authorization_for_execution` denies on action mismatch (`DENY_ACTION_ID_MISMATCH`) and fingerprint mismatch (`DENY_STALE_EVALUATION`). Tampered plan after valid pre-auth: runner `DENIED`, executor not called (`test_k_runner_final_verify_blocks_tampered_plan`).
- **Tests:** `test_s5b1_c_stale_fingerprint_never_called`, `test_s5b1_d_wrong_action_never_called`.

### Original action preservation

- **Requirement:** `action_id` and `plan_fingerprint` preserved across resolution.
- **Result:** **PASS.** Resolution evidence and dogfood run align on `DOGFOOD-S2-S7A-2026-09-12` and fingerprint `fc185926299025214cacd2a6904773d69c894d9f0edf18ed07549030e074275c`.
- **Tests:** `test_h_*`, `test_i_plan_fingerprint_preserved`.

### Loop prevention (automatic resolution)

- **Requirement:** At most one automatic resolution attempt per run state.
- **Result:** **PASS.** `MAX_AUTOMATIC_RESOLUTION_ATTEMPTS = 1`; second call → `RESOLUTION_UNRESOLVED` (`test_j_loop_second_automatic_resolution_unresolved`).

### Closure vs pytest result

- **Requirement:** `run_closed` independent of pytest pass semantics for safety-denied paths; `NO_REQUIRED_POSTFLIGHT` → `run_closed=true` when git postflight not required.
- **Result:** **PASS.** `evaluate_run_closure` in `postflight.py` L152–154. Denied execution: `run_closed: false`, `test_failed: false`. Dogfood L1 plan: `closure_reason: NO_REQUIRED_POSTFLIGHT`, `run_closed: true` (flag `postflight_completed` remains false when no git postflight ran — closure authority is `evaluate_run_closure`, not that flag alone).

---

## 4. Dogfood evidence cross-check

**Run:** `tools/run_authorized_test_plan.py` with `tools/test_safety/reference_cases/dogfood_s2_s7a_regression.json`, **no** `--authorization-json`, `action_id=DOGFOOD-S2-S7A-2026-09-12`.

| Check | Dogfood packet | Matches implementation |
|-------|----------------|-------------------------|
| Authorization initially absent | `authorization_present_before: false` | Yes — `pre_auth=None` |
| Resolution attempted | `resolution_attempted: true` | Yes |
| Attempt count = 1 | `resolution_attempt_count: 1` | Yes |
| Gate PASS | `gate_decision: PASS` | Yes |
| Authorization created | `AUTHORIZED`, `authorization_id` set | Yes |
| Original action preserved | `original_action_preserved: true` | Yes |
| Fingerprint preserved | Same fp in resolution and runner_evidence | Yes |
| Runner verification | `execution_verification: VALID` | Yes |
| Executor executed | `executor_called: true`, 63 passed | Yes |
| Run closed | `run_closed: true` | Yes |

**DOGFOOD_EVIDENCE_MATCH: PASS**

---

## 5. Explicit runner bypass scan (in scope only)

**In-scope callers of authoritative execution:**

- `tools/run_authorized_test_plan.py` (production CLI)
- `tools/test_safety/safety_resolution.py`
- `tests/tools/test_test_safety_*.py`

**Out of scope (known NOT_CONNECTED — not failure conditions for this verification):** raw pytest, CI, Chat Runtime, `_execute_agent_tool`, Cursor Shell, general shell.

**Repository search:** No `test_safety` / `run_authorized_test_plan` imports under `ai_tool/**`.

**EXPLICIT_RUNNER_BYPASS: NONE_FOUND**

(`--dry-bind-only` is not an executor bypass; it skips the S7a execution path by design.)

---

## 6. Application verification verdict

**VERIFIED conditions (all met for Explicit Runner only):**

1. Safety stack wired in production explicit-runner code  
2. Missing authorization triggers automatic resolution on default CLI path  
3. Executor not reached before `AUTHORIZED` resolution + runner verify  
4. Stale/mismatch re-verified at runner boundary  
5. BLOCKED / human approval / errors fail-safe (no spurious `test_failed` on deny)  
6. Same-action preservation on resolution path  
7. Postflight + closure connected on execute path  
8. Dogfood evidence consistent with code  
9. No in-scope bypass to executor found  

### Machine summary

```text
S7_APPLICATION_VERIFICATION:
VERIFIED

EXPLICIT_RUNNER_SCOPE:
APPLICATION_VERIFIED

AUTO_RESOLUTION_APPLICATION:
PASS

AUTHORIZATION_ENFORCEMENT:
PASS

RUNNER_FINAL_VERIFY:
PASS

BLOCKED_FAIL_SAFE:
PASS

ORIGINAL_ACTION_PRESERVATION:
PASS

POSTFLIGHT_CLOSURE_APPLICATION:
PASS

DOGFOOD_EVIDENCE_MATCH:
PASS

EXPLICIT_RUNNER_BYPASS:
NONE_FOUND

GENERAL_RUNTIME:
NOT_CONNECTED

READY_FOR_S8_RUNTIME_BRIDGE:
true
```

**Scope statement:** `APPLICATION_VERIFIED` applies to **Explicit Test Runner only**. Agent chat, tool gate, and shell remain **GENERAL_RUNTIME = NOT_CONNECTED**.

**S8 entry:** With `S7_APPLICATION_VERIFICATION = VERIFIED` and `READY_FOR_S8_RUNTIME_BRIDGE = true`, proceed to **S8 READ-ONLY** design for **Test Action Runtime Bridge** (routing only; reuse S7a stack — no reimplementation of safety logic).

---

## 7. S8 — Runtime Bridge (READ-ONLY design pointers; not implemented)

**Goal (future):**

```text
Agent action (TEST_EXECUTION)
  → Test Safety Runtime Bridge (routing only)
  → run_explicit_test_with_auto_resolution / explicit runner
  → Safety resolution → execute → postflight → closure
  → Results back to Task Runtime
```

**Code facts at verification time (no changes made in S7):**

| # | Topic | Observation |
|---|--------|-------------|
| 1 | How agent runs tests today | Via LLM `tool_call` → `_execute_agent_tool` (`agent_turn.py`); no dedicated test action type. |
| 2 | `ActionRecord` | `tools/ai/task_runtime.py`: `action_id`, `task_id`, `type`, `tool_name`, `arguments`, …; orchestration records `type="tool_call"`. |
| 3 | Shell vs test | Distinguished only by registry tool name; no `TEST_EXECUTION` model yet. |
| 4 | Explicit `TEST_EXECUTION` type | Not present; requires design decision (new `type` vs constrained tool + plan schema). |
| 5 | Routing before `_execute_agent_tool` | Likely insertion at tool dispatch in `agent_turn` (after `agent_tool_gate`); orchestrator hook possible later. |
| 6 | Returning results to task runtime | Map `TEST_SAFETY_EXPLICIT_RUN` / `runner_evidence` to `ActionRecord` + `EvidenceRecord` (`run_closed`, `closure_reason`, execution tail). |
| 7 | Failure / repair | Task `FailureRecord` / revalidation exist; mapping from `resolution_stop_reason` / `AWAITING_HUMAN_APPROVAL` not designed. |
| 8 | Duplicate suppression | Runner: `ConsumedAuthorizationRegistry` per binding key; agent duplicate-call policy is a separate layer — bridge should bind stable `action_id`. |
| 9 | Human approval | Runner stops with `AWAITING_HUMAN_APPROVAL`; chat human-approval runtime is separate — bridge must surface state, not re-run gate logic. |
| 10 | No safety reimplementation | Thin wrapper calling `run_explicit_test_with_auto_resolution(action_id, plan, repo_root, …)` with plan supplied by task/runtime. |

**S8 prohibition (unchanged):** Do not modify in bridge design phase without explicit approval: ChatTaskOrchestrator, `_execute_agent_tool`, `ActionRecord`, `agent_tool_gate`, runner, test safety core, CI, shell, Git Governance, human approval runtime — **position only** until S8 design is approved.

---

## 8. References

| Asset | Path |
|-------|------|
| CLI | `tools/run_authorized_test_plan.py` |
| S7a resolution | `tools/test_safety/safety_resolution.py` |
| Runner wedge | `tools/test_safety/runner_wedge.py` |
| Authorization | `tools/test_safety/authorization.py` |
| Postflight / closure | `tools/test_safety/postflight.py` |
| Dogfood plan | `tools/test_safety/reference_cases/dogfood_s2_s7a_regression.json` |
| Dogfood run artifact | `reports/TEST_SAFETY_DOGFOOD_EXPLICIT_RUN.json` (regenerable; not required in git) |
| Architecture (S4) | `reports/TEST_SAFETY_S4_RUNTIME_ARCHITECTURE.md` |
| S7a implementation report | `reports/TEST_SAFETY_S7A_REPORT.md` |
