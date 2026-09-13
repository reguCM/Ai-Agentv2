# Web Tool Failure Analysis — Phase 1

**Date:** 2026-08-28  
**Git HEAD:** `82fca73`  
**Run:** `runs/ai_tool/20260828_212555_web_tool_failure_analysis/`  
**Production changes:** NONE  
**Git commit:** NOT EXECUTED

## 目的

Web Tool 経路（`search_web` → `read_url_text` → LLM 回答）の失敗原因を **4 領域 + 仮説 H1–H5** に切り分け、次に修正すべき箇所を特定する。本 Phase は調査のみ。

## 調査方法

| ソース | 内容 |
|--------|------|
| Tool-only probes | `search_web` / backend 別 / `read_url_text` 直接呼び出し |
| Practical Evaluation 再分析 | `runs/ai_tool/20260828_201538_web_tool_practical_evaluation/`（qwen3:8b live） |
| 仮想本文抽出 | 調査 harness の `virtual_body_extract()`（production 非変更） |

Harness: `ai_tool/web_tool_failure_analysis.py`  
Runner: `ai_tool/run_web_tool_failure_analysis.py`

---

## ドメイン評価サマリ

| 領域 | Grade | 根拠 |
|------|-------|------|
| SEARCH_QUALITY | **FAIL** | 6 query 中 4 が空 hits；snippet 100% 空；query 変形で ranking 崩壊 |
| FETCH_QUALITY | **PARTIAL** | HTTP 200 だが truncated 64KB・nav/TOC 中心・本文未到達 |
| RESULT_UTILIZATION | **FAIL** | Fetch 後 HTML/JSON メタ応答；空 search で hallucination |
| AGENT_LOOP | **PARTIAL** | Fetch 省略（Case B）；max rounds で null（Case C） |
| LLM_CAPABILITY | **FAIL** | C4/C5/H5 が live trace で再現 |
| MODEL_CAPABILITY | **UNKNOWN** | Primary model（deepseek）Tool Calling 非対応 |

**Overall:** FAIL

---

## A. SEARCH_QUALITY

### Tool-only probe 結果（2026-08-28 live）

| Query | Hits | 1位 title | duckduckgo | wikipedia-ja | 分類 |
|-------|------|-----------|------------|--------------|------|
| `大阪市 人口` | 5 | 大阪市 | 空 | 5件 | A3（snippet 空） |
| `大阪市の人口` | 5 | 大阪市の不祥事 | 空 | 5件（無関係） | **A3 ranking** |
| `Osaka city population` | 0 | — | 空 | 空 | A2 backend 空 |
| `大阪市 現在の人口 最新情報` | 0 | — | 空 | 空 | A2 backend 空 |
| `大阪市 人口 官方統計` | 0 | — | 空 | 空 | A2 backend 空 |
| `this-query-should-return-nothing-xyz123` | 0 | — | 空 | 空 | 期待通り |

### 所見

- **A1（LLM query 不良）:** Case A の query `大阪市 人口` は妥当。**UNKNOWN**（A1 単独原因とは言えない）
- **A2（backend 不良）:** duckduckgo が全 probe で **0 件**。英語・長文 query も全 backend 空
- **A3（ranking 不良）:** `大阪市の人口` → 「不祥事」「地名」等。**CONFIRMED**
- **A4（LLM hit 選択）:** Case A は正しい URL を Fetch。**PASS**（このケースのみ）

**Grade: FAIL**

---

## B. FETCH_QUALITY

### Wikipedia 大阪市 probe

| 項目 | 値 |
|------|-----|
| HTTP status | 200 |
| Content-Type | text/html; charset=UTF-8 |
| size_bytes | 65536 |
| truncated | **true** |
| mw-parser-output in chunk | **false** |
| population_section_marker | true（TOC `#人口` のみ、数値なし） |
| nav_like_markers | 3（vector-toc, mw-navigation, sidebar） |
| script_tag_density | 0.05 / 1K chars |

**64KB 時点の内容:** `<head>`, script, nav, TOC リスト。**人口セクション本文は未到達**。

仮想抽出（investigation-only）では TOC テキストに「人口」見出しは出るが、**人口数値は含まれない**（truncation により本文未到達のため）。

Case A live trace でも同一 URL・同一 truncated 65536B を LLM が受信 → HTML パーサー/BeautifulSoup 論で回答（C5）。

**Grade: PARTIAL**（取得自体は成功；LLM 利用可能データではない）

---

## C. RESULT_UTILIZATION（Practical Eval 再分析）

