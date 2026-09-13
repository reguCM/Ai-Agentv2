# External Tool Research — Summary

Phase 2 調査の要約。詳細は [external_tool_research/](./external_tool_research/) を参照。

## 優先順位と結論

| 順位 | 方式 | 状態 | AI-Agent Phase 1 での位置づけ |
|------|------|------|-------------------------------|
| 1 | **Model Context Protocol (MCP)** | 採用（実験） | `MCPToolProvider` で最小接続 |
| 2 | **OpenAI Apps SDK** | 調査済 | MCP 上に構築。UI/リソース拡張は Phase 1 外 |
| 3 | MCP 対応 Tool / Server | 調査済 | 公開 Server は allowlist 前提で将来 |
| 4 | 旧 ChatGPT Plugin | 対象外 | Apps SDK + MCP に置き換え済み |
| 5 | その他 Plugin 方式 | UNKNOWN | 未調査 |

## MCP（採用理由）

- オープン標準（JSON-RPC 2.0）
- Tool discovery: `tools/list`
- Tool 実行: `tools/call`
- metadata: `name`, `description`, `inputSchema`, 任意 `outputSchema`
- トランスポート: stdio, HTTP 等
- OpenAI Apps SDK の基盤

**注意:** 仕様は tool annotations を信頼できない場合があると明記。クライアント側で risk / execution_mode を再判定する必要がある。

公式: [MCP Tools Specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

## OpenAI Apps SDK

- ChatGPT 内アプリ向け。**MCP Server が必須**
- オプションで Web UI（iframe + MCP Apps bridge）
- Developer Mode で HTTPS `/mcp` エンドポイントを登録
- AI-Agent は ChatGPT ホストではないため、**MCP クライアント部分のみ参考**にする

公式: [Apps SDK Quickstart](https://developers.openai.com/apps-sdk/quickstart)

## 既存 AI-Agent Tool との差分

| 観点 | AI-Agent Local | MCP |
|------|----------------|-----|
| 登録 | `registry/tools.json` 手動 | Server 側 `tools/list` |
| スキーマ | registry `input` 形式 | JSON Schema |
| 実行 | Python import | RPC `tools/call` |
| 可視性 | `visibility` フィールド | クライアントポリシー |
| 安全 | `agent_tool_gate` | クライアント実装必須 |

## Phase 1 で採用しなかったもの

- 公開 MCP Server の大量接続
- HTTP/SSE トランスポート（stdio のみで十分と判断）
- Apps SDK UI / Resources
- OAuth 付き外部 API Tool
- 有料 API

## 参照ドキュメント

- [mcp_overview.md](./external_tool_research/mcp_overview.md)
- [openai_apps_sdk.md](./external_tool_research/openai_apps_sdk.md)
