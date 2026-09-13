# Goal Handoff Packet 仮仕様 v0.1

**内部ID:** `goal_handoff_v0`
**状態:** PROVISIONAL
**記録日:** 2026-09-10
**機械正本:** `registry/schema/goal_handoff.schema.json`
**Registry 参照:** `registry/skills.json` → `output_contracts.goal_handoff`
**発行 Skill:** `.agents/skills/goal-handoff/SKILL.md`
**概念入口:** `docs/concepts/CONCEPT_DEFINITIONS.md`（`goal_handoff_packet`）
**状態追記:** `docs/CURRENT_DEVELOPMENT_STATE.md`（2026-09-10 Dev Skill Registry / Goal Handoff）
**Policy Manifest:** `ai_tool/policy/development_policy.json` の `canonical_files` に本ファイルを含む

## 1. 目的

Dev Skill 合成（PRD → Tech Spec → Task Breakdown）の成果を、実装フェーズへ渡す **単一の機械可読 Packet** にまとめる。

- Production Runtime とは **未接続**（v0）
- Mission Memory の `mission.json` とは **別契約**
- `spec_proposal` / LLM Proposal とは **別系統**

## 2. 境界

| 区分 | Goal Handoff | 混同しない相手 |
|---|---|---|
| 生成主体 | Cursor / Codex Dev Skills | Production Chat turn |
| 消費主体 | 実装担当 AI / 人間 | Mission Memory store |
| 正本 | `docs/handoffs/*.json` | `local_state/mission_memory/` |
| Goal 原文 | `goal.original_request_excerpt`（任意抜粋） | Mission `original_goal` |
| Task | `implementation_tasks`（人間計画） | Runtime `TaskRecord` |

`runtime_boundary.production_connected` は v0 で常に `false`。

## 3. フィールド要約

### 3.1 識別

- `handoff_version`: 現行 `0.1`
- `handoff_id`: `gh-YYYYMMDDTHHMMSSZ-slug`
- `status`: `draft` → 人間承認後 `ready`
- `provisional`: v0 は常に `true`

### 3.2 `source`

設計成果の出典。推測で埋めない。

```json
{
  "skills": ["write-prd", "tech-spec", "planning-and-task-breakdown", "goal-handoff"],
  "documents": {
    "prd": "docs/prds/example.md",
    "tech_spec": "docs/tech-specs/example.md",
    "plan": "tasks/plan.md",
    "task_list": "tasks/todo.md"
  },
  "git": {
    "branch": "dev/current",
    "head": "531cdd4",
    "worktree": "D:/AI-Agent-worktrees/dev-current"
  }
}
```

`git` は観測値。Packet 正本にはしない。

### 3.3 `goal` / `scope`

- `goal.summary`: 実装者向け 1 段落
- `scope.in_scope` / `scope.non_goals`
- `scope.affected_paths`: 変更見込みパス（repo 相対、1 件以上）

### 3.4 `acceptance_criteria`

安定 ID `A1`, `A2`, ... と検証方法。

### 3.5 `implementation_tasks`

`planning-and-task-breakdown` から持ち上げる実行単位。

| フィールド | 意味 |
|---|---|
| `id` | `T1`, `T2`, ... |
| `title` | 短いタイトル |
| `acceptance` | 完了条件 |
| `verification` | 確認手順 |
| `dependencies` | 先行 task id |
| `size` | `S` / `M` / `L` / `XL` |
| `maps_to_acceptance` | 関連する `A*` |

`status=ready` では原則 `size` は `S` または `M` のみ。

### 3.6 `test_plan`

最低限 `pytest` 配列が必須。repo 相対パスまたは pytest node id。

### 3.7 `human_gates`

列挙値のみ:

- `git_push`
- `merge_to_stable`
- `promote_to_master`
- `production_e2e`
- `architecture_review`
- `security_review`

Repository Policy の Human Approval 要件は Packet 未記載でも有効。

### 3.8 `runtime_boundary`

```json
{
  "production_connected": false,
  "notes": "Dev Handoff Packet only. Production Chat / Mission Memory / Goal Completion Gate do not consume this file in v0."
}
```

## 4. ライフサイクル

1. `goal-handoff` Skill が `draft` を書く
2. 人間が upstream 文書と Packet を照合
3. 問題なければ `status: ready`
4. 実装 branch / worktree は Packet を参照して開始
5. 置き換え時は新 Packet の `supersedes` に旧 `handoff_id`

## 5. `ready` 判定チェックリスト

- [ ] JSON Schema 検証 PASS
- [ ] `open_questions` が空、または人間が実装続行を明示
- [ ] `acceptance_criteria` >= 1
- [ ] `implementation_tasks` >= 1
- [ ] `test_plan.pytest` >= 1
- [ ] `scope.affected_paths` >= 1
- [ ] `runtime_boundary.production_connected == false`

## 6. 非目標（v0）

- Production Chat からの自動読込
- Mission Memory への自動変換
- Handoff からの自動 branch 作成
- README / H4 専用フィールド

## 7. 例

`docs/handoffs/examples/goal-handoff-example.json`
