# Web Tool — Design Options（判断材料のみ）

**Phase:** Web Tool Re-entry Investigation Phase 1  
**HEAD:** `875cc47`  
**Status:** 実装なし — 次フェーズの判断材料

---

## 現状サマリ

| Tool | コード | Registry | Agent schema | 役割 |
|------|--------|----------|--------------|------|
| search_web | WT（未コミット） | なし | **非公開** | Discovery |
| read_url_text | HEAD | なし | **experimental overlay** | Fetch |

Prompt は両 Tool を前提とするが、**HEAD では search_web が LLM に渡らない**。

---

## オプション比較

### Option 0: 現状維持

| 内容 | 評価 |
|------|------|
| search_web WT のまま、Registry 非公開 | Prompt/schema drift 継続 |
| read_url_text overlay のみ | Fetch 単体は使える |
| Search→Fetch loop | **不完全** |

| Pros | Cons |
|------|------|
| 変更リスクゼロ | Web 調査能力が設計と乖離 |
| HR 不要 | 監査・調査の繰り返し诱因 |

**推奨度:** 開発 re-entry の **落としどころにはならない**（意図的凍結以外）。

---

### Option 1: search_web 正式採用（Registry + visibility=agent）

| 内容 |
|------|
| WT `tools/system/network/*` を selective commit |
| Registry に search_web 追加（HR） |
| 既存 general_web_search 契約維持 |
| System Prompt drift **解消** |

| Pros | Cons |
|------|------|
| Discovery→Fetch loop **完成** | HR + E2E + gate trust |
| 実装・テスト既存（WT） | search 品質限界は残る |
| Prompt と schema 一致 | network 表面拡大 |

**HR 必要:** Registry、Agent schema、gate auto_allow 方針  
**推奨度:** **高** — 最小変更で設計意図に一致

---

### Option 2: read_url_text 改良

| 改良候補 | 性質 |
|----------|------|
| HTML → readable text 抽出 | Fetch 品質 |
| charset / encoding 強化 | 互換 |
| max_bytes ポリシー見直し | 仕様 |
| Registry 正式登録 | 採用 |

| Pros | Cons |
|------|------|
| 精読品質向上 | search 不足は残る |
| experimental → production 道 | HTML parser 依存・テスト増 |

**HR 必要:** Registry 登録、output shape 変更時  
**推奨度:** **中** — Option 1 と並行または直後

---

### Option 3: search_web 改良（同一 Tool 内）

| 改良候補 | 分類 |
|----------|------|
| backend 追加（Bing 等） | search 品質 |
| rank アルゴリズム改善 | 機械 rank（まだ A/B） |
| 検索結果から snippet 以外取得 | **責務拡張に注意** |

| Pros | Cons |
|------|------|
| Discovery 品質 UP | 「意味理解」は依然 LLM 側 |
| 新 Tool ID 不要 | 本文 fetch 混在は Fetch と競合 |

**「意味を含めた検索」:** rank 改善だけでは **C にならない**。意図解析を Tool に入れるなら **Option 4 相当**。

**HR 必要:** output/backend 変更  
**推奨度:** **中** — Option 1 採用後

---

### Option 4: 上位 Research Tool 追加（Search/Fetch 維持）

例: `research_web`, `agentic_web_research`

| Tool 責務 |
|-----------|
| 意図整理（限定的でも可） |
| 複数 query 生成 |
| search_web 複数回 |
| read_url_text 複数回 |
| 結果統合（structured） |

| Pros | Cons |
|------|------|
| C パターンを明示分離 | 新 Tool 設計・HR・E2E |
| search/fetch 単純性維持 | 過剰設計リスク |

**HR 必要:** 新 Tool ID、Registry、Safety、Prompt  
**推奨度:** **低〜中** — 具体ユースケース確定後

`search_web_include_mean` 的な rename/拡張は **Option 4 の一形態**（同一 Tool 拡張ではなく分割推奨）。

---

### Option 5: 新 Tool 分割

| 分割案 | 例 |
|--------|-----|
| Search / Fetch / Extract | `web_search`, `fetch_url`, `extract_readable_text` |
| Vendor split | 将来 Bing/Google provider |

| Pros | Cons |
|------|------|
| 責務最明確 | Tool 数増、Agent routing 複雑化 |
| テスト分離 | 移行コスト |

**HR 必要:** 全面  
**推奨度:** **低**（現時点）— Option 1+2 で不足が残る場合

---

## 推奨判断順序（実装は次 Phase）

```text
1. Option 1 — search_web 正式採用（WT commit + Registry HR）
2. Option 2 — read_url_text 品質 + Registry HR（experimental 卒業）
3. Option 3 — search 品質（backend/rank）— 契約内改善
4. Option 4 — 上位 Research Tool — ユースケース証明後
5. Option 5 — 分割 — 必要性が HR で示された場合のみ
```

---

## Human Review チェックリスト（次 Phase 用）

| # | 判断 | HR |
|---|------|-----|
| HR-W1 | search_web Registry 登録 + visibility=agent | **必須** |
| HR-W2 | search_web WT → HEAD commit | **必須** |
| HR-W3 | read_url_text Registry 正式登録 | **必須** |
| HR-W4 | read_url output（HTML extract）変更 | 仕様変更時 |
| HR-W5 | 新 Research Tool ID | **必須** |
| HR-W6 | SSRF / network policy 変更 | **必須** |
| HR-W7 | System Prompt Web 節の整理 | 推奨（Option 1 とセット） |

---

## 完了条件への回答（設計 Options 観点）

| # | 回答 |
|---|------|
| 5. 意味検索は拡張 vs 新 Tool | **LLM 側が意味理解（B）**。Tool 側 C は **新上位 Tool（Option 4）** が適切。search_web rename/拡張 alone では不十分 |
| 8. 不足の解決先 | search 未公開 → **Registry 採用（Option 1）**；精読品質 → **read_url 改良（Option 2）**；多段 research → **LLM loop または Option 4** |
| 9. HR 箇所 | 上表 HR-W1〜W7 |

**STOP — 調査完了。次の判断を待つ。**
