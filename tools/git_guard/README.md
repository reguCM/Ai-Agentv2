# Git Guard (sandbox artifact)

Minimal, **config-driven** Git safety checks for **Local / fixed automation** - **no Strong LLM**.

See **[POLICY.md](./POLICY.md)** for the standing ladder: repeated Git checks migrate here (Guard -> Hook -> Local), not back to Strong LLM. Human/Strong Gate remains for conflict, adoption, history-destruction, and semantic judgment.

## IMPACT note

This package started as a **sandbox artifact** under `goals/_git-guard/`.
Canonical copy is **in-repo** `tools/git_guard/`. Git hooks on `D:\AI-Agent`
(`pre-commit` / `pre-push` → `configs/ai-agent.*.json`) call this tree. See **[DEPLOYED.md](./DEPLOYED.md)** for install paths, Local invoke, human push approval (`--no-verify` only after explicit human OK), and uninstall.

## Invoke from Local

```text
python tools/git_guard/guard.py --config tools/git_guard/examples/check-only.example.json
python tools/git_guard/guard.py --config <path.json> --json
python tools/git_guard/guard.py --config <path.json> --run-tests
python tools/git_guard/guard.py --config <path.json> --action push --target-remote github --target-branch stabilize/foo
```

Working directory can be anywhere; `repo` in config points at the worktree.

## Exit codes

| Code | Name | Meaning |
|------|------|---------|
| 0 | PASS | All configured checks ok |
| 1 | ERROR | Usage / bad config / not a git repo |
| 2 | FAIL | Policy block (wrong branch, dirty, deny path, forbid action, test fail, ...) |
| 3 | NEED_HUMAN | Dangerous / gated action - Local must stop and ask a human |

**Dangerous ops still NEED_HUMAN.** Guard encodes repeated mechanical checks; it does **not** replace human confirmation on push/merge to protected branches, force push, or reset --hard. See `DEFERRED.md` and `POLICY.md`.

## Layout

```text
_git-guard/
  guard.py
  config.schema.json
  POLICY.md
  DEFERRED.md
  README.md
  install-hooks.md
  install-hooks.ps1
  examples/
    check-only.example.json
    selective-adopt.example.json
  hooks/
    pre-commit.sample
    pre-push.sample
  reports/
    smoke.md
```

## Config (small set)

| Field | Role |
|-------|------|
| `repo` | Worktree path (absolute, or `"."` / empty → cwd toplevel; env `GIT_GUARD_REPO` overrides) |
| `require_branch` / `allow_branches` / `deny_branches` | Branch gates (globs ok) |
| `require_clean` + `ignore_untracked` | Porcelain dirty check |
| `forbid_staged` | No staged files |
| `base_ref` / `diff_refs` | Path set for allow/deny |
| `allow_path_globs` / `deny_path_globs` | Path policy |
| `forbid_overlap_refs` | No overlap with other refs' trees |
| `remotes` | URL contains / `forbid_push` |
| `forbid_actions` / `human_gate_actions` / `action` | Proposed-op gate |
| `required_tests` | Optional cmds with `--run-tests` |

Goal-specific names (units, adopt tickets) belong in **config copies**, never hardcoded in `guard.py`.

## Hooks

See [install-hooks.md](./install-hooks.md) and **[DEPLOYED.md](./DEPLOYED.md)**.
Samples call `guard.py`. **Deployed:** hooks are installed on `D:\AI-Agent\.git\hooks` (canonical AI-Agent) with in-repo `tools/git_guard` and `configs/ai-agent.*.json`. Installer refuses targets outside `D:\AI-Agent-worktrees\sandboxes\` unless `-IUnderstand`.

## Smoke

Smoke examples under `examples/` use `repo: "."` (current worktree). They do not require an external baseline clone.
