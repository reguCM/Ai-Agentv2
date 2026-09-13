# Behavior Comparison — Local vs MCP Fetch

**Run:** `runs/ai_tool/20260828_153335_mcp_fetch_comparison/`

安全性以外の挙動差。14 ケースで未確認の項目は **NOT TESTED** / **UNKNOWN** と明記。

---

## Interface（OBSERVED — Run `outputs.json` / `comparison.json`）

| 項目 | Local `read_url_text` | MCP `fetch` |
|------|----------------------|-------------|
| tool_id | `local:read_url_text` | `mcp:fetch` |
| input: url | required | required |
| input: size limit | `max_bytes` (1–65536) | `max_length` (default **5000**) |
| input: timeout | `timeout_seconds` (1–60) | **NOT IN SCHEMA** |
| input: raw HTML | N/A | `raw` (default false) |
| input: chunk offset | N/A | `start_index` — **NOT TESTED** in 14 cases |
| output_schema | structured dict（`ok`, `url`, `status_code`, `content`, …） | **null**（MCP descriptor） |
| MCP output shape | N/A | `text_parts[]` + optional `structured_content` |

---

## Output format（OBSERVED）

| 観点 | Local | MCP |
|------|-------|-----|
| 成功時 primary payload | `content` 文字列 + HTTP metadata | テキスト blob（often 前置説明文 + 本文） |
| text/plain | raw body | `Content type ... cannot be simplified to markdown, but here is the raw content:` ラッパー（normal_plain 等） |
| text/html | raw HTML（normal_html: 78 bytes） | markdown 簡略化（normal_html: text_length 67, `raw: false`） |
| HTTP status in output | `status_code` フィールド | 本文中の error 文字列または implicit — **structured status field なし** |
| final URL | `final_url` フィールド | **NOT TESTED** as dedicated field |
| truncated flag | `truncated` boolean | **NOT TESTED** as dedicated field |

---

## HTML / Markdown / text 処理（OBSERVED）

| case | Local | MCP |
|------|-------|-----|
| normal_html | raw HTML 78 bytes | simplified markdown-like text |
| normal_plain | raw plain 20 bytes | raw モードでもラッパー文付き 164 chars |
| normal_https | raw HTML 559 bytes | raw モード、ラッパー + HTML 679 chars |

**NOT TESTED:** MCP `start_index` による chunk 再取得。

---

## Redirect（OBSERVED）

| case | Local | MCP |
|------|-------|-----|
| boundary_redirect | ok **true**（harness が redirect 先 plain 相当を取得） | ok **false**, ReadTimeout ~31s |

**NOT TESTED:** MCP が public URL → private redirect をどう扱うか（production URL 起点）。

---

## Error representation（OBSERVED）

| 状況 | Local | MCP |
|------|-------|-----|
| HTTP 404 | `ok: false`, `error: "http error: 404"` | `ok: false`, `is_error: true`, text: `... status code 404` |
| HTTP 500 | `ok: false`, `error: "http error: 500"` | 同上 pattern |
| timeout | `ok: false`, `error: "timeout"` | failure_timeout では ok **true**（27122 ms） |
| SSRF block | `ok: false`, `error: "ssrf blocked: ..."` | N/A（MCP は別挙動） |
| connection fail | **NOT TESTED**（deterministic mock 外） | metadata case: ConnectError in text |

---

## Size limit（OBSERVED）

| case | Local | MCP |
|------|-------|-----|
| boundary_large | size **65536**, truncated **true** | text_length **5232**（max_length=5000 + ラッパー） |
| boundary_near_max | size **65000**, truncated false | text_length **65132**（max_length=100000） |
| boundary_small | size **64** | text_length **193**（ラッパー込み） |

単位: Local は **bytes**、MCP は **characters**（schema 記述）。同一単位での厳密比較は **NOT TESTED**。

---

## Timeout（OBSERVED）

| case | Local | MCP |
|------|-------|-----|
| failure_timeout | timeout **3s** → error at **3009 ms** | 同一 slow endpoint で ok **true** at **27122 ms** |

MCP input schema に timeout パラメータなし（OBSERVED）。

---

## Execution / Provider（OBSERVED）

| 項目 | 値 / 状態 |
|------|-----------|
| MCP transport | stdio subprocess |
| cold start（3 samples） | 755–885 ms |
| total call median | **984.6 ms** |
| `MCPToolProvider.list_descriptors()` | **failed**（inputSchema フィールド名不一致、Run note） |
| experimental MCP client（comparison 専用） | list_tools / call_tool **成功** |

**NOT TESTED:** persistent session / connection reuse。

---

## Tool contract 互換（Run hypotheses — 設計評価ラベル）

`comparison.json` → `hypotheses.H-MCP-6`: **PARTIALLY_SUPPORTED**  
根拠（Run 記録）: input/output shapes differ materially (structured HTTP metadata vs markdown text blob).

**NOT TESTED:** Agent-facing unified contract、registry 形式への自動マッピング。

---

## 分類凡例

| ラベル | 意味 |
|--------|------|
| OBSERVED | 14 ケース Run に記録あり |
| NOT TESTED | 14 ケースの範囲外 |
| UNKNOWN | Run にも仕様確定情報も不足（本 doc では乱用しない） |
