# MCP Memory — Candidate Research

**Source:** [modelcontextprotocol/servers — src/memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)  
**Package:** `@modelcontextprotocol/server-memory` (Node.js)

## Summary

Knowledge graph 永続化。Tools: `create_entities`, `delete_entities`, `add_observations`, `read_graph`, `search_nodes` 等。

| 性質 | 内容 |
|------|------|
| Side Effect | **write 主体**（グラフ変更） |
| Storage | ローカル JSONL（`MEMORY_FILE_PATH`） |
| Authentication | 不要 |

## 評価

最初の実 Tool には**不適** — [SAFETY_BOUNDARY.md](../SAFETY_BOUNDARY.md) の write 自動実行禁止と衝突。Tool Creation Layer 検証より、将来のメモリ層設計向け。

詳細: [PUBLIC_TOOL_COMPARISON.md](../PUBLIC_TOOL_COMPARISON.md)
