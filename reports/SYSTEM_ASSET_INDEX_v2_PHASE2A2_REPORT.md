# SYSTEM_ASSET_INDEX v2 — Phase 2A.2 Report

Verified Asset Baseline Enrollment（完了）。Phase 2B は未開始。

## 概念分離

| 概念 | 意味 |
|------|------|
| `verification.freshness` | 過去の人間/監査による確認状態（今回 **変更なし**） |
| `baseline_status` | Change Detection 用 fingerprint Evidence の有無（Enrollment レポート上の分類） |

`VERIFIED` + `baseline_status=MISSING` は許容。自動で `POSSIBLY_STALE` / `STALE` にはしない。

## Historical Evidence 構造

```text
reports/verification_evidence/
  asset_<asset_id>.json          # 最新スナップショット（evidence_ref 固定）
  history/<asset_id>/<verification_id>.json   # 不変履歴
```

不変条件:

- 同一 `verification_id` で内容（fingerprint payload）を上書きしない
- 履歴ファイルが存在する場合、異なる内容の再書き込みは拒否

Evidence スキーマ拡張（任意フィールド）: `source_audit`, `enrollment_phase`

## ツール

| ツール | 役割 |
|--------|------|
| `tools/project_asset_baseline_enrollment.py` | 分類・推奨アクション（READ-ONLY） |
| `tools/enroll_project_asset_baselines.py` | レポート出力 / `--capture-approved` のみ capture |
| `tools/capture_project_asset_baselines.py` | Evidence 書き込み（`--all-verified-with-watch` **無効化**） |

`--capture-approved` は `live_reconfirm=true` かつ `recommended_action=CAPTURE_BASELINE` の Asset のみ。VERIFIED であることだけでは capture しない。

## Baseline coverage

### Phase 2A.1 → 2A.2（checker summary）

| 段階 | UNCHANGED | CHANGE_CANDIDATE | UNKNOWN |
|------|-----------|------------------|---------|
| 2A.1 終了時 | 2 | 0 | 33 |
| 2A.2 Enrollment 後 | 24 | 2 | 9 |

成功条件（件数減少そのものではない）: UNKNOWN が減った Asset には **新規 Verification Evidence** があること。

- **24 UNCHANGED**: 再確認済み baseline あり（fingerprint 比較可能）
- **9 UNKNOWN**: baseline なし（Host / STALE / POSSIBLY_STALE / 監視不能等）— 捏造なし
- **2 CHANGE_CANDIDATE**: 自己参照 Asset（`project_assets_registry`, `system_asset_index_view`）— レジストリ更新と生成 Index の同期タイミングによる一時差分。運用では `generate_system_asset_index.py` → registry 順 capture で整合。

### Enrollment 分類（capture 後・`reports/project_asset_baseline_enrollment.json`）

| 区分 | 件数（概算） |
|------|----------------|
| BASELINE_READY | 26 |
| BASELINE_MISSING_HUMAN_REVIEW_REQUIRED | 4 |
| BASELINE_NOT_OBSERVABLE | 4 |
| NOT_APPLICABLE | 1 |

### recommended_action 残件

| アクション | 代表 Asset | 理由 |
|------------|------------|------|
| HUMAN_REVIEW_REQUIRED | `dev_skill_registry_bundle`, `current_dev_state`, `grill_human_v0` | `freshness=POSSIBLY_STALE` |
| WATCH_MAPPING_REVIEW_REQUIRED | `grill_observation_v0` | `research/grill_observation_v0` 不在 |
| NOT_OBSERVABLE | `cursor_user_rules`, `cursor_host_skills`, `test_improvement_loop`, `local_llm_human_judge_proxy` | Host / NOT_OBSERVED |
| NO_ACTION | `diagnostic_framework_index` | `freshness=UNKNOWN` |

## 新規 capture（Enrollment 承認分）

`phase2a2_baseline_enrollment` により、Phase 2A.1 で未登録だった **VERIFIED・監視可能** Asset に Evidence を付与（`source_audit` に従来 `verification_method` を記録）。  
既存 2 件（`project_assets_registry`, `system_asset_index_view`）は履歴付きで更新。

**capture しなかった理由**: 上表のとおり（自動 VERIFIED 扱い禁止・ファイル存在のみ不可・Host 不可）。

## Watch mapping 修正（実装）

- `_norm_path`: 先頭 `.` を誤って除去しない（`.cursor/`, `.agents/` を監視可能に）
- `_looks_like_repo_path`: ルート直下単一ファイル（`PROJECT_SPEC.md`, `AGENTS.md`）を path として許可

## 監査 Evidence 再利用

READ-ONLY 監査の `verification_method` を `source_audit` に写し、**live reconfirm**（`--capture-approved`）時に現行 fingerprint を取得。  
`verified_revision` 以降にコミット差分がある場合は READ-ONLY レポートでは `REVERIFY_FIRST` / `HUMAN_REVIEW_REQUIRED`（自動 baseline 化しない）。

## Tests

`tests/registry/test_project_asset_baseline_enrollment.py`（9）+ `test_project_asset_freshness.py`（10）+ `test_project_assets.py`（7）: **26 passed**（当該スコープ）。

## Registry freshness mutation

Enrollment capture 前後で `freshness` フィールド: **変更 0**（capture 内ガード）。

## Phase 2B readiness

| 条件 | 状態 |
|------|------|
| Baseline coverage 可視化 | `reports/project_asset_baseline_enrollment.json` / `.md` |
| Evidence history | CONNECTED |
| Baseline なしを正とみなさない | UNKNOWN + 明示理由 |
| Human Review 対象 | POSSIBLY_STALE / watch gap / Host が列挙済み |
| 100% baseline | **非要求**（Host・NOT_OBSERVED は残存可） |

Phase 2B（freshness 更新・Human Approval UI）は **自動開始しない**。
