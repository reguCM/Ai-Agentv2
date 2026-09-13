# Development Test Safety — S6 Automatic Safety Resolution Architecture (READ-ONLY)

**Date:** 2026-09-12  
**Scope:** `TEST_EXECUTION` only. **No code / policy / registry changes in S6.**

---

## Executive summary

S5a–S5c established an **authoritative lifecycle** on the **explicit test runner wedge** when callers supply a complete chain (evaluate → gate → bind → verify → execute → postflight → closure).

**Missing Authorization Resolution** — automatically detecting “no valid authorization for this original test action,” running safety evaluation, and **resuming the same action** without LLM re-planning — is **NOT_CONNECTED** in code today. The CLI `run_authorized_test_plan.py` always calls `prepare_evaluation_and_authorization` **before** `execute_authorized_test_plan`; there is no branch for “authorization absent → resolve → resume.”

S6 design concludes: **feasible** on top of existing primitives, with **Architecture B** as the target shape and an **initial wedge** that extends the runner layer (Architecture A/B hybrid) without touching Chat Runtime or `agent_tool_gate`.

---

## 1. CURRENT_EXECUTION_PATH (code-verified)

### Authoritative test safety path (CONNECTED)

```text
test_plan (+ action_id)
  → evaluate_test_plan()                    [tools/test_safety/validator.py]
  → evaluate_shadow_gate()                  [tools/test_safety/shadow_gate.py]
  → bind_test_safety_authorization()        [tools/test_safety/authorization.py]
  → execute_authorized_test_plan()          [tools/test_safety/runner_wedge.py]
       → verify_authorization_for_execution()
       → ConsumedAuthorizationRegistry (exactly-once spawn)
       → executor (default_pytest_executor)
       → run_required_postflight()           [tools/test_safety/postflight.py]
       → evaluate_run_closure()
  → TEST_SAFETY_RUNNER_EVIDENCE
```

Entry: `tools/run_authorized_test_plan.py` (explicit; not CI, not chat).

### Everything else (NOT_CONNECTED to test safety)

| Path | Observation |
|------|-------------|
| Shell / CI `python -m pytest` | No safety layer |
| `ai_tool/run_agent_test_batch.py` | `run_chat_turn` agent tests; not pytest safety |
| `_execute_agent_tool` → `authorize_tool_execution` | **Project Agent tool trust** (`tools/system/agent_tool_gate.py`); tool name + `auto_allow` list; **not** `TEST_SAFETY_AUTHORIZATION` |
| `task_execution_guard` | Superseded task / premise revalidation blocks; **not** test safety |
| Research `decide_execution_gate` | Separate pipeline (`tools/ai/state/execution_gate.py`) |

---

## 2. MISSING_AUTHORIZATION_DETECTION_POINT

### Today

| Location | Detects missing auth? |
|----------|------------------------|
| `execute_authorized_test_plan` | **No.** Expects `authorization_packet`. If `authorization != AUTHORIZED` after verify → `SAFETY_AUTHORIZATION_FAILURE`; does **not** invoke validator. |
| `run_authorized_test_plan.py` | **External:** always runs `prepare_evaluation_and_authorization` first — resolution is **manual orchestration**, not automatic. |
| `bind_test_safety_authorization` | Produces AUTHORIZED/DENIED; not invoked on “missing packet.” |

### Option comparison (§4)

| Option | Fit | Code reality |
|--------|-----|--------------|
| **A — Runner boundary** | **Best initial wedge** | Runner already owns verify + execute + postflight. Missing-auth detection = first step before verify: “no packet / stale / wrong binding → resolution required.” |
| **B — Authorization Resolver** | **Best final shape** | **No** class/module named Authorization Resolver. Closest analogues: `authorize_tool_execution` (different domain), `task_execution_blocked` (task guards). A dedicated **Test Safety Resolver** layer is **new design**, not an existing runtime type. |
| **C — Tool execution boundary** | **Defer** | Test runner **does not** use `_execute_agent_tool`. Forcing test safety into `agent_tool_gate` would conflate tool trust with plan-bound authorization (S4.1 violation risk). Future: only if a **registered test-runner tool** uses that path (S4 Option B deferred). |

**Recommended detection point (initial):** inside or immediately before `execute_authorized_test_plan` / a thin `resolve_test_safety_if_needed()` called from the **explicit runner only**.

