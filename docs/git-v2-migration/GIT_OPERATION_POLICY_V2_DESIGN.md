# Git Operation Policy v2 — Design Draft

| Field | Value |
|-------|--------|
| **STATUS** | **`FROZEN_PROMOTION_CANDIDATE`** |
| **PROJECT_CANONICAL** | **`False`** — does **not** replace Production policy until Promotion Gate (§47) |
| **RECOVERY_OPERATIONAL_REFERENCE** | **`True`** — may be cited during Recovery / A_ROUTE work |
| **PROMOTION_TARGET (human)** | `docs/GIT_OPERATION_POLICY.md` |
| **PROMOTION_TARGET (machine)** | `ai_tool/policy/git_governance.json` |
| Document role | Design only (no Production implementation) |
| Instruction ID | `GIT_POLICY_V2_DESIGN_001` |
| Baseline Production HEAD | `7e23ad6` (`dev/current`) |
| Baseline contract version | `2026-09-12.3` |
| Protected Recovery Source | `D:\AI-Agent-recovery\dev-current_20260913_113041` |
| Authoring date | 2026-09-13 |
| Last design update | `GIT_POLICY_V2_FREEZE_AND_PROMOTION_PREP_001` (2026-09-13); prior: `GIT_POLICY_V2_UPDATE_SESSION_STATE_RESTORATION_001` |
| Supersedes (semantic) | `docs/GIT_OPERATION_POLICY.md` v1 — **not yet adopted** |
| Promotion packet | `GIT_POLICY_V2_PROMOTION_PACKET.md` (same directory) |

## Classification legend

Each substantive item is tagged with one of:

- **CONFIRMED_CURRENT_STATE** — Verified on Production at baseline audit (READ-ONLY).
- **INCIDENT_EVIDENCE** — Observed during Git / Working Tree / Commit Integrity investigation (this program of work).
- **V2_REQUIREMENT** — Normative intent for v2 (design target).
- **DESIGN_CANDIDATE** — Proposed mechanism; not implementation-committed.
- **OPEN_DECISION** — Requires human choice before spec freeze or implementation.

**Do not treat DESIGN_CANDIDATE or V2_REQUIREMENT as current Production behavior.**

---

## 0. Current verified baseline

**CONFIRMED_CURRENT_STATE**

| Asset | Location / value |
|-------|------------------|
| Semantic policy v1 | `docs/GIT_OPERATION_POLICY.md` |
| Machine contract | `ai_tool/policy/git_governance.json` (`contract_version`: `2026-09-12.3`) |
| Manifest ref | `ai_tool/policy/development_policy.json` → `distribution.git_governance_ref` |
| git_guard | `tools/git_guard/` |
| Live hooks | `git rev-parse --git-common-dir` → `D:/AI-Agent/.git/hooks` (not worktree-local `.git/hooks`) |
| Adapters | `.cursor/rules/git-governance-adapter.mdc`, `docs/adapters/GIT_GOVERNANCE_CURSOR_HOST.md`, `AGENTS.md` |
| Validators / tests | `ai_tool/policy/git_governance_*.py`, `tests/ai_tool/policy/test_git_governance*.py`, `tests/tools/test_git_guard_*.py`, `tests/tools/test_agent_git_local_operation_bridge.py` |

**CONFIRMED_CURRENT_STATE — commit action**

- `approval_class`: `TASK_AUTHORIZATION_REQUIRED`
- `authorization.runtime_binding`: `NOT_CONNECTED`
- `auto_commit_token`: `AUTO_COMMIT_ALLOWED`
- `required_conditions`: all five with `enforcement_status`: `NOT_CONNECTED`
- `validator_bindings`: `[]`

**CONFIRMED_CURRENT_STATE — pre-commit (live hook path)**

- Invokes `guard.py` with `ai-agent.pre-commit.json` **without** `--action`
- Enforces: valid repo, `origin` URL policy, `deny_path_globs` on collected paths (staged + unstaged + untracked)
- Does **not** enforce: dependency closure, required tests, candidate isolation, staged-only tree tests, commit authorization

**CONFIRMED_CURRENT_STATE — CONFIG_PRESENT ≠ ENFORCEMENT_ACTIVE**

- `forbid_actions` in pre-commit JSON does not run on hook path because `check_action` requires `action` / CLI `--action` (verified Critical Claims Verification).

**V2_REQUIREMENT**

- Preserve: `push_safety` v2.1, `local_safety` v2.2, destructive-op Agent gate, contract distribution, drift tests.

**OPEN_DECISION**

- Whether v2 semantic doc replaces v1 in-repo path or ships as `GIT_OPERATION_POLICY_V2.md` until cutover.

---

## 1. Four safety layers (v2 structure)

**V2_REQUIREMENT**

| Layer | Scope |
|-------|--------|
| **A. Git Operation Safety** | Destructive / history-changing Git commands and worktree operations |
| **B. Commit Integrity Safety** | Committed tree is semantically self-contained and matches validated candidate |
| **C. Evidence / Diagnostic Safety** | Claims (“tests passed”, “same diff”, “this module loaded”) are traceable and fresh |
| **D. Instruction Execution Safety** | Humans and agents complete mandatory safety procedures without partial copy / gate skip |

**V2_REQUIREMENT — layer C/D integration (diagnostic artifact safety)**

- Primary home for Production worktree filesystem side effects during audit/diagnostic runs: **Layer C**.
- Pre/post execution gates, completion markers, approval continuity, and session state restoration: **Layer D** (see §16, §18, §21, §35, §46).
- Does **not** replace Layer A Git Operation Safety; extends “read-only” operations that still touch the filesystem (§16) or shell session state (§46).

**DESIGN_CANDIDATE**

- Map each machine contract `action_id` and each gate to primary layer(s) in `git_governance.json` v2 extension.

---

## 2. Top-level principles (Rules 2.1–2.8)

| Rule | Tag | Statement |
|------|-----|-----------|
| 2.1 | V2_REQUIREMENT | Safe Git operation ≠ safe commit |
| 2.2 | V2_REQUIREMENT | Working Tree PASS ≠ Commit Candidate PASS |
| 2.3 | V2_REQUIREMENT | Commit candidate must be reconstructible from committed HEAD + intended commit delta only |
| 2.4 | V2_REQUIREMENT | Tests must not PASS only because unrelated dirty WT changes exist |
| 2.5 | V2_REQUIREMENT | Final index at commit must match validated candidate |
| 2.6 | V2_REQUIREMENT | Agents must not skip, reorder, or infer-pass policy gates |
| 2.7 | V2_REQUIREMENT | Do not cleanup a healthy WT before recovery completes |
| 2.8 | V2_REQUIREMENT | Full root-cause is not mandatory before recovery baseline |

**INCIDENT_EVIDENCE** (supports 2.2–2.5, 2.7–2.8)

- Grill / completion tests PASS in worktree, FAIL on ISO at same nominal HEAD overlay (runtime outcome divergence).
- Completion guard in dirty `agent_turn`; HEAD lacked implementation tests expected (CASE 1).
- Recovery snapshot `dev-current_20260913_113041` taken before destructive cleanup.

