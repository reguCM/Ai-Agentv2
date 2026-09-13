# S10 — First Full Repair Loop Gap Review (READ-ONLY)

**Date:** 2026-09-12  
**Authority:** S9 connected stack; S8.1 semantics unchanged  
**Method:** Static trace of production Chat + Task Runtime (no new fixtures)

---

## CURRENT_FAILURE_PATH

`run_test_plan` → `execute_test_plan_action` → `bridge_test_execution` → runner sets `test_failed` from `execution_result.ok` (`runner_wedge.execute_authorized_test_plan`). Orchestrator maps `status="failure"` when `test_failed` (Safety already passed; executor was called).

Observation: `_observe_run_test_plan` (not generic `observe_tool` failure branch).

---

## TEST_FAILURE_TO_FAILURE_RECORD

| Artifact | pytest FAIL (executor called) |
|----------|-------------------------------|
| `ActionRecord.result_status` | `failure` |
| `ActionRecord.evidence_gain` | `false` (predicate fails) |
| `FailureRecord.failure_code` | **`pytest_failed`** (not `test_safety_*`) |
| `EvidenceRecord` | Created; `supported_completion_conditions` **empty**; `relevant_content` = compact `test_safety_summary` JSON |
| `test_failed` / `run_closed` on outcome | Top-level + `runner_evidence`; closure predicate requires `!test_failed` |
| Safety-blocked (no executor) | `test_safety_execution_authorization_failure` |

**Verdict:** Code/test failure is distinguished from Safety denial at `FailureRecord` level.

---

## FAILURE_CONTEXT_TO_AGENT

| Channel | Content |
|---------|---------|
| LLM tool message | `prepare_tool_result_for_llm("run_test_plan")` → `test_safety_llm_view` (tails, flags, `packet_path`, `action_id`) — **no full packet** |
| `orchestrator.hint()` | `small_task_hint` includes `failure_history` **codes** only (not stderr) |
| `recovery_hint()` | Injected as system message after tool round; lists forbidden **same tool+arguments** |
| Event `summarize_tool_result` | Generic scalars via `observe_tool_result` — **no `run_test_plan`-specific failed-test id** |

**Gaps:** Structured **failed test node id** not observed in code path (may appear only inside stderr tail). `recovery_hint` text assumes **read-only** recovery.

---

## REPAIR_ACTION_PATH

**Exists (not Test-Safety-specific):** sandbox `create_file` / `edit_file` (e.g. `tests/test_safe_mutation_tools_p218.py`), `read_file` / `search_*`, capability injection, `add_local_replan`, premise/revalidation labs (separate domains).

**Not connected:** No link from `FailureRecord(pytest_failed)` to “next tool should be edit” — **LLM discretion only**, subject to `relevant_tools()` keyword matching on task text.

---

## RETEST_TRIGGER_PATH

**Who calls `run_test_plan` again:** Only the **LLM** via another tool call in `agent_turn` (no Runtime auto-retest).

**S9 rules still hold:** new `action_id`, new Safety cycle, same `test_plan` allowed when prior `evidence_gain=false`; duplicate suppression only after **successful closed** gain.

**Friction:** `AgentTaskRuntime.recovery_hint()` tells the model **not to repeat the same failed action** and to pick a **read-only** action — conflicts with intentional **same-plan retest after code fix**.

---

## RETEST_IDENTITY_RULE

**CONNECTED (S9):** Same arguments + failed run → `should_execute` true → bridge allowed. Same arguments + successful closed gain → pre-bridge suppress.

---

## COMPLETION_PATH

| Step | Status |
|------|--------|
| Predicate → `support_completion_conditions(["test_run_closed"])` | **CONNECTED** when `test_run_closed` ∈ `TaskRecord.completion_conditions` |
| `evaluate_task` on current task | Called from `_append_test_safety_evidence` |
| Default `initialize()` tasks | **T1** = `relevant evidence observed` / explicit conditions — **not** `test_run_closed` unless ctor/handoff sets it |
| T1 complete → `current_task_id = T2` | Implemented in **generic** `observe_tool` after `evidence_gain` — **`_observe_run_test_plan` returns early; does not run T1→T2 switch** |
| Goal **G1** complete | Needs **T2** `answer produced` + goal conditions — pytest PASS alone insufficient by design (S8.1) |

---

## STAGNATION_PROTECTION