**Recommended detection point (final):** standalone **Test Safety Resolution** module called by runner (and later other TEST_EXECUTION entrypoints), not embedded in validator/gate/binder.

---

## 3. AVAILABLE_ACTION_PRESERVATION_MECHANISM

| Mechanism | Code | Test safety suitability |
|-----------|------|-------------------------|
| `ActionRecord` | `tools/ai/task_runtime.py` | `action_id`, `type`, `tool_name`, `arguments` — **can carry** `test_plan` / `commands` in `arguments` without new schema fields (S4.1). **Not wired** to runner today. |
| `accept_semantic_followup` → `status: EXECUTABLE`, `action` dict | `task_orchestration.py` | Pattern: single retained action payload; **not** test-specific; no authorization hook. |
| H4 “pending action” inject | tests / help selection | **Read/search** bridge; not a general pending-action store on `AgentTaskRuntime`. |
| Runner `action_id` + `current_plan` args | `runner_wedge.py` | **CONNECTED** for wedge; original action = caller-supplied id + plan dict — **no LLM** if caller preserves them. |

**Gap:** Chat/orchestrator does not enqueue “pending TEST_EXECUTION” with safety state. For S7 implementation, prefer **runner-held request object** `{action_id, test_plan}` or `ActionRecord` snapshot passed through resolution → same references on resume.

**Principle (S4.1 / §3):** Resolution must not mutate `commands` / fingerprint-relevant fields; only attach `evaluation_ref` + `authorization_id` externally (evidence / sidecar).

---

## 4. AVAILABLE_RESUME_MECHANISM

| Mechanism | Resume without LLM? | Notes |
|-----------|----------------------|-------|
| `verify_authorization_for_execution` + same `authorization_packet` | **Yes** (S5a/b) | **Required** immediately before executor (§15). |
| `ConsumedAuthorizationRegistry` | **Once per binding key** | Prevents double **execution**; does not replace re-verify on resume after async gap. |
| `should_execute` | Partial | Suppresses duplicate **tool** calls with same args when prior action had `evidence_gain`; **not** authorization-aware. |
| Orchestrator “continuation” / mission `completion_runtime` | Human-driven | Restores task graph; **no** test safety authorization restore. |
| `apply_human_decision` | Research safety assessment only | `tools/ai/state/safety_assessment.py`; **not** test safety. |

**Resume design (S7+):** After resolution yields `AUTHORIZED`, call **same** `execute_authorized_test_plan(action_id, current_plan, authorization_packet, ...)` with **unchanged** `action_id` and plan; no new action_id for “retry after safety.”

---

## 5. BLOCKED_STATE_MAPPING

Gate / binder today:

- `gate_decision == BLOCKED` → `authorization == DENIED` (S5a).
- Runner: `SAFETY_AUTHORIZATION_FAILURE`, `executor_called=false`, `test_failed=false` (S5b).

**Do not map safety BLOCKED to `TEST_FAILED`.**

| Safety outcome | Suggested runtime / evidence mapping (no new enum in S6) |
|----------------|----------------------------------------------------------|
| Safety forbidden (relevant UNKNOWN, prohibited side effect) | `authorization=DENIED`; evidence `outcome=SAFETY_AUTHORIZATION_FAILURE`; optional `TaskStatus.BLOCKED` **only when** action is task-bound in orchestrator (future). |
| Original action retention | Keep `ActionRecord` / runner request **unchanged**; store `blocked_reasons` on resolution evidence. |
| Retry | **Not automatic.** Explicit human or system **re-resolution** after re-evaluation triggers (§12). |

**No** `BLOCKED_WAITING_FOR_SAFETY_RESOLUTION` (S4.1).

---

## 6. HUMAN_APPROVAL_MAPPING

Binder (S5a): `human_approval_required` on gate → `DENIED` with `HUMAN_APPROVAL_REQUIRED` (execution auth not granted).

| Class | Gate | Authorization | Runtime expression (existing strings) |
|-------|------|---------------|----------------------------------------|
| A — Safety impossible | BLOCKED | DENIED | Evidence denial; optional `TaskStatus.BLOCKED` |
| B — Possible but approval needed | PASS + `human_approval_required` | DENIED (today) | **`AWAITING_HUMAN_APPROVAL`** (`agent_recovery_loop.py`) — **not** `AWAITING_HUMAN` (grill/clarification) |