---

## 3. Commit Integrity Gate — state machine

**V2_REQUIREMENT**

Mandatory gates are non-optional; no commit without traversing authorized terminal state `COMMIT_ALLOWED`.

**DESIGN_CANDIDATE — standard transitions**

```
WORKTREE_IN_PROGRESS
  → PRECHECK
  → CHANGE_BOUNDARY_IDENTIFIED
  → DEPENDENCY_CLOSURE_CONFIRMED
  → COMMIT_CANDIDATE_BUILT
  → CANDIDATE_PROVENANCE_VERIFIED
  → ISOLATED_CANDIDATE_TESTED
  → SELECTIVE_STAGE
  → STAGED_DIFF_AUDITED
  → CANDIDATE_INDEX_IDENTITY_VERIFIED
  → STAGED_TREE_REPRODUCED
  → STAGED_TREE_TESTED
  → HUMAN / TASK AUTHORIZATION
  → COMMIT_ALLOWED
  → POST_COMMIT_VERIFY
  → PUSH_ALLOWED
```

**OPEN_DECISION**

- Which transitions are **machine-enforced** vs **human attestation** vs **agent rule-only** (see §38).
- Whether `PUSH_ALLOWED` reuses existing `push_safety` v2.1 only or adds commit-evidence binding.

---

## 4. PRECHECK

**V2_REQUIREMENT**

Before Git-changing operations, record at minimum:

- Repository identity and absolute path
- Branch, HEAD SHA, `git-common-dir`
- Staged count, dirty tracked files, untracked files
- Operation purpose
- Recovery Source presence when applicable

**DESIGN_CANDIDATE**

