# Test Safety — S6.1 Human Decision Closure

**Status:** CLOSED (design only; **no repository code changes in S6.1**)  
**Supersedes:** none (extends `reports/TEST_SAFETY_S6_AUTOMATIC_RESOLUTION_ARCHITECTURE.md`)  
**S6 Architecture Review:** **APPROVED**

---

## Canonical Human Decision Summary

```text
Persistence:
  No generic Pending Action Store in S7 initial.
  Resolution state scoped to one explicit Test Runner run (in-process).
  Durable cross-session resume: deferred.

Freshness:
  No time-TTL as primary gate.
  Validity: action_id + plan_fingerprint + evaluation_ref + verify_authorization_for_execution.
  Plan change → mandatory re-evaluation.
  Host / UNKNOWN resolution → new evaluation allowed on same plan (new evaluation_ref).

Scope (S7):
  Explicit Test Runner only.
  NOT: ChatTaskOrchestrator, _execute_agent_tool, general shell, CI.

Human states:
  Safety forbidden → BLOCKED (not TEST_FAILED).
  Approval needed → AWAITING_HUMAN_APPROVAL (distinct from BLOCKED).
  No Human Approval Runtime in S7.

Auto-resolution:
  At most ONE automatic resolution attempt per run:
    missing auth → resolve → if AUTHORIZED resume same action → else stop.
  No automatic retry loop; explicit retry or state change for re-eval.

Original action:
  Same action_id, same test plan, same plan_fingerprint during resolution.
  No LLM test action regeneration.
  Plan change → new safety evaluation required.

Resolver:
  Detect missing auth → validator → gate → bind → resolution evidence only.
  No pytest; execution delegated to existing runner_wedge (S5b/c).

Fail-safe:
  Validator/gate/bind errors, malformed packets, unresolved relevant UNKNOWN,
  plan/action mismatch, resolution attempt exhausted → no executor; not TEST_FAILED.
```

---

## Decision 1 — Persistence

**APPROVED.**

| Item | S7 initial |
|------|------------|
| Generic Pending Action Store | **Do not create** |
| Resolution state carrier | Single **explicit Test Runner run** (in-memory / run evidence on same invocation) |
| Cross-run / cross-session resume | **Deferred** (future phase) |
| `ActionRecord` persistence for safety | **Not required** in S7a |

Evidence for a run may still be written to `TEST_SAFETY_RUNNER_EVIDENCE` (+ future `resolution_result` block) as **artifacts**, not as a global pending queue.

---

## Decision 2 — Authorization / Evaluation Freshness

**APPROVED.**

**Not primary:** wall-clock TTL on authorization.

**Primary validity (unchanged from S5a/S5b):**

| Check | Mechanism |
|-------|-----------|
| `action_id` | `verify_authorization_for_execution` |
| `plan_fingerprint` | `compute_plan_fingerprint(current_plan)` vs auth packet |
| `evaluation_ref` | Bound at bind time; mismatch → DENIED |
| Authorization | `authorization == AUTHORIZED` after verify |

**Re-evaluation triggers:**

| Event | Requirement |
|-------|-------------|
| Test plan change (fingerprint) | **Mandatory** full evaluate → gate → bind |
| Relevant host state change / UNKNOWN cleared | **May** create **new** `TEST_SAFETY_EVALUATION` on **same** plan (new `evaluation_ref`); fingerprint unchanged |
| Automatic retry loop | **Forbidden** (Decision 5) |

---

## Decision 3 — Initial Connection Scope

**APPROVED.**

S7 / S7a **CONNECTED:**

- `tools/test_safety/runner_wedge.py` orchestration path
- `tools/run_authorized_test_plan.py` or successor entry that calls resolution + wedge

S7 **NOT_CONNECTED:**

- `ChatTaskOrchestrator` / `run_chat_turn`
- `_execute_agent_tool` / `authorize_tool_execution`
- General shell / Cursor shell gate
- CI pipelines

---

## Decision 4 — Human State

**APPROVED.**

| Class | Safety / gate | Runtime / evidence expression |
|-------|---------------|-------------------------------|
| Safety execution forbidden | `gate_decision=BLOCKED`, `authorization=DENIED` | `BLOCKED` semantics; **not** `TEST_FAILED` |
| Approval required, not safety-forbidden | `human_approval_required` (binder may DENIED until approval) | **`AWAITING_HUMAN_APPROVAL`** in resolution/run evidence |

- **Do not** conflate with `AWAITING_HUMAN` (grill / clarification).
- **Human Approval Runtime / UI:** not built in S7.

---

## Decision 5 — Automatic Resolution Attempt

**APPROVED.**

Per **single explicit runner run**:

