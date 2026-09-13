# Test Safety — S8 Test Action Runtime Bridge Architecture Review

**Date:** 2026-09-12  
**Mode:** READ-ONLY (no code, registry, policy, or runtime changes)  
**Prerequisite:** S7 Application Verification — `APPLICATION_VERIFIED` (Explicit Runner only). `GENERAL_RUNTIME = NOT_CONNECTED`.

**References:** `reports/TEST_SAFETY_S7_APPLICATION_VERIFICATION.md`, `reports/TEST_SAFETY_S4_RUNTIME_ARCHITECTURE.md`, `reports/TEST_SAFETY_S4_1_HUMAN_DECISION_CLOSURE.md`, `reports/TEST_SAFETY_S6_AUTOMATIC_RESOLUTION_ARCHITECTURE.md`.

---

## CURRENT_AGENT_TEST_EXECUTION_MODEL

| Observation | Code / artifact |
|-------------|-----------------|
| Primary execution path | LLM `tool_calls` → `agent_turn.run_chat_turn` loop → `_execute_agent_tool` (`ai_tool/chat_interface/agent_turn.py` ~L1442–1502) |
| Trust gate (separate domain) | `authorize_tool_execution` / `agent_tool_gate` — tool name + arguments; **not** Test Safety authorization |
| Runtime recording | `ChatTaskOrchestrator.observe_tool` → `ActionRecord` with `type="tool_call"`, `action_id=f"A{n}"` assigned **after** tool execution (`task_orchestration.py` L2968–2982, L3289–3299) |
| Dedicated test execution action | **NOT_FOUND** — no `TEST_EXECUTION` type, no `run_test_plan` in `registry/tools.json` |
| Pytest from agent | **NOT_CONNECTED** to Test Safety. Registry has `test_tool` (single registered tool smoke test), not repo pytest plans |
| `run_command` / shell tool | Suggested in `registry/workspace_concepts.json`; **not** present in `registry/tools.json` for agent visibility |
| Explicit Test Safety path | `tools/run_authorized_test_plan.py` → S7a → S5c only; **no** import from `ai_tool/**` |
| Goal Handoff `test_plan` | `docs/specs/GOAL_HANDOFF_V0.md` — `pytest[]` paths; **no** runtime adapter to `tools/test_safety` `test_plan` shape |
| Tetris / lab pytest | Separate subprocess paths (e.g. `ai_tool/tetris_code_specialization_lab/`) — **not** authoritative Test Safety |

**Conclusion:** Agent “tests” today are indistinguishable generic `tool_call`s. Meaningful test execution is not modeled; safety stack is not reachable from chat runtime.

---

## TEST_ACTION_REPRESENTATION_OPTIONS

### Option A — New `ActionRecord.type = TEST_EXECUTION`

```text
type = "TEST_EXECUTION"
arguments = { "test_plan": { plan_id, commands, declared_* } }
```

| Criterion | Assessment |
|-----------|------------|
| Runtime change | **High** — `observe_tool` assumes `tool_call`; dispatch, relevance audit, failure paths keyed on `tool_name` |
| ActionRecord fit | **Good** semantically; fields already allow arbitrary `arguments` |
| Registry | No new tool; LLM must emit non-registry action (unless orchestrator synthesizes) |
| Schema validation | New JSON Schema for arguments; validate before bridge (not in bridge inference) |
| Local LLM difficulty | **Harder** — non-standard action type vs tool_calls API |
| Routing certainty | **High** if only orchestrator creates `TEST_EXECUTION` |
| Generalization (GPU/Git/API) | **Best** long-term — distinct action types per execution class |
| Duplicate suppression | Must extend `should_execute` beyond `(tool_name, arguments)` |
| Recovery | Clear failure classes on `ActionRecord` + `FailureRecord` |
| Human approval | Maps cleanly to `resolution_stop_reason` |

### Option B — Dedicated tool (e.g. `run_test_plan`)

```text
type = "tool_call"  (unchanged)
tool_name = "run_test_plan"
arguments = { "test_plan": { ... }, "action_id": optional forbidden }
```

| Criterion | Assessment |
|-----------|------------|
| Runtime change | **Lower** — fits existing tool loop + registry pattern |
| ActionRecord fit | **Native** — same as other tools |
| Registry | **Required** — new entry + implementation module (S4.1 deferred hook now viable) |
| Schema validation | Tool `input` schema in `registry/tools.json` + jsonschema at dispatch |
| Local LLM difficulty | **Easier** — standard tool_call |
| Routing certainty | **High** — dispatch on `tool_name == "run_test_plan"` |
| Generalization | Additional tools (`run_gpu_check`, …) or one tool with `execution_kind` |
| Duplicate suppression | Reuses `should_execute(tool_name, arguments)` |
| Recovery | Tool `failure` + structured payload for safety vs pytest |
| Human approval | Distinct tool result envelope |

