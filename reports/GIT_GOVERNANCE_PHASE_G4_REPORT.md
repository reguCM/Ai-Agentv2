# Git Governance Phase G4 — Enforcement / Guard Alignment Report

## Status

**G4: COMPLETE** (Human review before G5)

## Summary

| Metric | Value |
|--------|------:|
| Contract actions | 21 |
| PARTIALLY_ENFORCED | 6 |
| NOT_CONNECTED | 6 |
| GUIDANCE_ONLY | 4 |
| CONTRACT_DEFINED (commit) | 1 |
| CONTRACT_ONLY (amend_after_hook_failure) | 1 |
| NOT_APPLICABLE (read-only) | 3 |

**Config ↔ contract alignment:** `config_alignment_ok: true` after adding `force_push_with_lease` to hook configs.

**Not claimed:** full ENFORCED coverage. HUMAN_APPROVAL_REQUIRED / AGENT_ALWAYS_BLOCK without a guard path remain `NOT_CONNECTED` / `CONTRACT_ONLY` / `RAW_CLI_ENFORCEMENT_GAP`.

## Enforcement paths (evidence)

| Check | Result |
|-------|--------|
| `guard.py` + `ai-agent.pre-push.json` `--action push` | exit **3** NEED_HUMAN |
| `--action force_push` | exit **2** FAIL (forbid_actions) |
| `--action force_push_with_lease` | exit **2** FAIL (G4 config) |
| `--action reset_hard` | exit **2** FAIL (forbid; **GUARD_STRONGER** vs contract HUMAN_APPROVAL_REQUIRED) |
| staged `.env` + deny_path_globs | exit **2** FAIL |
| wrong `origin` URL + url_must_contain | exit **2** FAIL |

## Hooks (READ-ONLY)

- Documented: `tools/git_guard/DEPLOYED.md`
- Shared hooks: `D:\AI-Agent\.git\hooks\pre-commit` / `pre-push` — **exist**, thin launcher → in-repo `guard.py` + configs
- **Not modified in G4** (all-worktree impact)

## Raw CLI gaps (explicit)

Direct `git` without hooks / without `guard --action` bypasses enforcement for:

`clean`, `rebase`, `worktree_remove`, `branch_delete`, `stash`, `amend`, `merge_to_main`, and **all** actions when `--no-verify` or no hook install.

## Commit / AUTO_COMMIT_ALLOWED

- `commit` → `CONTRACT_DEFINED` + `RUNTIME_NOT_CONNECTED` (no Runtime wiring in G4)

## Changes made (minimal)

1. `forbid_actions`: added `force_push_with_lease` to `ai-agent.pre-commit.json` and `ai-agent.pre-push.json`
2. `ai_tool/policy/git_governance_enforcement.py` — `validate_git_governance_enforcement()`, `build_enforcement_matrix()`
3. `tests/tools/test_git_guard_governance_alignment.py` — negative + scope-gap tests
4. Contract note on `force_push_with_lease` validator binding

## Changes not made

- `guard.py` logic, shared hooks, Runtime/GoalContract, Cursor User Rules, git wrapper

## Tests

```text
pytest tests/tools/test_git_guard_governance_alignment.py
pytest tests/ai_tool/policy/test_git_governance*.py tests/ai_tool/policy/test_policy_distribution.py
```

## Artifacts

- Machine matrix: `reports/GIT_GOVERNANCE_PHASE_G4.json`
- Validator API: `validate_git_governance_enforcement()` in `git_governance_enforcement.py`

## Next

G5 Drift / Distribution Tests — **PENDING** (do not auto-start).
