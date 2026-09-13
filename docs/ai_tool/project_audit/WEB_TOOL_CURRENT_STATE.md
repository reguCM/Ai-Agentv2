# Web Tool — Current State Investigation

**Phase:** Web Tool Re-entry Investigation Phase 1（読み取り専用）  
**Date:** 2026-08-28  
**HEAD:** `875cc47` — `ai-agent: freeze current development state`  
**Branch:** `master`  
**Commit:** 禁止（本 Phase）

---

## Git 記録（作業開始時）

| 項目 | 値 |
|------|-----|
| HEAD | `875cc47` |
| Branch | `master` |

### 対象 Tool 関連ファイル状態

| Path | HEAD | Working tree |
|------|------|--------------|
| `tools/system/network/search_web.py` | **不在** | `??` untracked |
| `tools/system/network/general_web_search.py` | **不在** | `??` untracked |
| `registry/tools.json` → `search_web` | **不在** | 同上（HEAD にエントリなし） |
| `ai_tool/experimental/read_url/*` | **committed** | clean |
| `ai_tool/catalog/entries/local_read_url_text.json` | **committed** | clean |
| `ai_tool/agent_integration/production_bridge.py` | **committed** | clean |
| `tests/test_general_web_search.py` | **不在** | `??` untracked |
| `tests/ai_tool/experimental/test_read_url_text.py` | **committed** | clean |

> **Source of truth:** 正式採用判断は **HEAD** を基準とする。`search_web` 実装はディスク上に存在するが **未コミット（WT only）** — 本調査では「実装候補・WT 実体」として記述し、正式採用とは区別する。

---

## 1. search_web

### 1.1 実装（WT — HEAD 未コミット）

| 項目 | 値 |
|------|-----|
| Agent 入口 | `tools/system/network/search_web.py` → `search_web(query, limit=None)` |
| 本体 | `tools/system/network/general_web_search.py` → `general_web_search()` |
| 共有 HTTP | `tools/system/tool_builder/research/web.py`（`http_get`, `compact_hit`, `search_duckduckgo`, `search_wikipedia`） |
| Pipeline 用 search | `research.web.search_web` — **Agent 経路からは呼ばない**（テストで明示） |

### 1.2 Registry（HEAD）

**`search_web` は Registry に存在しない。** `visibility=agent` なし。

→ **HEAD 時点で Ollama Tool schema に載らない。** LLM は Tool として選択不可。

### 1.3 Agent 接続（HEAD）

| 経路 | 状態 |
|------|------|
| `create_ollama_tools(registry)` | search_web **非公開** |
| `execute_tool()` Registry lookup | 未登録のため実行不可 |
| System Prompt | **言及あり** — 「search_web: 実際にWeb検索…」 |
| stdout 要約 | `summarize_tool_result` に search_web 専用分岐あり |

**Drift:** Prompt / stdout は search_web を前提とするが、Registry schema には無い（CURRENT_STATE_FREEZE.md でも OBSERVED）。

### 1.4 LLM schema（想定 — Registry 登録時）

WT の過去 Registry ドラフトより（参考、HEAD 非適用）:

```json
{
  "query": { "type": "string", "required": true },
  "limit": { "type": "number", "description": "return_limit、省略時5件" }
}
```

### 1.5 検索処理の実体

```text
query (文字列)
  → DuckDuckGo Instant Answer API (JSON GET)
  → Wikipedia JA OpenSearch
  → Wikipedia EN OpenSearch
  → compact_hit(title, snippet, url, backend)
  → rank_hits_for_query（トークン一致スコア — 非 LLM）
  → return top N hits
```

| 項目 | 値 |
|------|-----|
| ページ本文取得 | **なし** |
| 既定 return_limit | 5 |
| 既定 fetch_limit | 5（limit=1 でも内部は複数 fetch 後 rank） |
| リトライ | backend 単位で errors 蓄積、全体リトライなし |
| タイムアウト | 12s（research.web `REQUEST_TIMEOUT`） |
| API キー | なし |

