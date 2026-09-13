# Test Safety — S9 Runtime Bridge Completion Verification

**Date:** 2026-09-12  
**Authority:** `reports/TEST_SAFETY_S8_1_HUMAN_DECISION_CLOSURE.md`  
**Method:** Static trace + `tests/tools/test_test_safety_s9_completion_verification.py` (preflight-gated)

## 1. D1 — Single-source plan validation

| Check | Result |
|-------|--------|
| `EXTERNAL_REF_DIRECT` | **UNSUPPORTED** (unchanged from S9 D1 gate) |
| `SINGLE_SOURCE_PLAN_VALIDATION` | **PASS** — `tool_argument_validation.py` loads `registry/schema/test_safety_evaluation.schema.json`, validates via `Draft202012Validator(doc).evolve(schema=$defs/test_plan)` |
| Schema duplicate subset file | **None** — no `run_test_plan_*.json` tool schema; `registry/tools.json` documents normative shape by reference text only |

## 2. Runtime routing (code trace)

```
agent_turn: name == "run_test_plan" && orchestrator
  → authorize_tool_execution
  → ChatTaskOrchestrator.execute_test_plan_action
      → test_safety.runtime_bridge.bridge_test_execution
      → safety_resolution.run_explicit_test_with_auto_resolution
      → (S7a) prepare_evaluation_and_authorization / execute_authorized_test_plan
```

| Fallback | Result |
|----------|--------|
| `_execute_agent_tool` for `run_test_plan` when orchestrator present | **None** |
| `orchestrator is None` | **FOUND** — falls through to `_execute_agent_tool` → registry stub `run_test_plan_entry` (not pytest) |
| Raw pytest / subprocess outside Safety stack on happy path | **None** — pytest only via `runner_wedge.default_pytest_executor` inside authorized bridge |
| `ORCHESTRATOR_MISSING_PATH` | **STUB_ONLY** — `run_test_plan_entry` does not execute pytest |

## 3. D2 — Action ID

| Check | Result |
|-------|--------|
| `allocate_action_id()` → `predetermined_action_id` → `ActionRecord.action_id` | **PASS** — fixture `test_d2_action_id_single_increment` |
| Double `_action_index` increment on one call | **NONE** — `observe_tool` skips increment when `predetermined_action_id` set |

## 4. D3 — evidence_gain / should_execute

| Scenario | `evidence_gain` | Verified |
|----------|-----------------|----------|
| Safety BLOCKED / executor not called | false | `_observe_run_test_plan` + blocked fixture |
| pytest FAIL (executor_called, test_failed) | false | predicate + status failure |
| Successful closed run | true candidate | integration test |
| `should_execute` implementation | unchanged | `AgentTaskRuntime.should_execute` fixture |
| Non-gain ≠ automatic retry | no second bridge call without explicit `execute_test_plan_action` | `test_d3_run_test_plan_bypasses_should_execute_no_auto_second_call` |
| `run_test_plan` pre-bridge | reuses `should_execute` before `bridge_test_execution` (continuation path exempt) | **PASS** — duplicate suppression + failed retry fixtures |

## 5. D8 — Evidence persistence

| Check | Result |
|-------|--------|
| `TEST_SAFETY_EXPLICIT_RUN` → `runs/test_safety_explicit/{action_id}.json` | **PASS** — integration test |
| `EvidenceRecord` / `action_id` / `target` (packet path) | **PASS** |
| LLM tool transport | **PASS** — `prepare_tool_result_for_llm("run_test_plan")` → `test_safety_llm_view` only; internal `raw` still holds full `test_safety` |

## 6. D4 — `test_run_closed` / closure predicate

Normative predicate: `safety_run_closure_predicate` ≡ `executor_called && !test_failed && runner_evidence.run_closed`.

| Case | Supported |
|------|-----------|
| All true | yes |
| pytest FAIL + lifecycle closed | **NOT_SUPPORTED** |
| PASS + run_closed false | **NOT_SUPPORTED** |
| Safety BLOCKED | **NOT_SUPPORTED** |

Completion condition wiring: `_append_test_safety_evidence` → `support_completion_conditions(["test_run_closed"])` when predicate holds.

## 7. D5 — Human approval continuation

| Layer | Result |
|-------|--------|
| S7 stack `RESOLUTION_SKIPPED` + executor | **PASS** — `test_d5_stack_resolution_skipped_with_valid_auth` |
| Orchestrator same `action_id`, no duplicate `ActionRecord` | **PASS** — `test_d5_orchestrator_continuation_same_action_id` (bridge mocked for AWAITING→resume) |
| End-to-end EXTERNAL plan + synthetic human-approved packet without mock | **NOT_CONNECTED** (generator out of scope per S8.1) |

## 8. Controlled runtime integration

**PASS** — `test_s9_controlled_runtime_integration` (no LLM; real Safety stack + single controlled pytest).

---

## Final verdict

```text
S9_RUNTIME_BRIDGE: READY

D3_FAILED_RETRY: PASS

D3_SUCCESS_DUPLICATE_SUPPRESSION: PASS

D8_LLM_RESULT_MINIMIZATION: PASS

FULL_PACKET_INTERNAL_PERSISTENCE: PASS

RAW_PYTEST_FALLBACK: NONE

ORCHESTRATOR_MISSING_PATH: STUB_ONLY

CONTROLLED_RUNTIME_INTEGRATION: PASS

READY_TO_COMMIT_S9: true
```

(Gap closure 2026-09-12: D8 LLM shrink + D3 pre-bridge `should_execute` reuse.)

## S9 stage candidates (when ready)

- `tools/test_safety/tool_argument_validation.py`
- `tools/test_safety/runtime_bridge.py`
- `tools/system/test_safety/run_test_plan_entry.py`
- `ai_tool/chat_interface/agent_turn.py` (run_test_plan branch only)
- `ai_tool/chat_interface/task_orchestration.py` (S9 methods only)
- `tools/ai/task_runtime.py` (`patch_action_result`)
- `registry/tools.json`, `registry/agent_tool_trust.json`
- `tests/tools/test_test_safety_tool_argument_validation.py`
- `tests/tools/test_test_safety_runtime_bridge.py`
- `tests/tools/test_test_safety_s9_completion_verification.py`
- `reports/TEST_SAFETY_S9_D1_REF_IMPLEMENTATION_CHECK.md`
