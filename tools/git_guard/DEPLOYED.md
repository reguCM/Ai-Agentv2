# Git Guard — DEPLOYED (AI-Agent)

**V2 host live install (2026-09-13):** `tools/git_guard/DEPLOYED.v2.md`  
(`D:\Ai-Agent_v2\.git\hooks`. This file below is the 2026-09-08 Production / `D:\AI-Agent` record — LEGACY_EVIDENCE_ONLY.)

**Status:** Promoted into `stabilize/tool-result-contract` (in-repo `tools/git_guard/`). Hooks use **in-repo only** (sandbox fallback removed).
**Installed / updated:** 2026-09-08 (Asia/Tokyo)
**Canonical package root:** worktree `tools/git_guard/` (e.g. `D:\AI-Agent-worktrees\_promote-tooling\tools\git_guard\`)
**Canonical:** in-repo `tools/git_guard/`. The old grok-sandbox `_git-guard` tree was a superseded mirror and has been retired.

## What was installed

### Hooks (canonical repo)

| Hook | Path | Config |
|------|------|--------|
| pre-commit | `D:\AI-Agent\.git\hooks\pre-commit` | `$TOP/tools/git_guard/configs/ai-agent.pre-commit.json` |
| pre-push | `D:\AI-Agent\.git\hooks\pre-push` | `$TOP/tools/git_guard/configs/ai-agent.pre-push.json` + `--action push` |

Hooks resolve `$TOP=$(git rev-parse --show-toplevel)` and require in-repo `tools/git_guard/guard.py`. If missing (worktree without tooling), hooks **fail clearly** (exit 1) — no sandbox fallback.
`repo: "."` resolves to show-toplevel from process cwd (any worktree sharing this `.git`).
Optional override: set env `GIT_GUARD_REPO` to an absolute worktree path.

### Configs under `configs/`

| File | Use |
|------|-----|
| `ai-agent.pre-commit.json` | Hook: secrets deny globs, origin URL must contain `github.com/reguCM/Ai-Agentv2`, forbid force_push/reset_hard. |
| `ai-agent.pre-push.json` | Hook: remote check + forbid force_push/reset_hard; **push_safety v2.1** — verified fast-forward **PASS**; unsafe **BLOCK**; unresolved **NEED_HUMAN**. |
| `local.check-stabilize.json` | Local CLI for stabilize/wip/sandbox/promote worktrees. |
| `local.selective-adopt.json` | Local CLI for selective-adopt style. |

## How Local invokes

```text
cd D:\AI-Agent-worktrees\_promote-tooling
python tools/git_guard/guard.py --config tools/git_guard/configs/ai-agent.pre-commit.json

python tools/git_guard/guard.py --config tools/git_guard/configs/ai-agent.pre-push.json --action push --target-remote origin
```

Exit codes: `0` PASS, `1` ERROR, `2` FAIL, `3` NEED_HUMAN.

## Push safety (v2.1)

pre-push passes `--action push` and one or more `--push-ref local|local_sha|remote|remote_sha` lines from git stdin.

With `push_safety: v2.1`, verified **fast-forward** pushes to allowed remotes **PASS** without `--no-verify`.

- **BLOCK (exit 2):** non-fast-forward, ref delete, forbidden remote URL, forbid_actions
- **NEED_HUMAN (exit 3):** missing push-ref context or ancestry cannot be verified
- **`--no-verify`:** still bypasses all hooks; use only for exceptional human ops, not normal safe push

## Smoke results (post-merge 2026-09-08 JST)

From `D:\AI-Agent-worktrees\_promote-tooling` on `stabilize/tool-result-contract` @ `2c1b887`:

| Check | Exit |
|-------|------|
| `guard.py --help` | **0** |
| `ai-agent.pre-commit.json` | **0 PASS** |
| `ai-agent.pre-push.json --action push` | **3 NEED_HUMAN** |

## Out of scope

- No GitHub push
- H2H3 not merged
- Sandbox `_git-guard` kept as mirror only (no delete)
