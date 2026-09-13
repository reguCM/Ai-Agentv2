# Human Requirement Resolution — Minimum Wedge Implementation

**Date:** 2026-09-12  
**Basis:** `HUMAN_REQUIREMENT_PRESERVATION_AUDIT.md`, `HUMAN_REQUIREMENT_RESOLUTION_ARCHITECTURE.md` (HD-1…HD-5 closed)

## Summary

Minimum wedge implemented across six stages. Mission is requirement authority; implementation-entry is gated before `ChatTaskOrchestrator` + `_chat_turn`.

## Stage delivery

| Stage | Status | Evidence |
|-------|--------|----------|
| 1 Agent-task routing | DONE | `_CREATION_INTENT` in `task_orchestration.is_agent_task` |
| 2 Mission schema | DONE | `mission.schema.json`: `structured_requirements`, `requirement_resolution_phase`, supplement `requirement_resolution` |
| 3 Span-first → proposal → validator | DONE | `requirement_resolution.py` |
| 4 Implementation-entry gate | DONE | `run_chat_turn` + `implementation_entry_requested` |
| 5 Grill / resume | DONE | `requirement_resolution_grill.py`, session `awaiting_requirement_resolution` |
| 6 Projection | DONE | `project_to_runtime_adoption` → `completion_conditions` / `explicit_constraints` |

## Key modules

- `ai_tool/chat_interface/requirement_resolution.py`
- `ai_tool/chat_interface/requirement_resolution_grill.py`
- `ai_tool/chat_interface/agent_turn.py` (gate, resume, timing `requirement_resolution`)
- `ai_tool/mission_memory/chat_persist.py` (persist structured requirements)
- `registry/schema/grill_question_contract.schema.json` (`grill_reason: requirement_resolution`)

## HD alignment

- **HD-1:** Mechanical `segment_original_goal` + per-span proposal (`propose_span_disposition`; LLM via `chat_fn` when heuristic env off) + `validate_structured_requirements`
- **HD-2:** `requirements_block_implementation_entry` only blocks on `materiality=blocks_design` unresolved rows
- **HD-3:** `implementation_entry_requested` — handoff or `chat` + `is_agent_task`; not `classify_request` label
- **HD-4:** Mission `put_mission` on block and on orchestrator start; `original_goal` immutable via store
- **HD-5:** `CONSTRAINT` + `constraint_subtype=prohibition`

## Operations

- **Tests / deterministic runs:** `AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC=1` uses `heuristic_span_proposal` (no span LLM).
- **Production span LLM:** default when heuristic env unset; failures surface as `requirement_resolution` communication errors.

## Verification

### Unit / integration

```text
pytest tests/ai_tool/chat_interface/test_requirement_resolution_wedge.py  → 7 passed
pytest tests/ai_tool/chat_interface/test_agent_task_loop_p216.py::test_requirement_transport_failure_is_reported_as_communication_blocked
pytest tests/ai_tool/chat_interface/test_agent_task_loop_p216.py::test_requirement_llm_has_its_own_timing_phase
pytest tests/ai_tool/mission_memory/test_validate.py
```

### Controlled E2E (in wedge tests)

`test_run_chat_turn_blocks_then_resumes_e2e`:

```text
User: 簡単なテトリスを作って
  → awaiting_requirement_resolution, mission phase AWAITING_HUMAN, agent loop not entered
User: 最小の落下テトリスで十分
  → phase REQUIREMENTS_RESOLVED, human_confirmed on 「簡単な」, _chat_turn entered once
```

### Representative cases (heuristic static)

| Case | Covered in tests |
|------|------------------|
| 簡単なテトリス | segment + block + resume |
| Pythonでテトリス | `test_python_constraint_projection` |
| 赤いボタン prohibition | `test_prohibition_subtype` |
| 見た目は二の次 | heuristic in module (informational PREFERENCE) |
| なるべく / 初心者 | heuristic unresolved → human (not separate test) |

## Confirmed gaps (post-wedge)

- FACT / ENVIRONMENT resolution routes are classified on rows but **no dedicated research/probe loop** in this wedge (phase enums exist; human grill is wired for `user_intent`).
- `development` / `tool_creation` spec-proposal routes unchanged (non–implementation-entry per architecture).
- Full production LLM span quality not evaluated (heuristic-backed CI).
- Some pre-existing `test_agent_task_loop_p216` assertions (e.g. `test_07` progress_state, `test_25` COMPLETION_CHECKING) fail independently of this wedge.

## IMPLEMENTATION_READY (wedge scope)

```text
IMPLEMENTATION_READY: true
```

Follow-on: enable span LLM in production with golden utterances; FACT/ENV automated routes; handoff parity.