| Case | Search | Fetch | 問題分類 | Grade |
|------|--------|-------|----------|-------|
| A 単純検索 | 1 | 1 | **C5** HTML/JSON メタ応答 | FAIL |
| B Search→Fetch | 1 | 0 | **C2** Fetch 未実行 + 無関係 hits | FAIL |
| C 複数比較 | 5 | 0 | **C1** 空/不足 + max rounds null | FAIL |
| D 最新情報 | 2 | 0 | **C1** 空 hits | FAIL |
| E 再検索 | 2 | 0 | **C1** 空 hits | PARTIAL |
| F 空検索 | 2 | 0 | **C4/H5** 空 search + 外部数値 | FAIL |
| G HTML-heavy | 3 | 1 | **C5** HTML メタ応答 | FAIL |

**Grade: FAIL**

---

## D. AGENT_LOOP

| 観察 | Case | 詳細 |
|------|------|------|
| Search 後 Fetch 省略 | B | 明示的「読んで」指示でも read_url_text 0 回（**H3 CONFIRMED**） |
| 空 search 後 hallucination | F | 約1,900万人等（**H5 CONFIRMED**） |
| max rounds 打切り | C | 5×search、final_answer null |
| 正しい Search→Fetch | A, G | 実行するが回答品質 FAIL |

**Grade: PARTIAL**

---

## 仮説検証

### H1 — raw HTML が LLM 利用を阻害

| 観点 | 結果 |
|------|------|
| Strict criterion（raw 無・virtual 有） | **NOT MET**（TOC に「人口」文字列あり） |
| Practical criterion | **SUPPORTED** — truncated nav/TOC、人口数値未到達、LLM C5 応答 |

**Verdict: PARTIAL**（truncation + HTML 構造が主要因；単独 H1 strict は未確定）

### H2 — search 品質不良で Fetch に進めない

- 6 query 中 4 が空 hits
- query 変形で無関係 title

**Verdict: PARTIAL CONFIRMED**（Case D/E/F でも live で空 hits）

### H3 — 十分な search でも Fetch しない

- Case B: hits あり（無関係だが）、Fetch 0

**Verdict: CONFIRMED**

### H4 — Fetch 十分でも LLM が利用しない

- Case A: Fetch 成功だが人口未回答、HTML 論

**Verdict: PARTIAL CONFIRMED**（Fetch 内容が事実十分かは truncation により UNKNOWN だが、利用失敗は CONFIRMED）

### H5 — Tool 外情報の補完

- Case F: 空 search → 「約1,900万人」

**Verdict: CONFIRMED**

---

## 最終質問（Q1–Q10）

| # | 質問 | 回答 |
|---|------|------|
| Q1 | search_web は Discovery として十分か | **PARTIAL** — URL 発見は可能だが snippet 空・backend/ranking 不安定 |
| Q2 | 検索品質に問題があるか | **YES** — FAIL |
| Q3 | raw HTML が主要ボトルネックか | **YES** — PARTIAL 確定（truncation + nav/TOC 中心） |
| Q4 | LLM は Tool 結果を正しく利用しているか | **NO** — FAIL |
| Q5 | LLM は Tool 外情報を補完しているか | **YES** — Case F |
| Q6 | Agent loop に構造問題があるか | **PARTIAL** |
| Q7 | Prompt 修正が必要か | **UNKNOWN** |
| Q8 | Tool 実装修正が必要か | **LIKELY YES** |
| Q9 | Agent loop 修正が必要か | **UNKNOWN** |
| Q10 | Research Tool 必要性 | **NOT_ESTABLISHED** |

---

## 次に修正すべき箇所（優先順位）

1. **read_url_text Fetch 品質** — truncated raw HTML を LLM 利用可能テキストへ（Human Review 要）
2. **LLM Result utilization** — Prompt/モデル指示で HTML メタ解析ではなく事実抽出を促す（Tool 単独では不十分）
3. **search_web 品質** — snippet 空、duckduckgo 空、prefix ranking 問題
4. **Agent Search→Fetch 継続** — 明示 Fetch 指示の遵守（Case B）
5. **Primary model Tool Calling** — deepseek-coder-v2:16b 非対応（MODEL_CAPABILITY、Web Tool 外）

---

## 成果物一覧

| パス | 種別 |
|------|------|
| `docs/ai_tool/project_audit/WEB_TOOL_FAILURE_ANALYSIS.md` | 本報告 |
| `ai_tool/web_tool_failure_analysis.py` | 調査 harness |
| `ai_tool/run_web_tool_failure_analysis.py` | runner |
| `tests/ai_tool/project_audit/test_web_tool_failure_analysis.py` | テスト |
| `runs/ai_tool/20260828_212555_web_tool_failure_analysis/` | run artifacts |

---

## 安全・変更境界

| 項目 | 状態 |
|------|------|
| Production code | NONE |
| Registry | NONE |
| Agent | NONE |
| Prompt | NONE |
| Git commit | NONE |
| Safety | PASS |

**STOP: YES** — Implementation Phase へは進まない。
