# Local `read_url_text` vs MCP Fetch — Documentation Only

**状態:** ADOPT CANDIDATE（比較記録。MCP 接続なし）

| 項目 | Local `local:read_url_text` | MCP Fetch (`mcp-server-fetch`) |
|------|----------------------------|--------------------------------|
| Provider | experimental local | MCP 公式 |
| Method | GET only | GET |
| Output | `content` 文字列 + HTTP metadata | markdown 変換本文 |
| SSRF | DNS + IP + redirect 再検証（不完全 — 政策参照） | 公式 CAUTION: 内部 IP 可能 |
| max_length | max_bytes 65536 | デフォルト 5000 |
| Network | urllib stdlib | 独自実装 |
| Registry | 未登録 | 外部 Server |
| SDK | N/A | MCP 1.x 記載（本プロジェクト 2.x） |

## 意図的差別化

- Local: Tool Creation Layer 検証用、最小 GET
- MCP: markdown 変換、chunk、robots.txt 等

## 参照

- [URL_FETCH_SAFETY_POLICY.md](./URL_FETCH_SAFETY_POLICY.md)
- [candidate_research/fetch.md](./candidate_research/fetch.md)
- [MCP_SDK_COMPATIBILITY.md](./MCP_SDK_COMPATIBILITY.md)
