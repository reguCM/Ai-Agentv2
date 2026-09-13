# Local Implementation Report — `local:workspace_read_text_scoped`

**日付:** 2026-08-28  
**Run:** `runs/ai_tool/20260828_055850_scoped_filesystem_read/scoped_filesystem_read/`

## 実装

| 項目 | 値 |
|------|-----|
| 実装 Path | `ai_tool/experimental/scoped_read/` |
| Tool ID | `local:workspace_read_text_scoped` |
| Provider | local（experimental、Registry 未登録） |
| エントリ関数 | `workspace_read_text_scoped(path, offset=None, limit=None)` |
| Input | `{"path": "<repo-relative>"}`（offset/limit は任意） |
| Output | Specification `output_schema`（`ok`, `path`, `content`, `root_id`, …） |

### モジュール構成

```text
ai_tool/experimental/scoped_read/
  config.py   — allowed_roots.experimental.json 読込
  paths.py    — repo root / allowlist / binary sniff
  reader.py   — workspace_read_text_scoped
```

## Safety

| 項目 | 実装 |
|------|------|
| allowlist | JSON 3 ルート、最深マッチ root_id |
| traversal | `..` セグメント事前拒否 |
| symlink | `Path.resolve()` 後に allowlist 再検証 |
| absolute path | repo 内かつ allowlist 内のみ許可 |
| size | `max_bytes=65536`（config、experimental 明示） |
| text | バイナリ sniff 拒否、UTF-8 `errors=replace` |
| read-only | write/delete 等の API なし |

## 既存 `read_file` との非置換

| 項目 | `read_file`（本番） | `workspace_read_text_scoped` |
|------|---------------------|------------------------------|
| Scope | workspace 全体 | allowlist 3 ルート |
| Output | `lines[]` | `content` 文字列 |
| Registry | 登録済 | **未登録** |
| 用途 | Agent 本番 | Tool Creation 実験 |

詳細: [EXISTING_READ_FILE_RELATION.md](./EXISTING_READ_FILE_RELATION.md)

## Tests

```text
Scoped tests:          30 passed, 2 skipped, 0 failed
Tool Creation tests:   35 passed, 0 failed
```

スキップ: symlink（Windows 権限）、chmod permission（Windows 非対応）

## Safety metrics

```text
false_accept:    0
false_reject:    0
unsafe_accept:   0
UNKNOWN→OK:      0（暗黙変換なし）
```

## Audit

既存 `ai_tool.core.audit.append_audit` を**変更せず**利用。  
実験 run 内: `audit.jsonl`（requested/resolved path, allowlist_decision, failure_reason）

## Catalog

正式 Registry 登録なし。Draft: run 内 `catalog_draft.json`

## 変更範囲

```text
agent.py        unchanged
tools/          unchanged
registry/       unchanged
read_file       unchanged
MCP             untouched
diagnostic FW   unchanged
```

## 未解決（UNKNOWN）

| 項目 | 状態 |
|------|------|
| `tool_status` に `experimental` enum | Schema は `unavailable` のみ — `catalog_hints.experiment_status=experimental` で表現 |
| Symlink テスト | Windows では symlink 作成権限不足時 SKIP |
| Permission denied テスト | Windows では SKIP |
| `max_lines_default=500` | Specification に output フィールド未定義 — config experimental 値として実装 |
| 複数 allowlist root 重叠時 root_id | **実装判断:** 最深（最長パス）root を採用（テストで検証） |

## STOP 条件

本 Phase 完了。以下には未着手:

Agent 統合 / Registry / MCP / read_file 変更
