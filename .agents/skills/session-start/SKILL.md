---
name: session-start
description: Run the repository Session Start / resync check before development work. Use when the user says work is starting, resuming, or asks for current status after a gap, branch change, or AI handoff.
---

# Session Start

## Overview

Read and follow the canonical Session Start Policy. This Skill does not replace that Policy; it routes Cursor/Codex to the correct resync depth before coding.

**What this skill does NOT do:**

- Copy or rewrite `docs/AI_DEVELOPMENT_SESSION_START_POLICY.md`
- Start implementation, commit, push, or merge
- Connect to Production Chat, Mission Memory, or Goal Handoff runtime

## When to Use

- User says: 作業開始 / 作業再開 / 状況確認 / 今日の作業始めます / 前回の続き / 現在の状態を確認
- Branch, worktree, HEAD, or working tree may have changed since the last turn
- Another AI or environment may have touched the repository

**When NOT to use:** Same session with clear continuous context and a narrow follow-up instruction (for example: "add one more test").

## Required Reading

Before deciding resync depth, Read:

1. `docs/AI_DEVELOPMENT_SESSION_START_POLICY.md` — trigger rules, light vs full sync
2. `docs/CURRENT_DEVELOPMENT_STATE.md` — current worktree, branch themes, known NOT_CONNECTED items
3. `docs/SYSTEM_ASSET_INDEX.md` — when the task touches experimental assets
4. `registry/skills.json` — when the task involves adopted Dev Skills or Handoff

Do not treat chat memory or prior summaries as repository truth.

## Light Session Check

Run when Session Start Policy §5 applies. Minimum facts to collect from the repository:

1. Current worktree path
2. Current branch
3. HEAD
4. staged / unstaged / untracked
5. Recent related commits
6. Current primary work theme

Then classify as one of:

| Label | Meaning |
|---|---|
| `READY` | Safe to proceed |
| `RESUME` | Continue only the unfinished portion |
| `ALREADY_DONE` | Prior request already completed |
| `NEED_FULL_SYNC` | Escalate to full sync |

Report the label and the evidence used.

## Full Session Sync

Escalate when Session Start Policy §6 triggers match. Additional checks include:

- Compare recorded HEAD vs current HEAD
- New commits since last report
- Unfinished vs completed work
- Whether the current user request is still valid
- Relevant canonical specs and latest test state

Do not skip full sync because the user message sounds simple.

## Output

Return a short resync report with:

1. **Classification** — READY / RESUME / ALREADY_DONE / NEED_FULL_SYNC
2. **Observed state** — worktree, branch, HEAD, dirty summary
3. **Canonical sources read** — paths only
4. **Next action** — what to do before editing code

If `NEED_FULL_SYNC`, list missing facts before implementation.

## Red Flags

- Assuming branch/worktree from memory
- Treating `CURRENT_DEVELOPMENT_STATE.md` history sections as current values without `git` verification
- Starting code changes before classification
- Mixing Production Runtime facts with Dev Skill workflow facts

## See Also

- `docs/AI_DEVELOPMENT_SESSION_START_POLICY.md`
- `docs/GIT_OPERATION_POLICY.md`
- `docs/DEVELOPMENT_TEST_POLICY.md`
- `ai_tool/policy/development_policy.json`
