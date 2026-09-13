# Implementation Plan: Phase 3A /goal and /run Boundary

## Overview

Split Production goal definition from Runtime preparation. `/goal` reuses the existing requirement-to-handoff path and stops. `/run` validates and mechanically prepares the exact saved handoff as Runtime Goal/Task records, without LLM calls, sandbox creation, tools, execution, verification, or completion judgment.

## Architecture Decisions

- Parse `/goal` and `/run` at the Production Chat boundary in `agent_turn.py`.
- Keep legacy external handoff and Production Handoff paths unchanged for compatibility.
- Add a preparation-only operation to the existing Goal Handoff Runtime Bridge; keep the existing execution-seeding behavior unchanged.
- Prove packet identity with the existing `handoff_id`, a canonical JSON hash diagnostic, and immutable-field comparison.

## Task List

- [x] Add explicit `/goal` routing and standalone usage response.
- [x] Add fail-closed `/run` routing from `session.production_handoff_packet`.
- [x] Add preparation-only Runtime conversion with all tasks pending.
- [x] Test Tetris preservation, exact handoff reuse, no sandbox/execution, and Calculator isolation.
- [x] Run focused and compatibility regressions (one legacy Sandbox test remains environment-blocked).

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `/run` accidentally enters `_chat_turn` | High | Return a completed boundary result before agent-loop selection |
| Legacy Handoff regeneration is invoked | High | `/run` calls only validation and Runtime Bridge preparation |
| Runtime conversion mutates the saved packet | High | Deep-copy input and compare canonical hashes/immutable fields |
| Existing legacy paths regress | Medium | Keep routing intact and run existing Handoff tests |
