# Common Tool Model (Phase 1 Draft)

## ToolDescriptor

実装: `ai_tool/core/models.py`

```python
@dataclass
class ToolDescriptor:
    id: str                    # 例: "local:cpu_status", "mcp:get_current_time"
    name: str
    provider: "local" | "mcp" | "api" | "other"
    source: str                # registry パス / MCP server ラベル
    description: str
    capabilities: list[str]
    input_schema: dict         # JSON Schema
    output_schema: dict | None
    permissions: list[str]
    risk_level: "low" | "medium" | "high"
    execution_mode: "read" | "write" | "modify"
    availability: "local" | "remote"
    authentication: "none" | "user" | "token" | "oauth" | "unknown"
    cost: "free" | "paid" | "unknown"
    status: "experimental" | "available" | "disabled" | ...
    evidence: list[str]
    # Local bridge fields:
    registry_name, module, function, visibility
```

## ToolExecutionResult

```python
@dataclass
class ToolExecutionResult:
    tool_id: str
    provider: ProviderKind
    ok: bool
    result: Any
    error: str | None
    duration_ms: float | None
    audit_id: str | None
```

## マッピング: registry/tools.json → ToolDescriptor

| registry フィールド | ToolDescriptor |
|---------------------|----------------|
| `name` | `name`, `id=local:{name}` |
| `description` | `description` |
| `keywords` | `capabilities` |
| `input` | `input_schema`（JSON Schema へ変換） |
| `risk` | `risk_level` |
| `visibility` | `permissions` に `visibility:*` |
| `module` / `function` | bridge フィールド |
| （推論） | `execution_mode`（名前・risk から機械推論） |

`execution_mode` の推論は Phase 1 の暫定ルール。将来は registry に明示フィールド追加を検討（**tools.json 変更は Phase 1 外**）。

## マッピング: MCP tools/list → ToolDescriptor

| MCP | ToolDescriptor |
|-----|----------------|
| `name` | `name`, `id=mcp:{name}` |
| `description` | `description` |
| `inputSchema` / `input_schema` | `input_schema` |
| `outputSchema` / `output_schema` | `output_schema` |
| （クライアント設定） | `provider=mcp`, `availability=remote` |
| （ポリシー） | `risk_level`, `execution_mode` はサーバ宣言を信用せずクライアント側で設定 |

MCP 仕様上、tool annotations は信頼できない場合があるため、**risk / execution_mode は MCP Server の宣言だけに依存しない**。

## 手動カタログ

`registry/ai_tool_catalog.json` は `ToolDescriptor` と同一形状の JSON。自動マージはしない。

## 状態ラベル（status）

| 値 | 意味 |
|----|------|
| `available` | Local registry 由来の本番 Tool |
| `experimental` | MCP・実験 Tool |
| `adopt_candidate` | 統合候補（コード上の型として予約） |
| `disabled` | 実行拒否 |
| `not_ready` | 記述のみ・未検証 |

## 既存 Agent Tool 定義との比較

`create_ollama_tools()` が LLM に渡すのは `name`, `description`, `parameters`（JSON Schema）のみ。

`ToolDescriptor` はそれに加え risk, execution_mode, provider, permissions を機械処理用に保持する。Agent 統合時は **LLM 向け subset** と **機械向け full descriptor** を分離する想定。
