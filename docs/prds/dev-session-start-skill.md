# PRD: session-start Skill（薄型 Wrapper）

**状態:** draft（Handoff 試行用）
**日付:** 2026-09-10

## 問題

Dev Skill Registry はできたが、作業再開時に Cursor/Codex が毎回 `AI_DEVELOPMENT_SESSION_START_POLICY.md` を正しく読む手順が Skill 化されていない。Policy 本文を Skill に複製せず、既存正本を Read して従う薄型 Skill が必要。

## 目標

`session-start` Skill を追加し、`registry/skills.json` に登録する。Skill 本文は Policy の手順参照のみ。Production Runtime には接続しない。

## 非目標

- Policy 本文の変更
- Local Agent への Skill 配信
- Handoff / Mission Memory との統合

## 受け入れ基準

1. `.agents/skills/session-start/SKILL.md` が存在し、軽量/Full Sync の判断手順を参照する
2. `registry/skills.json` に `session-start` が `provisional` で登録される
3. Schema 検証テストが PASS する

## 参照正本

- `docs/AI_DEVELOPMENT_SESSION_START_POLICY.md`
- `registry/skills.json`
- `.agents/skills/goal-handoff/SKILL.md`（Handoff との境界）
