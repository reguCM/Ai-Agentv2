# Tech Spec: session-start Skill（薄型 Wrapper）

**PRD:** `docs/prds/dev-session-start-skill.md`
**状態:** draft（Handoff 試行用）

## 実装方針

Policy 本文をコピーしない。Skill は次を固定する。

1. 発動トリガーの例（Session Start Policy §3 参照）
2. 軽量 Check の必須項目（branch / HEAD / status）
3. Full Sync へ昇格する条件
4. 判定ラベル（READY / RESUME / ALREADY_DONE / NEED_FULL_SYNC）
5. 読む正本一覧（`CURRENT_DEVELOPMENT_STATE.md` 等）

## 変更ファイル（予定）

| パス | 変更 |
|---|---|
| `.agents/skills/session-start/SKILL.md` | 新規 |
| `registry/skills.json` | skill 登録、phase=utility |
| `registry/schema/skills.schema.json` | 変更不要（既存 enum で足りる） |
| `tests/registry/test_skills_registry.py` | skill 数・path 存在の期待値更新 |
| `.agents/skills/PROVENANCE.md` | provisional 行追記 |

## テスト

- `tests/registry/test_skills_registry.py`
- `tests/ai_tool/policy/test_policy_distribution.py`（Policy Manifest 非変更のため回帰のみ）

## 境界

- `runtime_connected: false`
- imported Skill 本文は変更しない
