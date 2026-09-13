# Git Guard - Policy (standing)

Git Guard は **Git Governance の Validator / Enforcement Adapter** の一部である。
意味正本は `docs/GIT_OPERATION_POLICY.md`、承認区分の機械契約は `ai_tool/policy/git_governance.json`
（本ファイルは運用方針 Adapter。config JSON が hook 実行時の機械入力）。

## Migrate repeated Git safety off Strong LLM

When the **same** Git check / safety judgment repeats in this project, do **not** keep routing it to Strong LLM. Migrate stepwise to **Git Guard / Script / Hook / Validator**.

### Ladder

1. **First time** - observe manually (Human or Strong LLM may help once).
2. **Same check appears 2-3 times** - mark as a commonize candidate.
3. **Criteria stable** - implement in Git Guard (read-only git checks + exit codes).
4. **Goal-specific conditions** - put in **config**, never hardcode Goal names / unit IDs (e.g. not U3/U4).
5. **Auto-checkable before commit/push** - wire a **Hook** (`pre-commit` / `pre-push` samples).
6. **Reusable across Local runs** - call from **Local / fixed pipeline** (`python guard.py --config ...`).

### Remain on Human / Strong Gate only

Keep these out of blind automation (Guard may still emit `NEED_HUMAN` = exit 3):

- Conflict resolution
- Adoption judgment (what to take / skip semantically)
- History-destruction risk (force push, reset --hard, rewrite)
- Semantic judgment (intent of a change, whether a merge is “correct”)

Dangerous ops in config should use `human_gate_actions` / `forbid_actions` so Local never auto-approves them.

### Safe Push (v2.1, pre-push)

Normal **fast-forward** push to policy-allowed remotes/branches is **PASS** when the hook supplies `--push-ref` (stdin SHAs) and ancestry checks succeed. Non-FF overwrite, ref delete, and `forbid_actions` remain **BLOCK**. Missing hook context or undefined policy → **NEED_HUMAN** (not “push is always human”). Do not use `--no-verify` for routine safe pushes.

### Safe local destructive ops (v2.2)

`restore` / `reset` / `clean` / `worktree remove` have **no Git pre-exec hooks**. Use explicit guard:

`python guard.py --config configs/ai-agent.local-ops.json --action local_git --local-op 'restore|path|...'`

See `LOCAL_OPS_ENFORCEMENT.md` for machine vs policy-only coverage. Filesystem `rm -rf` / `Remove-Item -Recurse -Force` is **not** git_guard-enforced.

### IMPACT_SYNC when a new Git check appears

Whenever a **new Git check item** or **incident pattern** appears:

1. Evaluate: can criteria be stated without LLM judgment?
2. If yes -> add to Guard checks and/or example config fields.
3. Sync in the same change set (same spirit as IMPACT_SYNC for 正本 / Rule / Help / Registry / Test):
   - `guard.py` (logic)
   - `config.schema.json` + examples
   - Hook samples / `install-hooks.md` if commit/push-time
   - Docs (`README.md`, this `POLICY.md`, `DEFERRED.md` if deferred)
   - Smoke / reports under `reports/`

If **not** auto-checkable yet -> note in `DEFERRED.md`; keep Human/Strong Gate.

### Deployed on AI-Agent (2026-09-08)

Practical hooks are installed on `D:\AI-Agent\.git\hooks` using `configs/ai-agent.pre-commit.json` and `configs/ai-agent.pre-push.json`. Details, Local invoke, human push bypass, and uninstall: **[DEPLOYED.md](./DEPLOYED.md)**. Scope reminder below still applies for stabilize/adopt worktrees — hooks use `repo: "."` and do not rewrite refs.

### Scope reminder

This Guard lives in-repo at `tools/git_guard/`. It must **not** disturb ongoing selective-adoption worktrees/refs.
