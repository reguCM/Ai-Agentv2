# Git Policy V2 — Promotion Packet

| Field | Value |
|-------|--------|
| Instruction ID | `GIT_POLICY_V2_FREEZE_AND_PROMOTION_PREP_001` |
| Design artifact | `GIT_OPERATION_POLICY_V2_DESIGN.md` |
| Design STATUS | `FROZEN_PROMOTION_CANDIDATE` |
| PROJECT_CANONICAL | `False` |
| RECOVERY_OPERATIONAL_REFERENCE | `True` |
| Baseline Production HEAD (reference) | `7e23ad6` (`dev/current`) |
| Date | 2026-09-13 |

**This packet does not modify Production.** Promotion to Project canonical policy is a **separate** step on an **isolated worktree** after Recovery baseline reconstruction.

---

## 1. Purpose of V2

Git Operation Policy v2 consolidates Recovery / Git Governance audit findings into a single design that:

- Separates **Git operation safety**, **commit integrity**, **evidence/diagnostic safety**, and **instruction execution safety** (four layers).
- Defines **source-of-truth hierarchy** and **conflict handling** (`POLICY_CONSISTENCY_STATUS=BLOCKED`).
- Formalizes **A_ROUTE** Recovery (Full Git Base + Verified Overlay + isolated reconstruction + verification) without premature commit decomposition.
- Distinguishes **Verified Runtime Closure** from **Full Git Tree / index / commit tree**.
- Strengthens **READ-ONLY** semantics (Git vs filesystem), **session state restoration**, **command completeness**, and **approval continuity**.

Until Promotion Gate conditions are met, Production continues to use **v1** canonicals.

---

## 2. Source of Truth hierarchy

| Rank | Asset | Role |
|------|-------|------|
| 1 | `docs/GIT_OPERATION_POLICY.md` | Human semantic canonical |
| 2 | `ai_tool/policy/git_governance.json` | Machine contract (must align with 1) |
| 3 | Validators / hooks / runtime bindings | Enforcement only |
| 4 | Tests | Verification only |
| 5 | Recovery snapshots / diagnostics / incidents | Evidence only |
| 6 | V2 design + this packet | Pre-promotion; **not** Production policy |

**Conflict:** Human canonical vs machine contract vs validator vs runtime — **no auto-pick** → Human Review.

---

## 3. Major changes from V1 → V2 (semantic)

| Area | V2 emphasis |
|------|-------------|
| Commit integrity | Explicit pipeline: dependency closure, candidate provenance/isolation, selective stage, staged diff audit, staged-tree reproduction/verification |
| Recovery | A_ROUTE only; reconstruction before commit decomposition |
| Evidence | Diagnostic artifacts off Production; Git READ-ONLY ≠ filesystem READ-ONLY |
| Execution | Command completeness, approval continuity states, session env save/restore |
| Paths | NUL-delimited parsing; skip-worktree / sparse checkout awareness |
| Audit | No blind error suppression; evidence logic self-validation |
| Authorization vs integrity | Both required; neither substitutes for the other |
| Enforcement | `CONFIG_PRESENT != ENFORCEMENT_ACTIVE` |

Full detail: `GIT_OPERATION_POLICY_V2_DESIGN.md` (§1–§47, especially §47).

---

## 4. Not yet enforced on current Production

The following are **design / guidance** or **partially** present in v1 until promotion and implementation phases complete:

- Full **Commit Integrity** gate chain as mandatory pre-commit contract
- **A_ROUTE** as documented standard route in human canonical
- **Approval continuity** state machine in runtime agents
- **COMMAND_STATUS=INCOMPLETE** hard block before shell execution
- **POLICY_CONSISTENCY_STATUS** automated blocker across all validators
- Unified **status comparison** validator (CASE 18)
- **Staged-tree verification** as required promotion step
- Per-rule **enforcement maturity** labels in contract (`GUIDANCE_ONLY` … `TESTED`)
- Regression **CASE 12–18** as automated tests