```text
1. Detect missing or invalid authorization for (action_id, current_plan).
2. Run automatic safety resolution once (validator → gate → bind).
3. If AUTHORIZED → verify → delegate to execute_authorized_test_plan (same action_id, same plan).
4. If BLOCKED / ERROR / DENIED / approval unresolved → stop; executor NOT_CALLED.
```

- **Max automatic resolution attempts:** **1**
- Further re-evaluation only via **explicit retry** or **documented state change** (plan fingerprint change, new host evaluation per Decision 2).
- Loop `no auth → resolve → resume → no auth → resolve` is **forbidden** by: single auto attempt + post-resolve must attach `authorization_packet` + existing `ConsumedAuthorizationRegistry` + mandatory verify before execute.

---

## Decision 6 — Original Action

**APPROVED.**

Throughout resolution and resume:

- **Same** `action_id`
- **Same** test plan content for fingerprint purposes (no silent edits to commands / declared_*)
- **Same** `plan_fingerprint` unless human/system intentionally changes plan → triggers Decision 2 re-eval

**Forbidden:** LLM re-plan or new test action id for “after safety.”

---

## Decision 7 — Resolver Responsibility

**APPROVED.**

**In scope (S7a `safety_resolution` or equivalent):**

1. Missing / invalid authorization detection  
2. `evaluate_test_plan`  
3. `evaluate_shadow_gate` (decision rules remain `decide_gate_from_evaluation` — no duplicate)  
4. `bind_test_safety_authorization`  
5. Resolution evidence (status, reasons, evaluation_ref, authorization_id, binding_key)

**Out of scope:**

- pytest / subprocess test execution  
- Postflight (runner wedge S5c)  
- Run closure logic changes beyond passing through existing wedge  

**Delegation:** On `AUTHORIZED`, call existing `execute_authorized_test_plan` with **unchanged** `action_id`, `current_plan`, and produced `authorization_packet`.

---

## Decision 8 — Fail-safe

**APPROVED.**

Do **not** call executor when:

- Validator exception / invalid evaluation packet  
- Gate exception / invalid gate packet  
- Authorization bind failure / DENIED  
- Malformed or unknown schema version  
- Unresolved relevant UNKNOWN (gate BLOCKED)  
- Plan fingerprint mismatch at verify  
- Action id mismatch at verify  
- Automatic resolution attempt already consumed for this run  

**Not** classified as `TEST_FAILED` (safety authorization failure ≠ test outcome).

---

## S7a Entry Condition Checklist

| Item | S6.1 status |
|------|-------------|
| Persistence model | **CLOSED** (run-scoped only) |
| Freshness rules | **CLOSED** (no TTL primary) |
| Connection scope | **CLOSED** (explicit runner only) |
| Human state mapping | **CLOSED** |
| Single auto-resolution attempt | **CLOSED** |
| Original action preservation | **CLOSED** |
| Resolver vs runner split | **CLOSED** |
| Fail-safe | **CLOSED** |

```text
S7A_ENTRY:
  ALLOWED
```

---

## S7a Deliverables (approved scope; not started in S6.1)

1. `tools/test_safety/safety_resolution.py` (or agreed name) — resolution only  
2. Runner/CLI wiring: no authorization → resolve once → resume → `execute_authorized_test_plan`  
3. Tests: **fixture / fake executor** first (mirror S5b-1); **no** general runtime connection  
4. Evidence: `resolution_result` on run evidence (design); optional schema extension in S7a  
5. **No** pending store, **no** CI/chat/tool hook  

---

## S7a Explicit Non-Goals (carry forward)

- Pending Action Store (global)  
- Time-TTL authorization  
- Automatic resolution retry loops  
- Chat / `_execute_agent_tool` / CI / shell-wide gate  
- Human Approval Runtime UI  
- LLM test action regeneration  
- `development_policy` / registry changes (unless separately approved)  
- P2b  

---

## Artifacts

| Document | Role |
|----------|------|
| `reports/TEST_SAFETY_S6_AUTOMATIC_RESOLUTION_ARCHITECTURE.md` | S6 READ-ONLY architecture (approved) |
| `reports/TEST_SAFETY_S6_1_HUMAN_DECISION_CLOSURE.md` | This closure |
| `reports/TEST_SAFETY_S6_1_HUMAN_DECISION_APPLIED.json` | Machine summary |

---

## Final Verdict

```text
S6_ARCHITECTURE_REVIEW:
  APPROVED

S6_1_HUMAN_DECISIONS:
  CLOSED

S7A_ENTRY:
  ALLOWED

S6_1_CODE_CHANGES:
  NONE

AUTO_START_S7A:
  false
```

S7a implementation requires **explicit Human instruction** to begin.
