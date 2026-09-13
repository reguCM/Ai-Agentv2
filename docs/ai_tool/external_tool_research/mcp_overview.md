# MCP Overview (Research Notes)

調査日: 2026-08-28  
公式仕様を優先。

## 概要

Model Context Protocol (MCP) は、LLM アプリケーションと外部データ・Tool を接続するオープン標準。JSON-RPC 2.0 ベース。

## Tool 関連プロトコル

### Capability

Server は初期化時に `tools` capability を宣言。

```json
{
  "capabilities": {
    "tools": {
      "listChanged": true
    }
  }
}
```

### tools/list

クライアントが利用可能 Tool を列挙。ページネーション対応。

レスポンスの各 Tool:

- `name` — 一意識別子
- `description` — 人間可読説明
- `inputSchema` — JSON Schema（パラメータ）
- `outputSchema` — 任意
- `annotations` — 動作ヒント（**信頼できない場合あり**）

### tools/call

```json
{
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": { "location": "New York" }
  }
}
```

結果は `content`（text / image 等）、任意 `structuredContent`、`isError` フラグ。

## トランスポート

- **stdio** — ローカル subprocess（Phase 1 で採用）
- **Streamable HTTP** — リモート Server
- **SSE** — レガシー

## Python SDK（本プロジェクト）

- パッケージ: `mcp>=2.1,<3`（`ai_tool/requirements.txt`）
- Server: `MCPServer`（旧 FastMCP）
- Client: `ClientSession` + `stdio_client`

## AI-Agent への示唆

1. **Discovery と Execution を分離** — MCP は既存設計と整合
2. **metadata は list 時点で取得可能** — LLM 推測不要
3. **annotations は二次判定** — risk / execution_mode はクライアント側
4. **プロセス境界** — stdio は安全境界の一例だが、Server コード自体は信頼対象の選別が必要

## 公開 MCP Server 例（調査のみ・未接続）

filesystem, fetch, time 系などがコミュニティで流通。Phase 1 では自作 `time_server` のみ使用。

## リンク

- [Tools — MCP Specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP GitHub](https://github.com/modelcontextprotocol)
