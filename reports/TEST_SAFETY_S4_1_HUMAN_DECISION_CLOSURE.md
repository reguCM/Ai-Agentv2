# Development Test Safety — S4.1 Human Decision Closure

**Status:** CLOSED (design only; **no repository code changes in S4.1**)  
**Supersedes:** none (extends `reports/TEST_SAFETY_S4_RUNTIME_ARCHITECTURE.md`)  
**S4 Architecture:** **APPROVED**

---

## Human Decision Summary (canonical)

```text
Safety PASS is bound to:
  action_id + plan_fingerprint + evaluation_ref + gate_decision

Original Action:
  preserve, do not regenerate

PASS:
  authorize existing Executor (Gate does not run pytest)

BLOCKED:
  do not execute; do not mark TEST_FAILED

Human Approval:
  distinct from Safety BLOCKED

Invalid/stale evaluation:
  authorization = DENIED (not TEST_FAILED)

Postflight required:
  must complete before Run CLOSED

Initial Runtime Scope:
  TEST_EXECUTION only

Initial Connection:
  explicit Test Runner / test entry (S4 Option A wedge)

Final Lifecycle (target):
  Action → Safety → Authorization → Execute → Postflight → Closure

Option C (Required First Action):
  adopted as final lifecycle narrative only;
  do not implement against non-existent RequiredFirstAction / ExecutionOrderConstraint / authorize_action_proposal primitives in S5
```

---

## Decision 1 — Safety Authorization Identity

**APPROVED.**

| Field | Role |
|-------|------|
| `action_id` | Original test execution action (stable for exactly-once) |
| `plan_fingerprint` | Cryptographic-stable hash input over **plan-only** safety inputs |
| `evaluation_ref` | Pointer to `TEST_SAFETY_EVALUATION` (schema_version, validator_id, generated_at, optional reference_case_id) |
| `gate_decision` | `PASS` \| `BLOCKED` at authorization time |

**Invalidation rule:** If `fingerprint(current_plan) != fingerprint(authorized_plan)`, any prior PASS authorization is **void**; require full re-evaluation.

### `plan_fingerprint` normative inputs (S5a)

Fingerprint **includes** (from declared test plan + commands used for validator evaluation):

| Key | Source on plan |
|-----|----------------|
| `commands` | `test_plan.commands` (ordered list, normalized) |
| `declared_primary_risk_level` | optional override |
| `declared_dimensions` subset | at minimum dimensions that affect safety: `llm`, `gpu`, `network`, `subprocess`, `long_running_process`, `tool_execution`, `filesystem_write`, `repository_outside_write`, `git_operation`, `external_service`, `credentials`, `shared_resource` |
| `declared_write_scope` | maps to Decision text `declared_write_paths` |
| `plan_id` | identity hint only; **not** sufficient alone |

Fingerprint **excludes:**

- `host_process_notes`, readonly git snapshot, ollama on host, CPU load, etc.
- `generated_at`, `validator_id`, gate packets, run IDs

Host / environment facts live in **evaluation evidence** (`readonly_observations`, `relevant_unknowns`), not in fingerprint.

**S5a deliverable:** canonical `compute_plan_fingerprint(test_plan) -> str` + tests (fixture plans).

---

## Decision 2 — Original Action Preservation

**APPROVED.**

- Do **not** return the test plan to the LLM for regeneration after safety check.
- Preserve via existing `ActionRecord`: `action_id`, `type`, `tool_name`, `arguments` (including `commands` / operation payload).
- Safety evaluation and authorization are **separate** artifacts linked by `evaluation_ref` + fingerprint + `action_id`.

```text
Original Test Action (ActionRecord, unchanged)
  → Safety Evaluation (TEST_SAFETY_EVALUATION)
  → Authorization record
  → same Original Test Action → Executor
```

---

## Decision 3 — PASS Resume Semantics

**APPROVED.**

| Component | Responsibility |
|-----------|----------------|
| Gate | `authorization = GRANTED` only when `gate_decision == PASS` and binding valid |
| Executor | subprocess / pytest / existing runner |

Resume predicate (all required):

```text
authorized_action_id == action_id
AND evaluation_ref matches stored authorization
AND plan_fingerprint matches current plan
AND authorization not expired/superseded (exactly-once state)
```

---

## Decision 4 — BLOCKED Semantics

**APPROVED.**

```text
Safety BLOCKED ≠ TEST_FAILED ≠ REGRESSION_FAILED
```

- Do not execute test.
- Do not mark test outcome as failed due to safety block alone.
- **No new enum** in S5 (e.g. no `BLOCKED_WAITING_FOR_SAFETY_RESOLUTION`).

| Situation | Existing expression (initial) |
|-----------|-------------------------------|
| Safety-forbidden execution | `TaskStatus.BLOCKED` / goal blocked + safety `blocked_reasons` in events or run record |
| Human decision pending (non-safety-forbidden) | see Decision 5 |

---

## Decision 5 — Human Approval vs Safety Block

**APPROVED.**

| Class | Gate / runtime posture |
|-------|-------------------------|
| **A** Safety execution forbidden | `gate_decision = BLOCKED` |
| **B** Conditionally allowed but needs human approval | `gate_decision` may be `PASS` with `human_approval_required=true` **or** explicit deny until approval — runtime state **`AWAITING_HUMAN_APPROVAL`** |

Do **not** treat A and B as the same status.

### S5-pre check (READ-ONLY, existing code)