Production v1 remains authoritative for day-to-day Git operations until Promotion Gate §5.

---

## 5. Promotion target files

| Target | Action on promotion |
|--------|---------------------|
| `docs/GIT_OPERATION_POLICY.md` | Merge V2 human semantics; preserve history / version notes |
| `ai_tool/policy/git_governance.json` | Sync action IDs, approval classes, readiness enums per V2 |
| `ai_tool/policy/development_policy.json` | Update `distribution.git_governance_ref` / version if required |
| `.cursor/rules/git-governance-adapter.mdc` | Adapter pointers only (no full policy copy) |
| `tools/git_guard` / hooks | Classify and bind validators per layer A–D |
| `tests/` (git governance / commit integrity) | CASE 1–18 coverage per phase H |

**Out of scope for promotion:** Recovery-only paths under `D:\AI-Agent-recovery\` (remain evidence).

---

## 6. Required validators (classification)

| Layer | Examples (from V2 design) |
|-------|---------------------------|
| A — Git operation | `git_guard`, pre-push, local_safety destructive ops |
| B — Commit integrity | Dependency closure, selective stage, staged-tree verify, candidate/index identity |
| C — Evidence / diagnostic | Production write probe, artifact path allowlist (stdout / recovery dir) |
| D — Instruction execution | Session restoration checker, command completeness, approval continuity |

Each binding should record maturity: `CONTRACT_DEFINED` → `VALIDATOR_IMPLEMENTED` → `RUNTIME_BOUND` / `HOOK_BOUND` → `TESTED`.

---

## 7. Required regression tests

Reference **CASE 1–18** in `GIT_OPERATION_POLICY_V2_DESIGN.md` §40 / §47.

Priority additions from Recovery incidents:

- CASE 12 — modified execution content after manual repair  
- CASE 13 — NUL-safe path / skip-worktree  
- CASE 14 — no `check-ignore -q` for ignored-set evidence  
- CASE 15 — ignored prefix bucket (`local_state/`)  
- CASE 16 — runtime closure ≠ git tree  
- CASE 17 — reconstruction before decomposition  
- CASE 18 — canonical porcelain compare  

---

## 8. Promotion Gate (checklist)

1. V2 design **frozen** (`FROZEN_PROMOTION_CANDIDATE`)  
2. **Isolated worktree** from confirmed Git base  
3. **Recovery overlay** reconstructed  
4. **Candidate verification** passes  
5. Update **`docs/GIT_OPERATION_POLICY.md`**  
6. Sync **`ai_tool/policy/git_governance.json`**  
7. Implement / classify **validator bindings**  
8. Add **regression tests**  
9. **Consistency audit** (human / machine / enforcement)  
10. **Staged-tree verification**  
11. **Human approval**  
12. **Commit** (on promotion worktree — not uncontrolled Production mutation)

---

## 9. Rollback vs STOP

V2 Recovery policy does **not** rely on silent rollback or automatic route switching.

- On ambiguity, policy conflict, or failed gate → **STOP** + **Human Review**.  
- Alternatives (non–A_ROUTE) are **proposals** only.  
- Promotion failure → fix forward on isolated worktree; do not force-push Production without explicit human governance.

---

## 10. Current Recovery scope

During active Recovery (`dev/current` baseline `7e23ad6`):

- **Do not** apply V2 as Project canonical on Production yet.  
- **May** cite V2 design + this packet for A_ROUTE overlay design, audits, and governance decisions.  
- **Verified Runtime Closure Candidate** (`baseline-candidates/...`) is evidence, not a git tree substitute.

---

## 11. Next decision

**DECISION:** `READY_FOR_ISOLATED_WORKTREE_CREATION_PLAN`

Execute Promotion Gate steps 2–12 only after human approval of isolated worktree plan and confirmed overlay set design.

---

*End of Promotion Packet*
