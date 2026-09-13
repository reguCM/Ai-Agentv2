# Human Requirement Resolution Wedge — Final Triage

**Date:** 2026-09-12  
**Architecture / HD-1…HD-5:** unchanged.

---

## 1. `test_25` NEW_REGRESSION — RESOLVED

### Observed failure (current, pre-fix)

```text
Expected activity status COMPLETION_CHECKING in events
Actual: ['LLM_WAITING', 'TOOL_RUNNING', 'RESULT_AUDITING', 'LLM_WAITING', 'FINAL_SYNTHESIS']
```

### Baseline vs current (`47b11df` worktree vs dev-current)

| Item | @47b11df | @current (before fix) |
|------|----------|------------------------|
| After `orchestrator.observe_tool(...)` (non–test-safety path) | `evidence_gain` + `EVIDENCE_UPDATING` (if gain) + **`COMPLETION_CHECKING`** | **only** `observe_tool`; no completion activity |
| `observed_via_test_safety_bridge` branch | same completion activities | same (unchanged) |

**Causal file / hunk:** `ai_tool/chat_interface/agent_turn.py` — tool-result handling inside `_chat_turn` (~1561–1585). **Not** `requirement_resolution.py`, not pre-`_chat_turn` gate, not mission `put_mission`.

**Why wedge test surfaced it:** `test_25` uses `_prepare` → heuristic requirement resolution + orchestrator; tool loop still runs, but activity contract regressed in `_chat_turn` (likely concurrent `agent_turn.py` edit vs `47b11df`, not requirement extraction).

### Fix (minimal)

Restored baseline post–`observe_tool` block: `evidence_gain`, optional `EVIDENCE_UPDATING`, **`COMPLETION_CHECKING`**. Removed duplicate `evidence_gain` assignment in test-safety branch only.

**Requirement Gate:** untouched. No test weakening.

### Re-run (post-fix)

```text
test_25_real_loop_emits_major_activity_states  PASS
test_requirement_resolution_wedge (7)           PASS
test_requirement_transport_failure              PASS
test_requirement_llm_has_its_own_timing_phase PASS
test_agent_task_loop_p216 full                  66 passed, 4 failed (unchanged pre-existing)
```

Pre-existing (unchanged): `test_07`, `test_33`, `test_34`, `test_35`.

---

## 2. Bypass reclassification

### `handoff_packet` (`run_chat_turn(..., handoff_packet=…)`)

| Question | Finding |
|----------|---------|
| Requirement authority | Handoff packet (`acceptance_criteria`, `scope`, `human_gates`); mission `original_goal` separate |
| Mission `structured_requirements` | Not populated from NL wedge; `prepare_implementation_entry_bundle` → `bundle_from_handoff()` → phase `REQUIREMENTS_RESOLVED` without span extraction |
| Unresolved blocking rows on mission | Not expressed via NL `structured_requirements` for this entry |
| Check before implementation-entry | Handoff readiness / schema elsewhere; **no** `requirements_block_implementation_entry` on mission rows at `_chat_turn` |

**NL wedge:** does not run span extraction — **EXPECTED**.  
**Implementation gate:** contract carried by handoff artifact, not mission NL fields — **HANDOFF_GATE: NOT_APPLICABLE** (NL structured contract); not `IMPLEMENTATION_REQUIREMENT_GATE_BYPASS` for handoff-shaped entry.

### Goal continuation

| Question | Finding |
|----------|---------|
| Reuse mission | Yes (`mission_id` in packet, `restore_orchestrator_from_goal_continuation`) |
| `requirement_resolution_phase` | Not read/restored on resume path |
| Stop if unresolved | **No** — `_chat_turn` proceeds with restored orchestrator |

**NL wedge:** bypass — **EXPECTED** (resume mid-execution).  
**Implementation gate on mission phase:** **not enforced** — **GOAL_CONTINUATION_GATE: FAIL** (latent; out of NL wedge scope unless mission left `AWAITING_*`).

### Grill resume

| Grill type | Structured requirement update | Gate re-eval | `blocks_design` stop | Implementation only if resolved |
|------------|--------------------------------|--------------|----------------------|----------------------------------|
| **requirement_resolution** | Yes (`apply_requirement_resolution_grill_answer` → mission) | Yes (`requirements_block_implementation_entry`) | Yes | Yes (`_requirement_resolution_resume_turn`) |
| Conversation / boundary grill | Supplements / boundary dimensions; not NL span rows | No `requirement_resolution_phase` | N/A to NL wedge | `_chat_turn` after restore (pre-existing) |

**GRILL_RESUME_GATE:** **PASS** (requirement-resolution grill); conversation/boundary — pre-existing, not NL wedge.

### Summary

```text
NL_WEDGE_BYPASS:
EXPECTED   # handoff, continuation, non–requirement-resolution grills skip NL span extraction

IMPLEMENTATION_REQUIREMENT_GATE_BYPASS:
NONE       # for new NL chat + is_agent_task path (gate enforced)
             # goal_continuation: no mission phase check (latent FAIL, not wedge regression)
```

**NORMAL_REQUEST_GATE:** **PASS**

---

## 3. LLM smoke evidence

Completion verification used an **injected deterministic `chat_fn`** returning per-span JSON (exercises `propose_span_disposition` LLM branch with `use_heuristic_only=False`). **Not** a live Ollama/provider call.

```text
NON_HEURISTIC_LLM_PATH: PASS
LIVE_LLM_SMOKE: NOT_RUN
```

Repo policy (`docs/DEVELOPMENT_TEST_POLICY.md`): live LLM not required for every commit unless a specific gate says so — **not elevated to commit blocker** here.

---

## 4. Final regression (post `test_25` fix)

| Suite | Result |
|-------|--------|
| `test_requirement_resolution_wedge.py` | 7/7 PASS |
| Controlled E2E (`test_run_chat_turn_blocks_then_resumes_e2e`) | PASS |
| `test_25` | PASS |
| `test_agent_task_loop_p216.py` | 66 PASS, 4 FAIL (pre-existing only) |

---

## Final Verdict

```text
HUMAN_REQUIREMENT_WEDGE:
READY

TEST_25_NEW_REGRESSION:
RESOLVED

NL_WEDGE_BYPASS:
EXPECTED

IMPLEMENTATION_REQUIREMENT_GATE_BYPASS:
NONE

NORMAL_REQUEST_GATE:
PASS

HANDOFF_GATE:
NOT_APPLICABLE

GOAL_CONTINUATION_GATE:
FAIL

GRILL_RESUME_GATE:
PASS

NON_HEURISTIC_LLM_PATH:
PASS

LIVE_LLM_SMOKE:
NOT_RUN

ORIGINAL_GOAL_PRESERVATION:
PASS

SOURCE_SPAN_COVERAGE:
PASS

CONTROLLED_E2E:
PASS

NEW_REGRESSIONS:
NONE

READY_TO_COMMIT:
true
```

**Notes:** `READY_TO_COMMIT` assumes wedge + `test_25` fix only; **four pre-existing** `p216` failures remain. `GOAL_CONTINUATION_GATE: FAIL` is a **documented latent gap** (no mission phase check on continuation); not fixed in this triage to avoid architecture expansion.
