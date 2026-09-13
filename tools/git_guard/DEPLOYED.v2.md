# Git Guard — DEPLOYED (AI-Agent System V2)

**Status:** `DEPLOYED` on this V2 host  
**Host worktree:** `D:\Ai-Agent_v2`  
**HEAD at install:** `5993b8a4d7b70dd413641a6556565fad217d76e2` (`main`, before this recording commit)  
**Installed:** 2026-09-13 (Asia/Tokyo)  
**Canonical package:** in-repo `tools/git_guard/`  
**Legacy Production record:** `tools/git_guard/DEPLOYED.md` (`D:\AI-Agent` — LEGACY_EVIDENCE_ONLY)

This file records **this repository's** live hooks. It does not rewrite the 2026-09-08 Production install.

## What was installed

| Hook | Path | Config |
|------|------|--------|
| pre-commit | `D:\Ai-Agent_v2\.git\hooks\pre-commit` | `$TOP/tools/git_guard/configs/ai-agent.pre-commit.json` |
| pre-push | `D:\Ai-Agent_v2\.git\hooks\pre-push` | `$TOP/tools/git_guard/configs/ai-agent.pre-push.json` + `--action push` |

Source copies in-repo:

- `tools/git_guard/hooks/pre-commit`
- `tools/git_guard/hooks/pre-push`

Hooks resolve `$TOP=$(git rev-parse --show-toplevel)` and require in-repo `tools/git_guard/guard.py`. No `GIT_GUARD_CONFIG` env required. No sandbox fallback. `repo: "."` is show-toplevel.

Probe helper: `git rev-parse --git-common-dir` → `D:\Ai-Agent_v2\.git` → `hooks\`.  
`legacy_absolute_hook_host_used`: **false** (`D:\AI-Agent\.git\hooks` is not probed).

## Configs

| File | Use |
|------|-----|
| `configs/ai-agent.pre-commit.json` | deny globs; origin URL must contain `github.com/reguCM/Ai-Agentv2`; forbid force_push/reset_hard |
| `configs/ai-agent.pre-push.json` | same remote check + **push_safety v2.1** |
| `configs/ai-agent.local-ops.json` | local_safety v2.2 (not a hook) |

origin (local): `https://github.com/reguCM/Ai-Agentv2.git`

## How to invoke without git

```text
cd D:\Ai-Agent_v2
python tools/git_guard/guard.py --config tools/git_guard/configs/ai-agent.pre-commit.json --json
python tools/git_guard/guard.py --config tools/git_guard/configs/ai-agent.pre-push.json --action push --target-remote origin --json
```

Exit: `0` PASS, `1` ERROR, `2` FAIL, `3` NEED_HUMAN.

## Smoke results (2026-09-13 JST, this host)

`inspect_live_hook_deployment`: **observed=true**, **ok=true**, both hooks `thin_adapter` / `references_in_repo_guard` / `config_pattern_ok`.

| Check | Exit | Detail |
|-------|------|--------|
| `hook_deployment_status` paths | n/a | `D:\Ai-Agent_v2\.git\hooks\pre-commit` and `pre-push` exist |
| `guard.py` pre-commit `--json` | **0 PASS** | branch `main`; deny none; origin Ai-Agentv2.git |
| `guard.py` pre-push `--action push` (no `--push-ref`) | **3 NEED_HUMAN** | v2.1 requires hook stdin ref context |
| `guard.py` pre-push simulated first push (`remote_sha=zero`) | **0 PASS** | `PUSH_NEW_BRANCH: remote branch does not exist yet (create)` |

No `git push` was performed.

## Out of scope

- GitHub `git push` / `--force`
- Installing hooks via `install-hooks.ps1` (that script still refuses this `.git\hooks` unless `-IUnderstand`; live copy used in-repo canonical hook files)
- Replacing Production `D:\AI-Agent` hooks
