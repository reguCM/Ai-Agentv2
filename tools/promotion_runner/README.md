# Promotion Runner (sandbox artifact → promote to `tools/promotion_runner/`)

Config-driven **Local / fixed** automation to promote a delta onto a new `promote/*` branch.
**No Strong LLM** in the loop. Goal-specific values live in **config JSON**, never hardcoded in `promote.py`.

## Invoke

```text
python promote.py --config path.json           # dry-run (PLAN only)
python promote.py --config path.json --apply
python promote.py --config path.json --apply --run-tests
python promote.py --config path.json --json
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | PASS / dry-run-ok |
| 1 | ERROR (usage/config/runtime) |
| 2 | FAIL (path policy / tests) |
| 3 | NEED_HUMAN (conflict, merge/push/reset, stop-before-commit) |

## Modes

- `diff_apply` — `git diff source_from..source_to` then `git apply` onto target worktree
- `path_checkout` — `git checkout source_to -- <paths>` onto target

Apply always targets a **new/updated local** `promote/<name>` from `target_base`. Never merges into stabilize/main. Never pushes.

## Ladder

See [POLICY.md](./POLICY.md).
