# Production Wedge B — Task Graph Adoption Report

## WEDGE_B_STATUS

PASS

## Git

- HEAD (baseline): `bf20161`
- Staged: none
- Commit / Push: not performed

## Summary

- `ai_tool/domain_task_graph_adoption.py` — task graph → TaskRecord rows + `task_graph_projection_sidecar`
- `task_orchestration.py` — `domain_task_graph` init path, slice/restore sidecar
- `domain_goal_graph_adoption.py` — clear sidecar on goals-only adoption
- Tests: `tests/ai_tool/test_domain_task_graph_adoption_wedge_b.py` (22 tests)

## Primary goal rule (PHASE 2N)

First entry in `supports_goal_ids` → mapped runtime goal → `TaskRecord.goal_id`.

## Sidecar key

`task_graph_projection_sidecar` on completion_runtime snapshot.

## Tests

- Wedge A+B targeted: 34 passed
- Regression (task_runtime, handoff, execution_end_invariants): see session log
