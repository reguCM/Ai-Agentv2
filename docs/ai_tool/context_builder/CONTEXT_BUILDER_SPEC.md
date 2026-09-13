# Tool Development Context Builder — Specification (Phase 1)

**状態:** EXPERIMENTAL  
**Component:** `ai_tool.context_builder`

## 目的

Tool 開発・変更時に LLM / Cursor / 人間へ渡すべき関連情報を**機械的に収集・整理**する。  
LLM の推論改善ではなく、「何を渡すべきか」の Manifest 生成が目的。

## 入力

```json
{
  "tool_id": "local:workspace_read_text_scoped",
  "fetch_content": true,
  "compression": "full"
}
```

| フィールド | 必須 | 説明 |
|------------|------|------|
| `tool_id` | yes | Tool 識別子 |
| `fetch_content` | no | `true` なら scoped read で本文取得 |
| `compression` | no | `full`（全文）または `none`（Manifest のみ） |

## 出力

```json
{
  "status": "OK",
  "tool_id": "...",
  "manifest": { "tool_id": "...", "slots": { ... } },
  "selected_files": [ ... ],
  "missing_slots": [ ... ],
  "excluded_files": [ ... ],
  "warnings": [ ... ],
  "content": { "path": "...", "text": "..." }
}
```

`status`: `OK`（P0 全 slot 解決）| `PARTIAL`（P0 欠落）| `ERROR`

## Fixed Slots

| Slot | 優先度 | 内容 |
|------|--------|------|
| identity | P0 | tool_id, provider, module, spec_ref |
| specification | P0 | Tool Specification |
| contract | P0 | contract ブロック + TOOL_CONTRACT.md |
| implementation | P0 | 実装パス（allowlist 外は参照のみ） |
| tests | P0 | Test Contract + テストパス参照 |
| safety | P0 | Safety Boundary + allowlist 等 |
| change_policy | P1 | TOOL_CHANGE_POLICY.md |
| catalog | P1 | CATALOG.md |
| known_limitations | P1 | spec.known_limitations |
| related_context | P2 | mapping / 実装レポート等 |

欠落時: `{"status": "UNKNOWN", "reason": "NOT_FOUND"}` — **推測で埋めない**

## 本文取得

```text
Manifest（何を渡すか）
    ↓
workspace_read_text_scoped（allowlist 内のみ）
    ↓
content map
```

`scoped_read` は変更しない。呼び出すのみ。

## Safety

- allowlist 外は本文取得しない（参照メタデータのみ）
- `.env` / credentials / token 等は `EXCLUDED_SENSITIVE`
- Tool ID から任意 Path を生成しない（rules JSON のみ）
- LLM 要約・自動送信なし

## 監査

各 selected_file に `path`, `slot`, `reason`, `priority` を記録。

## 参照

- [selection_rules.json](./selection_rules.json)
- [OVERLAP_ANALYSIS.md](./OVERLAP_ANALYSIS.md)