Human Approval Runtime: **NOT_CONNECTED.** Resolution output should record `resolution_result` ≈ “approval pending” in evidence JSONL, not fake approval.

---

## 7. REEVALUATION_TRIGGERS

| Trigger | Effect on authorization |
|---------|-------------------------|
| **Test plan change** (fingerprint) | Prior PASS **void**; must re-run validator → gate → bind (S4.1 Decision 1). |
| **Stale at verify** | `verify_authorization_for_execution` → `STALE_EVALUATION` / DENIED (S5a). |
| **Explicit retry** | New evaluation packet + new `evaluation_ref.generated_at`; same `action_id` allowed if plan unchanged. |
| **Human input** | May change plan → fingerprint change → full re-eval. |
| **Relevant UNKNOWN cleared** | Same plan fingerprint; **new** evaluation with updated `declared_dimensions` or host evidence → new `evaluation_ref`; then bind. |
| **BLOCKED gate** | Re-eval only after inputs change; do not loop bind on identical evaluation. |

---

## 8. HOST_STATE_REEVALUATION

**Decided (S4.1 / S5a):** host observations ∉ `plan_fingerprint`.

| Situation | Design |
|-----------|--------|
| Plan unchanged, host changed (e.g. ollama stopped, GPU now known) | **Optional** re-evaluation: same `plan_fingerprint`, new `TEST_SAFETY_EVALUATION` + `readonly_observations` / `relevant_unknowns`; new `evaluation_ref`; re-bind. |
| Same old authorization after host change | **Risk:** gate facts stale; recommend treat as **resolution required** if evaluation age/ref does not match current policy (OPEN: max TTL). |
| Irrelevant host note | PASS + warning (S3 Case D); no re-eval required for execution. |

Resolver must pass `host_process_notes` into `evaluate_test_plan` only at evaluation time; never into fingerprint.

---

## 9. LOOP_PREVENTION

| Control | Status | Use for resolution |
|---------|--------|-------------------|
| `authorization_binding_key` + `ConsumedAuthorizationRegistry` | **CONNECTED** (S5b) | Prevents double **execute** for same auth triple. |
| `verify_authorization_for_execution` before execute | **CONNECTED** | Mandatory on every execution attempt (§15). |
| Resolution loop `no auth → safety → resume → no auth` | **NOT_CONNECTED** | **Design:** (1) After successful resolution, caller must pass **authorization_packet** into execute path. (2) Cap **resolution attempts per `(action_id, plan_fingerprint)`** per run (e.g. max 1 auto-resolve unless explicit retry flag). (3) Do not re-enter resolution if last result was DENIED with unchanged plan+host inputs. |
| `should_execute` | **CONNECTED** (tool dedup) | **Not sufficient** alone for safety loops. |

---

## 10. STALE_AUTHORIZATION_PROTECTION

**Maintained:**

```text
execute path:
  verify_authorization_for_execution(action_id, current_plan)
  → fingerprint match
  → evaluation_ref match (implicit in stored auth packet)
  → AUTHORIZED
```

Resolution must **not** skip verify. If plan changes between resolution and execute → DENIED → trigger re-resolution (new fingerprint).

---

## 11. FAIL_SAFE_BEHAVIOR

| Failure | Executor | Test failed? | Resolution result |
|---------|----------|--------------|-------------------|
| Validator / gate / bind exception | NOT_CALLED | **false** | ERROR (evidence); no AUTHORIZED |
| Invalid schema / missing plan | NOT_CALLED | **false** | ERROR |
| DENIED authorization | NOT_CALLED | **false** | BLOCKED / DENIED mapping |
| Executor failure | Called | **true** (pytest) | Separate from safety; postflight still runs (S5c §8) |

Do not mark entire runtime `TEST_FAILED` for safety resolution ERROR unless existing taxonomy already does (chat agent tests use separate acceptance — **not** applicable to runner evidence).

---

## 12. EVIDENCE_CHAIN

Single run trace (design target; S7 may add `resolution` block to runner evidence):

