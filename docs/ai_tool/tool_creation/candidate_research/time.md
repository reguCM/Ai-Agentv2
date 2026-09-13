# MCP Time — Candidate Research（ベースライン）

**Source:** [modelcontextprotocol/servers — src/time](https://github.com/modelcontextprotocol/servers/tree/main/src/time)  
**本プロジェクト:** [ai_tool/providers/mcp/time_server.py](../../../../ai_tool/providers/mcp/time_server.py)（簡略版）

## Phase 1 実績

- EXP-001: Local vs MCP `get_current_time` 成功（[experiments/EXP-001](../../experiments/EXP-001_local_vs_mcp_time.md)）
- **最初の自作 Tool としての新規性は低い**

## 公式 vs 自作

| | 公式 `mcp-server-time` | 本プロジェクト time_server |
|--|------------------------|---------------------------|
| Tools | `get_current_time`, `convert_time` | `get_current_time` のみ |
| Input | `timezone` (IANA) 必須 | なし |
| Output | structured JSON | ISO8601 文字列 |

## 再利用価値

- Local/MCP 比較パイプラインの**ベースライン**
- Tool Specification / Provider / Audit の参照実装
- 新規題材としては優先度低

詳細: [PUBLIC_TOOL_COMPARISON.md](../PUBLIC_TOOL_COMPARISON.md)