### 1.6 返却 shape

```json
{
  "query": "...",
  "hits": [
    { "title": "...", "snippet": "...", "url": "...", "backend": "duckduckgo|wikipedia-ja|wikipedia-en" }
  ],
  "backends_tried": ["duckduckgo", "wikipedia-ja", "wikipedia-en"],
  "error": null | "string",
  "fetch_limit": 5,
  "return_limit": 5,
  "candidates_collected": 7
}
```

- **snippet:** API 由来の短い要約（full page text ではない）
- **url:** 検索結果リンク（本文は取得しない）

### 1.7 「意味理解」の所在 — **モデル A + 軽量機械 rank（B の query 生成は LLM 側）**

| 層 | 意味理解 |
|----|----------|
| Tool (`search_web`) | **なし** — query をそのまま backend へ |
| Tool (`rank_hits_for_query`) | トークン/部分文字列スコア — **意図解析ではない** |
| Agent / LLM | ユーザー要求 → **search query を生成**（モデル B の前半） |
| Tool Builder `query_intent.py` | Research Pipeline 専用 — **Agent search_web 経路では未使用** |

`search_web_include_mean` — **コードベースに存在しない**（今回 rename 対象外）。

分類: **A（単純検索）+ LLM が query 生成（B の Agent 側部分）**。C（Tool 側意図解析・複数検索統合）は **未実装**。

### 1.8 System Prompt 使用指針（HEAD agent.py）

- URL 不明・探索 → `search_web`
- 既知 URL 本文 → `read_url_text`
- hits/本文に無い URL を補完しない
- 8 ステップ Web 調査手順

### 1.9 Safety / Network

| 項目 | 値 |
|------|-----|
| network_access | **あり** — 外向き HTTPS GET（DDG/Wikipedia API） |
| SSRF | search 自体は固定 API URL — ユーザー URL fetch ではない |
| filesystem write | なし |
| agent_tool_gate | Registry 未登録のため Agent 実行経路では未到達（HEAD） |

### 1.9 エラー処理

- 空 query → `error: "query が空です"`, hits=[]
- 不正 limit → error 文字列
- 全 backend 失敗 → errors 連結 or `"検索結果がありません"`

### 1.10 UNKNOWN

- WT 実装を Registry/HEAD に正式採用するタイミング
- DDG Instant Answer の地域・鮮度保証
- 日本語クエリに対する backend 品質

---

## 2. read_url_text

### 2.1 実装（HEAD committed）

| 項目 | 値 |
|------|-----|
| 関数 | `ai_tool.experimental.read_url.reader.read_url_text` |
| HTTP | `ai_tool.experimental.read_url.http_client.default_http_get` |
| SSRF | `ai_tool.experimental.read_url.ssrf.validate_url` + redirect 各 hop 再検証 |
| Spec | `docs/ai_tool/tool_creation/specs/local_read_url_text.json` |
| Catalog | `ai_tool/catalog/entries/local_read_url_text.json` |

### 2.2 Registry / Agent 公開

| 項目 | 値 |
|------|-----|
| Registry `tools.json` | **未登録** |
| Agent overlay | `production_bridge.py` — `local:read_url_text` |
| Ollama schema | overlay 経由で公開（既定 ON） |
| 無効化 | `AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL=1` |
| execute_tool | `is_experimental_agent_tool` → `execute_experimental_agent_tool` |
| agent_tool_gate | **通過**（experimental も gate 対象） |

### 2.3 LLM schema

```json
{
  "required": ["url"],
  "properties": {
    "url": { "type": "string" },
    "max_bytes": { "type": "integer", "minimum": 1, "maximum": 65536 },
    "timeout_seconds": { "type": "number", "minimum": 1, "maximum": 60 }
  }
}
```

Description 末尾に routing 文言が bridge により追加: 「既知URL…探索は search_web」

### 2.4 取得処理

