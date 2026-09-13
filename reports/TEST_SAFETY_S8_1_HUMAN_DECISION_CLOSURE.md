# Test Safety — S8.1 Human Decision Closure

**Status:** CLOSED (design only; **no repository code changes in S8.1**)  
**Supersedes:** none (extends `reports/TEST_SAFETY_S8_RUNTIME_BRIDGE_ARCHITECTURE.md`)  
**S8 Architecture Review:** **APPROVED**  
**Prerequisite:** `reports/TEST_SAFETY_S7_APPLICATION_VERIFICATION.md` — `APPLICATION_VERIFIED` (Explicit Runner)  
**Amendment:** 2026-09-12 — Human clarifications on D6, D2, D3, D4, D5, D7 (closure text only)

---

## Canonical Human Decision Summary

```text
Representation — D1:
  Canonical tool name: run_test_plan.
  Structured tool argument: arguments.test_plan (object).
  Normative plan shape: registry/schema/test_safety_evaluation.schema.json#/$defs/test_plan.
  Tool-arg JSON Schema: prefer single canonical $ref to that $defs/test_plan (no duplicated subset without Human Decision).
  S9: verify current schema loader resolves external/cross-file $ref; if NOT_SUPPORTED, stop — do not silently duplicate constraints to proceed.
  Bridge must not infer or generate test_plan from commands/shell.

Tool trust (agent_tool_gate) — D6:
  run_test_plan in repo default auto_allow (registry/agent_tool_trust.json).
  agent_tool_gate is NOT skipped for run_test_plan (tool trust still runs).
  auto_allow permits the TOOL only; Test Safety MUST still run on every execution.
  Safety Bridge path enabled together with run_test_plan (no shadow path).
  FORBIDDEN: fallback to direct pytest / shell / _execute_agent_tool generic execution for test intent.
  Do not merge agent_tool_gate semantics with Test Safety authorization.

Routing:
  ChatTaskOrchestrator.execute_test_plan_action → thin runtime_bridge → run_explicit_test_with_auto_resolution.
  agent_turn: single dispatch branch for run_test_plan.
  Only authoritative path: bridge → S7a stack (no parallel pytest shortcut).

Action identity — D2:
  Single allocation authority: allocate_action_id() (orchestrator) is the ONLY source of A{n}.
  Same id → bridge (Safety action_id) → observe_tool(predetermined_action_id=...).
  No LLM-supplied action_id; no bridge-generated surrogate id; no second increment on observe.

Recording:
  observe_tool path (not split record_test_action).

Duplicate / retry (Runtime) — D3:
  should_execute() implementation unchanged.
  evidence_gain=false on failed pytest or safety-blocked runs allows a FUTURE attempt
    (should_execute may return true) — but non-gain does NOT trigger automatic retry.
  Agent/orchestrator must issue an explicit new tool call to retry; no implicit re-run loop.
  evidence_gain candidate only when predicate (D4) holds plus existing audit/novel rules.

Evidence persistence — D8:
  Full TEST_SAFETY_EXPLICIT_RUN under runs/ — audit / detailed evidence canonical (not LLM context).
  EvidenceRecord: persisted path + structured summary (flags: run_closed, test_failed, resolution_result, …).
  LLM: never inject full packet into context on every turn.
  Traceability: action_id → runs/ path (or equivalent index) → full packet.
  runs/** : generated artifact — not Git commit target.

Completion — D4 (normative predicate):
  Condition label: test_run_closed (string id on task only).
  AUTHORITATIVE satisfaction predicate (from persisted run evidence / runs/ packet):
    executor_called == true
    AND test_failed == false
    AND run_closed == true
  run_closed means TEST SAFETY LIFECYCLE CLOSED — NOT "test succeeded" by itself.
    (e.g. pytest may pass while run_closed is false if postflight/closure rules fail.)
  Never call support_completion_conditions for test_run_closed unless predicate is verified
    against evidence — never from the condition name alone.

Human approval resume — D5:
  bridge accepts optional authorization_packet (CLI --authorization-json parity).
  Resume = continuation of same action_id; no duplicate ActionRecord.
  No durable pending store (S6.1 unchanged).
  OUT OF SCOPE / NOT_CONNECTED in D5: who produces the human-approved AUTHORIZED packet
    after approval (UI, CLI, external workflow) — deferred to S9+ / Human Approval Runtime bridge.

Goal Handoff / S9 plan boundary — D7:
  S9 initial wedge: PRESTRUCTURED_TEST_PLAN_ONLY (structured test_plan in tool arguments).
  Bridge-inferred test_plan from shell/commands: FORBIDDEN.
  Handoff test_plan.pytest[] → Safety test_plan: separate module, S9+ (not in S9 wedge).

S9 scope:
  Bridge routing only; no Validator/Gate/Authorization/executor/postflight reimplementation.
```

---

## S8 Fixed Context (not re-opened)

The following remain **approved without revision** in S8.1:

- `run_test_plan` tool model (vs generic shell parse)
- `ChatTaskOrchestrator.execute_test_plan_action`
- Thin `tools/test_safety/runtime_bridge.py` → existing S7a stack
- Test Safety logic reuse; no reimplementation in Bridge
- Bridge must not infer/generate `test_plan` from commands

S4.1 / S6.1 Human Decisions (fingerprints, BLOCKED vs TEST_FAILED, one auto-resolution per run, no global pending store, etc.) **stand**; this closure only adds **Runtime Bridge** decisions.

---

## Decision 1 — S8.1-D1: Tool name / schema

**APPROVED: Option A.**

| Item | Choice |
|------|--------|
| Canonical tool name | **`run_test_plan`** |
| Structured argument | **`arguments.test_plan`** (object passed to bridge unchanged after validation) |
| Normative plan schema | **`registry/schema/test_safety_evaluation.schema.json#/$defs/test_plan`** |
| Tool argument JSON Schema | **`registry/schema/`** file for tool input; **prefer `$ref`** to evaluation `#/$defs/test_plan` as **single canonical** definition |
| S9 schema loader | **Must verify** whether existing loaders (e.g. `validate_packet_schema` / registry validation) **resolve external or cross-file `$ref`** when validating tool arguments |
| If external `$ref` not supported | **Do not** silently duplicate `test_plan` constraints to unblock S9 — **stop** and obtain Human Decision (e.g. `ReferencingRegistry`, bundled schema, or explicit approved mirror) |
| Bridge `test_plan` inference | **FORBIDDEN** (no command scraping / plan synthesis in bridge) |

**S8.1 code note (READ-ONLY):** Today `tools/test_safety/validator.py` `validate_packet_schema` loads one schema file and uses `Draft202012Validator(schema)` without a cross-file registry — **tool-arg external `$ref` resolution is NOT_VERIFIED in S8.1**; S9 implements per row above.

---

## Decision 2 — S8.1-D6: `agent_tool_gate`

**APPROVED: Option A** (extended — `auto_allow` alone is insufficient).

| Item | Choice |
|------|--------|
| `run_test_plan` in default `auto_allow` | **Yes** — `registry/agent_tool_trust.json` (or documented repo initial value) |
| **Omit `agent_tool_gate` for test runs** | **Forbidden** — `authorize_tool_execution` (or equivalent trust check) **still runs** for `run_test_plan` |
| **After `auto_allow`** | **Test Safety stack mandatory** on every execution (validator → gate → authorization → runner). `auto_allow` ≠ plan authorized. |
| **Activation timing** | Safety Bridge path **enabled together with** `run_test_plan` wiring — no period where the tool runs without bridge |
| **Fallback** | **Forbidden** — no direct `pytest` / shell / generic tool path as substitute when bridge or safety stops |
| Plan-level authorization | **Test Safety only** |

---

## Decision 3 — S8.1-D2: `observe_tool` API

**APPROVED: Option A** (extended — single action-id authority).

| Item | Choice |
|------|--------|
| **Single allocation authority** | **`allocate_action_id()`** on orchestrator is the **only** issuer of runtime `A{n}` for `run_test_plan` |
| API shape | **`observe_tool(..., predetermined_action_id=None)`** — when set, must equal id from `allocate_action_id()` for that invocation |
| Index rule | Predetermined path: **no** second `_action_index` increment |
| Safety binding | **Same** `action_id` string passed to `bridge_test_execution` / `run_explicit_test_with_auto_resolution` |
| Alternative `record_test_action` split path | **Rejected** |

---

## Decision 4 — S8.1-D3: `should_execute` interaction

**APPROVED: Option A** (extended — no auto-retry from non-gain).

| Item | Choice |
|------|--------|
| `should_execute()` implementation | **Unchanged** |
| `evidence_gain` on failure / safety deny | **false** |
| `evidence_gain` candidate | Only when **D4 normative predicate** holds (plus existing audit/novel rules) |
| **Non-gain ≠ auto-retry** | Prior attempt with `evidence_gain=false` **does not** schedule or trigger automatic re-execution; **explicit** new agent tool call required |
| Runtime-only `run_token` in arguments | **Rejected** (S8.1) |

---

## Decision 5 — S8.1-D8: Evidence persistence

**APPROVED: Option A** with LLM boundary.

| Item | Choice |
|------|--------|
| Full packet storage | **`runs/`** — complete `TEST_SAFETY_EXPLICIT_RUN` JSON per run |
| Canonical role of full packet | **Audit and detailed evidence authority** (predicate checks, human review, post-hoc join) |
| `EvidenceRecord` | **Path** to `runs/` artifact + **structured summary** (not full packet body) |
| LLM context | **Never** return full packet on every turn — summary / tail / flags only in tool result |
| Traceability | **`action_id` → `runs/` path** (naming convention fixed in S9) so full packet is recoverable |
| Git | **`runs/**` is generated output — exclude from Git commits** (same class as other run artifacts) |

---