### Option C — Parse shell/pytest strings

| Criterion | Assessment |
|-----------|------------|
| All dimensions | **Rejected** — heuristic; violates S4/S8 “semantic identification”; bypass-prone |

---

## RECOMMENDED_TEST_ACTION_MODEL

**Option B — dedicated registry tool `run_test_plan`** with **structured `test_plan` object** in arguments (same normative shape as `tools/test_safety/reference_cases/*.json` → `test_plan`).

**Rationale (single choice):**

1. S4.1 Human Decision explicitly **deferred** broad `_execute_agent_tool` hook until a **dedicated test-runner tool** exists — S8 satisfies that precondition without inventing a parallel action-type channel first.
2. Smallest compatible surface with **current** LLM tool-calling and `observe_tool` / `FailureRecord` paths.
3. Option A remains the **second-phase** generalization (`TEST_EXECUTION` internal type) once bridge proves stable; tool dispatch can set `type` to `TEST_EXECUTION` in evidence extensions later without changing safety stack.

**Option C:** not recommended.

---

## RUNTIME_ROUTING_OPTIONS

### Route A — Immediately before `_execute_agent_tool`

```text
if name == "run_test_plan":
    result = orchestrator.execute_test_plan_action(...)
else:
    result = _execute_agent_tool(...)
```

- `agent_tool_gate` still runs **inside** `_execute_agent_tool` unless duplicated — **must not** merge gates; either call gate once then branch, or implement `run_test_plan` as real tool that only calls bridge (Route C).

### Route B — Task / orchestration layer

```text
agent_turn → orchestrator.execute_test_plan_action(...)  # allocates action_id, bridge, normalized tool result
```

- Keeps `agent_turn` thin (one dispatch branch).
- **Preferred** for Test Safety vs trust separation: **tool trust** (allow/deny `run_test_plan`) via gate; **test authorization** via bridge only.

### Route C — Tool executor internal

```text
_execute_agent_tool → tools....run_test_plan() → bridge_test_execution()
```

- Minimal `agent_turn` diff (registry only).
- **Downside:** `action_id` is not available inside tool unless passed in arguments (forbidden) or read from thread-local context (not present today).

| Route | Recommendation |
|-------|----------------|
| A | Acceptable if it **only** delegates to orchestrator method (same as B) |
| B | **RECOMMENDED** — `ChatTaskOrchestrator.execute_test_plan_action` owns action_id allocation + bridge + result shape |
| C | **Not recommended** for action_id binding and observability ordering |

**Gate separation (mandatory):**

| Gate | Responsibility |
|------|----------------|
| `agent_tool_gate` | May this **tool** run at all? (trust / auto_allow) |
| Test Safety (S7a) | May this **plan** run for this **action_id**? (validator → gate → authorization) |

Do **not** fold Test Safety into `authorize_tool_execution`.

---

## RECOMMENDED_ROUTING_POINT

**Route B:** `ChatTaskOrchestrator.execute_test_plan_action`, invoked from `agent_turn` when `tool_name == "run_test_plan"` **after** optional `agent_tool_gate` check (either by calling gate explicitly before orchestrator, or by a thin trusted-tool path — implementation detail for S9).

Bridge module location (design only): `tools/test_safety/runtime_bridge.py` — **routing only**, no safety logic duplication.

---

## TEST_PLAN_SOURCE

| Source | Exists? | S8 role |
|--------|---------|---------|
| Agent tool arguments | **Will be** primary — LLM fills `test_plan` per schema | **Required** structured input; **no** inference in bridge |
| Automatic Agent → Test Safety conversion | **NOT_CONNECTED** | **Not in scope** — requires explicit **Test Plan adapter** at boundary if handoff/PRD supplies only `pytest[]` |
| Goal Handoff `test_plan.pytest[]` | Spec only | Future adapter: `handoff_test_plan_adapter(pytest_paths) → test_plan.commands[]` — **separate** from bridge; not auto inside bridge |
| Bridge-generated plan from shell strings | **Forbidden** | |

**Adapter rule:** `Agent Action → structured test arguments → (optional adapter) → test_plan dict → bridge`. Bridge receives **already structured** `test_plan`; does not scrape commands.

---

## ACTION_ID_BINDING

