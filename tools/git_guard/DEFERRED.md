# Deferred - not in scope for blind automation

Git Guard is **not** a replacement for a human (or Strong Gate) on:

- Push / merge into protected branches (`stabilize/*`, `main`, promote tips, etc.)
- Force push, `reset --hard`, history rewrite
- Conflict resolution and selective-adoption **judgment**
- Semantic review of whether a path set is “the right” adopt set

Those should stay `human_gate_actions` -> exit **NEED_HUMAN (3)**, or stay entirely out of Local auto-run.

## Candidates to evaluate later (IMPACT_SYNC)

When these incident patterns recur with stable criteria, consider Guard fields + examples + hook wiring (see POLICY.md):

- Signed-off / commit message shape (mechanical only)
- Max commit count / range size for selective adopt
- Explicit protected-ref list beyond config examples
- Worktree path denylist (hard refuse known adopt dirs from wrong Goal)

Until criteria are stable, leave on Human/Strong Gate and note here.