```text
action_id
plan_fingerprint
safety_evaluation_ref     ← evaluation_ref (+ full packet in artifact store)
gate_decision
authorization_id
authorization_binding_key
resolution_result         ← NEW field (S7): RESOLVED | DENIED | APPROVAL_PENDING | ERROR
execution_verification
executor_called
execution_result
postflight_result
run_closed
closure_reason
```

**Today:** `TEST_SAFETY_RUNNER_EVIDENCE` covers execution/postflight/closure; **no** `resolution_result` field yet. Evaluation/gate/authorization stored in CLI dry-bind output or tests only.

**Feasibility:** Yes — extend evidence packet or append linked JSON artifacts under `reports/` / `runs/` without changing Task Runtime.

---

## 13. SafetyResolution concept (§6–8)

**Proposed bounded responsibility** (design only; **not implemented**):

```text
SafetyResolution (TEST_EXECUTION only)
  Input:  action_id, test_plan (from ActionRecord.arguments or runner request),
          optional existing authorization_packet, optional host_process_notes
  Steps:  if valid AUTHORIZED auth for (action_id, fingerprint) → RESOLVED (no-op)
          else evaluate_test_plan → evaluate_shadow_gate → bind_test_safety_authorization
  Output: resolution_status + authorization_packet + evaluation_ref + gate_decision
  Must NOT: pytest, LLM replan, mutate plan fingerprint inputs, fake human approval
```

### Resolver output → existing mapping (§8)

| Logical output | Map to (avoid new enum) |
|----------------|------------------------|
| RESOLVED | `authorization == AUTHORIZED`; proceed to existing execute path |
| BLOCKED | `authorization == DENIED` or gate BLOCKED; evidence `SAFETY_AUTHORIZATION_FAILURE` |
| AWAITING_HUMAN_APPROVAL | `HUMAN_APPROVAL_REQUIRED` + status string `AWAITING_HUMAN_APPROVAL` in evidence |
| ERROR | DENIED + `reasons` include resolver error; executor not called |

---

## 14. PASS resume checklist (§9)

Before executor:

- [ ] `action_id` equals original request
- [ ] `current_plan` fingerprint equals `authorization.plan_fingerprint`
- [ ] `evaluation_ref` matches evaluation packet used at bind time
- [ ] `verify_authorization_for_execution` returns AUTHORIZED
- [ ] `ConsumedAuthorizationRegistry` allows consume (first spawn) or explicit new run id for retry policy

**No LLM** in this path.

---

## 15. Postflight (§17)

Automatic resolution **ends** at AUTHORIZED handoff. S5c unchanged:

```text
Authorization → Execute → required_postflight → Closure
```

Resolver does not run postflight.

---

## 16. ARCHITECTURE_OPTIONS (§19)

| Arch | Description | Verdict |
|------|-------------|---------|
| **A — Runner embedded** | Runner detects missing auth → inline safety → execute | **Minimal; good first code** |
| **B — Test Safety Resolution Layer** | `resolve_test_safety()` → runner execute | **Recommended target** — matches validator/gate/binder separation |
| **C — General Authorization Resolution** | Any action type | **Over-scoped for S7**; keep interfaces narrow (`TEST_EXECUTION` only) |

---

## 17. RECOMMENDED_FINAL_ARCHITECTURE

```text
Original Test Execution Request (action_id + test_plan)
        ↓
Test Safety Resolution Layer
  ├─ has valid AUTHORIZED binding? → hand off
  └─ else → Validator → Gate → Binder
        ↓
  BLOCKED / APPROVAL_PENDING / ERROR → hold original action; no executor
  AUTHORIZED → verify_authorization_for_execution (again at runner)
        ↓
Runner Wedge (existing S5b/c)
  → executor → postflight → closure
```

**Final form:** Architecture **B**, with policy scope **TEST_EXECUTION** only and extension point `action_type == "TEST_EXECUTION"` for future generalization (§18).

---

## 18. RECOMMENDED_INITIAL_WEDGE

```text
Phase S7a (proposed; not started):
  tools/test_safety/safety_resolution.py
    resolve_test_safety_authorization(action_id, test_plan, ...) → resolution evidence + auth packet

  extend execute path:
    run_authorized_test_plan.py OR new run_test_execution_with_resolution.py
      if authorization missing or verify fails with STALE:
        resolve → if AUTHORIZED → execute_authorized_test_plan(same action_id, same plan, auth)
      else return safety failure evidence

  tests: fake executor only first; then one controlled pytest (mirror S5b-2)
```

