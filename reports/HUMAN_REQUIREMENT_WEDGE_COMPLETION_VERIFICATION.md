# Human Requirement Wedge — Completion Verification (pre-commit)

**Date:** 2026-09-12  
**Scope:** READ-ONLY verification; no code/schema changes.

## 1. Production LLM failure → fail-safe (no silent heuristic)

**Evidence:** `requirement_resolution.py` — `propose_span_disposition` uses heuristic only when `use_heuristic_only` or `chat_fn is None`; no `except` fallback to heuristic in `extract_requirement_resolution`. `agent_turn.run_chat_turn` wraps `prepare_implementation_entry_bundle` in `try/except` and sets `RequirementDecomposition` with `source="requirement_resolution"` (no orchestrator).

**Executed:**

```text
AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC unset
run_chat_turn(..., chat_fn raises RuntimeError)
→ failure_phase=requirement_resolution, communication_status=FAILED, task_runtime=None
→ no requirement_resolution mission fields (no silent resolve)
```

**Verdict:** PASS — no silent heuristic fallback on LLM failure.

## 2. Implementation-entry gate bypass (incl. development / tool_creation)

| Path | Reaches `_chat_turn` + `ChatTaskOrchestrator` (mutation-capable agent loop)? | Requirement wedge (NL extraction + block)? |
|------|-----------------------------------------------------------------------------|------------------------------------------|
| `route=development` | **No** — `_spec_proposal_turn` / `propose_specification` only | N/A |
| `route=tool_creation` | **No** — same | N/A |
| `route=chat` + `is_agent_task` | **Yes** (after gate) | **Yes** |
| `handoff_packet` arg | **Yes** — `bundle_from_handoff()` → phase `REQUIREMENTS_RESOLVED` without NL spans | **Bypass** (by design: handoff artifact) |
| `goal_continuation_packet` | **Yes** — restore orchestrator, no re-gate | **Bypass** (resume) |
| `conversation_grill_state` / boundary resume | **Yes** — restore mid-mission | **Bypass** (resume) |
| `production_handoff_turn` | Orchestrator for handoff pipeline; not standard gated NL entry | Separate |

**Verdict for development/tool_creation:** **NONE** — do not enter implementation-entry agent loop.

**Verdict overall:** **FOUND** — `handoff_packet`, goal continuation, and grill resume still reach implementation without NL wedge (pre-existing + handoff design; not introduced for dev/tool_creation routes).

## 3. `test_agent_task_loop_p216` — PRE_EXISTING vs NEW_REGRESSION

Baseline: git worktree at `47b11df` (last commit before uncommitted wedge).

| Test | @47b11df | @current (wedge) | Classification |
|------|----------|------------------|----------------|
| `test_requirement_transport_failure_*` | FAIL | PASS | Wedge fix (intentional) |
| `test_requirement_llm_has_its_own_timing_phase` | FAIL | PASS | Wedge fix (intentional) |
| `test_07_partial_with_evidence_is_progress` | FAIL | FAIL | **PRE_EXISTING** |
| `test_33_tool_round_limit_*` | FAIL | FAIL | **PRE_EXISTING** |
| `test_34_real_model_empty_*` | FAIL | FAIL | **PRE_EXISTING** |
| `test_35_finalization_*` | FAIL | FAIL | **PRE_EXISTING** |
| `test_25_real_loop_emits_major_activity_states` | PASS | FAIL | **NEW_REGRESSION** |

Counts: baseline 6 failed / 64 passed; current 5 failed / 65 passed.

## 4. Production LLM path smoke (heuristic env **off**)

Mock `chat_fn` returns per-span JSON (exercises `propose_span_disposition` LLM branch, not `heuristic_span_proposal`).

**Turn 1** `簡単なテトリスを作って`:

- `original_goal` preserved on mission
- `structured_requirements` source_text union covers full utterance
- `awaiting_requirement_resolution=True`, `_chat_turn` not entered

**Turn 2** human answer:

- Events: `requirement_resolution_answer_applied`, `requirement_resolution_closed`
- `requirement_resolution_phase=REQUIREMENTS_RESOLVED`, grill session cleared, `_chat_turn` entered once

**Not asserted:** fixed LLM disposition labels (per instructions).

**Note:** Ad-hoc mock must key spans by `Span (start,end)` in prompt; naive substring matching can mis-route (false FAIL). Controlled pytest E2E still uses `AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC=1` for determinism.

---

## Final report

```text
HUMAN_REQUIREMENT_WEDGE:
PARTIAL

PRODUCTION_LLM_PATH:
PASS

SILENT_HEURISTIC_FALLBACK:
NONE

IMPLEMENTATION_GATE_BYPASS:
FOUND

PRE_EXISTING_TEST_FAILURES:
CONFIRMED

NEW_REGRESSIONS:
FOUND

ORIGINAL_GOAL_PRESERVATION:
PASS

SOURCE_SPAN_COVERAGE:
PASS

GRILL_RESUME:
PASS

CONTROLLED_E2E:
PASS

READY_TO_COMMIT:
false
```

**READY_TO_COMMIT false rationale:** `NEW_REGRESSION` (`test_25`); documented `IMPLEMENTATION_GATE_BYPASS` on handoff/continuation/grill resume (architecture-known, not dev/tool_creation). Recommend triage `test_25` before commit or accept as follow-up.