| Status | Observed usage |
|--------|----------------|
| `AWAITING_HUMAN` | `boundary_grill`, `decision_change_gate`, `goal_completion_gate`, `task_orchestration` conversation grill — **clarification / selection**, not generic approval queue |
| `AWAITING_HUMAN_APPROVAL` | `tools/system/context_monitor/agent_recovery_loop.py` — **approval-shaped** stop |

**S5 guidance:** Test Safety **human approval (B)** should align with **`AWAITING_HUMAN_APPROVAL`** semantics where a dedicated approval is required; use `AWAITING_HUMAN` only when reusing grill-style clarification (narrow). **Human Approval Runtime / UI:** still **NOT_CONNECTED**; no new UI in S5 initial wedge.

Shadow Gate today: `human_approval_required` flag exists; authoritative authorization must record approval **pending vs satisfied** separately from `BLOCKED` reasons.

---

## Decision 6 — Fail-safe

**APPROVED.**

Deny authorization (`authorization = DENIED`), **without** TEST_FAILED:

- Validator crash
- Gate crash
- Invalid evaluation packet
- Unknown evaluation schema version
- Missing evaluation
- Fingerprint mismatch
- Action identity mismatch

Map to gate reasons including existing `INVALID_OR_UNVERIFIED_EVALUATION` and S5 additions `PLAN_FINGERPRINT_MISMATCH`, `ACTION_IDENTITY_MISMATCH` (names provisional until S5a schema).

---

## Decision 7 — Exactly-once Authorization

**APPROVED.**

Prevent `Gate → resume → Gate → resume` loops for the **same** action + plan.

Store authorization state keyed by:

```text
(action_id, plan_fingerprint, evaluation_ref) → ACTIVE | VOID
```

- **Same triple + PASS:** idempotent grant; do not re-run gate for execution resume.
- **Plan change (fingerprint change):** VOID prior authorization; require re-evaluation.
- **New action_id:** new authorization chain.

S5a implements binding + state machine tests before blocking real pytest broadly.

---

## Decision 8 — Postflight Binding

**APPROVED.**

Carry `required_postflight` from gate through execution.

```text
PASS → Execute → Postflight (if required) → Run Closure
```

If `postflight_git_check_required == true` and postflight not completed with recorded result:

- Run **must not** be marked **CLOSED**.
- Test result PASS/FAIL is **orthogonal** to run closure (Decision 4).

S5c negative tests: closure blocked without postflight.

---

## Decision 9 — Initial Runtime Wedge

**APPROVED.**

First connection **only**:

```text
Explicit Test Runner / test entry (Option A)
  → Authoritative Test Safety Gate
  → existing Executor
```

Not in initial S5 wedge:

- All shell commands
- CI gate
- Broad `_execute_agent_tool` hook (Option B deferred until a dedicated test-runner tool exists)

---

## Decision 10 — Option C position

**APPROVED.**

- **Final lifecycle story:** Original Action → Required Safety Check → Resume → Execute → Postflight → Closure.
- **S5 implementation:** use **existing** primitives (`ActionRecord`, `record_action`, `emit_event`, `task_execution_guard`, runner entry) — **not** fictional `RequiredFirstAction`, `ExecutionOrderConstraint`, `authorize_action_proposal` (confirmed **NOT_FOUND** in repo as of S4).

---

## S5 Entry Condition Checklist

| Item | S4.1 status |
|------|----------------|
| Action identity | **CLOSED** (Decision 1, 2, 7) |
| Plan fingerprint | **CLOSED** (Decision 1 normative inputs) |
| PASS resume | **CLOSED** (Decision 3) |
| BLOCKED semantics | **CLOSED** (Decision 4) |
| Human approval distinction | **CLOSED** (Decision 5 + existing status mapping) |
| Postflight binding | **CLOSED** (Decision 8) |
| Exactly-once | **CLOSED** (Decision 7) |
| Initial runner wedge | **CLOSED** (Decision 9) |

```text
S5_ENTRY:
  ALLOWED
```

---

## S5 Phased Delivery (approved scope)

### S5a — Authoritative Authorization Contract / Binding

Implement and test:

```text
evaluation + action_id + plan_fingerprint → authorization record
```

- `execution_authoritative=true` on authorization artifact (distinct from S3 shadow packet)
- Fail-safe + fingerprint mismatch + exactly-once
- **No** broad pytest blocking yet (fixture / synthetic runner only)

### S5b — Explicit test entry connection

Wire **Option A** runner path to S5a authorization before executor.

### S5c — Lifecycle negatives

- Stale evaluation (plan change voids PASS)
- Postflight required → no closure without postflight
- BLOCKED does not imply TEST_FAILED
- Human approval pending vs safety BLOCKED

---

## S5 Explicit Non-Goals (carry forward)

- CI connection
- General shell gate
- GPU / file / external API / git gates (beyond test-safety postflight git **read-only** check)
- Human Approval UI new build
- Cursor development-wide gate
- P2b
- Implementing RequiredFirstAction / ExecutionOrderConstraint as new runtime types in S5

---

## Artifacts

| Document | Role |
|----------|------|
| `reports/TEST_SAFETY_S4_RUNTIME_ARCHITECTURE.md` | S4 READ-ONLY architecture (approved) |
| `reports/TEST_SAFETY_S4_1_HUMAN_DECISION_CLOSURE.md` | This closure |
| `tools/test_safety/shadow_gate.py` | Decision logic single source (unchanged in S4.1) |

---

## Final Verdict

```text
S4_ARCHITECTURE:
  APPROVED

S4_1_HUMAN_DECISIONS:
  CLOSED

S5_ENTRY:
  ALLOWED

S4_1_CODE_CHANGES:
  NONE

AUTO_START_S5:
  false
```

S5 実装開始は別途 Human の明示指示を待つ。
