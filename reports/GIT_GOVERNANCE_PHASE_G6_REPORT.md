# Git Governance Phase G6 — Registry / SYSTEM_ASSET_INDEX Integration Report

## Status

**G6: COMPLETE**

**G5 verdict preserved:** `CONSISTENT_WITH_KNOWN_GAPS` (not promoted to `CONSISTENT`)

## A. Updated assets

| asset_id | Change |
|----------|--------|
| `git_operation_policy` | `enforcement_level` → **DOCUMENTATION** (was ENFORCED); removed validator conflation; `POSSIBLY_STALE` |
| `git_guard` | Validator role notes; `freshness_dependencies`; `POSSIBLY_STALE` |
| `policy_manifest` | `related_assets` + `git_governance_contract` |
| `cursor_user_rules` | Host drift note + link to checklist |

## B. New assets

| asset_id | Role |
|----------|------|
| `git_governance_contract` | Machine Contract (`2026-09-12.3`) |
| `git_governance_cursor_adapter` | Cursor reference adapter |
| `git_hooks_deployment` | EXTERNAL enforcement adapter (DEPLOYED.md) |

## C. Source of Truth mapping

```text
Semantic     → git_operation_policy (GIT_OPERATION_POLICY.md)
Machine      → git_governance_contract (git_governance.json)
Manifest     → policy_manifest.git_governance_ref
Cursor       → git_governance_cursor_adapter (.mdc)
Validator    → git_guard (guard.py + configs)
Hooks        → git_hooks_deployment (shared .git/hooks via DEPLOYED.md)
```

## D. Freshness dependencies (directed only)

- `git_governance_contract` ← `git_operation_policy`
- `git_guard` ← `git_governance_contract` + hook config paths
- `git_hooks_deployment` ← `git_guard` + `DEPLOYED.md`
- `git_governance_cursor_adapter` ← `git_governance_contract`

`related_assets` used for human navigation only (not staleness propagation).

## E. Enforcement metadata

- Policy prose is **not** `ENFORCED`.
- Contract is **VALIDATED** (tests + drift audit), not full runtime enforcement.
- Guard/hooks **ENFORCED** on their scope; registry `notes` document partial coverage and known gaps.

## F. Verification

- **No automation** `→ VERIFIED` for Git Governance enrollment assets (`POSSIBLY_STALE` + stale_reason).
- Baseline evidence captured for new assets under `reports/verification_evidence/`.
- Linked phase reports G2–G5.

## G. SYSTEM_ASSET_INDEX

- Regenerated via `tools/generate_system_asset_index.py`
- `--check` **PASS**

## H. Tests

`tests/registry/test_git_governance_registry.py` + existing registry/freshness/governance tests **PASS**.

## I. Freshness dry run

See `reports/project_asset_freshness_g6_dry_run.json` for `UNCHANGED` / `CHANGE_CANDIDATE` / `UNKNOWN` counts.

## J. Remaining known gaps (unchanged intent)

Runtime commit authorization, amend paths, clean/rebase/worktree_remove, merge_to_main, RAW CLI bypass — documented in contract notes and `git_governance_invariants.KNOWN_ENFORCEMENT_GAPS`.

## Git Governance series

```text
G1–G6 COMPLETE
```

Separate future work: Runtime `AUTO_COMMIT_ALLOWED`, host User Rule verification, artifact/commit provenance.
