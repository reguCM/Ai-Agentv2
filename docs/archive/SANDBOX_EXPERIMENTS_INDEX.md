# Sandbox experiments INDEX (2026-09 isolation wave)

**Purpose:** Normal development keeps only this Index. Details live under Archive; open on demand.

**Archive root:** `D:\\AI-Agent-worktrees\\archive\\from-grok-sandbox\\archive\\2026-09-isolation\\`

**Policy:** RECORD / completed Goal proofs -> Archive. Normal Goal work = `D:\\AI-Agent-worktrees\\*`. Dedicated Sandboxes = `D:\\AI-Agent-worktrees\\sandboxes\\`.

**Updated:** 2026-09-08 (JST) — H2H3 (`promote/h2h3-from-delta`) merged into `stabilize/tool-result-contract` (help `/h` + `ai_tool/help`); tooling previously @ `2c1b887`.

## Archived (moved)

| ID | Summary | Archive location |
|----|---------|------------------|
| A2 | Conditions bridge experiment (contract/detector/PROOF) | `archive/2026-09-isolation/goals/a2-conditions-bridge/` |
| C2 | Negation constraints experiment | `archive/2026-09-isolation/goals/c2-negation-constraints/` |
| O2 | Order bridge (incomplete) | `archive/2026-09-isolation/goals/o2-order-bridge/` |
| S3/shadow | Shadow judge harness | `archive/2026-09-isolation/goals/shadow-judge-harness/` |
| H1 | Help System H1 goal docs/detector/goldens (runtime vendored into `ai_tool/help/h1_service.py` on promote) | `archive/2026-09-isolation/goals/help-system-h1/` |
| selective-a52 | Selective adoption catalogs/patches U1–U6 (mega not merged) | `archive/2026-09-isolation/goals/_selective-adoption-a52c979/` |
| dirty-triage | Worktree dirty triage notes | `archive/2026-09-isolation/goals/_worktree-dirty-triage/` |
| tmp-ref | Temp exports/patches/bootstrap | `archive/2026-09-isolation/goals/_tmp_ref/` |
| proof-iso | Isolation proof 2026-09-08 | `archive/2026-09-isolation/proofs/20260908-124916-isolation/` |

## Still live under sandbox (not archived yet)

Retired 2026-09-09. Living records were copied to `D:\AI-Agent-worktrees\archive\from-grok-sandbox\`. The grok-sandbox top-level tree is no longer part of the standing layout.

| ID | Archive location | Note |
|----|------------------|------|
| H2H3 goal | `from-grok-sandbox/goals/help-system-h2h3/` | Runtime already merged into stabilize |
| Git Guard | in-repo `tools/git_guard/` | Former sandbox tree was a superseded mirror |
| Promotion Runner | in-repo `tools/promotion_runner/` | Former sandbox tree was a superseded mirror |
| Reorg docs | `from-grok-sandbox/goals/_reorg-normal-layout/` | Layout/CLASSIFICATION records |
| Baseline clone | **not copied** | Regenerable from `wip/tool-result-contract-20260908` @ `a52c979`; `_meta` only at `from-grok-sandbox/baselines/_meta/` |

## Promote / merge status (canonical repo)

| Branch | SHA | Status |
|--------|-----|--------|
| `stabilize/tool-result-contract` | (post-merge tip) | **MERGED tooling** + **MERGED H2H3** (`ai_tool/help`, `/h` wiring in agent_turn / task_orchestration) |
| `promote/tooling-git-guard-runner` | `e9de097` | Merged into stabilize (kept; do not delete) |
| `promote/h2h3-from-delta` | (see worktree) | **MERGED** into stabilize (INDEX kept ours + this note; help `/h` + `ai_tool/help`) |

## DISCARD candidates (listed only)

See CLASSIFICATION.md — `__pycache__`, pytest temps under archive/goals, etc. **Do not delete without human gate.**