# Implementation Plan: Production aligned_spec to Goal Handoff

## Overview

Continue the final Production Phase 1 `aligned_spec` through the existing Dev Skill Pipeline to PRD, Tech Spec, Plan, and a schema-valid Goal Handoff, then stop before Runtime.

## Architecture Decisions

- Keep `production_handoff_bridge.py` as the Production boundary owner.
- Reuse the final Production `aligned_spec`; do not run standalone grill-me again.
- Read Mission requirements and confirmed Human decisions without creating a second source of truth.
- Remove Tetris-specific fallback behavior from the generic Production path.
- Do not seed Runtime from the generated Goal Handoff.

## Completed Tasks

- [x] Reuse final `aligned_spec` as the existing pipeline's Phase 1 result.
- [x] Connect the downstream pipeline through the Production bridge.
- [x] Return a validated Goal Handoff and stop before Runtime.
- [x] Add Tetris semantic-preservation and Calculator negative tests.

## Verification

- [x] Focused Dev Skill Pipeline and registry tests pass.
- [x] Phase 1 / 1.1 focused regression tests pass.
- [x] Goal Handoff schema validation passes.
- [x] Runtime is not started by the new path.
- [ ] Two existing sandbox worktree tests require Git metadata write permission in this environment.
