# MCP Fetch — Candidate Research

**Source:** [modelcontextprotocol/servers — src/fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch)  
**Package:** `mcp-server-fetch` (Python, uvx)

## Summary

| 項目 | 内容 |
|------|------|
| Tool名 | `fetch`（1 tool） |
| Input | `url` (required), `max_length`, `start_index`, `raw` |
| Output | Markdown 化された本文（chunk 対応） |
| Side Effect | read-only（ネットワーク取得） |
| Annotations | 公式 README に ToolAnnotations 表なし（Fetch は単一 tool） |
| Network | **あり** |
| Risk | **中〜高**（SSRF・内部 IP・robots.txt） |

## Safety 論点（深掘り）

- 公式 **CAUTION**: ローカル/内部 IP アクセス可能 → SSRF リスク
- `max_length` デフォルト 5000 — サイズ制限あり
- HTTP error / timeout — 実装依存（要 Test Contract Failure カテゴリ）
- redirect / content-type — 実装依存
- robots.txt — ツール経由はデフォルト遵守、プロンプト経由は別

## AI-Agent との関係

- 既存 `search_web` は**検索ヒット一覧**（title/snippet/url）。Fetch は**単一 URL 本文** — 用途は非重複
- [SAFETY_BOUNDARY.md](../SAFETY_BOUNDARY.md): `network_access: true` → 外部 Tool は `human_required` デフォルト
- MCP SDK: 公式は **MCP 1.x 必須**、本プロジェクト AI-TOOL は **MCP 2.x** — 接続実験時は要注意（[CURRENT_STATUS.md](../../CURRENT_STATUS.md)）

## Tool Creation Layer 適合

| 観点 | 評価 |
|------|------|
| Specification 明確性 | 高 |
| Test Contract | 中（ネットワークで非決定論的） |
| Local 無料実装 | 可（urllib/httpx + allowlist） |
| MCP 比較 | 高（単一 tool） |

詳細比較: [PUBLIC_TOOL_COMPARISON.md](../PUBLIC_TOOL_COMPARISON.md)
