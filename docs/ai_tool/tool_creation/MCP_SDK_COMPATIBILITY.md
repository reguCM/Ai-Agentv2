# MCP SDK Compatibility — AI-TOOL Layer

**状態:** EXPERIMENTAL（調査メモ。運用ルールは未確定）

## 背景

| コンポーネント | MCP SDK |
|----------------|---------|
| 本プロジェクト AI-TOOL（`ai_tool/`） | **2.x**（`mcp>=2.1,<3`） |
| 自作 `time_server` | MCP 2.x `MCPServer` |
| 公式 Fetch / Git / Time README | **1.x 必須**（`mcp>=1.29.0,<2`）と明記 |
| 公式 Filesystem | Node.js（`@modelcontextprotocol/server-filesystem`） |

## 既知の差分（Phase 1 実験より）

| Wire / モデル | MCP 1.x クライアント想定 | MCP 2.x（本プロジェクト） |
|---------------|---------------------------|---------------------------|
| Tool schema フィールド | `inputSchema` | `input_schema` |
| エラーフラグ | `isError` | `is_error` |
| 構造化結果 | `structuredContent` | `structured_content` |

対応: `ai_tool/providers/mcp/provider.py` で両方吸収済み。

## 公式 Reference Server 接続方針（案）

| Server | 推奨接続 | 備考 |
|--------|----------|------|
| **Time** | 自作 `time_server`（2.x）を継続 | EXP-001 済み |
| **Filesystem read** | npx Node server | Python SDK 版ではない。stdio クライアントは共通 |
| **Fetch** | 別 venv で `mcp-server-fetch`（1.x）または SDK 2 対応待ち | README: v2 port in progress |
| **Git** | 同上（1.x） | read-only 比較は将来 |

### 実験時の原則

1. **本番 `.venv` の MCP 2.x を無理に downgrade しない**
2. 公式 Python Server が 1.x 固定の場合:
   - **Option A:** 別プロセス / 別 venv で 1.x クライアント実験（隔離）
   - **Option B:** 自作 MCP 2.x 参照 Server で同等 tool のみ実装（Time と同様）
   - **Option C:** Node Filesystem は npx で起動し、MCPToolProvider は transport のみ共有
3. 接続は `runs/ai_tool/` 配下の実験のみ。Agent 本番統合は NOT READY

## Filesystem MCP 比較（Scoped Read 実装時）

```text
Local:  workspace_read_text_scoped (Python, allowlist JSON)
MCP:    npx @modelcontextprotocol/server-filesystem <3 allowed dirs>
        tool: read_text_file のみ使用
```

allowlist ディレクトリは [allowed_roots.experimental.json](./allowed_roots.experimental.json) の 3 ルートを npx 引数に渡す。

## Versioning（FUTURE / UNKNOWN）

| 項目 | 状態 |
|------|------|
| Tool Specification `version` bump 規則 | UNKNOWN |
| MCP SDK メジャーアップ時の Provider 互換層 | FUTURE CONSIDERATION |
| 公式 Server の MCP 2.x 正式対応時期 | UNKNOWN（upstream 追跡） |

## 参照

- [CURRENT_STATUS.md](../../CURRENT_STATUS.md) — AI-TOOL Phase 1
- [PROVIDER_BOUNDARY.md](./PROVIDER_BOUNDARY.md)
- [PUBLIC_TOOL_COMPARISON.md](./PUBLIC_TOOL_COMPARISON.md)
