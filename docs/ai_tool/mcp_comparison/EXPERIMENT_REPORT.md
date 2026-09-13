# Experiment Report — MCP Fetch Comparison Phase 1

**Run:** `runs/ai_tool/20260828_153335_mcp_fetch_comparison/`  
**experiment:** `MCP_FETCH_COMPARISON_PHASE1`  
**started_at:** `2026-08-28T06:33:35.580467+00:00`

---

## 1. 実験目的

Local experimental Tool `local:read_url_text` と公開 MCP Fetch Tool を同一条件セット（14 ケース）で比較し、以下について**観測可能な事実**を記録する。

- Tool Model / Provider で Local と MCP をどこまで同一表現できるか
- Safety 境界の差（Client-side vs Server-side）
- 入出力・エラー・サイズ・redirect・timeout 等の挙動差
- MCP metadata（annotations）の有無

**目的外:** MCP 本番導入、Agent 統合、Registry 登録、採用判断。

---

## 2. 実験条件

| 項目 | 値 |
|------|-----|
| ケース数 | **14** |
| Local Tool | `local:read_url_text` |
| MCP Tool | `mcp:fetch`（`mcp-server-fetch` **2026.8.18**） |
| fixture server | `http://127.0.0.1:58447`（決定論的 HTTP） |
| MCP 起動 | stdio: `python -m mcp_server_fetch --ignore-robots-txt` |
| MCP SDK（Run 時 venv） | MCP **1.x**（evaluation notes） |
| 比較 runner | `ai_tool/experimental/mcp_fetch_comparison/` |

### Local 実行方法（Run inputs より）

| local_mode | 件数 | 方法 |
|------------|------|------|
| `harness_fixture` | 10 | `fetch_fn` がローカル fixture server から応答再生。`local_args.url` は SSRF 通過用 URL（inputs 記録: `http://example.com/fixture/...`）。**実ネットワークで example.com の /fixture パスを取得したわけではない。** |
| `production` | 4 | 実装そのまま（`read_url_text` デフォルト HTTP）。`normal_https` + safety 4 件。 |

### MCP 実行方法

- 各ケースで `call_tool('fetch', {url, ...})`（experimental MCP client）
- fixture ケース: `http://127.0.0.1:58447/...`
- `normal_https`: `https://example.com/`（実ネットワーク、環境依存）

### mock / fixture / real web の区別

| 種別 | ケース |
|------|--------|
| Local fixture（harness） | normal_plain, normal_html, boundary_*, failure_*（slow 除く実装依存） |
| Local production + fixture URL | safety_*（loopback fixture URL） |
| Local production + real web | normal_https |
| MCP → local fixture | 大半のケース |
| MCP → real web | normal_https |

**別枠（本 Run 外）:** Local Real Web Smoke Test — `runs/ai_tool/20260828_153616_read_url_real_web_smoke/`

---

## 3. 結果（Run 転記）

### 3.1 ケース成否

- **両方 ok:** 6
- **両方 not ok:** 5
- **Local not ok / MCP ok:** 3（failure_timeout, safety_localhost, safety_private_ip）
- **Local ok / MCP not ok:** 0

詳細: [COMPARISON.md](./COMPARISON.md)

### 3.2 実行性能（OBSERVED）

| 指標 | 値 |
|------|-----|
| MCP list_tools duration | **873.7 ms** |
| MCP call total median | **984.6 ms** |
| Local harness success duration | **1.5–13 ms**（ケースによる） |

### 3.3 MCP descriptor（OBSERVED）

- `output_schema`: null
- `annotations`: null
- input: `url`, `max_length`, `start_index`, `raw`

### 3.4 Provider 互換（OBSERVED）

- experimental client: **成功**
- 既存 `MCPToolProvider.list_descriptors()`: **失敗**（810.9 ms, ExceptionGroup）
- 記録理由: MCP 1.x `inputSchema` vs Provider の `input_schema` 想定

### 3.5 Safety gate（OBSERVED）

- Local descriptor → `allow`
- MCP descriptor → `human_required`（trust_external true/false いずれも）

---

## 4. 判定（実験として確認できたこと）

以下は **当 Run の範囲** に限定した記録。

1. 14 ケースは完了し、`comparison.json` に結果が残っている。
2. Local と MCP で **ok 不一致が 6 ケース** 観測された（redirect timeout、timeout 意味差、safety 3 件等）。
3. Safety 4 ケースで **Local は SSRF ブロック、MCP はネットワーク到達** が `safety_results.json` に記録された。
4. MCP 1 呼び出しあたり **~985 ms**（中央値）の stdio オーバーヘッドが観測された。
5. MCP tool **annotations は null** — untrusted metadata 前提の設計と矛盾しない。
6. 既存 **MCPToolProvider は当環境で Fetch server を list できなかった**（adapter / SDK 分離が必要な兆候）。

### Hypotheses（Run `comparison.json` — 設計仮説ラベル、採用判断ではない）

| ID | verdict |
|----|---------|
| H-MCP-1 Common Tool Model | PARTIALLY_SUPPORTED |
| H-MCP-2 Provider isolatable | PARTIALLY_SUPPORTED |
| H-MCP-3 annotations untrusted | SUPPORTED |
| H-MCP-4 Client-side safety re-eval | SUPPORTED |
| H-MCP-5 Trust model needed | SUPPORTED |
| H-MCP-6 Common contract | PARTIALLY_SUPPORTED |

---

## 5. 実験として行っていないこと

- Agent からの Tool 選択
- Registry 登録
- MCP 長期接続・並列
- MCP 全機能（robots.txt デフォルト、`start_index` chunk 等）の網羅
- 採用 / 不採用の決定

---

## 6. Run 成果物

| ファイル | 内容 |
|----------|------|
| `inputs.json` | 14 case 定義 |
| `comparison.json` | 全結果 + hypotheses |
| `outputs.json` | descriptor + execution metrics |
| `safety_results.json` | safety gate + per-case safety |
| `evaluation.json` | stop_after: report |
| `audit.jsonl` | 監査 1 行 |
| `REPORT.md` / `FAILURE_ANALYSIS.md` | Run 内簡易サマリ |

---

## 7. evaluation.json（転記）

```json
{
  "success_criteria_met": true,
  "stop_after": "report",
  "agent_integration": false,
  "registry_registration": false
}
```

**解釈:** Phase 1 実験目的（比較記録）は Run 上 met。**MCP 本番 ready ではない。**
