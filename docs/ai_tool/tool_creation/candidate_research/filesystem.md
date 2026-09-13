# MCP Filesystem — Candidate Research

**Source:** [modelcontextprotocol/servers — src/filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)  
**Package:** `@modelcontextprotocol/server-filesystem` (Node.js, npx)

## Summary

| 項目 | 内容 |
|------|------|
| Tool数 | 多数（read / write 混在） |
| Read-only tools | `read_text_file`, `read_media_file`, `read_multiple_files`, `list_directory`, `search_files`, `get_file_info`, `directory_tree`, `list_allowed_directories` 等 |
| Write tools | `write_file`, `edit_file`, `move_file`, `create_directory` 等 |
| Access control | CLI 引数または MCP Roots で allowed directories |
| Annotations | 各 tool に `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint: false` |

## Safety 論点（深掘り）

- **allowed path** — サーバ起動時または Roots でスコープ
- **path traversal** — 実装が正規化・検証（要実地確認、公式は allowed 外拒否）
- **read vs write** — annotations で機械的区別（クライアントは信用しない — [PROVIDER_BOUNDARY.md](../PROVIDER_BOUNDARY.md)）
- **size** — `head`/`tail` で部分読み取り可能
- **binary** — `read_media_file` は base64

## AI-Agent との関係

- 本番 Registry に `list_files`, `read_file`, `search_files` **既存**（`tools/file/workspace/`）
- 最初の実 Tool は**既存 Tool の置換ではなく**、Tool Creation Layer 検証用の**新規 experimental Tool** として設計すべき（[TOOL_CHANGE_POLICY.md](../TOOL_CHANGE_POLICY.md)）
- read-only サブセットのみなら Safety Boundary の実地検証に最適

## Tool Creation Layer 適合

| 観点 | 評価 |
|------|------|
| Specification 明確性 | 高（path + optional head/tail） |
| Test Contract | **高**（temp dir で決定論的） |
| Safety 検証価値 | **最高**（allowlist + traversal） |
| MCP 比較 | 高（read tool のみ接続） |
| 実用重複 | 中（既存 file tools あり） |

詳細比較: [PUBLIC_TOOL_COMPARISON.md](../PUBLIC_TOOL_COMPARISON.md)
