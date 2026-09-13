# SYSTEM_ASSET_INDEX

**Human-readable Asset Index** — 正本は `registry/project_assets.json` です。
本ファイルは生成物です。手編集しないでください。更新は Registry を編集し、
`python tools/generate_system_asset_index.py` を実行してください。

Registry は「現在の Repository の絶対最新状態」ではなく、**最後に確認された状態と鮮度**を記録します。

**Registry digest:** `51a5952976a3a3f8c015ba4688caade7563cf07d027db5b318f3e0dd6a7f9194`  
**Human view:** `docs/SYSTEM_ASSET_INDEX.md`  

作業再開時は本 Index と `docs/CURRENT_DEVELOPMENT_STATE.md` を参照する。
記載と実態が矛盾したら、現在の Repository を優先する。

---

## Policy

### Development Test Policy (`dev_test_policy`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Policy |
| Scope | `REPOSITORY` |
| Status | IMPLEMENTED |
| Path | `docs/DEVELOPMENT_TEST_POLICY.md` |
| Source of Truth | docs/DEVELOPMENT_TEST_POLICY.md |
| Consumers | `cursor`, `codex` |
| Enforcement | GUIDANCE |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Git Operation Policy (`git_operation_policy`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Policy |
| Scope | `REPOSITORY` |
| Status | DOCUMENT_ONLY |
| Path | `docs/GIT_OPERATION_POLICY.md` |
| Source of Truth | docs/GIT_OPERATION_POLICY.md |
| Consumers | `human`, `cursor`, `codex`, `local_agent` |
| Enforcement | DOCUMENTATION |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | git_governance_post_g6_closure_reverify |
| Notes | Semantic Source of Truth for Git (human prose). Machine contract: git_governance_contract. |

### Grill v0 (human-facing) (`grill_human_v0`)

| 欄 | 値 |
|---|---|
| **Freshness** | **POSSIBLY_STALE** |
| Category | Policy |
| Scope | `REPOSITORY` |
| Status | PROVISIONAL |
| Path | `docs/GRILL_V0.md` |
| Source of Truth | docs/GRILL_V0.md |
| Consumers | `human` |
| Enforcement | DOCUMENTATION |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | migrated_from_system_asset_index_v1 |

### Development Policy Manifest (`policy_manifest`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Policy |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/policy/development_policy.json` |
| Source of Truth | ai_tool/policy/development_policy.json |
| Consumers | `cursor`, `codex`, `local_agent` |
| Enforcement | VALIDATED |
| Related Tests | `tests/ai_tool/policy/test_development_policy.py`, `tests/ai_tool/policy/test_policy_distribution.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |
| Notes | Machine contract; prose in canonical_files. |

### AI Development Session Start Policy (`session_start_policy`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Policy |
| Scope | `REPOSITORY` |
| Status | IMPLEMENTED |
| Path | `docs/AI_DEVELOPMENT_SESSION_START_POLICY.md` |
| Source of Truth | docs/AI_DEVELOPMENT_SESSION_START_POLICY.md |
| Consumers | `cursor`, `codex` |
| Enforcement | GUIDANCE |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Project Rule

### Concept Definitions (`concept_definitions`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Project Rule |
| Scope | `REPOSITORY` |
| Status | PROVISIONAL |
| Path | `docs/concepts/CONCEPT_DEFINITIONS.md` |
| Source of Truth | docs/concepts/CONCEPT_DEFINITIONS.md |
| Consumers | `cursor`, `codex`, `local_agent` |
| Enforcement | GUIDANCE |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Project Origin Spec (`project_spec`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Project Rule |
| Scope | `REPOSITORY` |
| Status | DOCUMENT_ONLY |
| Path | `PROJECT_SPEC.md` |
| Source of Truth | PROJECT_SPEC.md |
| Consumers | `human` |
| Enforcement | DOCUMENTATION |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Cursor Rule

### Agent Development Policy (Cursor) (`cursor_dev_rule`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Cursor Rule |
| Scope | `REPOSITORY`, `CURSOR` |
| Status | IMPLEMENTED |
| Path | `.cursor/rules/agent-development-policy.mdc` |
| Source of Truth | ai_tool/policy/development_policy.json (adapter; not prose canonical) |
| Consumers | `cursor` |
| Enforcement | PROMPT_CONSTRAINT |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |
| Notes | alwaysApply: true observed in session. |

### Cursor User Rules (Settings) (`cursor_user_rules`)

| 欄 | 値 |
|---|---|
| **Freshness** | **UNKNOWN** |
| Category | Cursor Rule |
| Scope | `HOST`, `EXTERNAL` |
| Status | UNKNOWN |
| Path | — (repository 外または複数) |
| Source of Truth | NOT_OBSERVED (Cursor Settings; not in repository) |
| Consumers | `cursor` |
| Enforcement | PROMPT_CONSTRAINT |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_session_prompt_observation |
| Stale Reason | Repository path NOT_OBSERVED; HOST_ADAPTER_NOT_VERIFIED (see docs/adapters/GIT_GOVERNANCE_CURSOR_HOST.md) |
| Notes | G5/G6: Host Git rules are not verified from repository CI. |

### Git Governance Cursor Adapter (`git_governance_cursor_adapter`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Cursor Rule |
| Scope | `REPOSITORY`, `CURSOR` |
| Status | IMPLEMENTED |
| Path | `.cursor/rules/git-governance-adapter.mdc` |
| Source of Truth | ai_tool/policy/git_governance.json (adapter reference; not semantic substitute) |
| Consumers | `cursor` |
| Enforcement | PROMPT_CONSTRAINT |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | git_governance_post_g6_closure_reverify |
| Notes | Host User Rules remain HOST_ADAPTER_NOT_VERIFIED; see docs/adapters/GIT_GOVERNANCE_CURSOR_HOST.md |

### Skill Namespace Compatibility Adapter (`skill_namespace_compat_rule`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Cursor Rule |
| Scope | `REPOSITORY`, `CURSOR` |
| Status | IMPLEMENTED |
| Path | `.cursor/rules/skill-namespace-compat.mdc` |
| Source of Truth | registry/skills.json alias_index |
| Consumers | `cursor` |
| Enforcement | PROMPT_CONSTRAINT |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Adapter

### AGENTS.md Policy Adapter (`codex_adapter`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Adapter |
| Scope | `REPOSITORY` |
| Status | IMPLEMENTED |
| Path | `AGENTS.md` |
| Source of Truth | ai_tool/policy/development_policy.json distribution.consumers.codex |
| Consumers | `codex` |
| Enforcement | GUIDANCE |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Registry

### Models Registry (`models_registry`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Registry |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `registry/models.json` |
| Source of Truth | registry/models.json |
| Consumers | `local_agent` |
| Enforcement | VALIDATED |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Policy Audit Certificate Index (`policy_audit_registry`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Registry |
| Scope | `REPOSITORY` |
| Status | GENERATED |
| Path | `docs/policy_audit_registry.json` |
| Source of Truth | docs/policy_audit_registry.json (index only; not policy canonical) |
| Consumers | `human` |
| Enforcement | DOCUMENTATION |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Project Governance Asset Registry (`project_assets_registry`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Registry |
| Scope | `REPOSITORY` |
| Status | IMPLEMENTED |
| Path | `registry/project_assets.json` |
| Source of Truth | registry/project_assets.json |
| Consumers | `human`, `cursor`, `codex` |
| Enforcement | VALIDATED |
| Related Tests | `tests/registry/test_project_assets.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |

### Dev Skill Registry (`skills_registry`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Registry |
| Scope | `REPOSITORY`, `CURSOR` |
| Status | IMPLEMENTED |
| Path | `registry/skills.json` |
| Source of Truth | registry/skills.json |
| Consumers | `cursor`, `codex` |
| Enforcement | VALIDATED |
| Related Tests | `tests/registry/test_skills_registry.py` |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Tool Registry (`tools_registry`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Registry |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `registry/tools.json` |
| Source of Truth | registry/tools.json |
| Consumers | `local_agent`, `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Schema / Contract

### Git Governance Machine Contract (`git_governance_contract`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Schema / Contract |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/policy/git_governance.json` |
| Source of Truth | ai_tool/policy/git_governance.json |
| Consumers | `cursor`, `codex`, `local_agent` |
| Enforcement | VALIDATED |
| Related Tests | `tests/ai_tool/policy/test_git_governance.py`, `tests/ai_tool/policy/test_git_governance_adapters.py`, `tests/ai_tool/policy/test_git_governance_drift.py`, `tests/tools/test_git_guard_governance_alignment.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | git_governance_post_g6_closure_reverify |
| Notes | contract_version 2026-09-12.3. G5 verdict CONSISTENT_WITH_KNOWN_GAPS. known_enforcement_gaps: commit authorization, amend, amend_after_hook_failure, clean, rebase, worktree_remove, branch_delete, merge_to_main. |

### Goal Handoff v0 (`goal_handoff_spec`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Schema / Contract |
| Scope | `REPOSITORY` |
| Status | PROVISIONAL |
| Path | `docs/specs/GOAL_HANDOFF_V0.md` |
| Source of Truth | docs/specs/GOAL_HANDOFF_V0.md + registry/schema/goal_handoff.schema.json |
| Consumers | `cursor`, `codex` |
| Enforcement | VALIDATED |
| Related Tests | `tests/registry/test_skills_registry.py` |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Precondition Contract (`precondition_contract`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Schema / Contract |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `registry/schema/precondition_contract.schema.json` |
| Source of Truth | registry/schema/precondition_contract.schema.json |
| Consumers | `production_runtime` |
| Enforcement | VALIDATED |
| Related Tests | `tests/ai_tool/test_precondition_contract.py` |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Skill

### Cursor Host Skills (`cursor_host_skills`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Skill |
| Scope | `HOST`, `EXTERNAL` |
| Status | UNKNOWN |
| Path | — (repository 外または複数) |
| Source of Truth | NOT_OBSERVED in repository (~/.cursor/skills-cursor/) |
| Consumers | `cursor` |
| Enforcement | GUIDANCE |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |
| Stale Reason | Host path observed on disk; not versioned in repo. |

### Dev Skill Registry / Goal Handoff (bundle) (`dev_skill_registry_bundle`)

| 欄 | 値 |
|---|---|
| **Freshness** | **POSSIBLY_STALE** |
| Category | Skill |
| Scope | `REPOSITORY`, `CURSOR` |
| Status | PROVISIONAL |
| Path | `registry/skills.json` |
| Source of Truth | registry/skills.json |
| Consumers | `cursor`, `codex` |
| Enforcement | NOT_CONNECTED |
| Related Tests | `tests/registry/test_skills_registry.py` |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | migrated_from_system_asset_index_v1 |
| Stale Reason | Prior index dated 2026-09-10; runtime_connected flags not re-measured. |

### Session Start Skill (`session_start_skill`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Skill |
| Scope | `REPOSITORY`, `CURSOR` |
| Status | PROVISIONAL |
| Path | `.agents/skills/session-start/SKILL.md` |
| Source of Truth | .agents/skills/session-start/SKILL.md |
| Consumers | `cursor`, `codex` |
| Enforcement | GUIDANCE |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Guard / Gate

### Git Guard (`git_guard`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Guard / Gate |
| Scope | `REPOSITORY`, `EXTERNAL` |
| Status | IMPLEMENTED |
| Path | `tools/git_guard/guard.py` |
| Source of Truth | tools/git_guard/POLICY.md + configs |
| Consumers | `local_agent`, `human` |
| Enforcement | ENFORCED |
| Related Tests | — |
| Last Verified | 2026-09-11T22:29:55.918052+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | git_governance_post_g6_closure_reverify |
| Notes | Validator/Gate only (not Git Governance semantic SoT). ENFORCED on guard action path + hook-invoked checks; not full agent CLI coverage. |

### Git Hooks Deployment (shared .git) (`git_hooks_deployment`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Guard / Gate |
| Scope | `EXTERNAL` |
| Status | IMPLEMENTED |
| Path | `tools/git_guard/DEPLOYED.md` |
| Source of Truth | tools/git_guard/DEPLOYED.md |
| Consumers | `human`, `local_agent` |
| Enforcement | ENFORCED |
| Related Tests | — |
| Last Verified | 2026-09-11T22:29:57.086969+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | git_governance_post_g6_closure_reverify |
| Notes | Physical hooks: D:\AI-Agent\.git\hooks\pre-commit and pre-push (thin adapter → worktree tools/git_guard). Not modified in G4–G6. |

### Goal Completion Gate v0 (`goal_completion_gate`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Guard / Gate |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | PROVISIONAL |
| Path | `docs/GOAL_COMPLETION_GATE_V0.md` |
| Source of Truth | docs/GOAL_COMPLETION_GATE_V0.md |
| Consumers | `production_runtime` |
| Enforcement | VALIDATED |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Human Requirement Resolution Wedge (`human_requirement_resolution_wedge`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Guard / Gate |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `reports/HUMAN_REQUIREMENT_RESOLUTION_ARCHITECTURE.md` |
| Source of Truth | reports/HUMAN_REQUIREMENT_RESOLUTION_ARCHITECTURE.md |
| Consumers | `production_runtime` |
| Enforcement | VALIDATED |
| Related Tests | `tests/ai_tool/chat_interface/test_requirement_resolution_wedge.py`, `tests/ai_tool/chat_interface/test_goal_continuation_requirement_gate.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |

### Project Asset Verification Tool (`project_asset_verifier`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Guard / Gate |
| Scope | `REPOSITORY` |
| Status | IMPLEMENTED |
| Path | `tools/project_asset_verification.py` |
| Source of Truth | tools/project_asset_verification.py |
| Consumers | `human`, `cursor`, `codex` |
| Enforcement | VALIDATED |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |

### Spawn Authorization (Stage 7 experiment) (`stage7_spawn_authorization`)

| 欄 | 値 |
|---|---|
| **Freshness** | **STALE** |
| Category | Guard / Gate |
| Scope | `EXPERIMENT` |
| Status | LEGACY |
| Path | — (repository 外または複数) |
| Source of Truth | NOT_OBSERVED in repository (historical: runs/tetris_goal_recursive_convergence_v0/20260911T133046Z_tetris_fresh_production/stage7/spawn_authorization.py) |
| Consumers | `experiment_harness` |
| Enforcement | NOT_CONNECTED |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |
| Stale Reason | Run artifact path not present in git tree at 1536cc2; registry aligned to committed baseline. |
| Notes |  EPHEMERAL_RUN; do not require runs/ path on disk for governance registry. |

---

## Runtime Guard

### Agent Stop Control (P2a) (`p2a_agent_stop_control`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/chat_interface/agent_stop_control.py` |
| Source of Truth | ai_tool/chat_interface/agent_stop_control.py |
| Consumers | `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | `tests/ai_tool/chat_interface/test_agent_stop_control.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | p2a_dependency_closure_commit_1536cc2 |
| Notes | Registered at P2a dependency closure; agent_turn import dependency (not Requirement Architecture dependency). |

### Progress Classification Shadow (P2a) (`p2a_progress_classification_shadow`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/chat_interface/progress_classification_shadow.py` |
| Source of Truth | ai_tool/chat_interface/progress_classification_shadow.py |
| Consumers | `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | `tests/ai_tool/chat_interface/test_progress_classification_shadow.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | p2a_dependency_closure_commit_1536cc2 |
| Notes | Registered at P2a dependency closure; agent_turn import dependency (not Requirement Architecture dependency). |

### Progress Classification v0 (P2a) (`p2a_progress_classification_v0`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/chat_interface/progress_classification_v0.py` |
| Source of Truth | ai_tool/chat_interface/progress_classification_v0.py |
| Consumers | `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | `tests/ai_tool/chat_interface/test_progress_classification_v0.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | p2a_dependency_closure_commit_1536cc2 |
| Notes | Registered at P2a dependency closure; agent_turn import dependency (not Requirement Architecture dependency). |

### Semantic Stagnation Warning (P2a) (`p2a_semantic_stagnation_warning`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/chat_interface/semantic_stagnation_warning.py` |
| Source of Truth | ai_tool/chat_interface/semantic_stagnation_warning.py |
| Consumers | `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | `tests/ai_tool/chat_interface/test_semantic_stagnation_warning.py` |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | p2a_dependency_closure_commit_1536cc2 |
| Notes | Registered at P2a dependency closure; agent_turn import dependency (not Requirement Architecture dependency). |

### State Cycle Detection v0 (P2a) (`p2a_state_cycle_detection_v0`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/chat_interface/state_cycle_detection_v0.py` |
| Source of Truth | ai_tool/chat_interface/state_cycle_detection_v0.py |
| Consumers | `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | p2a_dependency_closure_commit_1536cc2 |
| Notes | Registered at P2a dependency closure; agent_turn import dependency (not Requirement Architecture dependency). |

### Pipeline Observer Budget (`pipeline_observations`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/pipeline_observations.py` |
| Source of Truth | ai_tool/pipeline_observations.py |
| Consumers | `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | p2a_dependency_closure_commit_1536cc2 |
| Notes | Registered at P2a dependency closure; agent_turn import dependency (not Requirement Architecture dependency). |

### Final Answer Policy Enforce (`policy_enforce`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/policy/enforce.py` |
| Source of Truth | ai_tool/policy/enforce.py |
| Consumers | `local_agent` |
| Enforcement | ENFORCED |
| Related Tests | `tests/ai_tool/policy/test_development_policy.py` |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |
| Notes | agent.py final answer path only; Chat run_chat_turn NOT_CONNECTED per TDA. |

### Development Policy Loader (`policy_loader`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/policy/loader.py` |
| Source of Truth | ai_tool/policy/loader.py |
| Consumers | `local_agent` |
| Enforcement | VALIDATED |
| Related Tests | `tests/ai_tool/policy/test_policy_distribution.py` |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

### Task Execution Guard (`task_execution_guard`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Runtime Guard |
| Scope | `REPOSITORY`, `PRODUCTION` |
| Status | IMPLEMENTED |
| Path | `ai_tool/task_execution_guard.py` |
| Source of Truth | ai_tool/task_execution_guard.py |
| Consumers | `production_runtime` |
| Enforcement | ENFORCED |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | cursor_development_governance_audit_read_only |

---

## Safety Rule

### Live Execution Safety Rule (Stage 7 experiment) (`stage7_live_safety_rule`)

| 欄 | 値 |
|---|---|
| **Freshness** | **STALE** |
| Category | Safety Rule |
| Scope | `EXPERIMENT` |
| Status | LEGACY |
| Path | — (repository 外または複数) |
| Source of Truth | NOT_OBSERVED in repository (historical: runs/tetris_goal_recursive_convergence_v0/20260911T133046Z_tetris_fresh_production/stage7/LIVE_EXECUTION_SAFETY_RULE.json) |
| Consumers | `experiment_harness` |
| Enforcement | NOT_CONNECTED |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |
| Stale Reason | Run artifact path not present in git tree at 1536cc2; registry aligned to committed baseline. |
| Notes |  EPHEMERAL_RUN; do not require runs/ path on disk for governance registry. |

---

## Harness

### Grill Observation Research v0 (`grill_observation_v0`)

| 欄 | 値 |
|---|---|
| **Freshness** | **POSSIBLY_STALE** |
| Category | Harness |
| Scope | `REPOSITORY` |
| Status | PROVISIONAL |
| Path | `research/grill_observation_v0` |
| Source of Truth | research/grill_observation_v0/ (per-run specs) |
| Consumers | `human` |
| Enforcement | NOT_CONNECTED |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | migrated_from_system_asset_index_v1 |

### Local LLM Human-Judge Proxy v0 (`local_llm_human_judge_proxy`)

| 欄 | 値 |
|---|---|
| **Freshness** | **STALE** |
| Category | Harness |
| Scope | `REPOSITORY` |
| Status | LEGACY |
| Path | — (repository 外または複数) |
| Source of Truth | NOT_OBSERVED in current worktree (historical: research/llm_benchmarks/h4_decision_maker_bench/HUMAN_JUDGE_PROXY_V0.md) |
| Consumers | `human` |
| Enforcement | NOT_CONNECTED |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | migrated_from_system_asset_index_v1 |
| Stale Reason | v1 index path not present in worktree at verified_revision (research/ subtree absent on disk) |
| Notes |  Canonical path from SYSTEM_ASSET_INDEX v1; file NOT_OBSERVED in current worktree. |

### Test Improvement Loop v0 (`test_improvement_loop`)

| 欄 | 値 |
|---|---|
| **Freshness** | **STALE** |
| Category | Harness |
| Scope | `REPOSITORY` |
| Status | LEGACY |
| Path | — (repository 外または複数) |
| Source of Truth | NOT_OBSERVED in current worktree (historical: research/test_improvement_loop/V0_FREEZE.md) |
| Consumers | `human` |
| Enforcement | NOT_CONNECTED |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | migrated_from_system_asset_index_v1 |
| Stale Reason | v1 index path not present in worktree at verified_revision (research/ subtree absent on disk) |
| Notes |  Canonical path from SYSTEM_ASSET_INDEX v1; file NOT_OBSERVED in current worktree. |

---

## Index

### Current Development State (`current_dev_state`)

| 欄 | 値 |
|---|---|
| **Freshness** | **POSSIBLY_STALE** |
| Category | Index |
| Scope | `REPOSITORY` |
| Status | DOCUMENT_ONLY |
| Path | `docs/CURRENT_DEVELOPMENT_STATE.md` |
| Source of Truth | docs/CURRENT_DEVELOPMENT_STATE.md |
| Consumers | `human`, `cursor`, `codex` |
| Enforcement | DOCUMENTATION |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | migrated_from_system_asset_index_v1 |
| Stale Reason | Contains 2026-09-04 checkpoint history mixed with追記. |

### Diagnostic Framework Index (`diagnostic_framework_index`)

| 欄 | 値 |
|---|---|
| **Freshness** | **UNKNOWN** |
| Category | Index |
| Scope | `REPOSITORY` |
| Status | LEGACY |
| Path | `docs/diagnostic_framework/INDEX.md` |
| Source of Truth | docs/diagnostic_framework/INDEX.md |
| Consumers | `human` |
| Enforcement | DOCUMENTATION |
| Related Tests | — |
| Last Verified | 2026-09-11T21:19:00+09:00 |
| Verified Revision | `763f8c8e865130c165198696de4d2ab957d9ddfd` |
| Verification Method | not_reverified_in_governance_audit |

### SYSTEM_ASSET_INDEX (human view) (`system_asset_index_view`)

| 欄 | 値 |
|---|---|
| **Freshness** | **VERIFIED** |
| Category | Index |
| Scope | `REPOSITORY` |
| Status | GENERATED |
| Path | `docs/SYSTEM_ASSET_INDEX.md` |
| Source of Truth | registry/project_assets.json |
| Consumers | `human`, `cursor`, `codex` |
| Enforcement | DOCUMENTATION |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |

---

## Audit

### Safety Rule Application Audit v3 (artifact) (`governance_audit_v3`)

| 欄 | 値 |
|---|---|
| **Freshness** | **STALE** |
| Category | Audit |
| Scope | `EXPERIMENT` |
| Status | LEGACY |
| Path | — (repository 外または複数) |
| Source of Truth | NOT_OBSERVED in repository (historical: runs/tetris_goal_recursive_convergence_v0/20260911T133046Z_tetris_fresh_production/stage7/output/stage7b/SAFETY_RULE_APPLICATION_AUDIT_V3.json) |
| Consumers | `human` |
| Enforcement | NOT_CONNECTED |
| Related Tests | — |
| Last Verified | 2026-09-12T03:20:00+00:00 |
| Verified Revision | `1536cc2a2e5ea4c7735749eda787e206198e4f50` |
| Verification Method | project_asset_registry_reconciliation_20260912 |
| Stale Reason | Run artifact path not present in git tree at 1536cc2; registry aligned to committed baseline. |
| Notes |  EPHEMERAL_RUN; do not require runs/ path on disk for governance registry. |

---

<!-- generated-from: registry/project_assets.json -->
<!-- registry-assets-sha256: 51a5952976a3a3f8c015ba4688caade7563cf07d027db5b318f3e0dd6a7f9194 -->
