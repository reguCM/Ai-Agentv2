# 14-Case Comparison — Local vs MCP Fetch

**Run:** `runs/ai_tool/20260828_153335_mcp_fetch_comparison/`  
**started_at:** `2026-08-28T06:33:35.580467+00:00`  
**fixture_base_url:** `http://127.0.0.1:58447`  
**MCP package:** `mcp-server-fetch` **2026.8.18**

数値は `comparison.json` から転記。推測値なし。

## 実行モード（Run 記録）

| local_mode | ケース数 | 意味（Run inputs より） |
|------------|----------|-------------------------|
| `harness_fixture` | 10 | Local: `fetch_fn` がローカル fixture server から応答を再生。`local_args.url` は SSRF 通過用（inputs 上は `http://example.com/fixture/...`）。MCP: fixture URL へ直接 GET。 |
| `production` | 4 | Local: 実装そのまま（SSRF 有効）。`normal_https` と safety 4 件。 |

## サマリ表

| case_id | category | local_ok | mcp_ok | local_ms | mcp_ms | same_url |
|---------|----------|----------|--------|----------|--------|----------|
| normal_plain | normal | true | true | 13.302 | 986.2 | false |
| normal_html | normal | true | true | 1.774 | 924.8 | false |
| normal_https | normal | true | true | 50.920 | 950.1 | true |
| boundary_small | boundary | true | true | 1.514 | 894.1 | false |
| boundary_near_max | boundary | true | true | 2.276 | 872.6 | false |
| boundary_large | boundary | true | true | 2.037 | 938.0 | false |
| boundary_redirect | boundary | true | false | 2.191 | 30901.1 | false |
| failure_404 | failure | false | false | 1.553 | 864.8 | false |
| failure_500 | failure | false | false | 1.528 | 879.4 | false |
| failure_timeout | failure | false | true | 3009.731 | 27122.0 | false |
| safety_localhost | safety | false | true | 0.077 | 839.2 | true |
| safety_private_ip | safety | false | true | 0.074 | 984.0 | true |
| safety_link_local_metadata | safety | false | false | 0.074 | 1009.6 | true |
| safety_redirect_private | safety | false | false | 0.056 | 30843.0 | true |

**一致（local_ok == mcp_ok）:** 8 / 14  
**不一致:** 6 / 14（下記詳細）

## ケース別詳細（OBSERVED）

### normal_plain

| 項目 | Local | MCP |
|------|-------|-----|
| mcp_url / fixture | fixture `/plain` | `http://127.0.0.1:58447/plain` |
| size / output | size_bytes **20**, `text/plain; charset=utf-8`, content=`hello plain fixture\n` | text_length **164**（plain 用ラッパー文付き） |
| mcp args | — | `raw: true`, `max_length: 50000` |

### normal_html

| 項目 | Local | MCP |
|------|-------|-----|
| size | **78**, `text/html; charset=utf-8` | text_length **67**（markdown 簡略化、`raw: false`） |
| 差 | raw HTML 文字列 | `<p>Fixture</p>\n\nHello HTML` 形式 |

### normal_https

| 項目 | Local | MCP |
|------|-------|-----|
| url | `https://example.com/`（production、実ネットワーク） | 同一 URL |
| size | **559**, `text/html` | text_length **679** |
| 備考 | 環境依存（inputs notes） | 同一 |

### boundary_small

| 項目 | Local | MCP |
|------|-------|-----|
| size | **64** | text_length **193**（ラッパー含む） |

### boundary_near_max

| 項目 | Local | MCP |
|------|-------|-----|
| size | **65000**（truncated: false） | text_length **65132** |
| mcp max_length | — | **100000** |

### boundary_large

| 項目 | Local | MCP |
|------|-------|-----|
| size | **65536**, truncated **true** | text_length **5232** |
| 差 | local `max_bytes=65536` で切り詰め | mcp `max_length=5000` で切り詰め（観測値） |

### boundary_redirect

| 項目 | Local | MCP |
|------|-------|-----|
| local | ok **true**, final plain 相当（size 20） | — |
| mcp | — | ok **false**, `ReadTimeout('')`, duration **30901 ms** |
| mcp error text | — | `Failed to fetch http://127.0.0.1:58447/redirect: ReadTimeout('')` |

### failure_404

| Local | MCP |
|-------|-----|
| error: `http error: 404` | error: `mcp_tool_error`, text: `... status code 404` |

### failure_500

| Local | MCP |
|-------|-----|
| error: `http error: 500` | error: `mcp_tool_error`, text: `... status code 500` |

### failure_timeout

| Local | MCP |
|-------|-----|
| error: `timeout`, duration **3009.731 ms**（local timeout_seconds=**3**） | ok **true**, duration **27122 ms** |
| 備考 | fixture `/slow`（server sleep 15s 設計） | MCP input schema に timeout パラメータなし（inputs notes） |

### safety_localhost

| Local | MCP |
|-------|-----|
| error: `ssrf blocked: private or loopback IP` | ok **true**, localhost fixture 本文取得 |

### safety_private_ip

| Local | MCP |
|-------|-----|
| error: `ssrf blocked: private or loopback IP` | ok **true**, text_length **588**（`http://192.168.0.1/`） |

### safety_link_local_metadata

| Local | MCP |
|-------|-----|
| error: `ssrf blocked: private or loopback IP` | ok **false**, `ConnectError('All connection attempts failed')` |

### safety_redirect_private

| Local | MCP |
|-------|-----|
| error: `ssrf blocked: private or loopback IP`（URL が loopback のため fetch 前ブロック） | ok **false**, `ReadTimeout('')`, **30843 ms** |

## 実行性能（Run `outputs.json` → `execution`）

| 指標 | 値 |
|------|-----|
| MCP stdio cold_start_ms samples | 884.9, 795.5, 754.9 |
| MCP call total_ms samples | 1071.1, 984.6, 936.2 |
| MCP call total_ms **median** | **984.6** |
| Local case duration（成功 harness） | 約 **1.5–13 ms**（ケース内 `local.duration_ms`） |
| process_model | stdio subprocess per call（persistent reuse なし） |

**解釈（観測に基づく記述のみ）:** 当 Run では MCP 1 呼び出しの総時間はおおよそ **0.9–1.0 s 台**（中央値 985 ms）であり、Local harness 成功ケース（1–13 ms）より長い。MCP 側には stdio プロセス起動コストが含まれる。

## ok 一致 / 不一致の内訳

| パターン | 件数 | case_id |
|----------|------|---------|
| 両方 ok | 6 | normal_plain, normal_html, normal_https, boundary_small, boundary_near_max, boundary_large |
| 両方 not ok | 5 | boundary_redirect, failure_404, failure_500, safety_link_local_metadata, safety_redirect_private |
| Local not ok / MCP ok | 3 | failure_timeout, safety_localhost, safety_private_ip |
| Local ok / MCP not ok | 0 | — |
