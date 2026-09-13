# Git Governance Phase G3 — Adapter Alignment Report

## Status

**G3: COMPLETE** (Human review before G4)

## What changed

1. **Machine contract** (`git_governance.json` v `2026-09-12.2`): `adapters.consumers` registry for in-repo adapters + host checklist.
2. **New Cursor adapter:** `.cursor/rules/git-governance-adapter.mdc` (reference-only summary).
3. **Updated references:** `AGENTS.md`, `agent-development-policy.mdc`, `development_policy.json` consumer `required_references`.
4. **Semantic alignment:** `docs/GIT_OPERATION_POLICY.md` §4 — Option C, machine contract pointer, amend rules (PROJECT_CANONICAL).
5. **Guard policy adapter:** `tools/git_guard/POLICY.md` — validator role + contract pointer (no `guard.py` / config changes).
6. **Host checklist:** `docs/adapters/GIT_GOVERNANCE_CURSOR_HOST.md` for Cursor User Rules manual sync.

## Drift addressed

| Topic | G3 outcome |
|-------|------------|
| commit GIT §4 vs Option C | GIT §4 tied to `AUTO_COMMIT_ALLOWED` + contract |
| amend REPO_CANON_GAP | GIT §4 + contract + Cursor adapter |
| Cursor User Rules | Documented as OUTSIDE_REPOSITORY; checklist only |

## Verification

```text
pytest tests/ai_tool/policy/test_git_governance.py tests/ai_tool/policy/test_git_governance_adapters.py tests/ai_tool/policy/test_policy_distribution.py
```

Evidence: `reports/GIT_GOVERNANCE_PHASE_G3.json`

## Not in G3

- G4: guard config ↔ contract validation / generation
- G5: automated drift matrix tests
- G6: `registry/project_assets.json` / SYSTEM_ASSET_INDEX
- Editing host Cursor User Rules inside the IDE