**Requirement:** `runtime ActionRecord.action_id == Test Safety action_id` (no bridge-generated surrogate).

**Current gap (code-verified):** `action_id` is allocated in `observe_tool` **after** `_execute_agent_tool` returns (`_action_index` increment at L2970). Test Safety must run **before** observe, with a **pre-allocated** id.

**Design:**

1. Add orchestrator method `allocate_action_id() -> str` (same `A{n}` sequence, increment before execution).
2. `execute_test_plan_action` calls `allocate_action_id()`, passes to `bridge_test_execution(action_id=..., test_plan=...)`.
3. `observe_tool` must accept **optional predetermined `action_id`** for test actions (implementation S9 — listed as open API shape).

**Do not** put `action_id` in tool arguments for LLM to fill.

---

## BRIDGE_RESPONSIBILITIES

**In scope (routing only):**

```python
def bridge_test_execution(
    *,
    action_id: str,
    test_plan: Mapping[str, Any],
    repo_root: Path,
    eval_schema_path: Path,
    gate_schema_path: Path,
    consumed_registry: ConsumedAuthorizationRegistry | None = None,
) -> dict[str, Any]:
    return run_explicit_test_with_auto_resolution(
        action_id=action_id,
        current_plan=test_plan,
        authorization_packet=None,
        repo_root=repo_root,
        eval_schema_path=eval_schema_path,
        gate_schema_path=gate_schema_path,
        consumed_registry=consumed_registry or ConsumedAuthorizationRegistry(),
    )
```

**Out of scope (must not reimplement):** validator, gate, authorization bind/verify, fingerprint, executor, postflight, closure, resolution policy.

**Returns:** Full `TEST_SAFETY_EXPLICIT_RUN` packet (or stable subset) for result mapping.

---

## RESULT_MAPPING

Map `run_explicit_test_with_auto_resolution` outcome → tool result → `observe_tool` / `EvidenceRecord`.

| Safety outcome | Tool `status` | `ActionRecord.result_status` | Evidence |
|----------------|---------------|-------------------------------|----------|
| Executed, pytest ok, `run_closed` | `success` | `success` | `EvidenceRecord` with `source_type=test_safety_run`, summary tail, link to full packet path or embedded hash |
| Executed, pytest fail (`test_failed`) | `failure` (or `success` + flags — **prefer explicit `failure`**) | `failure` | Failure evidence + **not** safety block |
| Resolution `BLOCKED` / `ERROR` / `UNRESOLVED` | `failure` | `failure` | `failure_code=EXECUTION_AUTHORIZATION_FAILURE` |
| `AWAITING_HUMAN_APPROVAL` | `blocked` or dedicated `pending_approval` | map to runtime **AWAITING_HUMAN** pattern | No executor; no pytest failure |
| Runner verify DENIED (stale) | `failure` | `failure` | `EXECUTION_AUTHORIZATION_FAILURE` |

Include in tool result payload (for LLM + runtime):

```text
test_safety: {
  resolution_result,
  gate_decision,
  executor_called,
  test_failed,
  run_closed,
  closure_reason,
  execution_result: { ok, returncode, stdout_tail, stderr_tail }
}
```

---

## TEST_FAILURE_MAPPING

| Condition | Classification | `FailureRecord.failure_code` (candidate) |
|-----------|----------------|----------------------------------------|
| `executor_called` && `test_failed` | **PRODUCT / CODE FAILURE** | `pytest_failed` or existing `tool_failure` with structured subcode |
| `executor_called` && !`test_failed` && `run_closed` | Success path | — |
| `executor_called` && !`run_closed` | **Incomplete run** (postflight/closure) | `test_run_not_closed` |
| !`executor_called` && safety stop | **EXECUTION AUTHORIZATION FAILURE** | `test_safety_blocked` / `test_safety_human_approval_required` |

**Do not** record pytest failure when `executor_called` is false.

Hook: existing `observe_tool` → `FailureRecord` on `status == "failure"` (`task_orchestration.py` L3402–3415) with enriched `error.code` from bridge mapping.

---

## SAFETY_BLOCK_MAPPING

| `resolution_result` | Executor | Task treatment |
|---------------------|----------|----------------|
| `BLOCKED` | not called | Authorization failure; replan/recovery may propose **new** test action with different plan |
| `ERROR` / `UNRESOLVED` | not called | Same; surface `resolution_stop_reason` in events |
| Runner `SAFETY_AUTHORIZATION_FAILURE` | not called | Stale/mismatch after skip path |

**Not** `test_failed`; tetris repair loop must key off failure **class**, not pytest alone.

---

## HUMAN_APPROVAL_MAPPING

