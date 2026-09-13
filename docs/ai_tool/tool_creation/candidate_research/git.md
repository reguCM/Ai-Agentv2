# MCP Git — Candidate Research

**Source:** [modelcontextprotocol/servers — src/git](https://github.com/modelcontextprotocol/servers/tree/main/src/git)  
**Package:** `mcp-server-git` (Python, uvx)

## Summary

| Tool例 | 性質 |
|--------|------|
| `git_status`, `git_diff*`, `git_log`, `git_show`, `git_branch` | read 系 |
| `git_commit`, `git_add`, `git_reset`, `git_checkout`, `git_create_branch` | write/modify 系 |

**Input 共通:** `repo_path`（リポジトリスコープ）

## AI-Agent との関係

- 本プロジェクトは Git リポジトリ — 実用価値は高い
- 公式 Server は **read/write 混在** — 最初の実 Tool には read-only サブセット抽出が必要
- write tool 含む公式 MCP をそのまま接続すると [SAFETY_BOUNDARY.md](../SAFETY_BOUNDARY.md) と衝突

## 評価

| 観点 | 評価 |
|------|------|
| 実装難度 | 中（git CLI / GitPython） |
| Safety | write 混在でリスク高 — 初手には不向き |
| Test Contract | 中（temp git repo） |
| MCP 比較 | 中（多 tool、read 限定が手間） |

詳細: [PUBLIC_TOOL_COMPARISON.md](../PUBLIC_TOOL_COMPARISON.md)