## Decision 6 — S8.1-D4: Completion condition id

**APPROVED: Option A** — **normative predicate is canonical** (not “check predicate” in prose only).

### Condition label (task vocabulary only)

`test_run_closed` — string in `TaskRecord.completion_conditions`; **not** self-sufficient proof.

### Authoritative predicate (normative)

Evaluated against **persisted** Test Safety run evidence (e.g. `runs/` packet or equivalent structured fields). **All** must hold:

| Field | Required value | Meaning |
|-------|----------------|---------|
| `executor_called` | `true` | Authorized execution path ran pytest (or declared commands) |
| `test_failed` | `false` | Pytest/commands reported success in runner evidence |
| `run_closed` | `true` | **Safety lifecycle closed** per `evaluate_run_closure` — **not** synonymous with “test passed” alone |

**Semantics of `run_closed`:** lifecycle/postflight/closure rules satisfied enough to close the safety run (e.g. `closure_reason` such as `NO_REQUIRED_POSTFLIGHT` or successful required postflight). A pytest pass with `run_closed == false` **does not** satisfy this predicate.

### Mechanism

1. Load evidence for the test action (path from `EvidenceRecord` / tool result).  
2. Evaluate the **three-field predicate** above.  
3. Only then call `support_completion_conditions(task_id, evidence_id, ["test_run_closed"])`.

**Forbidden:** satisfying `test_run_closed` from the condition name, from pytest pass alone, or without reading run evidence.

---

## Decision 7 — S8.1-D5: Human approval resume

**APPROVED: Option A** with continuation semantics.

| Item | Choice |
|------|--------|
| Packet re-entry | **`bridge_test_execution(..., authorization_packet=...)`** — CLI `--authorization-json` parity |
| Valid pre-auth | **`RESOLUTION_SKIPPED`** → runner verify |
| Resume semantics | **Same `action_id` continuation** — **no duplicate `ActionRecord`** |
| Global pending authorization store | **Still none** (S6.1) |

### Explicitly out of D5 scope (NOT_CONNECTED)

| Topic | Status |
|-------|--------|
| **Who generates** the human-approved `TEST_SAFETY_AUTHORIZATION` packet after approval | **NOT_CONNECTED** — not decided in S8.1; no Human Approval Runtime UI/workflow in S9 wedge |
| Binding approval UI to binder | **Deferred** — D5 only defines **how a supplied packet re-enters** the bridge |

---

## Decision 8 — S8.1-D7: Goal Handoff adapter

**APPROVED: Option A** (extended — S9 boundary fixed).

| Item | Choice |
|------|--------|
| **S9 initial wedge mode** | **`PRESTRUCTURED_TEST_PLAN_ONLY`** — tool arguments carry full structured `test_plan` |
| **Bridge plan inference** | **`FORBIDDEN`** — no command scraping, no shell→plan inside bridge |
| **Handoff → Test Plan** | **`pytest[]` → Safety `test_plan` conversion** in a **separate module**, **S9+** (not shipped with first bridge wedge) |
| Handoff auto-adapter in S9 wedge | **No** |

---

## S9 Entry Condition Checklist

| Item | S8.1 status |
|------|-------------|
| S8 architecture approved | **YES** |
| All 8 OPEN_DECISIONS closed (with amendments above) | **YES** |
| S7 APPLICATION_VERIFIED | **YES** (Explicit Runner) |
| Implementation scope bounded | **YES** |
| S4.1 / S6.1 not contradicted | **YES** |

**S9 implementation:** allowed by human decision; **auto-start forbidden** until explicit S9 implementation task / approval.

---

## Final status (S8.1 consistency check)

```text
S8_ARCHITECTURE_STATUS: CLOSED_SINGLE_OPTION
S8_1_HUMAN_DECISIONS: CLOSED
IMPLEMENTATION_READY: true
READY_FOR_S9_IMPLEMENTATION: true
AUTO_START_S9: false
```

---

## S9 Initial Wedge (reminder)

1. `tools/test_safety/runtime_bridge.py` (thin)  
2. `run_test_plan` + orchestrator `execute_test_plan_action` + **`allocate_action_id` (single authority)**  
3. `agent_turn` dispatch — **gate + bridge**; **no pytest fallback**  
4. Tests (mock bridge + one real-stack integration)  
5. **Mode:** `PRESTRUCTURED_TEST_PLAN_ONLY`  
6. **Exclude:** Handoff adapter module, CI/shell intercept, `TEST_EXECUTION` enum, Human Approval packet **generation** UI, Safety stack edits  

---

## Evidence refs

- `reports/TEST_SAFETY_S8_RUNTIME_BRIDGE_ARCHITECTURE.md`
- `reports/TEST_SAFETY_S8_1_HUMAN_DECISION_CLOSURE.md` (this file)
- `reports/TEST_SAFETY_S8_1_HUMAN_DECISION_APPLIED.json`
- `reports/TEST_SAFETY_S7_APPLICATION_VERIFICATION.md`
