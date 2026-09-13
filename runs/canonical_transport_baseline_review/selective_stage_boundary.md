# Selective stage boundary (for next commit)

## `task_orchestration.py` (committed HEAD = Wedge A/B only)

**Stage (Canonical baseline):**

1. After `goal_completion_consumed = False` add only:
   - `structured_requirements`
   - `requirement_resolution_phase`
   - `projected_explicit_constraints`
   - `canonical_requirement_projection`
   - Do **not** stage `handoff_acceptance_projection` / `handoff_task_acceptance_mapping`

2. Methods block: `apply_canonical_requirements_from_state`, `canonical_requirement_evidence_trace`, `canonical_requirement_runtime_coverage` only (skip `handoff_acceptance_runtime_trace`)

3. `initialize()` — **no change** vs HEAD (Wedge A/B already committed)

4. `completion_runtime_slice` / `apply_completion_runtime` — **no canonical change required** for step1–4 (Wedge B sidecar hunks already on HEAD)

5. `snapshot()` tail: `structured_requirements` and `requirement_resolution_phase` optional dict keys (~4239–4248)

**Do not stage:** handoff trace methods; unrelated mission export if mixed in same hunk—split by `git add -p`.

## `requirement_resolution.py`

Stage entire canonical diff block from `_runtime_adoption_from_rows` through `sync_canonical_requirements_from_mission` and `__all__` updates (single contiguous worktree diff vs HEAD).

## `agent_turn.py`

Stage only:

- `sync_canonical_requirement_projection` import
- One line in `_attach_requirement_contract`

Do not stage other agent_turn dirty hunks.

## `goal_continuation_resume.py`

Stage only import + one call line in `restore_orchestrator_from_goal_continuation`.

## New files to `git add` whole file

- `tests/ai_tool/chat_interface/test_canonical_goal_transport_step1.py` … `step4.py`

## Explicitly exclude

- `test_canonical_goal_transport_step5.py`
- `goal_handoff_runtime_bridge.py` handoff trace hunks