| 項目 | 値 |
|------|-----|
| メソッド | GET のみ |
| redirect | 最大 5、各 hop SSRF 再検証 |
| max_bytes | 既定 65536 |
| timeout | 既定 10s |
| Content-Type | text/*, json, xml, html 系のみ許可 |
| HTML | **タグ除去なし** — bytes を decode して text として返す（raw HTML 可） |
| JavaScript | **非対応** — 静的 GET のみ |
| PDF / binary | content-type + sniff で拒否 |
| encoding | Content-Type charset → utf-8 fallback replace |
| 4xx/5xx | ok=false, error=`http error: {status}` |

### 2.5 返却 shape

```json
{
  "ok": true,
  "url": "要求URL",
  "final_url": "リダイレクト後",
  "status_code": 200,
  "content_type": "...",
  "size_bytes": 1234,
  "content": "本文テキスト",
  "truncated": false,
  "error": null
}
```

LLM へは `execute_tool` → `messages` に **raw JSON**（agent.py 標準経路）。

### 2.6 SSRF / Safety

| 防御 | 実装 |
|------|------|
| scheme | http/https のみ |
| localhost / private IP | 拒否 |
| DNS 解決後 public 確認 | あり |
| redirect to blocked | 拒否 |
| DNS rebinding TOCTOU | **UNKNOWN**（policy 明記） |
| HTTP_PROXY 悪用 | **UNKNOWN** |

risk_level: medium（catalog）。network_access: true。

### 2.7 adoption_status

Catalog: `experiment_status: experimental`, `adoption_status: not_reviewed`  
Phase 5 で production overlay 統合済み（`88febb3`）— Registry 正式登録は **未実施**。

---

## 3. Search → Fetch Agent loop（HEAD）

```text
User → Agent/LLM
  → [search_web]  ← HEAD: schema に無い → LLM 選択不可
  → hits (title, snippet, url)
  → LLM が url を選ぶ
  → [read_url_text]  ← overlay で schema あり → 選択可能
  → content
  → LLM 最終回答
```

| 段階 | HEAD で成立？ |
|------|----------------|
| Discovery (search_web) | **否** — Registry 未公開、実装 WT only |
| Fetch (read_url_text) | **条件付き yes** — overlay + tool-capable LLM + gate |
| 多ラウンド loop | `MAX_TOOL_ROUNDS=5` — 設計上可能 |
| Prompt 上の手順 | search → read_url **記述あり** |

**結論:** 設計上は **Discovery → Fetch 連携**だが、**HEAD では loop は半分のみ成立**（Fetch のみ）。search_web の Registry 採用が HR 待ちのギャップ。

---

## 4. テスト（読み取り実行）

| Suite | 結果 | 備考 |
|-------|------|------|
| `tests/test_general_web_search.py` | WT only、45 tests 内で PASS | HEAD 未コミット |
| `tests/ai_tool/experimental/test_read_url_text.py` | **PASS** | deterministic + mock |
| `tests/ai_tool/agent_integration/test_production_bridge.py` | **PASS** | overlay |

実行: `pytest tests/test_general_web_search.py tests/ai_tool/experimental/test_read_url_text.py tests/ai_tool/agent_integration/test_production_bridge.py` → **45 passed**

---

## 5. UNKNOWN 一覧

- search_web WT → HEAD 正式採用の HR 範囲
- HTML → readable text 抽出の要否
- Agent 本番で search_web + read_url 連携 E2E（HEAD schema 制約下）
- 一般 Web ページ（非 Wikipedia）の search 品質

---

## 関連

- [CURRENT_STATE_FREEZE.md](./CURRENT_STATE_FREEZE.md)
- [WEB_TOOL_RESPONSIBILITY_MATRIX.md](./WEB_TOOL_RESPONSIBILITY_MATRIX.md)
- [WEB_TOOL_DESIGN_OPTIONS.md](./WEB_TOOL_DESIGN_OPTIONS.md)
- `research/.../SEARCH_WEB_PATH_INVESTIGATION.md`（経路調査、実装変更なし）
