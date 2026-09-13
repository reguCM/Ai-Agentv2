# Experimental Allowlist Policy — Scoped Filesystem Read

**状態:** ADOPT CANDIDATE（実験用。本番 Tool 設定ではない）  
**対象 Tool（案）:** `local:workspace_read_text_scoped`

## 目的

最初の自作実 Tool（Scoped Filesystem Read）において、**読み取り可能なパスを機械的に限定**する。  
本番 `read_file`（workspace 全体）とは**別系統**の狭い allowlist で Safety Boundary を実証する。

関連: [PUBLIC_TOOL_COMPARISON.md](./PUBLIC_TOOL_COMPARISON.md) / [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) / [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md)

## 設定ファイル

```text
docs/ai_tool/tool_creation/allowed_roots.experimental.json
```

実装時はこの JSON を読み取り専用で参照する。Registry や `registry/tools.json` には**マージしない**。

## 許可ルート（Phase: First Tool 実装前）

| ID | 相対パス | 用途 |
|----|----------|------|
| `ai_tool_docs` | `docs/ai_tool/` | 設計ドキュメント |
| `ai_tool_runs` | `runs/ai_tool/` | 実験結果・監査ログ |
| `tool_creation_specs` | `docs/ai_tool/tool_creation/specs/` | Specification 自己参照テスト |

**意図的に許可しない例:**

- リポジトリ全体（本番 `read_file` のスコープ）
- `.env` / 認証情報ディレクトリ
- `tools/` 本番実装の直接読取（実験 Tool が本番コードに依存しない設計検証のため）

## パス解決ルール

| ルール | 内容 |
|--------|------|
| リポジトリ root 基準 | `registry/tools.json` の存在で root 確定（既存 `_paths.workspace_root()` と同思想） |
| `..` 拒否 | パスセグメントに `..` を含む入力は拒否 |
| root 外拒否 | `relative_to(repo_root)` 失敗時は error |
| 絶対パス | repo root 配下に解決できなければ拒否 |
| symlink | 解決後の実パスが allowlist root 外なら拒否（実装時必須） |
| ディレクトリ | **ファイルのみ**（`allow_directories: false`） |

詳細な error dict 形式は [EXISTING_READ_FILE_RELATION.md](./EXISTING_READ_FILE_RELATION.md) を参照。

## サイズ・形式制限

| 項目 | 値 |
|------|-----|
| 最大バイト | 65536（64 KiB。既存 `read_file` の `READ_MAX_BYTES` と同値） |
| デフォルト最大行数 | 500（`limit` 未指定時の実装方針。Specification 参照） |
| エンコーディング | UTF-8、`errors=replace` |
| バイナリ | 拒否（既存 `is_probably_binary` 相当の sniff） |

## Safety 分類

| フィールド | 値 |
|------------|-----|
| `side_effect` | `read_only` |
| `network_access` | `false` |
| `filesystem_access` | `read` |
| `risk_level` | `low`（allowlist 内）/ path 違反時は error のみ（副作用なし） |

Interface 互換と Safety 互換の分離は [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) を参照。

## 変更手順

1. `allowed_roots.experimental.json` を変更
2. [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) に従い Compatibility 分類を記録
3. Specification `version` bump（ルール未確定 — [MCP_SDK_COMPATIBILITY.md](./MCP_SDK_COMPATIBILITY.md) 参照）
4. pytest（allowlist 違反ケース）を更新
5. **人間承認後**のみ実装・Registry 検討

## MCP 公式 Filesystem との関係

公式 `@modelcontextprotocol/server-filesystem` は起動引数または MCP Roots で allowed directories を設定。  
本プロジェクトの experimental allowlist は **より狭いサブセット** とし、公式 Server 接続実験時は同じ 3 ルートのみを npx 引数に渡す（実装 Phase で実施）。

## 状態

| 項目 | ラベル |
|------|--------|
| ポリシー文書 | ADOPT CANDIDATE |
| 実行時 enforce | NOT READY（実装待ち） |
| Registry 反映 | NOT READY |
