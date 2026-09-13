# Promotion Runner — Policy

## Ladder (Strong LLM → Runner → Human)

1. **First time / conflict / semantic port** — Human or Strong LLM may craft the delta or port hunks once.
2. **Same mechanical promote repeats** — encode in Promotion Runner + config.
3. **Path/ref/test gates** — Runner + optional Git Guard (`git_guard_config`).
4. **Adoption into stabilize, push, history rewrite, conflict resolution** — **Human only** (exit 3).

## Human gate actions

`merge`, `push`, `reset_hard`, `delete_branch`, `force_push` → NEED_HUMAN (3). Runner must stop.

## IMPACT_SYNC

Reports include a checklist for 正本 / Rule / Help / Registry / Test surfaces.

## In-repo promotion

Canonical copy target: `tools/promotion_runner/` on a `promote/*` branch from stabilize tip.
Sandbox tree remains a RECORD mirror after in-repo promote (superseded by in-repo). The grok-sandbox copy was retired in Phase 2 Cleanup.
