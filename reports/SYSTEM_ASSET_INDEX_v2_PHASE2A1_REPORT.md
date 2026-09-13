# SYSTEM_ASSET_INDEX v2 — Phase 2A.1 Report

Verification Baseline Hardening（完了）。Phase 2B Human Review は未着手。

## Schema 変更

| 正本 | 変更 |
|------|------|
| `registry/schema/project_assets.schema.json` | `verification.verification_id` / `verification.evidence_ref`（任意）、`freshness_dependencies[]`（`kind`: `path` \| `asset_id`） |
| `registry/schema/verification_evidence.schema.json` | 新規。Evidence JSON の機械契約 |

`related_assets` は従来どおり一般関連のみ。staleness 伝播は `freshness_dependencies` のみ。

## Verification Evidence 形式

- **配置**: `reports/verification_evidence/`（既存 `reports/policy_audits/` と同系の reports 配下）
- **安定ファイル名**: `asset_<asset_id>.json`（capture 時。レジストリ自己参照で `evidence_ref` 更新が fingerprint を壊さないため）
- **必須フィールド**: `verification_id`, `asset_id`, `verified_at`, `verified_revision`, `verification_method`, `resolved_watch_paths`, `watch_snapshots[]`
- **各 snapshot**: `path`, `existence`, `content_fingerprint`（`sha256:<hex>`）、任意 `git_state_if_available`
- **dirty worktree**: 検証時点の未コミット・未追跡ファイルも snapshot に含める（`build_direct_watch_paths` が解決した path のみ）

## Registry 側（巨大 hash を埋め込まない）

```json
"verification": {
  "freshness": "VERIFIED",
  "last_verified_at": "...",
  "verified_revision": "...",
  "verification_method": "...",
  "verification_id": "...",
  "evidence_ref": "reports/verification_evidence/asset_<asset_id>.json"
}
```

**capture ツール**（`tools/capture_project_asset_baselines.py`）は `freshness` を変更しない。`verification_id` / `evidence_ref`（と evidence ファイル）のみ更新。レジストリ JSON を watch する Asset は保存後に registry watcher を再 capture する。

## Change Detection（比較基準）

- **主**: Evidence の `content_fingerprint` vs 現在（`tools/project_asset_verification.py` + `tools/check_project_asset_freshness.py`, `schema_version` 2, `comparison_primary: verification_evidence_fingerprint`）
- **補助**: git diff ヒント（rename / delete 等 → `PATH_RENAMED`, `PATH_DELETED`）
- **候補理由**: `DIRECT_CONTENT_CHANGE`, `DEPENDENCY_CHANGE`, `PATH_DELETED`, `PATH_RENAMED`, `BASELINE_MISSING`, `WATCH_MAPPING_UNKNOWN`
- **Checker**: Registry の `freshness` は読み取りのみ（実行前後でファイル bytes 一致を検証）

## freshness_dependencies

```json
"freshness_dependencies": [
  { "kind": "path", "path": "registry/project_assets.json" },
  { "kind": "asset_id", "asset_id": "other_asset" }
]
```

`asset_id` は依存 Asset の direct watch path を展開。Evidence 作成時に依存 path の snapshot も `resolved_watch_paths` に含める。

## Phase 1 自己変更 Regression

| Asset | Phase 2A | Phase 2A.1（baseline 取得後） |
|-------|----------|-------------------------------|
| `project_assets_registry` | `CHANGE_CANDIDATE`（`related_assets:system_asset_index_view` + 未追跡 path） | **`UNCHANGED`**（fingerprint 一致） |
| `system_asset_index_view` | （関連で間接ノイズ） | **`UNCHANGED`** |
| `policy_manifest` | `CHANGE_CANDIDATE`（`related_assets` 経由で index 変更） | **`UNKNOWN` / `BASELINE_MISSING`**（誤った related 伝播なし） |

Phase 1 で確認済みの自己参照 Asset について、**同一内容なら `UNCHANGED`** を達成（現 worktree + 取得済み evidence）。

## Dry Run before / after

| 指標 | Phase 2A（git + related） | Phase 2A.1（fingerprint、baseline 2 件のみ） |
|------|---------------------------|-----------------------------------------------|
| UNCHANGED | 25 | 2 |
| CHANGE_CANDIDATE | 6 | 0 |
| UNKNOWN | 4 | 33 |

件数の単純比較は**成功条件ではない**。2A.1 では 27 VERIFIED のうち **2 件のみ** human-approved baseline capture を実施したため、残りは意図的に `UNKNOWN` + `BASELINE_MISSING`（STALE 断定なし）。

**精度の改善**:

- 一般 `related_assets` だけでは候補を出さない（`policy_manifest` の偽候補解消）
- dirty / 未追跡を evidence に含めた同一 fingerprint で `UNCHANGED`（テストで保証）
- 自己参照レジストリは stable evidence path + post-save refresh で baseline と registry 整合

最新レポート: `reports/project_asset_freshness_candidates.json` / `.md`

## Tests

`tests/registry/test_project_asset_freshness.py`（10）+ `tests/registry/test_project_assets.py`（7）: **17 passed**（`tests/registry/` 全体は `test_skills_registry.py` の既存 schema 失敗 1 件が別件）。

## Registry freshness mutation

- **Checker 実行**: `freshness` 変更 **0**（ツール内ガード）
- **Baseline capture**（今回実行分）: `freshness` 変更 **0**（capture 終了時に before/after 比較）

## Phase 2B readiness

| 項目 | 状態 |
|------|------|
| Evidence + fingerprint 比較 | CONNECTED |
| `related_assets` からの自動候補 | 除去済み |
| `freshness_dependencies` | Schema + 検出 CONNECTED |
| 全 VERIFIED への baseline | **未完了**（27 件中 2 件のみ。捏造なし） |
| `POSSIBLY_STALE` 自動反映 | 未実装（意図どおり） |
| Human Approval / Re-verify Agent | 未実装（意図どおり） |

Phase 2B は**自動開始しない**。次は残り VERIFIED の計画的 baseline capture と Human Review ワークフロー設計。

## 実装ファイル一覧

- `tools/project_asset_verification.py` — watch 解決、evidence、検出
- `tools/check_project_asset_freshness.py` — READ-ONLY dry run
- `tools/capture_project_asset_baselines.py` — baseline 取得（freshness 非変更）
- `registry/schema/verification_evidence.schema.json`
- `registry/schema/project_assets.schema.json`（拡張）