Explicit runner: `RESOLUTION_AWAITING_HUMAN_APPROVAL` / gate `human_approval_required`.

Runtime today: `AWAITING_USER`, `AWAITING_HUMAN`, gap router `HUMAN_APPROVAL` — **separate** from Test Safety (`agent_turn`, `gap_resolution_router`).

**Bridge rule:** Emit structured result; **do not** approve inside bridge. Orchestrator maps to:

- `events.append("test_safety_human_approval_required", ...)`
- Task / chat state consistent with existing human gate patterns (exact enum **OPEN** — do not auto-merge with `confirmed_tool_gap`).

Re-run after human approval: **new** explicit run with human-provided authorization packet or elevated plan — **S9**; S8 only notes packet may be supplied via future `--authorization-json` equivalent on bridge API.

---

## RECOVERY_CONNECTION

**Tetris / E2E loop (design):**

```text
run_test_plan (bridge)
  → pytest FAIL (executor_called, test_failed)
  → FailureRecord (CODE)
  → recovery_hint / replan / code fix tasks
  → new run_test_plan action (new action_id, possibly same plan fingerprint if plan unchanged)
```

**Connected today:** `recovery_hint`, `record_failure`, `add_local_replan` exist on orchestrator — **not** wired to Test Safety outcomes.

**Separation:** Safety block → recovery must **not** assume code bug; pytest fail → recovery **may** assume code/test fix.

---

## DUPLICATE_SUPPRESSION

| Layer | Mechanism |
|-------|-----------|
| Test Safety | `ConsumedAuthorizationRegistry` — one spawn per `authorization_binding_key` per run |
| Agent runtime | `should_execute` — skip duplicate `(tool_name, arguments)` with prior `evidence_gain` on task |

**Bridge design:**

- One runtime action → one `action_id` → one `run_explicit_test_with_auto_resolution` call.
- Re-running **same** plan after code fix: arguments often identical → `should_execute` may suppress — **OPEN:** test actions should use `should_execute` override or include non-semantic `run_token` only in runtime (not in safety fingerprint) **or** treat failed test runs as not `evidence_gain` so retry is allowed.

**Recommendation:** Failed test / safety-blocked actions do not set `evidence_gain`; successful closed runs do. Aligns with “retry after fix” without breaking safety consume semantics (new action_id each attempt).

---

## COMPLETION_MAPPING

**Do not** complete task on pytest PASS alone.

**Proposed test-action completion predicate:**

```text
executor_called == true
AND test_failed == false
AND run_closed == true
```

Surface `run_closed` / `closure_reason` on evidence so `support_completion_conditions` / goal evaluation can require `test_run_closed` condition (new completion condition id — **OPEN** naming).

Pytest pass with `run_closed == false` (e.g. postflight required but failed) → task **not** complete.

---

## RECOMMENDED_FINAL_ARCHITECTURE

```text
LLM tool_call: run_test_plan({ test_plan })
  → agent_turn dispatch
  → agent_tool_gate (tool trust only)
  → ChatTaskOrchestrator.execute_test_plan_action
        → allocate_action_id()  # A{n}
        → bridge_test_execution(action_id, test_plan, repo_root, schemas)
              → run_explicit_test_with_auto_resolution (S7a, unchanged)
        → normalize to tool result + test_safety envelope
  → observe_tool (predetermined action_id)
  → ActionRecord / EvidenceRecord / FailureRecord
```

**Scope:** `TEST_EXECUTION` semantics via **one** registry tool; Explicit Runner safety stack unchanged; **GENERAL_RUNTIME** becomes **CONNECTED** only along this narrow path after implementation.

---

## RECOMMENDED_INITIAL_WEDGE

| Step | Deliverable |
|------|-------------|
| 1 | `tools/test_safety/runtime_bridge.py` — thin wrapper |
| 2 | `registry/tools.json` + `run_test_plan` implementation stub calling bridge (or orchestrator-only with no-op tool) |
| 3 | `execute_test_plan_action` on orchestrator + `allocate_action_id` |
| 4 | Single branch in `agent_turn` for `run_test_plan` |
| 5 | Tests: mock bridge; one integration test with real S7 stack (dev-only) |
| 6 | **No** changes to validator/gate/authorization/runner internals |

**Not in wedge:** CI, shell interception, Goal Handoff auto-adapter, general `TEST_EXECUTION` type enum, Human Approval packet injection UI.

---

## IMPLEMENTATION_READY

```text
false
```

Architecture is **single-option closed** for representation (Option B) and routing (Route B + bridge module). Implementation waits on **OPEN_DECISIONS** and explicit S9 implementation approval (S8 forbids code changes).

