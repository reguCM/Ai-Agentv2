# Installing Git Guard hooks

**Canonical AI-Agent deploy:** see **[DEPLOYED.md](./DEPLOYED.md)** (hooks already installed on `D:\AI-Agent\.git\hooks` with hardcoded paths).

For other repos: prefer throwaway / sandbox first. The installer refuses non-sandbox targets unless `-IUnderstand`.

## Manual copy

1. Choose a config (start with `examples/check-only.example.json`, copy and edit).
2. Copy sample hooks:

```text
copy hooks\pre-commit.sample  <repo>\.git\hooks\pre-commit
copy hooks\pre-push.sample    <repo>\.git\hooks\pre-push
```

On Unix:

```bash
cp hooks/pre-commit.sample "$REPO/.git/hooks/pre-commit"
cp hooks/pre-push.sample   "$REPO/.git/hooks/pre-push"
chmod +x "$REPO/.git/hooks/pre-commit" "$REPO/.git/hooks/pre-push"
```

3. Set environment (user or system, or a wrapper script):

```text
GIT_GUARD_ROOT=<repo>/tools/git_guard
GIT_GUARD_CONFIG=<repo>/tools/git_guard/examples/check-only.example.json
```

4. Commit/push in that repo - guard exit `2` / `3` blocks the hook.

## Optional install script

`install-hooks.ps1` writes samples into a path given by `GIT_GUARD_HOOK_TARGET`.

Safety:

- Refuses unless the target is under `D:\AI-Agent-worktrees\sandboxes\` **or** you pass `-IUnderstand`.
- Never defaults to `D:\AI-Agent` / stabilize worktrees.

```powershell
$env:GIT_GUARD_HOOK_TARGET = "D:\AI-Agent-worktrees\sandboxes\some-sandbox-repo\.git\hooks"
.\install-hooks.ps1
```

## Exit codes in hooks

| Code | Meaning | Hook effect |
|------|---------|-------------|
| 0 | PASS | allow |
| 2 | FAIL | block |
| 3 | NEED_HUMAN | block (dangerous op) |
| 1 | usage/error | block |

Push/merge to protected branches should remain `human_gate_actions` -> exit 3. Guard is not a substitute for human review.