- Detect in-progress Git operations: `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, rebase/bisect state → **STOP** normal commit-integrity flow.

**CONFIRMED_CURRENT_STATE**

- GIT v1 §3 already lists branch, HEAD, staged/unstaged/untracked (process-only).

---

## 5. Change boundary

**V2_REQUIREMENT**

- Scope is not file-list-only; units include feature, responsibility, runtime behavior, schema, test contract, persistence, import graph, registry, config, runtime bridge.

**DESIGN_CANDIDATE**

- `MIXED_CONCERN_FILE` classification when one file spans multiple boundaries.
- Whole-file stage allowed only after boundary review.

**INCIDENT_EVIDENCE**

- Canonical transport + completion + semantic + handoff wedges mixed across overlapping production files.

---

## 6. Dependency closure

**V2_REQUIREMENT**

For each commit candidate, confirm closure over: production imports, tracked/untracked deps, helpers, schema, registry, config, test helpers, fixtures, bridges, persistence formats, entry points, required generated sources.

**V2_REQUIREMENT — prohibition**

- Must not commit tracked production code that imports **untracked** runtime modules (left behind).

**INCIDENT_EVIDENCE**

- Tracked `agent_turn` importing multiple **untracked** semantic / gate modules (CASE 2).

**DESIGN_CANDIDATE**

- Static import closure tool (Python `importlib` / AST) + manifest of required paths for candidate.

**OPEN_DECISION**

- Closure depth: import-only vs runtime import graph vs test-import graph.

---

## 7. Untracked production dependency gate

**V2_REQUIREMENT**

- Untracked `.py` (and similar) that are runtime-import targets → `UNTRACKED_PRODUCTION_DEPENDENCY`.
- If not in commit scope → `BLOCKED_UNTRACKED_DEPENDENCY`.

**DESIGN_CANDIDATE**

- Classifier: `git ls-files` + import analysis + optional `UNTRACKED_PRODUCTION_DEPENDENCY` allowlist for generated/ephemeral (explicit).

---

## 8. Commit candidate

**V2_REQUIREMENT**

- Candidate = HEAD + intended commit delta only.
- Exclude: unrelated dirty changes, `runs/_diag_tmp`, caches, pytest artifacts, temp ISO, diagnostic copies, unrelated experiments.

**DESIGN_CANDIDATE**

- Provenance record per build: base HEAD, overlay sources, paths, SHA-256, candidate destination hash.

**INCIDENT_EVIDENCE**

- Overlay ISO trees used for experiments; risk of stale contamination (CASE 4, Fresh Isolation).

---

## 9. Candidate provenance

**INCIDENT_EVIDENCE**

- “Directory exists” insufficient for evidence (ISO without manifest).

**V2_REQUIREMENT**

Minimum provenance fields:

- `BASE_HEAD`, `CREATION_TIME`, `SOURCE_FILES`, `SOURCE_HASHES`, `OVERLAY_FILES`, `OVERLAY_HASHES`, `EXCLUDED_FILES`

**DESIGN_CANDIDATE**

- JSON schema `commit_candidate_provenance.v1.json` under `reports/` or tool output (not Production path until Phase C).

**V2_REQUIREMENT**

- Unknown provenance → not valid verification evidence.

---

## 10. Fresh isolation rule

**INCIDENT_EVIDENCE**

- Fresh directory + no destructive cleanup adopted in investigation.

**V2_REQUIREMENT**

- Prefer new directory per validation; do not overwrite ISO; do not cleanup-reuse old ISO.

---

## 11. Isolation environment check

**DESIGN_CANDIDATE**

- Light check before candidate tests: `cwd`, `sys.path`, `PYTHONPATH`, python executable/version, project module `__file__`, in-repo vs out-of-repo.

**V2_REQUIREMENT**

- Escalate to heavy diagnostics only on anomaly.

**INCIDENT_EVIDENCE**

- Same module SHA, different stop_reason (CASE 5) — environment/path factors not fully determined.

---

## 12. Runtime import provenance

**INCIDENT_EVIDENCE**

- `runs/_diag_tmp/runtime_import_provenance_*` used under escalation.

**DESIGN_CANDIDATE**

- **DIAGNOSTIC_ESCALATION** (Level 4), not default commit gate.

Triggers: WT PASS / candidate FAIL; same test different outcome; closure unknown; shadowing suspicion.

Output: module name, `__file__`, in-root flag, content SHA-256.

---

## 13. Semantic equality vs byte equality

**INCIDENT_EVIDENCE**

- SHA-256 differed; normalized source same (CRLF/LF, blank line) (CASE 3).

**V2_REQUIREMENT**

- `BYTE_DIFFERENT` ≠ `SEMANTIC_DIFFERENT` in policy text.

**DESIGN_CANDIDATE**

- Comparison order: (1) byte hash, (2) normalized diff, (3) semantic judgment — do not treat EOL-only as dependency break.

---

## 14. Path assumption safety

**INCIDENT_EVIDENCE**

- Wrong fixed paths for `goal_handoff_runtime_bridge.py`, `requirement_resolution.py` (CASE 7).

**V2_REQUIREMENT**

- DISCOVER → VERIFY → USE; no substitute file on missing path.

---

## 15. Symbol location safety

**INCIDENT_EVIDENCE**

- `_run_human_grill_resume` searched in wrong file (CASE 8).

**V2_REQUIREMENT**

- Repo-wide or scoped symbol discovery before fixing target file.

---

## 16. Read-only command safety

**V2_REQUIREMENT**

- “READ-ONLY” label insufficient; audit side effects.
- **Git Read-Only** and **Filesystem Read-Only** are **distinct** concepts (see below).
- Cross-reference: §35 (artifact destination), §18 (pre-execution gate, postcheck), §21 (completion evidence dimensions), §46 (session state restoration).

### Git Read-Only と Filesystem Read-Only は別概念

**V2_REQUIREMENT**（日本語を正本）

Git コマンドが READ-ONLY であっても、監査ツール・shell・Python・PowerShell・test runner 等はファイルを生成し得る。したがって `GIT_MUTATION=False` だけでは `FILES_MODIFIED=False` を意味しない。

少なくとも次を**独立**して扱う（相互に代替しない）:

| Dimension | Meaning |
|-----------|---------|
| Git Mutation | Index / HEAD / refs / hooks / config 等の Git 状態変更 |
| Production Filesystem Mutation | 監査対象 Production Worktree 内の作成・変更・削除 |
| Candidate Filesystem Mutation | 検証用 Candidate ツリー内の作成・変更・削除 |
| Session State Mutation | 同一 shell / プロセス内の環境変数・CWD 等（復元要件 §46） |
| Environment Mutation | （legacy label in checklists; prefer **Session State Mutation** for env + CWD scope) |
| External Diagnostic Artifact Creation | Production **外**への永続証跡の作成（許可条件は §35） |

**Example (INCIDENT_EVIDENCE pattern)**

- `git status` のみ使用でも、結果を Production 内の `output.txt` に保存した場合: `GIT_MUTATION=False`, `FILES_MODIFIED=True`.

**DESIGN_CANDIDATE — read-only execution checklist**

- `PYTHONDONTWRITEBYTECODE`, pytest cache, **all persistent output outside Production worktree**, scripts non-mutating **on Production path**, temp dirs outside Production, tool side effects.
- Validators must treat “ignored path” as **not** a safety excuse for writes inside Production (§35).

**INCIDENT_EVIDENCE — A_ROUTE baseline audit context**

- A_ROUTE Git baseline work is **not** abandoned because of diagnostic artifact pollution; artifact rules are **safety improvements** for A_ROUTE (and all routes). Alternative-route / C-route procedures are out of scope for this update.

---

## 17. PowerShell safety

**INCIDENT_EVIDENCE**

- Investigation scripts; scope and exit-code pitfalls.

**V2_REQUIREMENT**

- Explicit `$script:fail` / exit codes; do not assume function-local `$fail` mutates parent scope.

**DESIGN_CANDIDATE**

- Document exit semantics: `git diff --no-index` (0=same, 1=diff, >1=error); `robocopy` 0–7 success, ≥8 error.

**V2_REQUIREMENT**

- Scripts that change session-affecting state must follow §46 (save → try → **finally** restore); PowerShell is the primary reference shell in baseline audits.

---

## 18. Instruction completeness gate

**INCIDENT_EVIDENCE**

- Partial copy of long safety instruction (CASE 6).

**V2_REQUIREMENT**

- Long instructions carry: `INSTRUCTION_ID`, `EXPECTED_STEP_COUNT`, BEGIN/END markers, mandatory PRE/POST check.

**DESIGN_CANDIDATE**

- Result payload: `INSTRUCTION_ID`, `EXECUTED_STEP_COUNT`, `COMPLETION_MARKER`; missing END → `INSTRUCTION_INCOMPLETE` (not formal evidence).

### Command completeness and session state scripts

**V2_REQUIREMENT**

When an instruction changes session state (§46), completeness review must confirm the copyable script block includes, without truncation:

- `try` (or equivalent scoped change)
- `catch` / exception path where applicable
- `finally` / restore path
- closing block and `COMMAND_COMPLETE_MARKER` (or equivalent END marker)

**INCIDENT_EVIDENCE**

- Truncated instructions (e.g. `finally` block cut mid-command) must **not** be executed as READ-ONLY—even if Git commands alone are safe (aligns with CASE 6).

### Pre-Execution Artifact Destination Gate

**DESIGN_CANDIDATE** — gate name: `DIAGNOSTIC_ARTIFACT_DESTINATION_GATE`

Before running audit / diagnostic / compare / investigate instructions, confirm **where** persistent artifacts will be written.

| Verdict | Condition | Action |
|---------|-----------|--------|
| `NO_PERSISTENT_ARTIFACT` | stdout/stderr only (no durable files) | Allow if other gates pass |
| `OUTSIDE_PRODUCTION` | All durable artifacts under paths **outside** the Production worktree root | Allow if policy conditions met |
| `INSIDE_PRODUCTION` | Any durable artifact path resolves inside Production worktree | **BLOCK** (or redesign to stdout / external) |
| `UNKNOWN_DESTINATION` | Destination not declared or not computable | **BLOCK** |

**DESIGN_CANDIDATE — path resolution**

- Decide “inside Production” by **normalized path containment**, not substring heuristics alone.
- Future validator: resolve symlinks / junctions before containment check.

### Postcheck after audit / diagnostic execution

**V2_REQUIREMENT**

- Confirm Production `git status` (or agreed porcelain baseline) matches pre-execution snapshot when such a check is part of the instruction.

When Production status **changes** after execution:

1. Do **not** auto-repair.
2. Do **not** auto-delete diff-causing paths.
3. Identify diff cause (including self-generated audit artifacts).
4. Even if the agent created the files, do **not** delete them without Human Review or **pre-approved** Cleanup Policy.
5. Forbidden reasoning: “I created it, so I may remove it.”

**INCIDENT_EVIDENCE — `A_ROUTE_GIT_BASELINE_AUDIT_003`**

- Git operations during the audit were READ-ONLY (no tracked change, no stage change, HEAD unchanged).
- The audit run still created **untracked** files inside Production worktree:
  - `runs/_diag_tmp/A_ROUTE_GIT_BASELINE_AUDIT_003.ps1`
  - `runs/_diag_tmp/A_ROUTE_GIT_BASELINE_AUDIT_003_output.txt`
- Production porcelain entry count: **109 → 111**; POSTCHECK detected status change.
- Root cause: **audit process filesystem write**, not Git mutation.
- Confirmed: `GIT_MUTATION=False` but **`FILES_MODIFIED=False` was not claimable** for that run.

### Approval continuity (re-authorization)

**V2_REQUIREMENT**

- Automated “second run allowed” evaluation must **not** look at Git commands alone for READ-ONLY proof.

Minimum review dimensions:

- command completeness
- Git mutation
- filesystem output destination
- session state restoration design (when session state changes; §46)
- evidence / audit logic validity
- approval scope continuity

**DESIGN_CANDIDATE — auto-continue predicate (schema names TBD)**

```
COMMAND_COMPLETE
AND APPROVAL_SCOPE_CONTINUOUS
AND NO_UNAPPROVED_GIT_MUTATION
AND NO_PRODUCTION_ARTIFACT_WRITE
AND SESSION_STATE_RESTORATION_VALID
AND EVIDENCE_METHOD_VALID
```

- When no session-affecting change is performed: `SESSION_STATE_RESTORATION_VALID` may be `NOT_REQUIRED` (design enum).
- `NO_UNAPPROVED_GIT_MUTATION` subsumes READ-ONLY Git intent for audit paths; does not imply filesystem or session safety.

Formal field names must align with `git_governance.json` v2 extension before implementation.

---

## 19. Safety header self-containment

**V2_REQUIREMENT**

- Prohibitions and expected HEAD/branch/repo inside copyable command block.

---

## 20. Safety gate sequence immutable

**V2_REQUIREMENT**

- No omit, shorten, reorder, stale-evidence substitute, or inferred PASS on mandatory gates.

---

## 21. Evidence freshness

**V2_REQUIREMENT**

- Evidence binds HEAD SHA, timestamp, candidate identity, index identity; state change → prior evidence **STALE**.

### Completion evidence claims (independent)

**V2_REQUIREMENT**

These completion flags are **not interchangeable**:

| Claim | When true |
|-------|-----------|
| `GIT_MUTATION=False` | No Git state change per instruction scope |
| `FILES_MODIFIED=False` | No create/change/delete **inside target Production worktree** after audit start |
| `PRODUCTION_STATUS_UNCHANGED=True` | Porcelain (or agreed baseline) matches pre-run snapshot |
| `CANDIDATE_UNCHANGED=True` | Candidate tree identity unchanged per instruction scope |
| `ENVIRONMENT_RESTORED=True` | Environment variables touched by the instruction restored (see §46; schema may fold into `SESSION_STATE_RESTORED`) |
| `SESSION_STATE_CHANGED=` | Design field: whether any session-affecting state was modified (env, CWD, etc.) |
| `SESSION_STATE_RESTORED=True` | All captured session state restored after run (success or failure) |
| `CWD_RESTORED=True` | Current working directory returned to pre-instruction location when CWD was changed |

- `FILES_MODIFIED=False` requires explicit verification that no new/changed/deleted files exist in the Production worktree under test—not inference from `GIT_MUTATION=False`.
- `SESSION_STATE_RESTORED=True` does **not** imply `FILES_MODIFIED=False` or `PRODUCTION_STATUS_UNCHANGED=True` (§35, §46).
- `GIT_MUTATION=False`, `FILES_MODIFIED=False`, `PRODUCTION_STATUS_UNCHANGED=True`, `SESSION_STATE_RESTORED=True`, and `ENVIRONMENT_RESTORED=True` are **independent**; none substitutes for another.

**INCIDENT_EVIDENCE**

- `A_ROUTE_GIT_BASELINE_AUDIT_003`: `GIT_MUTATION=False`; `FILES_MODIFIED=False` and `PRODUCTION_STATUS_UNCHANGED=True` were **not** valid completion claims because of internal diagnostic artifacts (§18).

---

## 22. HEAD baseline comparison

**INCIDENT_EVIDENCE**

- Completion V2: 6 failures; HEAD comparison → 5 pre-existing, 1 new regression.

**DESIGN_CANDIDATE**

- Diagnostic Level 3 when candidate fails: run same test on HEAD-only baseline → `NEW_REGRESSION` vs `PREEXISTING_FAILURE`.

---

## 23. Test / implementation consistency

**INCIDENT_EVIDENCE — Regression CASE 1**

- Wedge A test required G1 false-success guard; implementation in dirty WT, not on committed HEAD `agent_turn`.

**V2_REQUIREMENT**

- Test demanding new behavior requires implementation in same or earlier commit.

---

## 24. Selective stage

**V2_REQUIREMENT**

- No `git add .` / `git add -A` without gate; no stage before candidate PASS (candidate).

**CONFIRMED_CURRENT_STATE**

- GIT v1 §7 discourages broad add; contract `add_all` = `GUIDANCE_ONLY`.

---

## 25. Staged diff audit

**V2_REQUIREMENT**

- Mandatory `git diff --cached` before commit: intended files/hunks only; no diag artifacts; UNKNOWN → STOP.

---

## 26. Staged tree validation

**V2_REQUIREMENT**

- Reconstruct tree from **HEAD + INDEX only**; run import smoke / targeted / required regressions there.

- Working tree PASS alone does not yield `COMMIT_ALLOWED`.

**DESIGN_CANDIDATE**

- Tool: `staged_tree_checkout` or `git archive` + index apply into temp dir (implementation Phase D).

---

## 27. Candidate / index identity

**V2_REQUIREMENT**

- After stage, manifest/normalized diff/hash must match validated candidate; else `BLOCKED_STAGE_MISMATCH`.

---

## 28. Pre-commit hook role

**CONFIRMED_CURRENT_STATE**

- Keep: repo validation, origin validation, sensitive path deny.

**DESIGN_CANDIDATE**

```
Commit Integrity Validator → Evidence / Ready State artifact
  → pre-commit hook verifies index matches artifact (lightweight)
