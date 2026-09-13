# Web Tool — Responsibility Matrix

**Phase:** Web Tool Re-entry Investigation Phase 1  
**HEAD:** `875cc47`  
**Scope:** `search_web` vs `read_url_text`（HEAD + WT 実装事実）

---

## 比較表

| 項目 | search_web | read_url_text |
|------|------------|---------------|
| **URLが必要か** | 否（query のみ） | **是**（必須引数 `url`） |
| **URLを発見できるか** | **是** — hits[].url を返す | 否 — 与えられた URL のみ |
| **Web検索するか** | **是** — DDG + Wikipedia API | 否 |
| **ページ本文を取得するか** | **否** — snippet のみ | **是** — HTTP GET body（最大 64KB） |
| **snippetを返すか** | **是** — title + snippet | 否（full response text） |
| **full textを返すか** | 否 | **是**（truncated 可、HTML raw 可） |
| **複数ページを扱えるか** | 複数 **hits**（最大5） | **1 URL / call** |
| **既知URLの精読に向くか** | 不向き | **向く** |
| **未知情報の探索に向くか** | **向く**（URL 発見） | 不向き（URL 前提） |
| **LLMによる意味理解** | query 生成・hits 解釈・URL 選択 | 要約・抽出は **LLM 側** |
| **Tool自身による意味理解** | **軽量 token rank のみ** — 意図解析なし | **なし** |
| **Safety boundary** | 固定 API への outbound GET | SSRF 検証 + GET only + size/time limit |
| **主な制約** | HEAD: Registry 未公開 / WT: 本文なし / Pipeline search と別経路 | experimental / Registry 未登録 / JS 非対応 / HTML 未整形 |

---

## 責務重複

| 観点 | 重複？ |
|------|--------|
| URL 発見 | **否** — search_web のみ |
| 本文取得 | **否** — read_url_text のみ |
| snippet 提供 | search_web のみ（read_url は full text） |
| Web outbound network | **両方** — 目的が異なる（search API vs 任意 public URL） |

**結論:** 責務の **重複は小さい**。競合ではなく **Search (Discovery) / Fetch (Read)** の分離。

---

## Agent loop における役割

```text
         search_web              read_url_text
              │                        │
    Discovery │                        │ Fetch
    (query→hits)                      (url→content)
              └──────────┬─────────────┘
                         │
                    LLM（意味理解・統合・回答）
```

| 能力 | 担当 |
|------|------|
| ユーザー意図理解 | **LLM / Agent** |
| 検索 query 生成 | **LLM** |
| 検索実行 | **search_web** |
| 関連 hit 選択 | **LLM** |
| 本文取得 | **read_url_text** |
| 複数ソース比較・要約 | **LLM**（現状 Tool なし） |

---

## 「意味を含めた検索」の分類

| パターン | search_web | read_url_text | LLM |
|----------|------------|---------------|-----|
| **A. 単純検索** | query 実行 | — | 任意 |
| **B. LLM query 生成** | query 実行 | — | **意図→query** |
| **C. Tool 側意図解析** | **未実装** | **未実装** | 補助のみ |

現状は **B**（Agent 経路）。C に相当する `search_web_include_mean` 等は **存在しない**。

---

## 不足機能の責務分類

| ユースケース | 現状 | 既存 Tool | LLM | 新 Tool 候補 |
|-------------|------|-----------|-----|-------------|
| 1. URL 不明 | search_web（WT）/ HEAD 未公開 | search_web | query 生成 | — |
| 2. URL 既知 | read_url_text | read_url_text | 要約 | — |
| 3. 検索結果比較 | hits 複数件 | search_web | 比較 | — |
| 4. 複数ページ精読 | 複数 read_url call | read_url_text × N | 統合 | batch fetch（将来） |
| 5. 検索→深掘り | loop 設計 | 両 Tool | 選択 | HEAD: search 未公開 |
| 6. リンク追跡 | **不可** | — | — | crawl Tool |
| 7. PDF / JS ページ | **拒否/空** | read_url 制限 | — | 専用 backend |
| 8. 「調べてまとめて」 | LLM 多段 tool loop | 両 Tool | **主担当** | research orchestrator（将来） |

---

## Human Review が必要になりうる変更

| 変更 | HR |
|------|-----|
| search_web Registry `visibility=agent` 追加 | **是** |
| read_url_text Registry 正式登録 | **是** |
| search_web 本文 fetch 追加（責務侵食） | **是** |
| read_url HTML→text 整形 | 仕様次第 |
| 新 Research / Agentic Tool | **是** |
| SSRF policy 緩和 | **是** |

---

## 外部設計との対応（参考）

| 一般 Agent パターン | 本プロジェクト |
|--------------------|----------------|
| Search tool | search_web（WT、Discovery） |
| Fetch / Browse tool | read_url_text（Fetch） |
| Search → Fetch chain | 設計上 yes / HEAD partial |
| Agentic multi-step research | **LLM loop + MAX_TOOL_ROUNDS** — 専用 Tool なし |
| JS rendering browser | **未対応** |

Local Agent として **Search/Fetch 分離は業界標準と整合**。不足は **Orchestration・採用ギャップ（search_web 未公開）** 側。
