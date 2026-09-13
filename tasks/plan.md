# Implementation Plan: session-start Skill

## Overview

Goal Handoff v0 の試行として、作業再開用の薄型 `session-start` Skill を追加する。Policy 複製はせず、既存 Session Start Policy を Read して従う手順を Skill 化する。

## Architecture Decisions

- Skill 本文は手順と参照のみ。Policy 全文は `docs/AI_DEVELOPMENT_SESSION_START_POLICY.md` に残す
- `registry/skills.json` で `provisional` 登録。Production 接続はしない
- Handoff Packet から実装を開始し、完了後に別 commit する

## Task List

### Phase 1: Skill 追加

- [ ] T1: `.agents/skills/session-start/SKILL.md` を作成
- [ ] T2: `registry/skills.json` と PROVENANCE を更新

### Checkpoint: Registry

- [ ] Registry schema 検証テスト PASS

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Policy と Skill の二重管理 | Med | Skill は参照リンクのみ。判定は Policy 正本 |
| Skill 数増加で Registry テストが壊れる | Low | test_skills_registry の期待値を同時更新 |

## Open Questions

- なし（試行スコープは session-start 追加のみ）
