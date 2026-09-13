# Git Governance Phase G2 — Machine Contract Report

## Status

**G2: COMPLETE** (Human review before G3)

## Deliverables

| Item | Path |
|------|------|
| Machine Contract | `ai_tool/policy/git_governance.json` |
| JSON Schema | `ai_tool/policy/git_governance.schema.json` |
| Loader / validator | `ai_tool/policy/git_governance_contract.py` |
| Tests | `tests/ai_tool/policy/test_git_governance.py` |
| Manifest reference | `development_policy.json` → `distribution.git_governance_ref` |

**Contract version:** `2026-09-12.1`  
**Actions defined:** 21

## Architecture (unchanged from G1)

`docs/GIT_OPERATION_POLICY.md` (semantic) → Machine Contract → (future) Adapters / Validators / Hooks

The contract declares `semantic_sources`; it is **not** the semantic authority.

## Human Decisions Encoded

- **Commit Option C:** default `agent_default_auto_commit: false`; `commit` → `TASK_AUTHORIZATION_REQUIRED` with token `AUTO_COMMIT_ALLOWED` (`runtime_binding: NOT_CONNECTED`).
- **Dangerous ops:** as specified in G2 brief (push human; force push variants blocked for agent; reset/clean/rebase/worktree_remove human).
- **Amend:** `amend` → `HUMAN_APPROVAL_REQUIRED`; `amend_after_hook_failure` → `AGENT_ALWAYS_BLOCK` with `human_direct_operation: OUTSIDE_AGENT_CONTRACT`.

## Still UNDECIDED / GUIDANCE_ONLY

- `stash` → `UNDECIDED` (no clear GIT markdown or G2 decision).
- `add_all`, `commit_message` → `GUIDANCE_ONLY` from GIT §7 / §9.

## NOT_CONNECTED

- `AUTO_COMMIT_ALLOWED` issuance and Runtime verification.
- All `required_conditions` on `commit`.
- Full agent CLI coverage (hooks are PARTIAL only where noted).

## Policy Drift (documented in contract)

Recorded in `policy_drift_notes` inside `git_governance.json` (commit auto, force push, reset/clean, amend).

## Verification

```text
pytest tests/ai_tool/policy/test_git_governance.py
pytest tests/ai_tool/policy/test_development_policy.py
pytest tests/ai_tool/policy/test_policy_distribution.py
```

All passed in G2 implementation run.

**Existing hooks / git_guard / Cursor rules / AGENTS.md:** not modified.

Machine evidence JSON: `reports/GIT_GOVERNANCE_PHASE_G2.json`

## Next

Do **not** start G3 automatically. Pending: Adapter Alignment, Enforcement Alignment, Drift/Distribution Tests, SYSTEM_ASSET_INDEX update.
