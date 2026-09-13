# Implementation Review — `local:workspace_read_text_scoped`

**対象:** `ai_tool/experimental/scoped_read/`  
**Reviewer:** Tool Creation Layer 実Tool完成 Phase 1（機械 + 文書）

## サマリ

| 判定 | 件数 |
|------|------|
| PASS | 11 |
| ISSUE | 3 |
| UNKNOWN | 4 |

**総合: PASS**（ISSUE は experimental 完成を阻害しない。Registry 前に解消推奨）

---

## 観点別

| # | 観点 | 判定 | 根拠 |
|---|------|------|------|
| 1 | Specification 一致 | PASS | output_schema キー、allowlist、side_effect 一致 |
| 2 | allowlist 読込 | PASS | `load_scoped_read_config()` → JSON、ハードコードなし |
| 3 | path normalization | PASS | repo root 基準、`Path.resolve` |
| 4 | traversal 防止 | PASS | `..` in parts 事前拒否 + relative_to |
| 5 | symlink 対策 | PASS | resolve 後 allowlist 再検証（deepest root） |
| 6 | size 制限 | PASS | max_bytes=65536（config） |
| 7 | text/binary 判定 | PASS | sniff + null byte |
| 8 | offset/limit | PASS | 1-based、default 500 lines |
| 9 | error contract | ISSUE | 失敗時 `path` が requested のままのケースあり（成功時は resolved 相対） |
| 10 | output contract | PASS | 成功時全フィールド、error=null |
| 11 | UNKNOWN 補完なし | PASS | 違反時 ok=false、フォールバックなし |
| 12 | hard-coded 安全境界 | ISSUE | 二項判定閾値 0.85、8192 sniff はコード内定数（config 未暴露） |

---

## ISSUE 詳細

### ISSUE-01: error 時の `path` フィールド不一致

- **内容:** 成功時 `path` は repo 相対解決後。失敗時は入力 `path` 文字列をそのまま返すことがある
- **Safety 影響:** なし
- **Contract 影響:** 低（`include_path_in_result` は満たす）
- **推奨:** Registry 前に Specification で明示、または常に `rel_display` に統一

### ISSUE-02: repo 外エラーメッセージ

- **内容:** `PATH_OUTSIDE_REPO` でも `error` 文言は `"path outside allowlist"`
- **Safety 影響:** なし（拒否は正しい）
- **推奨:** メッセージ分離は任意（情報漏洩低減のため現状も許容）

### ISSUE-03: バイナリ sniff 定数

- **内容:** `BINARY_SNIFF_BYTES=8192`、textish 比率 0.85 が `paths.py` 固定
- **推奨:** allowlist JSON へ移すか Specification に「experimental 定数」と明記

---

## UNKNOWN

| ID | 内容 |
|----|------|
| U-01 | `UnicodeDecodeError` 分岐 — `errors=replace` により通常到達しない |
| U-02 | Windows symlink テスト — 権限不足で SKIP |
| U-03 | Windows permission テスト — SKIP |
| U-04 | `.env` 等の explicit deny — allowlist 狭域で間接排除。パターン deny 未実装 |

---

## Tool Contract 対応（[TEST_CONTRACT.md](./TEST_CONTRACT.md) 参照）

| カテゴリ | Contract 要件 | テスト |
|----------|---------------|--------|
| Normal | allowlist 内 text 読取 | test_normal_* |
| Boundary | max_bytes、max_lines、empty | test_boundary_* |
| Invalid | path/dir/offset/limit | test_invalid_* |
| Failure | permission | test_failure_* (SKIP Windows) |
| Safety | traversal/allowlist/symlink/binary | test_safety_* |

詳細映射: [SCOPED_READ_TEST_MATRIX.md](./SCOPED_READ_TEST_MATRIX.md)

---

## コード変更

**今回 Phase:** 実装コード変更なし（レビューのみ PASS）
