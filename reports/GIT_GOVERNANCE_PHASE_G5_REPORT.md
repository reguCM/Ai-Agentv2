# Git Governance Phase G5 — Drift / Distribution Regression Report

## Status

**G5: COMPLETE** (Human review before G6)

**Overall verdict:** `CONSISTENT_WITH_KNOWN_GAPS` (expected when enforcement gaps remain explicit)

## G4.1 closure (reset_hard)

| Layer | Decision |
|-------|----------|
| Machine Contract | `reset_hard` → `AGENT_ALWAYS_BLOCK`, `OUTSIDE_AGENT_CONTRACT` |
| Semantic (`GIT_OPERATION_POLICY.md`) | Agent 禁止 / Human 直接操作は Agent 外 |
| Guard | unchanged — `forbid_actions` + exit **2** on `--action reset_hard` |
| GUARD_STRONGER drift | **resolved** (contract aligned to guard) |

**contract_version:** `2026-09-12.3`

## G5 deliverables

| Item | Path |
|------|------|
| Invariants + known gaps | `ai_tool/policy/git_governance_invariants.py` |
| Distribution / drift audit | `ai_tool/policy/git_governance_distribution.py` |
| Tests | `tests/ai_tool/policy/test_git_governance_drift.py` |
| Evidence | `reports/GIT_GOVERNANCE_PHASE_G5.json` |

## Validated surfaces

- Semantic invariants (G2/G4.1 human decisions)
- Contract version pin
- Semantic policy anchors (not full markdown diff)
- `development_policy.json` manifest + `git_governance_ref`
- In-repo adapters (no embedded contract JSON)
- Guard configs vs `AGENT_ALWAYS_BLOCK` forbid set (`force_push`, `force_push_with_lease`, `reset_hard`)
- Known gap registry (deletion ≠ enforcement)
- Host checklist metadata (`HOST_ADAPTER_NOT_VERIFIED`)
- Shared hooks READ-ONLY when present; `NOT_OBSERVED` when absent (no false FAIL)

## Negative drift fixtures

Contract approval change, guard forbid removal, manifest bad ref, contract version mismatch → **FAIL** as designed.

## Known enforcement gaps (explicit)

`commit`, `amend`, `amend_after_hook_failure`, `clean`, `rebase`, `worktree_remove`, `branch_delete`, `merge_to_main` — status `KNOWN` until evidence-based closure.

## Not changed

`guard.py`, shared hooks, Runtime, Cursor User Rules, git commit/push.

## Next

**G6** — SYSTEM_ASSET_INDEX / project_assets registry (do not auto-start).
