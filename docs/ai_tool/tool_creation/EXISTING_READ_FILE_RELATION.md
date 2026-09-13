# 既存 `read_file` との関係 — 非置換方針

**対象:** 実 Tool 候補 `local:workspace_read_text_scoped`（**experimental 完成** — [TOOL_COMPLETION_REPORT.md](./TOOL_COMPLETION_REPORT.md)）  
**方針:** [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) — **置換しない・並立する**

## 比較表

| 項目 | 本番 `read_file` | 実験 `workspace_read_text_scoped` |
|------|------------------|-----------------------------------|
| Registry | `registry/tools.json`（変更しない） | **未登録**（experimental） |
| モジュール | `tools.file.workspace.read_file` | `ai_tool.experimental.scoped_read.reader` |
| スコープ | **workspace 全体**（repo root） | **allowlist 3 ルートのみ** |
| 設定 | `_paths.workspace_root()` | `allowed_roots.experimental.json` |
| visibility | `agent` | `experimental`（案） |
| 出力形式 | `lines[]`（行番号付き配列） | `content` 文字列 + metadata（**意図的に差別化**） |
| offset/limit | あり | あり（同等セマンティクス） |
| サイズ上限 | 64 KiB | 64 KiB（同値） |
| バイナリ | 拒否 | 拒否 |

## なぜ別 Tool か

1. **Tool Creation Layer 検証** — Specification / Contract / allowlist を最初から設計
2. **Safety 実証** — 本番 workspace 全体ではなく狭い allowlist で traversal テスト
3. **非破壊** — 既存 Agent・`read_file` 利用者に影響なし
4. **MCP 比較** — 単機能（read text）に絞った Local/MCP 対照実験

## 共通の安全思想（既存コードから借用せず、仕様として再定義）

本番 `tools/file/workspace/_paths.py` の挙動を参考にした**仕様上の要件**（コピー実装は将来 Phase）:

- `..` セグメント拒否
- workspace/repo root 外拒否
- バイナリ sniff 拒否
- サイズ上限
- 失敗時 `ok: false` + `error`（黙って別パスへフォールバックしない）

**本番 `_paths.py` は今回変更しない。**

## Breaking Change ではない理由

- 新 `tool_id`、新 Registry エントリなし
- 既存 `read_file` のシグネチャ・戻り値は不変
- Catalog / Specification は別ファイル

## 将来の統合パス（UNKNOWN）

- experimental が成功 → 別途「本番 read_file への Safe Extension」か「置換」かを [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) で判断
- 現時点では**統合しない**

## 参照

- [ALLOWLIST_POLICY.md](./ALLOWLIST_POLICY.md)
- [specs/local_workspace_read_text_scoped.json](./specs/local_workspace_read_text_scoped.json)
