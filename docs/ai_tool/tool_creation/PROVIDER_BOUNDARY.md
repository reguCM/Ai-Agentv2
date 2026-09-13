# Provider Boundary

Tool **そのもの**（Logical）と **実装方式**（Physical / Provider）の境界。

**状態:** EXPERIMENTAL（文書化完了。Interface 完全実装は NOT READY）

## 概念

```text
Tool (Logical)
 │
 ├── Local Provider    → tools/*.py + registry/tools.json
 ├── MCP Provider      → MCP Server + tools/list, tools/call
 ├── API Provider      → HTTP client + OpenAPI 等
 └── External Provider → 未分類
```

Phase 1 AI-TOOL 実装（`ai_tool/providers/`）は**参照実装**。本 Phase では MCP を新規実装しない。

## 共通化する情報（全 Provider）

| 領域 | フィールド | ラベル |
|------|------------|--------|
| Identity | tool_id, name, version, description, provider, source | ADOPT CANDIDATE |
| Capability | capability, purpose, allowed/prohibited_operations | ADOPT CANDIDATE |
| I/O | input_schema, output_schema, error_format | ADOPT CANDIDATE |
| Side Effect | side_effect | ADOPT CANDIDATE |
| Security | risk_level, authentication, network/filesystem access | ADOPT CANDIDATE |
| Cost | cost | ADOPT CANDIDATE |
| Contract | can/cannot/must/must_not | ADOPT CANDIDATE |
| Lifecycle | tool_status, experiment_status, adoption_status | EXPERIMENTAL |

## Provider 固有にすべき情報（provider_specific）

### Local

```json
{
  "module": "tools.system.gpu.gpu_status",
  "function": "get_gpu_status",
  "registry_visibility": "agent",
  "registry_path": "registry/tools.json"
}
```

### MCP（将来接続）

```json
{
  "mcp_server_label": "ai-tool-time-server",
  "transport": "stdio",
  "server_command": ["python", "-m", "ai_tool.providers.mcp.time_server"],
  "mcp_tool_name": "get_current_time"
}
```

### API（未実装）

```json
{
  "base_url": "UNKNOWN",
  "method": "GET",
  "path": "/v1/...",
  "auth_header": "UNKNOWN"
}
```

## MCP との境界（Phase 10 — 実装なし）

MCP Server から取得できる情報と Tool Specification の対応:

| MCP（tools/list） | Tool Specification | 備考 |
|-------------------|-------------------|------|
| `name` | `name`, `tool_id` 生成 | ADOPT CANDIDATE |
| `description` | `description` | ADOPT CANDIDATE |
| `inputSchema` | `input_schema` | ADOPT CANDIDATE |
| `outputSchema` | `output_schema` | EXPERIMENTAL（任意） |
| `annotations` | **信用しない** → `provider_specific.mcp_annotations` | MUST 再判定 |
| permissions | MCP に標準なし | `provider_specific` または Catalog ポリシー |
| side effects | annotations のみ（非信頼） | `side_effect` はクライアント定義 |
| version | MCP Tool になし | Specification 側で管理 |
| contract | なし | Tool Contract を別途定義 |

### MCP に存在しない情報 → UNKNOWN / provider_specific

- `tool_id`（命名規則 `mcp:{name}` はクライアント規約）
- `experiment_status` / `adoption_status`
- `cost`（通常 `free` または `unknown`）
- Tool Contract（must_not 等）

### 将来パス（設計のみ）

```text
MCP Server
    ↓ tools/list
MCP Tool Definition
    ↓ 機械マッピング + 人間レビュー
Tool Specification
    ↓
Tool Catalog Entry（手動承認）
```

自動 Catalog 登録は **NOT READY**。

## ai_tool パッケージとの関係

| ai_tool コンポーネント | Tool Creation Layer |
|------------------------|---------------------|
| `ToolDescriptor` | Catalog Entry の実装ドラフト |
| `LocalToolProvider` | Local の Discovery/Execution |
| `MCPToolProvider` | MCP の Discovery/Execution（実験） |
| `evaluate_tool_safety` | Validator の一部 |

`ToolDescriptor` と Tool Specification は**近いが同一ではない**。将来マージ候補（EXPERIMENTAL）。

## Provider Interface（将来）

```text
class ToolProvider(Protocol):
    def list_descriptors() -> list[ToolDescriptor]
    def execute(tool_id, arguments) -> ToolExecutionResult
```

Phase 1 では Protocol 未実装。文書上の境界のみ確定。

## 状態サマリ

| 項目 | ラベル |
|------|--------|
| 共通化範囲の定義 | ADOPT CANDIDATE |
| MCP マッピング表 | EXPERIMENTAL |
| Provider Interface 実装 | NOT READY |
| API Provider | UNKNOWN |
