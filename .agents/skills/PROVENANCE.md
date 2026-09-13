# Skill provenance (standard development assets)

**Status:** adopted (Human Decision 2026-09-08). Standard development assets, not evaluation or trial.

Evaluation checkpoint `4951af9` remains as-is (not amended). This file records the subsequent adoption.

Skill bodies (`.agents/skills/**/SKILL.md`) are unmodified. Replace, reinforce, or add skills only when a real project confirms shortage, behavior mismatch, redundancy, or insufficient reproducibility.

| skill | source_repo | source_path | fetched | status |
|-------|-------------|-------------|---------|--------|
| grill-me | https://github.com/max4c/skills | skills/grill-me | 825b94d5c28b81d5cf1c66ce2f474dc2d3c87048 | adopted |
| write-prd | https://github.com/max4c/skills | skills/write-prd | 825b94d5c28b81d5cf1c66ce2f474dc2d3c87048 | adopted |
| tech-spec | https://github.com/max4c/skills | skills/tech-spec | 825b94d5c28b81d5cf1c66ce2f474dc2d3c87048 | adopted |
| graph-engineering | https://github.com/douinc/agent-skills | skills/graph-engineering | 30212729887fd1fb7317d7618d281b4036c3e4b1 | adopted |
| planning-and-task-breakdown | https://github.com/addyosmani/agent-skills | skills/planning-and-task-breakdown | 6ca0cd7db39b41b1c37e26d335c507ee92382c6d | adopted |
| goal-handoff | local | .agents/skills/goal-handoff | n/a | provisional |
| session-start | local | .agents/skills/session-start | n/a | provisional |

Composition (standard):
rough Goal -> write-prd (+ internal grill-me) -> graph-engineering -> tech-spec (+ internal grill-me) -> planning-and-task-breakdown -> goal-handoff
grill-me may also be invoked alone.

Machine catalog: `registry/skills.json` (schema: `registry/schema/skills.schema.json`)

Local provisional skill: `goal-handoff` (`.agents/skills/goal-handoff/SKILL.md`). Emits `docs/handoffs/*.json` per `docs/specs/GOAL_HANDOFF_V0.md`.

Alias 正本: `registry/skills.json` → `alias_index`

Namespace adapter（Cursor ミラー）: `.cursor/rules/skill-namespace-compat.mdc`

Imported skill bodies invoke `max:grill-me` / `max:write-prd` / `max:tech-spec`. Those names map to the local adopted skills. Other `max:*` / `bugbook:*` names are not adopted.