| Mechanism | Repair loop |
|-----------|-------------|
| `is_stagnating` / identical `FailureRecord` tail | **Usable** (3× same tool/args/code) |
| `should_execute` / duplicate suppression | **Usable** (success path only) |
| `recovery_hint` | **Partially counterproductive** for retest |
| Progress Classification `pytest_*` counters | **NOT wired** from `run_test_plan` in `snapshot_from_orchestrator` |
| State cycle / semantic stagnation shadow | **Generic**; `failure_signature` includes `pytest_failed:…` when failures exist |

---

## UNKNOWN_REASON_PRESERVATION

**Preserved:** `resolution_result`, `closure_reason`, Safety stop reasons, `FailureRecord.failure_code`, full `TEST_SAFETY_EXPLICIT_RUN` under `runs/`, Evidence summary + path. Future Grill/Human/Block routing **not connected** but audit trail sufficient for manual classification.

---

## EXISTING_COMPONENTS_REUSABLE

- S9 bridge + gate + observe + Evidence  
- Sandbox edit tools + `record_sandbox_mutation`  
- `FailureRecord` / `recovery_hint` / `add_local_replan` / gap router (stagnation branches)  
- `test_run_closed` completion id (S8.1)  
- S9 regression + `pure_unit` reference plan shape  

---

## MISSING_CONNECTIONS

1. **Task bootstrap:** production default tasks lack `test_run_closed` + explicit test intent in normal chat.  
2. **Post-test task advancement:** `_observe_run_test_plan` omits T1→T2 / goal evaluation hooks present in generic `observe_tool`.  
3. **Recovery copy vs repair:** `recovery_hint` read-only + forbid same failed `run_test_plan` conflicts with fix→retest loop.  
4. **Retest trigger:** no Runtime/policy nudge to re-invoke `run_test_plan` after mutation evidence.  
5. **Progress classification:** `pytest_failed` counter not fed from Chat `run_test_plan` outcomes.  
6. **Structured failure digest:** no first-class failed-test id in LLM view (stderr tail only).  
7. **End-to-end Chat loop test:** no existing fixture chaining LLM → fail → edit → retest → complete (S9 tests stop at orchestrator).

---

## MINIMUM_IMPLEMENTATION_WEDGE (proposal only — not implemented)

1. **Session/task template:** `completion_conditions` including `test_run_closed` on T1 (or dedicated task) + request text matching `run_test_plan` keywords.  
2. **Observe parity:** after `test_run_closed` support, mirror generic `observe_tool` **task-complete / T1→T2** transition for `run_test_plan`.  
3. **Recovery exception:** when last failure is `pytest_failed`, recovery text should allow **edit then same-plan retest** (narrow; no new duplicate spec).  
4. **Controlled E2E:** `run_chat_turn` + fake `chat_fn` script (pattern: `test_execution_end_invariants.py`) + sandbox edit + `pure_unit`-class plan — **new test in S10+**, not created here.

---

## CONTROLLED_ONE_LOOP_TEST_CANDIDATE (existing assets only)

| Asset | Role |
|-------|------|
| `tests/tools/test_test_safety_s9_completion_verification.py` | Bridge + `test_run_closed` on orchestrator (no LLM repair) |
| `tools/test_safety/reference_cases/pure_unit.json` | Minimal PASS plan shape |
| `tests/test_safe_mutation_tools_p218.py` | Sandbox **edit** path (disconnected from `run_test_plan`) |
| `ai_tool/run_tetris_sandbox_e2e.py` | Large E2E — **not** minimal first loop |

---

## IMPLEMENTATION_READY

**false** — S9 execute/observe/evidence/retest **identity** are connected; **full Chat repair loop** blocked by task model, recovery messaging, task advancement, and missing scripted E2E.

---

## 最重要判定

| Segment | Status |
|---------|----------|
| Implement → `run_test_plan` → Safety → pytest | **接続済み** (S9) |
| pytest FAIL → Failure/Evidence back to Runtime | **接続済み** (`pytest_failed`) |
| FAIL context → Agent (actionable repair) | **存在するが未接続/不足** (tails yes; recovery anti-retest; no failed-test id) |
| Agent → code edit | **存在するが未接続** (tools exist; no failure-driven routing) |
| Fix → re-`run_test_plan` | **存在するが未接続** (LLM-only; recovery friction) |
| PASS → `test_run_closed` | **接続済み** (if condition on task) |
| `test_run_closed` → Task/Goal COMPLETE | **存在するが未接続** (no T2 transition; default tasks) |