```

**OPEN_DECISION**

- Full heavy validation in hook vs external validator + hook only checks artifact freshness/hash.

---

## 29. Commit authorization

**CONFIRMED_CURRENT_STATE**

- `AUTO_COMMIT_ALLOWED` + `runtime_binding: NOT_CONNECTED`.

**V2_REQUIREMENT**

- **Authorization** and **Integrity** are separate gates.
- Integrity PASS alone does not authorize commit.
- Until runtime binding: retain Human Approval path (Option C preserved).

**DESIGN_CANDIDATE**

- Phase F: Goal/Task/Execution emits `AUTO_COMMIT_ALLOWED` with scope manifest binding to candidate provenance ID.

---

## 30. Destructive operation safety

**CONFIRMED_CURRENT_STATE**

- `push_safety` v2.1, `local_safety` v2.2, `agent_git_execution_gate` on `execute_tool`.

**V2_REQUIREMENT**

- Do not weaken when adding Commit Integrity.

---

## 31. Recovery snapshot rule

**INCIDENT_EVIDENCE**

- Example: `D:\AI-Agent-recovery\dev-current_20260913_113041`.

**V2_REQUIREMENT**

- Trigger recovery snapshot on: large dirty WT, mixed features, untracked production modules, unknown deps, destructive op consideration, git state doubt, baseline reconstruction.

**DESIGN_CANDIDATE**

- Manifest: HEAD, branch, status, diffs, inventories, file copy, SHA-256 manifest, return-point doc.

---

## 32. Recovery baseline rule

**V2_REQUIREMENT**

1. Protect current WT  
2. Build clean candidate elsewhere  
3. Validate candidate  
4. Establish new baseline  
5. Then cleanup old state  

Aligns with Rule 2.7.

---

## 33. Root cause investigation budget

**V2_REQUIREMENT**

- Stop deep investigation when: normal state protected, diff preserved, inventory preserved, clean reconstruction possible → enter `RECOVERY_BASELINE_MODE`.

Aligns with Rule 2.8.

---

## 34. Diagnostic escalation levels

**DESIGN_CANDIDATE**

| Level | Scope |
|-------|--------|
| 0 | Normal checks |
| 1 | Dependency closure |
| 2 | Clean candidate isolation |
| 3 | HEAD baseline comparison |
| 4 | Runtime import provenance |
| 5 | Environment / filesystem trace |

**V2_REQUIREMENT**

- Default commit path stops at Level 0–2; 4–5 only on triggers (§12).

---

## 35. Generated / diagnostic artifact boundary

**V2_REQUIREMENT**

- Exclude from normal commits: `runs/_diag_tmp`, temp ISO, pytest cache, `__pycache__`, transient logs.

- Summaries for evidence → formal `reports/` when needed **outside Production worktree** when the subject under audit **is** that Production worktree (see policy text below).

**CONFIRMED_CURRENT_STATE**

- pre-commit deny list is secrets-focused, not diag-path-focused.

### 診断・監査 Artifact の Production 外保存原則（正本: 日本語）

**V2_REQUIREMENT**

監査・診断・検証・比較・調査などの処理によって生成される一時ファイル・ログ・スクリプト・JSON・レポート・比較結果等を、**監査対象となっている Production Worktree 内へ保存してはならない。**

**Policy principle (Japanese authoritative; English gloss)**

> 診断・監査処理によって生成される Artifact は、監査対象の Production Worktree 内へ保存してはならない。Git 操作が READ-ONLY であっても、Production 内へファイルを生成した場合は Filesystem 上の変更として扱う。診断証跡が必要な場合は Production 外へ保存する。

*English gloss (non-authoritative): Do not persist diagnostic artifacts inside the Production worktree under audit; READ-ONLY Git does not imply an unchanged worktree filesystem.*

**Operational rules**

1. Prefer **stdout-only** completion for audit/diagnostic instructions.
2. When durable evidence is required, write only **outside** the Production worktree root.
3. Paths such as `runs/`, `logs/`, `reports/`, `temp/`, `_diag_tmp/` **inside Production** must not be used as audit sinks merely because they are “for diagnostics.”
4. `.gitignore` coverage does **not** justify Production-internal writes; ignored ≠ safe for audit integrity.
5. Treat all of the following as **Diagnostic / Audit Artifacts** when persisted: temporary PowerShell/Python scripts, stdout/stderr capture files, JSON, manifests, diffs, patches, hash lists, provenance records, diagnostic reports, benchmark results, debug logs, temporary copies, audit output bundles.
6. **DESIGN_CANDIDATE** external sink example (not the only allowed pattern): `D:\AI-Agent-recovery\diagnostics\<instruction-id>\` — implement-time validators must prove path is outside Production, not copy this string as sole spec.

**Cross-reference**

- Read-only Git vs filesystem: §16.
- Pre-execution gate and postcheck: §18.
- Completion claims: §21.
- Regression: CASE 10 (§40).
- Session state restoration: §46; CASE 11 (§40).

**Note on §12 escalation**

- Runtime import provenance and similar **Level 4–5** traces must follow the same Production-external rule when Production itself is the audit subject; historical use of `runs/_diag_tmp/...` under Production is incident context, not permission for future audit writes.

---

## 36. Git common dir awareness

**CONFIRMED_CURRENT_STATE**

- Live hooks at `D:/AI-Agent/.git/hooks`; worktree `.git/hooks` absent.

**V2_REQUIREMENT**

- Hook inspection and deployment docs must use `git rev-parse --git-common-dir`, not assume worktree `.git` layout.

---

## 37. Pre-commit action assumption

**CONFIRMED_CURRENT_STATE**

- `forbid_actions` in pre-commit config not active on default `git commit` hook invocation.

**V2_REQUIREMENT — principle CONFIG_PRESENT ≠ ENFORCEMENT_ACTIVE**

- Audit triad: **config**, **caller**, **runtime binding**.

---

## 38. Machine enforcement classification

**V2_REQUIREMENT**

Every policy item tagged at minimum:

| Class | Meaning |
|-------|---------|
| `MACHINE_ENFORCED` | Hook, guard, or runtime blocks violation |
| `PARTIALLY_ENFORCED` | Some paths only (e.g. Agent bridge, not raw CLI) |
| `AGENT_RULE_ONLY` | Adapter / user rules |
| `HUMAN_PROCESS_ONLY` | Documented procedure |
| `NOT_CONNECTED` | Contract field exists, no binding |
| `NOT_PRESENT` | No contract entry |

**DESIGN_CANDIDATE — v1 → v2 migration table (excerpt)**

| Topic | v1 class (baseline) | v2 target class |
|-------|---------------------|-----------------|
| Secrets in commit | PARTIALLY_ENFORCED (pre-commit deny) | MACHINE_ENFORCED |
| push safe FF | PARTIALLY_ENFORCED (pre-push) | MACHINE_ENFORCED (unchanged) |
| local destructive git | PARTIALLY_ENFORCED (guard + Agent) | PARTIALLY_ENFORCED |
| commit LEVEL 2 conditions | HUMAN_PROCESS_ONLY / NOT_CONNECTED | MACHINE_ENFORCED (candidate subset) |
| dependency closure | NOT_PRESENT | PARTIALLY_ENFORCED → MACHINE_ENFORCED |
| staged tree test | NOT_PRESENT | MACHINE_ENFORCED |
| AUTO_COMMIT_ALLOWED | NOT_CONNECTED | NOT_CONNECTED until Phase F |

---

## 39. Commit readiness states

**DESIGN_CANDIDATE**

Terminal allow: `READY` → leads to `COMMIT_ALLOWED` with authorization.

Block examples (non-exhaustive):  
`BLOCKED_UNKNOWN_BOUNDARY`, `BLOCKED_DIRTY_ONLY_PASS`, `BLOCKED_MISSING_DEPENDENCY`, `BLOCKED_UNTRACKED_DEPENDENCY`, `BLOCKED_MIXED_CONCERN`, `BLOCKED_CANDIDATE_PROVENANCE`, `BLOCKED_ISOLATION_FAILURE`, `BLOCKED_PREEXISTING_FAILURE_UNKNOWN`, `BLOCKED_STAGE_MISMATCH`, `BLOCKED_STAGED_TREE_FAILURE`, `BLOCKED_UNEXPECTED_HEAD`, `BLOCKED_UNEXPECTED_INDEX`, `BLOCKED_RECOVERY_REQUIRED`, `BLOCKED_INSTRUCTION_INCOMPLETE`, `BLOCKED_EVIDENCE_STALE`, `BLOCKED_SESSION_STATE_UNRESTORED` (design).

**OPEN_DECISION**

- Enum in machine contract vs validator-only strings.

---

## 40. Regression cases (retain in v2 tests)

| ID | Tag | Summary |
|----|-----|---------|
| CASE 1 | INCIDENT_EVIDENCE | WT PASS; HEAD missing test-required implementation |
| CASE 2 | INCIDENT_EVIDENCE | Tracked code depends on untracked production modules |
| CASE 3 | INCIDENT_EVIDENCE | Byte hash differs; normalized source same |
| CASE 4 | INCIDENT_EVIDENCE | Candidate/ISO exists; provenance unknown |
| CASE 5 | INCIDENT_EVIDENCE | Same module set; runtime content/outcome differs |
| CASE 6 | INCIDENT_EVIDENCE | Incomplete safety instruction copy |
| CASE 7 | INCIDENT_EVIDENCE | Wrong fixed path assumption |
| CASE 8 | INCIDENT_EVIDENCE | Wrong symbol search file |
| CASE 9 | CONFIRMED_CURRENT_STATE | `forbid_actions` in config; hook caller does not invoke `check_action` |
| CASE 10 | INCIDENT_EVIDENCE | READ-ONLY Git audit writes diagnostic `.ps1` / `output.txt` under Production `runs/_diag_tmp`; porcelain 109→111; POSTCHECK fail; no auto-cleanup (`A_ROUTE_GIT_BASELINE_AUDIT_003`) |
| CASE 11 | INCIDENT_EVIDENCE | READ-ONLY audit sets `GIT_OPTIONAL_LOCKS` / `PYTHONPATH` / `PYTHONDONTWRITEBYTECODE` or CWD; same shell session continues; restoration via save + `finally` (baseline audit practice) |
| CASE 12 | INCIDENT_EVIDENCE | Approved command manually repaired / completed before execution → `MODIFIED_EXECUTION_CONTENT`; must re-approve (§47) |
| CASE 13 | INCIDENT_EVIDENCE | Unicode / quoted Git path misparsed; skip-worktree mis-counted as not-skip (`AUDIT_002`/`AUDIT_003`; NUL-delimited re-verify) |
| CASE 14 | INCIDENT_EVIDENCE | Quiet flag suppresses stdout evidence (`git check-ignore -q` unusable for ignored-path set extraction) |
| CASE 15 | INCIDENT_EVIDENCE | Classifier assigns paths to wrong semantic bucket (`local_state/` → `other`; strict prefix rules) |
| CASE 16 | INCIDENT_EVIDENCE | Verified Runtime Closure Candidate treated as Full Git Tree / index |
| CASE 17 | INCIDENT_EVIDENCE | Commit decomposition / hunk optimization attempted before isolated Recovery reconstruction |
| CASE 18 | INCIDENT_EVIDENCE | Multiple ad-hoc status comparators diverge; canonical porcelain compare required (§47) |

**V2_REQUIREMENT**

- Phase H tests reference these cases by ID.

**V2_REQUIREMENT — CASE 10 expected behavior (design)**

*Regression: READ-ONLY audit attempts Production-internal diagnostic artifacts*

**Given**

- Git commands are READ-ONLY relative to index/HEAD/refs.
- Production status baseline is known at audit start.
- Audit script would write `diagnostic.ps1` / `output.txt` (or equivalent) under Production.

**Expected**

- `DIAGNOSTIC_ARTIFACT_DESTINATION_GATE` blocks `INSIDE_PRODUCTION`, **or** instruction is redesigned to stdout / external sink only.
- If execution still produces a Production status delta: POSTCHECK **FAIL**; no automatic cleanup; escalate to cause analysis / Human Review.

**Must not claim (false completion)**

- `FILES_MODIFIED=False` and `PRODUCTION_STATUS_UNCHANGED=True` when untracked audit artifacts appeared in Production.

**V2_REQUIREMENT — CASE 11 expected behavior (design)**

*Regression: READ-ONLY audit changes environment variables and does not restore*

**Given**

- Git commands are READ-ONLY.
- Audit temporarily sets `GIT_OPTIONAL_LOCKS`, `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE`, or changes CWD.
- The same shell session may run follow-on commands.

**Case A — no restoration path**

- No `finally` (or equivalent) restore; original values not saved.

**Expected**

- `SESSION_STATE_RESTORATION_GATE` → **BLOCK** (do not auto-continue).

**Case B — restoration path**

- Original values captured; restore on failure paths included; optional post-restore verification.

**Expected**

- `SESSION_STATE_RESTORATION_GATE` → **PASS** (other gates may still fail, e.g. CASE 10 artifact write).

**V2_REQUIREMENT — CASE 17 expected behavior (design)**

- Recovery reproduction proceeds when verified dependency closure is known; commit decomposition runs **after** isolated reconstruction and verification—not as a precondition to reconstruction.

---

## 41. v1 feature preservation

**V2_REQUIREMENT**

Preserve without weakening:

- `push_safety` v2.1, `local_safety` v2.2, git_guard, pre-commit sensitive-path protection, pre-push protection, Agent local destructive gate, machine contract + distribution, adapters, governance drift/alignment tests.

---

## 42. Naming / versioning

**V2_REQUIREMENT**

Separate namespaces:

| Name | Domain |
|------|--------|
| Git Operation Policy **v2** | Semantic commit / integrity policy |
| push_safety **v2.1** | Pre-push fast-forward safety |
| local_safety **v2.2** | Local destructive op probe |

Do not conflate version numbers in runbooks.

---

## 43. Implementation order (design only)

| Phase | Deliverable | Gate for phase exit |
|-------|-------------|---------------------|
| **A** | Policy v2 semantic specification (markdown) | Human review |
| **B** | `git_governance.json` extension + schema | Contract tests pass |
| **C** | Commit Integrity Validator (CLI) | Candidate + staged tree on fixture repo |
| **D** | Candidate / staged-tree tooling | Regression CASE 1–2 blocked in fixture; CASE 10 fixture for artifact gate (design) |
| **E** | pre-commit integration (artifact check) | Hook tests; no regression on deny paths |
| **F** | Runtime `AUTO_COMMIT_ALLOWED` binding | Issuance tied to provenance ID |
| **G** | Cursor / Codex / Local adapter alignment | Adapter tests |
| **H** | Regression tests CASE 1–18 | CI subset |

Each phase: own clean candidate + staged-tree validation before merge to Production.

---

## 44. Non-goals

**V2_REQUIREMENT**

v2 does **not** aim to:

- Run full Runtime Import Provenance on every commit
- Run full project E2E on every commit
- Mandate complete root-cause for all past incidents
- Automate all Git operations
- Eliminate Human Approval entirely

Goal: light path by default; staged diagnostics on anomaly.

---

## 45. Extension map (v1 assets → v2)

| Asset | Extension | Tag |
|-------|-----------|-----|
| `docs/GIT_OPERATION_POLICY.md` | New v2 doc or major version bump | OPEN_DECISION |
| `git_governance.json` | New actions: `commit_integrity_validate`, readiness enums; connect `commit` conditions | DESIGN_CANDIDATE |
| `git_governance_invariants.py` | New gaps closed; CASE registry | DESIGN_CANDIDATE |
| `tools/git_guard/guard.py` | Optional `--commit-evidence` / staged-tree mode | DESIGN_CANDIDATE |
| `ai-agent.pre-commit.json` | Evidence hash check; not full pytest | OPEN_DECISION |
| `git_governance_enforcement.py` | Triad audit: config/caller/binding | DESIGN_CANDIDATE |
| New tool | `tools/commit_integrity/` validator | DESIGN_CANDIDATE |
| Adapters | Gate sequence + instruction completeness | DESIGN_CANDIDATE |
| Tests | `test_commit_integrity_*.py`, CASE fixtures | DESIGN_CANDIDATE |

---

## 46. Session state restoration

**V2_REQUIREMENT**（日本語を正本）

### セッション状態復元原則

監査・診断・検証・テスト・Git 補助処理が、後続コマンドの挙動へ影響するセッション状態を一時的に変更する場合:

1. 変更前の状態を保存する  
2. 必要な範囲だけ一時変更する  
3. 正常終了・失敗・例外を問わず復元する  
4. 必要に応じて復元後の状態を確認する  

**Policy principle (Japanese authoritative; English gloss)**

> 後続処理へ影響する環境変数や Current Working Directory 等を一時的に変更する場合、変更前の状態を保存し、正常終了・異常終了を問わず元の状態へ復元しなければならない。

*English gloss (non-authoritative): Session-affecting env and CWD changes require capture and unconditional restore.*

- 「処理が READ-ONLY である」ことは、「Session State を変更していない」ことを意味しない (§16).

**INCIDENT_EVIDENCE — baseline audit practice**

READ-ONLY diagnostics have used temporary settings such as:

- `$env:GIT_OPTIONAL_LOCKS = "0"`
- `$env:PYTHONDONTWRITEBYTECODE = "1"`
- `$env:PYTHONPATH = <candidate>`
- `Set-Location <candidate>`

These do not mutate the Git repository, but **do** affect later commands in the **same** PowerShell / shell session. Baseline audits used: save prior values → `try` / `catch` → `finally` restore regardless of exit path.

### In scope (session-affecting state)

Judge by **“does this affect behavior of subsequent processing?”**, not by a fixed name list alone.

**Environment variables (examples)**

- `PYTHONPATH`, `PATH`, `GIT_OPTIONAL_LOCKS`, `PYTHONDONTWRITEBYTECODE`, `HOME`, `TEMP` / `TMP`, and any other variable that changes Git / Python / test-runner behavior.

**Working directory**

- `Set-Location`, `cd`, `chdir` — restore prior location when changed.

**Other**

- Any temporary state in the same process / shell session that affects follow-on commands.

### Out of scope (ordinary locals)

**V2_REQUIREMENT**

Ordinary local variables (e.g. PowerShell `$head`, `$count`, `$diff`, `$result`, `$status`; Python function locals) are **not** session restoration targets when they do not persist into the shell session.

If a construct looks local but writes **global / session** state, apply §46.

### Recommended pattern (PowerShell)

**DESIGN_CANDIDATE**

```powershell
$oldValue = $env:SOME_VARIABLE
$oldLocation = Get-Location

