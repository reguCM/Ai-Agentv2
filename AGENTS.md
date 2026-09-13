# Repository Policy Adapter for Codex

policy-distribution-version: 2026-09-06.1

共通開発ルールは次の正本を参照する。本文をこのファイルへ複製しない。

- `ai_tool/policy/development_policy.json`: machine-readable Policy Manifest / Contract
- `docs/AI_DEVELOPMENT_SESSION_START_POLICY.md`: 作業開始・再同期
- `docs/DEVELOPMENT_TEST_POLICY.md`: 開発検証・Causal Scope・E2E
- `docs/GIT_OPERATION_POLICY.md`: Git操作（意味正本）
- `ai_tool/policy/git_governance.json`: Git Governance 機械契約（承認区分・action ID）
- `docs/CURRENT_DEVELOPMENT_STATE.md`: 現在状態・既知Issue
- `docs/SYSTEM_ASSET_INDEX.md`: 実験資産の人間向け入口（詳細は各正本）
- `registry/skills.json`: 採用 Dev Skill 機械カタログ（本文は `.agents/skills/**/SKILL.md`）
- `docs/specs/GOAL_HANDOFF_V0.md`: Goal Handoff Packet 仮仕様 v0.1（PROVISIONAL / Runtime 未接続）

作業開始時は、必要な正本を現在のRepositoryから読み、記載と実態が矛盾する場合は現在の
Repositoryを確認する。Consumer固有指示を除き、このAdapterよりCanonical Policyを優先する。