**Do not** connect CI, chat, or `_execute_agent_tool` in the first wedge.

---

## 19. IMPLEMENTATION_READY

```text
IMPLEMENTATION_READY: false

Reason: S6 is READ-ONLY design only. Primitives exist (S5a–c); missing-auth resolution and evidence field `resolution_result` are NOT_CONNECTED.
```

---

## 20. OPEN_DECISIONS

1. **Where to persist** authorization between resolution and resume (runner in-memory vs `ActionRecord.arguments` vs run artifact file).
2. **Authorization TTL** — same fingerprint + old `evaluation_ref` after host state change: always re-resolve or time-bound?
3. **Orchestrator integration** — when TEST_EXECUTION lives on `ActionRecord`, who calls resolver (runner only vs task loop).
4. **Human approval** — record `AWAITING_HUMAN_APPROVAL` only in evidence vs also set `TaskStatus.BLOCKED`.
5. **Max auto-resolution attempts** per `(action_id, plan_fingerprint)` per session.
6. **Shadow vs authoritative gate packet** — resolution should produce binding from same `decide_gate_from_evaluation`; authoritative flag on authorization packet only (current S5a).
7. **CI entry** — explicit opt-in wrapper script vs forbidden until Human decision.

---

## 21. Final report block (required)

```text
CURRENT_EXECUTION_PATH:
  Explicit runner: evaluate → gate → bind → verify → execute → postflight → closure (CONNECTED).
  All other pytest/chat/tool paths: NOT_CONNECTED.

MISSING_AUTHORIZATION_DETECTION_POINT:
  NOT_CONNECTED; recommended at Test Safety Resolution Layer / runner pre-verify (Option A+B).

AVAILABLE_ACTION_PRESERVATION_MECHANISM:
  ActionRecord.arguments + runner action_id/plan; EXECUTABLE follow-up pattern (orchestrator); no global pending-action store.

AVAILABLE_RESUME_MECHANISM:
  verify_authorization_for_execution + same auth packet; ConsumedAuthorizationRegistry for spawn-once.

BLOCKED_STATE_MAPPING:
  DENIED / SAFETY_AUTHORIZATION_FAILURE; TaskStatus.BLOCKED optional when task-bound; not TEST_FAILED.

HUMAN_APPROVAL_MAPPING:
  HUMAN_APPROVAL_REQUIRED → AWAITING_HUMAN_APPROVAL (evidence); distinct from safety BLOCKED.

REEVALUATION_TRIGGERS:
  Plan fingerprint change (mandatory); explicit retry; UNKNOWN/host evidence update (same fingerprint).

HOST_STATE_REEVALUATION:
  Re-run evaluate with host_process_notes; new evaluation_ref; fingerprint unchanged.

LOOP_PREVENTION:
  binding_key consume + verify + resolution attempt cap (to implement); should_execute insufficient alone.

STALE_AUTHORIZATION_PROTECTION:
  verify_authorization_for_execution mandatory (existing S5a/b).

FAIL_SAFE_BEHAVIOR:
  Resolver/validator failures → no executor; not TEST_FAILED.

EVIDENCE_CHAIN:
  Feasible via extended RUNNER_EVIDENCE + artifact refs; resolution_result not yet in schema.

ARCHITECTURE_OPTIONS:
  A runner-embedded; B resolution layer (recommended); C general (defer).

RECOMMENDED_FINAL_ARCHITECTURE:
  Test Safety Resolution Layer → existing Runner Wedge (TEST_EXECUTION only).

RECOMMENDED_INITIAL_WEDGE:
  safety_resolution.py + runner/CLI orchestration; fake tests then one controlled pytest.

IMPLEMENTATION_READY:
  false (S6 READ-ONLY complete)

OPEN_DECISIONS:
  7 items (§20)
```

---

## 22. S6 compliance

- No changes to `runner_wedge`, `authorization.py`, `validator.py`, `shadow_gate.py`, Task/Chat Runtime, `agent_tool_gate`, CI, policy, registry, P2b.
- No new resolver implementation in S6.

**S7 implementation requires explicit Human approval** (do not auto-start).