---

## OPEN_DECISIONS

1. **Tool name / schema:** `run_test_plan` vs `execute_test_plan`; JSON Schema file for `arguments.test_plan` (align with `registry/schema/test_safety_evaluation.schema.json` `test_plan` subset).
2. **`observe_tool` API:** predetermined `action_id` parameter vs split `record_test_action` path.
3. **`should_execute` interaction:** exact rules for retry after failed pytest vs duplicate suppression.
4. **Completion condition id:** how goals reference `run_closed` (new condition string vs evidence predicate).
5. **Human approval resume:** how approved authorization packet re-enters bridge (CLI parity with `--authorization-json`).
6. **`agent_tool_gate`:** auto_allow for `run_test_plan` vs per-case trust.
7. **Goal Handoff adapter:** separate module timing (S9+ vs same wedge).
8. **Evidence persistence:** store full `TEST_SAFETY_EXPLICIT_RUN` under `runs/` vs inline summary only.

---

## Machine summary (S8 completion)

```text
CURRENT_AGENT_TEST_EXECUTION_MODEL:
tool_call_only_no_test_safety

TEST_ACTION_REPRESENTATION_OPTIONS:
A_TEST_EXECUTION_TYPE | B_DEDICATED_TOOL | C_STRING_PARSE_REJECTED

RECOMMENDED_TEST_ACTION_MODEL:
B_DEDICATED_TOOL_run_test_plan

RUNTIME_ROUTING_OPTIONS:
A_PRE_EXECUTE_AGENT_TOOL | B_ORCHESTRATOR | C_TOOL_INTERNAL

RECOMMENDED_ROUTING_POINT:
B_ORCHESTRATOR_execute_test_plan_action

TEST_PLAN_SOURCE:
STRUCTURED_TOOL_ARGUMENTS_REQUIRED; NO_AUTO_CONVERSION; OPTIONAL_HANDOFF_ADAPTER_LATER

ACTION_ID_BINDING:
PRE_ALLOCATE_A_n_BEFORE_BRIDGE; NO_LLM_action_id

BRIDGE_RESPONSIBILITIES:
ROUTING_ONLY_call_run_explicit_test_with_auto_resolution

RESULT_MAPPING:
TOOL_RESULT_ENVELOPE_WITH_test_safety_FIELDS

TEST_FAILURE_MAPPING:
executor_called_AND_test_failed_TO_CODE_FAILURE

SAFETY_BLOCK_MAPPING:
NOT_EXECUTOR_NOT_PYTEST_FAILURE_TO_AUTHORIZATION_FAILURE

HUMAN_APPROVAL_MAPPING:
RESOLUTION_AWAITING_HUMAN_APPROVAL_TO_RUNTIME_STATE_EVENTS_ONLY

RECOVERY_CONNECTION:
FEASIBLE_VIA_FailureRecord_AND_replan; NOT_CONNECTED_TODAY

DUPLICATE_SUPPRESSION:
LAYERED_binding_key_AND_should_execute; RETRY_POLICY_OPEN

COMPLETION_MAPPING:
test_failed_false_AND_run_closed_true

RECOMMENDED_FINAL_ARCHITECTURE:
run_test_plan_TOOL_TO_ORCHESTRATOR_TO_bridge_TO_S7a

RECOMMENDED_INITIAL_WEDGE:
BRIDGE_MODULE_PLUS_ORCHESTRATOR_METHOD_PLUS_AGENT_TURN_DISPATCH

IMPLEMENTATION_READY:
false

OPEN_DECISIONS:
8_ITEMS_LISTED_IN_SECTION_ABOVE

S8_ARCHITECTURE_STATUS:
CLOSED_SINGLE_OPTION

READY_FOR_S9_IMPLEMENTATION:
pending_human_approval_of_OPEN_DECISIONS
```

---

## S8 prohibitions (observed)

No changes were made to: `agent_turn.py`, `ChatTaskOrchestrator`, `ActionRecord`, `task_runtime`, `agent_tool_gate`, Tool Registry (live), Test Safety stack, Runner, CI, shell, Human Approval Runtime, Recovery Runtime.

---

## Traceability

| S7 entry | S8 outcome |
|----------|------------|
| `READY_FOR_S8_RUNTIME_BRIDGE: true` | Architecture for bridge **defined** |
| Explicit Runner only | Bridge targets **only** `run_explicit_test_with_auto_resolution` |
| No safety reimplementation | **BRIDGE_RESPONSIBILITIES** enforced by design |
