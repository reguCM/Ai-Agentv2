---
name: goal-handoff
description: Emit a machine-readable Goal Handoff Packet after PRD, tech spec, and task planning are complete. Use when implementation should start in a fresh branch or session and downstream agents need a single canonical packet instead of rereading every design artifact.
---

# Goal Handoff

## Overview

Package the outputs of the Dev Skill pipeline into one **Goal Handoff Packet**. The packet is the only machine bridge from design work to implementation in this repository.

**What this skill does NOT do:**

- Start implementation or edit production code
- Replace PRD / tech spec / `tasks/plan.md` / `tasks/todo.md`
- Create or update Mission Memory, Chat Runtime tasks, or Production Goal records
- Infer `parent_proposal_id`, mission ids, or runtime completion state

## When to Use

- `planning-and-task-breakdown` finished and the human approved the plan
- A new implementation branch, worktree, or agent session should continue from a single artifact
- You need explicit acceptance criteria, test targets, and human gates in one place

**When NOT to use:**

- No written plan or task list exists yet
- The work is a single obvious file change with no spec
- Open questions remain unresolved and would block safe implementation

## Prerequisites

Read these repository artifacts before emitting a packet:

1. `registry/skills.json` — confirm `goal-handoff` is listed and note `output_contracts.goal_handoff`
2. `docs/specs/GOAL_HANDOFF_V0.md` — human contract and field semantics
3. `registry/schema/goal_handoff.schema.json` — machine shape
4. Upstream artifacts produced in the current goal:
   - PRD path, if any
   - Tech spec path, if any
   - `tasks/plan.md`
   - Task list target (default `tasks/todo.md`)

If upstream artifacts conflict, stop and resolve with the human. Do not merge contradictions into the packet.

## The Handoff Process

### Step 1: Collect sources

Record:

- Skill ids used in this pipeline (`source.skills`)
- Repository-relative paths for PRD, tech spec, plan, and task list (`source.documents`)
- Observed git branch, HEAD, and worktree if available (`source.git`)

### Step 2: Normalize goal and scope

- `goal.summary` — one paragraph for the implementing agent
- `scope.in_scope` — what must change
- `scope.non_goals` — explicit exclusions
- `scope.affected_paths` — directories or files expected to change

Do not copy the entire PRD. Point to paths and summarize.

### Step 3: Lift acceptance and tasks

- `acceptance_criteria` — stable ids `A1`, `A2`, ...
- `implementation_tasks` — stable ids `T1`, `T2`, ...
  - Each task needs acceptance bullets, verification steps, and size `S|M|L|XL`
  - Map tasks to acceptance ids with `maps_to_acceptance` when useful
  - Reject `ready` status if any task is `L` or `XL` unless the human explicitly accepts the risk

### Step 4: Declare test plan and gates

- `test_plan.pytest` — repository-relative pytest targets required before handoff is `ready`
- `test_plan.e2e` / `test_plan.manual` — optional
- `human_gates` — only from the allowed enum in the schema

Default repository policy still applies even when a gate is omitted from the packet.

### Step 5: Write the packet

- Generate `handoff_id` as `gh-YYYYMMDDTHHMMSSZ-<slug>`
- Set `handoff_version` to `0.1`
- Set `provisional` to `true`
- Set `runtime_boundary.production_connected` to `false`
- Save to `docs/handoffs/{handoff_id}.json`

Create `docs/handoffs/` if missing.

### Step 6: Validate before `ready`

Before setting `status` to `ready`:

- [ ] JSON validates against `registry/schema/goal_handoff.schema.json`
- [ ] Every `implementation_tasks[].size` is `S` or `M`, or human explicitly accepted `L`/`XL`
- [ ] `acceptance_criteria` and `test_plan.pytest` are non-empty
- [ ] `scope.affected_paths` is non-empty
- [ ] Human reviewed the packet

Until human approval, keep `status: draft`.

## Output Contract

The packet MUST validate against `registry/schema/goal_handoff.schema.json`.

Required top-level fields:

| Field | Rule |
|---|---|
| `handoff_version` | Must be `0.1` |
| `handoff_id` | `gh-YYYYMMDDTHHMMSSZ-slug` |
| `status` | `draft` until human approval, then `ready` |
| `provisional` | Must be `true` in v0 |
| `source.skills` | Includes `goal-handoff` and upstream skills actually used |
| `source.documents.plan` | Usually `tasks/plan.md` |
| `source.documents.task_list` | Usually `tasks/todo.md` |
| `runtime_boundary.production_connected` | Must be `false` |

### Mapping from planning outputs

| Planning artifact | Packet field |
|---|---|
| Plan overview / phases | `goal.summary`, `scope.in_scope`, `risks` |
| Task titles and acceptance bullets | `implementation_tasks` |
| Checkpoints / verification steps | `implementation_tasks[].verification`, `test_plan` |
| Non-goals / out of scope | `scope.non_goals` |
| Open questions | `open_questions` (block `ready` if unresolved) |

### Runtime boundary statement

Use this default unless the human provides a better repo-specific sentence:

> Dev Handoff Packet only. Production Chat / Mission Memory / Goal Completion Gate do not consume this file in v0.

## Red Flags

- Emitting a packet without reading upstream artifacts
- Setting `status: ready` while `open_questions` is non-empty
- Treating the packet as a Mission `original_goal` replacement
- Adding Production-only fields (`mission_id`, `execution_id`, tool traces)
- Using README/H4/single-case special cases instead of general fields

## Verification

- [ ] `docs/handoffs/{handoff_id}.json` exists
- [ ] Instance validates against `registry/schema/goal_handoff.schema.json`
- [ ] `registry/skills.json` lists `goal-handoff` with `output_contract: goal_handoff`
- [ ] Human approval recorded before `status: ready`

## See Also

- `docs/specs/GOAL_HANDOFF_V0.md`
- `docs/handoffs/examples/goal-handoff-example.json`
- `.agents/skills/planning-and-task-breakdown/SKILL.md`
- `docs/GIT_OPERATION_POLICY.md`
