# Local destructive Git operations — enforcement map (v2.2)

**Policy model:** SAFE / BLOCK / NEED_HUMAN via `tools/git_guard/safe_local_operation.py` when
`guard.py` is invoked with `--config .../ai-agent.local-ops.json --action local_git --local-op ...`.

## v2.2.1 Agent bridge (PROJECT_AGENT)

| Path | Classification |
|------|----------------|
| `agent.py` `execute_tool()` when `arguments.command` (or `cmd`) carries destructive local git | **MACHINE_ENFORCED** via `tools/system/agent_git_execution_gate.py` → `agent_local_op_bridge.py` |
| `ai_tool/chat_interface/agent_turn.py` `_execute_agent_tool()` | **NOT_CONNECTED** (no shell command field on registry tools today) |
| Cursor IDE terminal | **RULE_ONLY** (adapter) |
| Human raw PowerShell / git CLI | **NOT_ENFORCED** |

Env `AI_AGENT_GIT_LOCAL_GATE=off` disables the bridge (escape hatch; not default).

NEED_HUMAN: explanations propagate; **resume after human answer** → `ENFORCEMENT_CONNECTED_BUT_RESUME_GAP`.

## Classification (READ-ONLY audit baseline)

| Operation | Git pre-exec hook | Explicit guard (`local_git`) | Contract / GIT markdown | Cursor adapter |
|-----------|-------------------|------------------------------|-------------------------|----------------|
| `git restore` / `checkout -- path` | NOT_ENFORCED | ENFORCED_BEFORE_EXECUTION (when probed) | POLICY_COVERAGE v2.2 | RULE_ONLY |
| `git reset` (modes) | NOT_ENFORCED | ENFORCED_BEFORE_EXECUTION | POLICY_COVERAGE v2.2 | RULE_ONLY |
| `git clean` | NOT_ENFORCED | ENFORCED_BEFORE_EXECUTION | POLICY_COVERAGE v2.2 | RULE_ONLY |
| `git worktree remove` | NOT_ENFORCED | ENFORCED_BEFORE_EXECUTION | POLICY_COVERAGE v2.2 | RULE_ONLY |
| `Remove-Item -Recurse -Force` / `rm -rf` | NOT_ENFORCED | NOT_ENFORCED | POLICY_DEFINED_BUT_NOT_MACHINE_ENFORCED | RULE_ONLY |
| `git reset --hard` (raw CLI) | NOT_ENFORCED | BLOCK via `forbid_actions` only on `--action reset_hard` | AGENT_ALWAYS_BLOCK | RULE_ONLY |

**MACHINE_ENFORCEMENT=false** for arbitrary shell unless the agent calls git_guard first.

**Recovery paths** (stash, reflog) are never treated as `RECOVERY_PROVEN` for SAFE.

## Evidence (design)

- **Evidence A:** `git checkout HEAD -- <path>` discarded unproven uncommitted work — v2.2 blocks restore/checkout when unstaged changes exist.
- **Evidence B:** verification worktree `Remove-Item -Recurse -Force` — agents must not auto-delete; probe worktree registry and use `git worktree remove` after guard PASS.