try {
    $env:SOME_VARIABLE = "temporary"
    Set-Location <temporary-location>
    # operation
}
finally {
    Set-Location $oldLocation

    if ($null -ne $oldValue) {
        $env:SOME_VARIABLE = $oldValue
    }
    else {
        Remove-Item Env:SOME_VARIABLE -ErrorAction SilentlyContinue
    }
}
```

**V2_REQUIREMENT**

- Distinguish **unset** vs **empty string** when restoring; do not blindly reset to a fixed default.
- **Forbidden:** restore only on success path (see below).

### try / finally cleanup guarantee

**V2_REQUIREMENT**

Restore must run on:

- command failure  
- pytest failure  
- Python / PowerShell exceptions  
- STOP / verification failure  
- unexpected exit  

Prefer language-native `try` / `finally` (or equivalent) when available.

### Session State Restoration Gate

**DESIGN_CANDIDATE** — gate name: `SESSION_STATE_RESTORATION_GATE`

| Concept | Rule |
|---------|------|
| `SESSION_STATE_CHANGED=False` | **PASS** (gate not applicable; `SESSION_STATE_RESTORATION_VALID` = `NOT_REQUIRED` in approval predicate) |
| `SESSION_STATE_CHANGED=True` | Require `ORIGINAL_STATE_CAPTURED=True`, `RESTORE_PATH_PRESENT=True`, `RESTORE_ON_FAILURE=True`, `NO_UNRESTORED_STATE=True` |
| Optional | `RESTORATION_VERIFIED=True` when instruction mandates post-restore check |
| Unknown | **BLOCK** — do not auto-continue |

### Separation from Git persistent mutation

| Class | Examples | Policy layer |
|-------|----------|--------------|
| **A. Session State Mutation** | `GIT_OPTIONAL_LOCKS`, `PYTHONPATH`, CWD | §46 — restore required |
| **B. Git Persistent Mutation** | `git config`, index, branch, worktree, hooks | Layer A — existing Git Operation Safety; **not** “restore like env” without explicit authorized rollback |

**V2_REQUIREMENT**

- Do not treat Git persistent mutations as equivalent to session state because they might be “undone later” without Layer A gates.

### Separation from filesystem mutation

**V2_REQUIREMENT**

Session restoration does **not** replace diagnostic artifact safety (§35).

Example: `PYTHONPATH` restored, but `output.txt` written under Production → `SESSION_STATE_RESTORED=True` may still coexist with `FILES_MODIFIED=True` and `PRODUCTION_STATUS_UNCHANGED=False`.

**Cross-reference**

- Instruction completeness (`finally` not truncated): §18  
- Completion evidence: §21  
- Approval continuity: §18  
- Regression: CASE 11 (§40)  
- Read-only dimensions: §16  

---

## 47. Frozen promotion corpus (Recovery audit consolidation)

**V2_REQUIREMENT** — this section freezes principles confirmed during Recovery / Git Governance / A_ROUTE audits. **PROJECT_CANONICAL=False** until Promotion Gate below is satisfied.

### Git Governance Source of Truth hierarchy

| Rank | Asset | Role |
|------|-------|------|
| 1 | `docs/GIT_OPERATION_POLICY.md` | Human semantic canonical — meaning, prohibitions, safety conditions |
| 2 | `ai_tool/policy/git_governance.json` | Machine contract — must align semantically with (1) |
| 3 | Validators / hooks / runtime bindings | Enforcement — **not** policy meaning canonical |
| 4 | Tests | Verify policy / contract / enforcement — **not** policy canonical |
| 5 | Recovery snapshots / diagnostics / incident reports | **Evidence only** |
| 6 | This V2 design + `GIT_POLICY_V2_PROMOTION_PACKET.md` | Pre-promotion material — **does not** replace Production policy until promoted |

**Conflict rule:** If human canonical, machine contract, validator, and runtime binding **contradict** in meaning → do **not** auto-continue → `POLICY_CONSISTENCY_STATUS=BLOCKED` → Human Review. Do not assume which side is correct without audit.

### Four safety layers (formal)

Layers **A–D** per §1: Git Operation Safety; Commit Integrity Safety; Evidence / Diagnostic Safety; Instruction Execution Safety (command completeness, approval continuity, session state restoration).

### Recovery Baseline Reconstruction（日本語を正本）

Recovery の第一目的は **「最新の検証済み作業状態を安全に再現する」** こと。Commit 分割・履歴整理・機能単位の美しい分離は **Recovery 再現後** に行う。

**Order (V2_REQUIREMENT):**

Verified Evidence → Full Git Base → Recovery Overlay → Isolated Reconstruction → Runtime / Test Verification → Recovered Baseline → Commit Candidate Decomposition → Selective Stage → Staged Tree Verification → Human Approval → Commit

Do **not** precede reconstruction with hunk split / change removal / history shaping **only** for commit-boundary optimization.

### Verified Runtime Closure ≠ Full Git Worktree

A Verified Runtime Closure Candidate proves **“this source/test/runtime closure was verified”** — not necessarily identical to full Git tree, index, or commit tree. Git baseline reconstruction = **Full Git Base + Verified Overlay**. Do not treat Candidate file set as the Git tree.

### Sparse checkout / skip-worktree / path parsing

Physical absence on disk ≠ Git deletion. Confirm Git tree, index, skip-worktree. Prefer **NUL-delimited** path lists (`git ls-tree -rz`, `git check-ignore --stdin -z` **without** `-q` when stdout is evidence). Do not classify Unicode paths with newline-split-only parsers.

### Git READ-ONLY vs filesystem READ-ONLY

Maintained in §16, §35. Ignored paths do **not** justify Production writes for diagnostics.

### Session State Restoration

Maintained in §46 (`GIT_OPTIONAL_LOCKS`, `PYTHONDONTWRITEBYTECODE`, `PYTHONPATH`, `PATH`, `CWD`, etc.).

### Command Completeness

Incomplete commands (`COMMAND_STATUS=INCOMPLETE`): unclosed brackets, truncated `finally`, cut script blocks → **do not execute**. Human/agent manual repair = **new execution content** → re-validate (CASE 12).

### Approval Continuity

No auto-approval on re-authorization. Compare to original approved scope: command, path, scope, Git mutation, filesystem output, session state, side effects, evidence logic.

**DESIGN_CANDIDATE states:** `APPROVAL_CONTINUITY_OK`, `REDUNDANT_REAUTH`, `SCOPE_EXPANDED`, `STATE_CHANGED`, `NEW_SIDE_EFFECT`, `MODIFIED_EXECUTION_CONTENT`, `UNKNOWN` → block auto-continue when not `OK` / `REDUNDANT_REAUTH`.

### Error suppression

Do not treat `2>$null`, `-ErrorAction SilentlyContinue`, or blind `check=False` as safe. Distinguish command failure from missing evidence. Do not use quiet modes that hide stdout when stdout is evidence (CASE 14: `git check-ignore -q`).

### Evidence logic validation

Reject audit results when the generator has impossible conditions, circular validation, or contradictory branches (CASE 13 pattern).

### Status comparison canonicalization

When comparing Production porcelain to Recovery snapshot, use one canonical meaning: `git status --porcelain=v1 --untracked-files=all`, `TrimEnd`, drop empty lines, deterministic sort, exact compare (CASE 18). Future: single shared validator.

### Commit Integrity vs authorization

Safe Git operation ≠ safe commit. Integrity gates (§3, §14): dependency closure, candidate provenance, isolation, selective stage, staged diff audit, index identity, staged-tree reproduction/verification. Authorization does not skip integrity; integrity PASS does not replace human authorization.

### CONFIG_PRESENT ≠ ENFORCEMENT_ACTIVE

Confirm config, caller, validator, hook/runtime binding (§37).

### Git common dir / hooks

Use `git rev-parse --git-common-dir`; do not assume worktree `.git/hooks` is live (§36).

### A_ROUTE Recovery Policy

**Standard Recovery route: A_ROUTE only** — Full Git Base + Verified Recovery Overlay + Isolated Reconstruction + Verification. If A_ROUTE cannot proceed safely → **STOP + Human Review** — no automatic alternate route. Alternatives are **proposals only**. Do not treat legacy “C route” as a normal execution route.

### Recovery incident lessons (INCIDENT_EVIDENCE)

- Diagnostic audit wrote artifacts inside Production (CASE 10)  
- Session env not restored (CASE 11)  
- Incomplete command manually completed (CASE 12)  
- Path parsing / skip-worktree misjudgment (CASE 13)  
- `check-ignore -q` suppressed evidence (CASE 14)  
- Ignored bucket classifier mis-tagged `local_state/` (CASE 15)  
- Runtime Candidate confused with Full Git Tree (CASE 16)  
- Commit decomposition before reconstruction (CASE 17)  
- Divergent status comparators (CASE 18)  

### Promotion Gate (to Project canonical)

Promotion to `docs/GIT_OPERATION_POLICY.md` + `git_governance.json` requires at minimum:

1. V2 design frozen (`FROZEN_PROMOTION_CANDIDATE`)  
2. Isolated worktree from confirmed Git base  
3. Recovery overlay reconstructed  
4. Candidate verification passes  
5. Human semantic doc updated  
6. Machine contract synchronized  
7. Validator bindings implemented/classified  
8. Regression tests added (CASE 1–18 subset per phase)  
9. Human canonical / machine contract / enforcement consistency audit  
10. Staged-tree verification  
11. Human approval  
12. Commit (on isolated worktree path—not ad hoc on dirty Production)

### Rule enforcement maturity (DESIGN_CANDIDATE)

Per-rule states where applicable: `GUIDANCE_ONLY`, `CONTRACT_DEFINED`, `VALIDATOR_IMPLEMENTED`, `RUNTIME_BOUND`, `HOOK_BOUND`, `TESTED`. Distinguish “documented” from “enforced.”

---

## Open decisions summary

1. v2 doc path and cutover from v1 (**OPEN_DECISION**).
2. Heavy work in pre-commit vs external validator + lightweight hook (**OPEN_DECISION**).
3. Dependency closure depth (**OPEN_DECISION**).
4. Readiness state enum in contract vs tool-only (**OPEN_DECISION**).
5. Runtime authorization schema for `AUTO_COMMIT_ALLOWED` scope (**OPEN_DECISION**).
6. Normalized diff canonical form (EOL, whitespace) (**OPEN_DECISION**).

---

## Document control

- This file is **design-only** and lives outside Production worktree.
- Production repository was not modified to create this draft.
- Update `GIT_POLICY_V2_UPDATE_DIAGNOSTIC_ARTIFACT_SAFETY_001` (2026-09-13): diagnostic artifact safety, CASE 10, §16/§18/§21/§35.
- Update `GIT_POLICY_V2_UPDATE_SESSION_STATE_RESTORATION_001` (2026-09-13): §46, CASE 11.
- Update `GIT_POLICY_V2_FREEZE_AND_PROMOTION_PREP_001` (2026-09-13): **STATUS=FROZEN_PROMOTION_CANDIDATE**, §47, CASE 12–18, `GIT_POLICY_V2_PROMOTION_PACKET.md` — **Recovery policy files only**; Production unchanged.
- Implementation phases **A–H** are not started by this document.

---

*End of Git Operation Policy v2 Design Draft*
