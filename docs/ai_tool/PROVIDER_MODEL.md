# Provider Model (Phase 1)

## 概念

```text
AI-TOOL
├── LocalToolProvider      [実装済・ADOPT CANDIDATE]
├── MCPToolProvider        [実装済・EXPERIMENTAL]
├── APIToolProvider        [未実装・UNKNOWN]
└── FutureProvider         [未実装]
```

Provider は **Discovery + Execution** を担う。選択（Selector）と安全判定（Validator）は Provider 外。

## LocalToolProvider

**パス:** `ai_tool/providers/local/provider.py`

| メソッド | 説明 |
|----------|------|
| `list_descriptors(visibility=?)` | `registry/tools.json` を `ToolDescriptor` 化 |
| `get_descriptor(tool_id)` | ID または registry name で検索 |
| `execute(tool_id, arguments)` | `importlib` で既存関数を呼び出し |

既存 `execute_tool()` と同じ実行経路（module/function）だが、**gate や会話コンテキストは含まない**。Phase 1 の比較・実験用。

### 参照実装

`local_get_current_time()` — registry 外の read-only 時刻取得。MCP `get_current_time` との比較用。

## MCPToolProvider

**パス:** `ai_tool/providers/mcp/provider.py`

| メソッド | 説明 |
|----------|------|
| `list_descriptors()` | stdio で MCP Server に接続し `tools/list` |
| `call_tool(name, arguments)` | `tools/call` |

### 参照 MCP Server

**パス:** `ai_tool/providers/mcp/time_server.py`

- `MCPServer("ai-tool-time-server")`（MCP Python SDK 2.x）
- Tool: `get_current_time()` → UTC ISO8601 文字列
- トランスポート: stdio のみ

### 制約（Phase 1）

- read-only Tool のみ想定
- 1 Server / 1 Tool で最小経路を検証
- 呼び出しごとに subprocess 起動（プール未実装）

### MCP SDK 互換メモ

MCP Python SDK 2.x は Pydantic モデルで `input_schema` / `is_error` / `structured_content`（snake_case）。Wire 上の JSON は `inputSchema` 等の camelCase。Provider 内で両方を吸収。

## ToolCatalog

**パス:** `ai_tool/registry/catalog.py`

| メソッド | 説明 |
|----------|------|
| `list_all_descriptors(include_mcp_live)` | local + 手動カタログ +（任意）live MCP |
| `summarize_for_agent_view()` | LLM 向け metadata subset |
| `safety_report()` | 全 Tool の `evaluate_tool_safety` 結果 |
| `audit_discovery()` | discovery イベントを監査ログへ |

## Provider 選択方針（将来）

```text
tool_id prefix:
  local:*  → LocalToolProvider
  mcp:*    → MCPToolProvider（server 設定は catalog / config）
  api:*    → APIToolProvider（未実装）
```

Phase 1 ではルーティング層は未実装。実験スクリプトが Provider を直接呼ぶ。

## 既存 Local Tool を LocalToolProvider として扱えるか

**はい。** `registry/tools.json` の全 21 Tool を `list_descriptors()` で変換可能。`visibility=="agent"` は 7 件（実験ログ参照）。
