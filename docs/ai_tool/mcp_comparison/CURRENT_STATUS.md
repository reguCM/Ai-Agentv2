# MCP Fetch Comparison — Current Status

**更新:** 2026-08-28（Phase 1 Freeze）

## 状態一覧

| 項目 | 状態 |
|------|------|
| MCP Fetch Comparison 実験（14 cases） | **COMPLETE** |
| 対象 Run | `runs/ai_tool/20260828_153335_mcp_fetch_comparison/` |
| Local `read_url_text` | **EXPERIMENTAL**（Registry 未登録） |
| MCP Fetch（`mcp-server-fetch`） | **EXPERIMENTAL / comparison target** |
| 比較ドキュメント | **FROZEN**（`docs/ai_tool/mcp_comparison/`） |
| Agent integration | **NOT READY** |
| Registry integration | **NOT READY** |
| Production MCP connection | **NOT READY** |
| MCP 本番 allowlist / 自動選択 | **NOT STARTED** |

## Local Tool Catalog 状態（既存記録）

```text
tool_status:         unavailable
experiment_status:   experimental
adoption_status:     not_reviewed
```

出典: [tool_creation/READ_URL_COMPLETION_REPORT.md](../tool_creation/READ_URL_COMPLETION_REPORT.md)

## 実験で観測された主要事実（要約）

| 観測 | 出典 |
|------|------|
| 14 ケース実行完了 | `comparison.json` |
| Safety 4 ケースで Local は SSRF ブロック、MCP は localhost/private へ到達したケースあり | `safety_results.json` / `comparison.json` |
| MCP stdio 1 呼び出しあたり総時間中央値 ≈ **985 ms**（cold start 含む） | `outputs.json` → `execution` |
| 既存 `MCPToolProvider.list_descriptors()` は当 Run 環境で **失敗** | `outputs.json` → `execution.existing_mcp_provider_list_ok: false` |
| MCP tool `annotations` は Run 時 **null** | `outputs.json` → `mcp_descriptor.annotations` |

## 位置づけ

```text
local:read_url_text
    ↓ experimental
    ↓ MCP Fetch との比較材料を取得（Phase 1）
    ↓ 正式採用判断には直結しない
```

既存 `read_file` の置換対象ではない。
