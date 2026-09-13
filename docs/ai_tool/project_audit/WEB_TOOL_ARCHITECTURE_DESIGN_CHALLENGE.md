# Web Tool Architecture Design Challenge — Phase 2

**Date:** 2026-08-28  
**Git HEAD:** `82fca73`  
**Role:** Design only（実装・Registry・Agent・Prompt 変更なし）  
**Inputs:** [WEB_TOOL_FAILURE_ANALYSIS.md](./WEB_TOOL_FAILURE_ANALYSIS.md), [WEB_TOOL_PRACTICAL_EVALUATION.md](./WEB_TOOL_PRACTICAL_EVALUATION.md)

---

## 1. Executive Summary

**CONFIRMED FACT:** 現行 Web Tool 経路（`search_web` → `read_url_text` → LLM 回答）は、大阪市人口を題材にした live 評価（qwen3:8b）で **実用 FAIL** と判定されている。Tool 実行自体は多くのケースで成功するが、**最終回答がユーザー質問に答えていない**。

**DESIGN PROPOSAL（本書の結論）:** 最大の問題は **「Evidence Contract（根拠データ契約）」の欠如** である。Search / Fetch は HTTP 成功を返しても、LLM が grounding 可能な **事実単位（fact-bearing evidence）** を Agent に渡していない。これは Tool・Interface・Architecture が重なった構造問題であり、単一レイヤーの patch では解決しない。

**推奨アーキテクチャ:** **案 C — Hybrid Evidence Pipeline（契約強化 + Agent 最小ポリシー）**

- Fetch Tool は「取得」だけでなく **「LLM 利用可能な evidence への正規化」** まで担当（ただし意味理解・要約はしない）
- Search Tool は Discovery のまま維持しつつ、**discovery card**（snippet・backend・relevance signal・empty 理由）を契約として強化
- Agent は LLM の自由判断に全委任せず、**不変条件（invariants）** のみ enforce（空結果時の hallucination 禁止、Fetch 必須条件の明示）
- 専用 Research Tool は **現時点では不要**（NOT_ESTABLISHED を維持）

Human Review 待ち。**Implementation Phase には進まない。**

---

## 2. Current Architecture

```
User question
    ↓
Agent (agent.py) — MAX_TOOL_ROUNDS=5, LLM tool-calling loop
    ↓
LLM — query 生成 / tool 選択 / 引数生成 / 最終回答
    ↓
search_web (Discovery)
    → general_web_search
        → duckduckgo | wikipedia-ja | wikipedia-en
        → rank_hits_for_query
    → returns { query, hits[{title, snippet, url, backend}], error, ... }
    ↓
read_url_text (Fetch)
    → SSRF-validated HTTP GET
    → returns { ok, content (raw HTML/text), truncated, size_bytes, ... }
    ↓
LLM — hits/content を解釈して final_answer
```

**CONFIRMED FACT — 責務定義（Registry / SYSTEM_PROMPT）:**

| コンポーネント | 正式責務 |
|----------------|----------|
| `search_web` | query → backend → title/snippet/URL hits（意味理解なし） |
| `read_url_text` | 既知 URL → read-only GET → 本文（探索なし） |
| LLM | query 生成、source 選択、情報抽出、回答合成 |
| Agent | tool loop 実行、raw result を LLM に返却 |

**OBSERVATION:** Prompt には Search→Fetch 手順と grounding ルールが既に記載されているが、live trace では遵守されないケースが複数ある（Case B, F）。

---

## 3. Observed Problems

### 3.1 問題一覧（観測ソース別）

| ID | Symptom | Source | Layer |
|----|---------|--------|-------|
| P1 | snippet が常に空（wikipedia probe） | Failure Analysis tool probe | Tool / Interface |
| P2 | duckduckgo backend が全 probe で 0 hits | Failure Analysis | Tool / Backend |
| P3 | query 変形で無関係 title が上位（「大阪市の人口」→「不祥事」） | Failure Analysis | Tool / Ranking |
| P4 | Fetch 65536B truncated、nav/TOC/script 中心、人口本文未到達 | Failure Analysis + Case A | Tool / Interface |
| P5 | Fetch 後 LLM が HTML/JSON 構造を説明（人口未回答） | Practical Eval Case A, G | LLM / Interface |
| P6 | 明示 Fetch 指示でも read_url_text 未実行 | Practical Eval Case B | Agent / LLM |
| P7 | 空 search 後に Tool 外数値を回答 | Practical Eval Case F | LLM / Agent |
| P8 | 5×search で Fetch 0、final_answer null | Practical Eval Case C | Agent / LLM |
| P9 | Primary model が Tool Calling 非対応 | Practical Eval | MODEL_CAPABILITY |

### 3.2 問題の相互依存（HYPOTHESIS → 強い OBSERVATION）

```
P1 snippet 空 ──→ LLM は URL だけ頼りに Fetch 判断
       │
P3 無関係 hits ──→ LLM が Fetch 省略 or 誤判断 (P6)
       │
P4 raw/truncated HTML ──→ LLM が事実抽出不能 → メタ解析 (P5)
       │
P2 空 search ──→ LLM が retry 不十分 or  hallucination (P7)
       │
P8 max rounds ──→ 複数 source 比較不能
```

**CONFIRMED FACT:** 単一原因ではない。Search 品質・Fetch 契約・LLM utilization・Agent loop が **負の連鎖** を形成している。

---

## 4. Root Cause Analysis

### 4.1 統合因果链

| 段階 | 内容 |
|------|------|
| **Observed symptom** | 「大阪市の人口を調べて」に対し、人口数値を根拠付きで答えない |
| **Immediate cause** | (a) Fetch 省略 (b) Fetch 結果の meta 応答 (c) 空 search 後の hallucination |
| **Underlying cause** | Tool output が fact-bearing でない；snippet/relevance 信号不足；LLM grounding 失敗 |
| **Architectural cause** | **Discovery と Evidence の契約が分離されていない**。Fetch が「HTTP body を返す」で止まり、Agent/LLM が raw web bytes から fact extraction まで担う設計になっている |

### 4.2 レイヤ別 Root Cause

#### Tool

| Problem | Immediate | Underlying | Architectural |
|---------|-----------|------------|---------------|
| P1–P3 Search | backend 空、ranking 弱、snippet 未填充 | Wikipedia API が snippet を返さない設計；DDG 不安定 | Discovery output が **decision-ready でない** |
| P4 Fetch | 64KB cap + HTML 先頭偏重 | byte-limit fetch が DOM 構造を無視 | Fetch contract が **transport layer** で止まっている |

#### Interface / Contract

| Problem | Immediate | Underlying | Architectural |
|---------|-----------|------------|---------------|
| P5 | LLM が `content` を HTML artifact と解釈 | schema に `main_text` / `evidence` / `fact_ready` がない | **意味的レイヤの欠如** |
| P7 | 空 hits と factual answer の区別が結果 JSON にない | error 文字列のみ；confidence / provenance なし | grounding 可能な **typed failure** がない |

#### Agent

| Problem | Immediate | Underlying | Architectural |
|---------|-----------|------------|---------------|
| P6, P8 | LLM の tool selection に依存 | enforce 可能な invariant が code にない | orchestration が **prompt-only** |
| P8 | 同一 tool 反復で round 消費 | multi-source 用の構造化戦略なし | **research session** 概念なし |

#### LLM

| Problem | Immediate | Underlying | Architectural |
|---------|-----------|------------|---------------|
| P5, P7 | meta 解析 / hallucination | 小モデル + 長 HTML + 弱 grounding | LLM に過剰な extraction 責務 |
| P6 | Fetch 省略 | instruction following 不安定 | Agent 側 backup policy なし |

---

## 5. Responsibility Boundary Analysis

### 5.1 現状の暗黙契約（OBSERVATION）

| 能力 | 現状の担当 | 問題 |
|------|------------|------|
| query 生成 | LLM | 概ね OK（Case A） |
| backend 選択 | Tool（固定3 backend） | LLM 不可視、改善困難 |
| ranking | Tool | prefix match 弱点 |
| source 選択 | LLM | snippet 空で困難 |
| HTTP 取得 | Tool | OK |
| 本文特定 | **LLM（暗黙）** | **FAIL — 本来 Tool or 専用 layer** |
| 事実抽出 | **LLM（暗黙）** | **FAIL on raw HTML** |
| evidence 評価 | LLM | 不安定 |
| retry 戦略 | LLM | 5 round 枯渇 |
| grounding / 不確実性 | Prompt + LLM | Case F で破綻 |

### 5.2 設計原則（DESIGN PROPOSAL）

**原則 1 — Tool は「賢く」なるが「理解する」な**

- Tool は deterministic transformation を担当（fetch, normalize, extract structure）
- Tool は user intent の解釈、要約、推論を担当しない

**原則 2 — LLM は synthesis と judgment、Tool は evidence production**

- LLM が raw HTML から nav を除去する設計は **アンチパターン**（P5 で確認）
- LLM は **evidence block** を読んで回答を組み立てる

**原則 3 — Agent は policy enforcement、LLM は planning**

- 「空 search → 数値回答禁止」は Agent invariant として enforce 可能
- 「どの URL を読むか」は LLM planning でよい（Fetch 必須条件は Agent が定義）

**原則 4 — Interface が責務境界を明示する**

- `truncated: true` だけでは不十分；**何が欠落したか**（`body_reached: false` 等）を返す

### 5.3 推奨責務マトリクス（Recommended）

| 能力 | Search Tool | Fetch Tool | Agent | LLM |
|------|-------------|------------|-------|-----|
| query 受付 | ✓ | — | — | 生成 |
| backend 実行 | ✓ | — | — | — |
| relevance signal | ✓（heuristic） | — | — | 最終選択 |
| HTTP GET | — | ✓ | — | — |
| SSRF / safety | — | ✓ | 監視 | — |
| HTML→readable text | — | ✓ | — | — |
| section / title 抽出 | — | ✓ | — | — |
| truncation 管理 | — | ✓ | — | — |
| Fetch 必須判定 | — | — | ✓（rule） | 提案 |
| empty-result policy | — | — | ✓ | — |
| multi-source 計画 | — | — | 補助 | ✓ |
| fact synthesis | — | — | — | ✓ |
| source attribution | — | metadata | — | ✓ |

---

## 6. Candidate Architecture A — Tool-Centric Evidence Platform

### 6.1 概要

Search / Fetch 両 Tool を **evidence production platform** として強化。Agent / LLM は薄く保つ。

### 6.2 Architecture

```
LLM → search_web(query) → DiscoveryCard[]
LLM → read_url_text(url) → DocumentEvidence { title, main_text, sections[], metadata, quality_flags }
LLM → synthesize answer from DocumentEvidence only
```

### 6.3 各層の責務

| 層 | 責務 |
|----|------|
| **Search Tool** | multi-backend fetch, dedupe, ranking, **snippet 補完**（title extract 等）, relevance_score, backend_health |
| **Fetch Tool** | HTTP GET, **main content extraction**, charset, title, section anchors, **quality_flags**（truncated, body_reached, boilerplate_ratio） |
| **Agent** | tool loop, invariant check（optional minimal） |
| **LLM** | query, URL 選択, 回答合成, attribution |

### 6.4 Interface changes（DESIGN PROPOSAL）

**search_web hit:**

```json
{
  "title": "...",
  "url": "...",
  "snippet": "...",
  "backend": "wikipedia-ja",
  "relevance_hint": "high|medium|low|unknown",
  "fetch_recommended": true
}
```

**read_url_text result:**

```json
{
  "ok": true,
  "url": "...",
  "document": {
    "title": "...",
    "main_text": "...",
    "sections": [{"heading": "人口", "text": "..."}],
    "content_type": "text/html",
    "extraction": {"method": "...", "version": "..."}
  },
  "quality": {
    "truncated": true,
    "body_reached": false,
    "fact_ready": false,
    "warnings": ["truncated_before_main_content"]
  }
}
```

### 6.5 Required implementation

- Fetch: content normalization layer（library 非限定 — 実装選択は Human Review）
- Search: snippet fallback, ranking 改善, backend 可用性メタデータ
- Schema / Registry 更新
- 評価 harness 拡張

### 6.6 Advantages

- LLM 負荷大幅削減（P5 対策）
- Tool output のテスト可能性が高い
- 小モデルでも fact synthesis しやすい

### 6.7 Disadvantages

- Fetch Tool 複雑化、メンテ負荷
- サイト依存の extraction 失敗
- 「取得だけ」という現行の単純さを失う

### 6.8 Failure modes

- JS-rendered page → extraction 空
- Wikipedia 以外で extraction 精度低下
- false confidence（fact_ready=true だが誤抽出）

### 6.9 Security

- extraction 前後で SSRF boundary 維持（変更なし）
- extraction library の CVE 管理が必要

### 6.10 Backward compatibility

- **Breaking:** schema 変更。旧 `content` のみクライアントは要更新
- 移行: `content` + `document.main_text` 並行期間

### 6.11 Complexity / Testability

- Complexity: **中〜高**
- Testability: **高**（fixture HTML で extraction 単体テスト可能）

---

## 7. Candidate Architecture B — Agent-Centric Policy Orchestrator

### 7.1 概要

Tool は最小変更（メタデータ追加のみ）。**Agent loop に Web Research Policy** を実装し、LLM の判断を補正・強制する。

### 7.2 Architecture

```
User → Agent (WebResearchPolicy)
         ├─ phase: DISCOVER → enforce search
         ├─ phase: FETCH     → enforce fetch if hits non-empty AND user needs facts
         ├─ phase: ANSWER    → block numeric claims if no evidence
         └─ LLM tool-calling within policy gates
```

### 7.3 各層の責務

| 層 | 責務 |
|----|------|
| **Search Tool** | 現状維持（微改善 optional） |
| **Fetch Tool** | 現状維持 |
| **Agent** | Fetch gate, empty-search handler, round budget, retry template, **answer guard** |
| **LLM** | planning + synthesis（policy 範囲内） |

### 7.4 Interface changes

- Tool schema **変更最小**
- Agent 内部 state: `{ search_results, fetch_results, evidence_status, phase }`
- LLM への context injection: policy reminder + structured trace

### 7.5 Required implementation

- `agent.py` web research state machine
- post-tool hooks（Fetch 未実行検知）
- pre-answer validation（evidence なし数値禁止 — ルールベース or 軽量チェック）
- Prompt 調整（Agent policy と整合）

### 7.6 Advantages

- Tool 変更が少ない
- Case B（Fetch 省略）、Case F（hallucination）に直接対処可能
- 段階導入可能

### 7.7 Disadvantages

- **P4/P5 は未解決** — raw HTML を LLM に渡し続ける
- Agent 複雑化、LLM との二重制御
- モデル差異（qwen vs deepseek）で policy 効果が変動

### 7.8 Failure modes

- policy が過剰 → 不要 Fetch 増加
- policy 抜け → LLM が依然 meta 解析
- max rounds 問題は根本解決しない

### 7.9 Security

- 変更少なく **リスク低**

### 7.10 Backward compatibility

- **高** — Tool contract 維持

### 7.11 Complexity / Testability

- Complexity: **中**（Agent ロジック増）
- Testability: **中** — policy 単体テスト可、extraction 品質は未テスト

---

## 8. Candidate Architecture C — Hybrid Evidence Pipeline（推奨）

### 8.1 概要

**A の Evidence Contract** と **B の最小 Agent Invariants** を組み合わせる。Search / Fetch の責務分離は維持し、Fetch に **normalization** を追加、Agent に **grounding invariants** のみ追加。

Research Tool は作らない。

### 8.2 Architecture

```
User question
    ↓
Agent [invariants: no-hallucination-on-empty, fetch-required-heuristic]
    ↓
LLM plans: search query
    ↓
search_web → DiscoveryCard[] (with relevance_hint, snippet_fallback)
    ↓
LLM selects URL(s)
    ↓
read_url_text → DocumentEvidence (main_text + quality_flags)
    ↓
Agent checks quality_flags → if fact_ready=false, allow LLM retry (alternate URL or report uncertainty)
    ↓
LLM synthesizes with mandatory source citation from evidence
```

### 8.3 各層の責務

| 層 | 責務 |
|----|------|
| **Search** | Discovery + **decision-support metadata**（snippet 補完、relevance_hint、backend_status） |
| **Fetch** | Transport + **normalization to readable evidence** + quality assessment |
| **Agent** | Invariants only（grounding gate, phase hint, round budget awareness） |
| **LLM** | Query, selection, synthesis, multi-source comparison planning |

### 8.4 Interface changes

- A と同様の enriched contract（段階導入可能）
- Phase 1: `main_text` + `quality` 追加、`content`  deprecated
- Phase 2: Search discovery cards

### 8.5 Required implementation

1. Fetch normalization + quality flags（**最小変更で最大効果**）
2. Search snippet fallback + ranking tweak（**中優先**）
3. Agent grounding invariants（**小さく**）
4. Prompt を contract に整合（「main_text を根拠に」）
5. Evaluation harness 更新

### 8.6 Advantages

- P4/P5/P6/P7 に同時に効く可能性が高い
- Research Tool 不要
- 責務境界が明確
- 段階 rollout 可能

### 8.7 Disadvantages

- Tool + Agent 両方に変更が必要
- extraction 品質が新たな変動要因
- Human Review で extraction 方針の合意が必要

### 8.8 Failure modes

- normalization 失敗 → quality.warnings → LLM が uncertainty 報告（許容）
- Agent invariant と LLM planning の競合
- 過剰 Fetch（コスト増）

### 8.9 Security

- SSRF boundary 維持
- extraction は local only、追加 network なし

### 8.10 Backward compatibility

- **中** — フィールド追加は backward compatible、semantic change は major

### 8.11 Complexity / Testability

- Complexity: **中**
- Testability: **高**（Tool 単体 + Agent policy 単体 + E2E）

---

## 9. Optional Candidate Architecture D — Unified Research Session Tool

### 9.1 概要

`web_research(query, goals)` のような **上位 abstraction** が、内部で search → rank → fetch → normalize → aggregate を実行し、**Research Report** を返す。

### 9.2 Architecture

```
LLM → web_research(query, options) → ResearchReport { sources[], evidence[], gaps[], confidence }
LLM → answer from ResearchReport
```

Search / Fetch は内部実装 detail になり、LLM からは不可視。

### 9.3 Advantages

- LLM tool call 回数削減（P8 対策）
- multi-source 比較が容易
- 一貫した output contract

### 9.4 Disadvantages — **過剰設計リスク: 高**

- 現行 Agent は general-purpose；Web 専用 mega-tool は責務過多
- 内部 orchestration を Tool に閉じると **LLM の source 選択能力を評価できない**
- テスト・デバッグが black box 化
- Failure Analysis で Research Tool 必要性は **NOT_ESTABLISHED**

### 9.5 評価

**DESIGN PROPOSAL:** 将来の Research Agent 化時の **第2段階候補**。現時点では採用しない。

---

## 10. Comparison Matrix

| 観点 | A Tool-Centric | B Agent-Centric | C Hybrid（推奨） | D Research Tool |
|------|----------------|-----------------|------------------|-----------------|
| P4 Fetch 品質 | ◎ | ✕ | ◎ | ◎ |
| P5 LLM meta 解析 | ◎ | △ | ◎ | ◎ |
| P6 Fetch 省略 | △ | ◎ | ◎ | ◎ |
| P7 Hallucination | △ | ◎ | ◎ | ◎ |
| P1–P3 Search 品質 | ◎ | △ | ○ | ○ |
| P8 max rounds | △ | △ | ○ | ◎ |
| 実装規模 | 中〜大 | 小〜中 | 中 | 大 |
| 過剰設計リスク | 中 | 低 | 低 | **高** |
| Testability | 高 | 中 | 高 | 中 |
| Backward compat | 低 | 高 | 中 | 低 |
| Research Tool 必要 | No | No | No | Yes（本質） |

---

## 11. Failure Mode Analysis（推奨案 C）

| Failure | 検知 | 回復 |
|---------|------|------|
| Search 空 | `hits=[]`, backend_status | LLM query 再 formulation；Agent が hallucination block |
| 無関係 hits | relevance_hint=low | LLM 別 URL / 別 query；Fetch 後 fact_ready=false |
| Fetch truncated | quality.body_reached=false | 別 URL 試行 or 「確認不可」 |
| Extraction 失敗 | main_text 空 | warnings 返却；LLM uncertainty |
| LLM Fetch 省略 | Agent invariant | Fetch 強制 or clarification |
| max rounds | round budget | 部分回答 + gaps 明示 |

---

## 12. Security Analysis

**CONFIRMED FACT:** 現行 `read_url_text` は SSRF validation あり。

| 案 | 追加リスク | 緩和 |
|----|------------|------|
| A/C Fetch normalization | CPU/memory（大 HTML） | byte limit 維持、timeout、streaming cap |
| A/C Search 改善 | 外部 API 呼出増 | 既存 backend 範囲内 |
| B Agent policy | prompt injection 経由 policy bypass | invariant は code ベース |
| D Research Tool | 内部 multi-fetch の SSRF 面拡大 | 単一 entry point で SSRF 集中 |

**DESIGN PROPOSAL:** Security boundary は Fetch entry point に集中維持。normalization は fetch 後 local processing のみ。

---

## 13. Compatibility Analysis

| 項目 | 影響 |
|------|------|
| Registry schema | C: フィールド追加（minor version bump 想定） |
| agent.py | C: 小規模 invariant 追加 |
| SYSTEM_PROMPT | C: contract 参照に更新 |
| 既存 tests | Fetch/Search output 変更で更新必要 |
| deepseek 非対応 | **全案共通** — MODEL_CAPABILITY 問題は別 track |

---

## 14. Complexity Analysis

| 案 | 初期 | 継続 | 判断 |
|----|------|------|------|
| A | 中〜高 | 中 | Fetch extraction メンテが永続コスト |
| B | 低〜中 | 中 | Agent policy 分岐が増殖しうる |
| C | 中 | 中 | **バランス最良** |
| D | 高 | 高 | 現目的に対し過剰 |

---

## 15. Recommended Architecture

**案 C — Hybrid Evidence Pipeline** を採用する。

### 15.1 採用理由

1. **CONFIRMED FACT:** 最大の実害は Fetch 結果の non-fact-bearing 性（P4→P5）と grounding 失敗（P7）。Tool contract 変更が最も直接効く。
2. **CONFIRMED FACT:** Fetch 省略（P6）は Agent invariant で補完可能。Tool のみでは不足。
3. Research Tool（D）は Failure Analysis で NOT_ESTABLISHED。C は Search/Fetch 分離を維持しつつ契約を強化する **最小の architectural shift**。
4. B のみでは P5 未解決。A のみでは P6/P7 が残る。

### 15.2 ユーザー質問別フロー（DESIGN PROPOSAL）

#### 「大阪市の人口を調べて」

1. LLM: `search_web("大阪市 人口")`
2. Search: hits + relevance_hint；1位「大阪市」 fetch_recommended
3. LLM: `read_url_text(wikipedia URL)`
4. Fetch: main_text に人口 section、quality.fact_ready=true/false
5. fact_ready=false → LLM retry 別 source or 不確実性報告
6. LLM: 人口数値 + URL 引用

#### 「複数の情報源から確認して」

1. search → 2–3 URL 選択
2. fetch × N（round budget 内）
3. LLM: source ごとに evidence 比較
4. 矛盾あれば gaps 明示

#### 「最近の人口推移を調べて」

1. search（recency 語付き query）
2. 空 hits → Agent block hallucination；LLM reformulate
3. fetch 公式統計 or Wikipedia
4. 最新性を evidence metadata から判断

---

## 16. Why Alternatives Were Rejected

| 案 | 却下理由 |
|----|----------|
| **A only** | Agent grounding（P6/P7）が未解決のまま |
| **B only** | raw HTML 問題（P4/P5）が残り、実用改善が限定的 |
| **D** | 過剰設計；Search/Fetch 正常化前に orchestration を上乗せ；NOT_ESTABLISHED |

---

## 17. Success Criteria（DESIGN PROPOSAL）

Web Tool 経路を **実用的（Practical PASS）** とみなす条件:

| # | Criterion | 測定 |
|---|-----------|------|
| S1 | relevant source 取得 | 評価 case で 1位 hit が意図 URL を含む率 ≥ 80% |
| S2 | 必要本文取得 | fact_ready=true 率 ≥ 70%（Wikipedia 系 case） |
| S3 | LLM が本文利用 | 回答に Tool 由来の数値/事実が含まれ、HTML meta 論が ≤ 10% |
| S4 | 根拠なき数値なし | 空 search 時の hallucination 0 件 |
| S5 | failure 区別 | 「確認不可」と factual claim を区別 |
| S6 | retry 可能 | 1回 query reformulation + 1 alternate URL で回復可能（case 定義内） |
| S7 | multi-source | 2 source fetch + 比較回答が 1 case 以上 PASS |
| S8 | Tool failure 処理 | HTTP error / truncation を自然言語で説明、crash なし |

---

## 18. Implementation Roadmap（Design only — 未実施）

| Phase | 内容 | 依存 |
|-------|------|------|
| **R1** | Fetch: main_text + quality flags | Human Review（extraction 方針） |
| **R2** | Eval harness: fact_ready / S1–S3 自動採点 | R1 |
| **R3** | Agent: grounding invariants（empty block, fetch gate） | R1 |
| **R4** | Search: snippet fallback + ranking | 独立 |
| **R5** | Prompt: contract 整合 | R1, R3 |
| **R6** | Practical re-eval（qwen3:8b + primary model track） | R1–R5 |

**Git commit / production change:** 本 Phase では行わない。

---

## 19. Remaining Unknowns

| ID | Unknown | 影響 |
|----|---------|------|
| U1 | extraction 方式の最適解（ルールベース vs library vs API） | R1 工数・品質 |
| U2 | Prompt 変更のみで P5 の何割が解決するか | B/C の比重 |
| U3 | qwen3:8b 以外モデルでの再現性 | 一般化 |
| U4 | duckduckgo 空 hits の環境依存性 | Search 改善優先度 |
| U5 | JS-heavy page の対応範囲 | スコープ |
| U6 | primary model Tool Calling 対応時期 | production 評価 |

---

## 20. Human Review Questions

1. Fetch normalization の許容範囲はどこまでか（main_text のみ vs section 構造）？
2. `content`（raw HTML）フィールドは deprecated か、debug 用に残すか？
3. Agent invariant の強制度（Fetch 強制 vs LLM 提案尊重）？
4. Search backend 追加（DDG 代替）の優先度？
5. fact_ready の定義を誰が決めるか（heuristic vs Human-labeled eval）？
6. Research Tool を将来導入する trigger 条件は？

---

## Appendix — Q1–Q10 回答

### Q1 — 現在の最大の問題は何ですか？

**CONFIRMED FACT に基づく回答:** **Evidence Contract の欠如**。Fetch が fact-bearing data を返さず、LLM が grounding 不能 → meta 解析または hallucination に至る。

### Q2 — その問題はどこにありますか？

**主:** Interface / Architecture  
**副:** Tool（Fetch normalization 不足）, LLM（utilization / hallucination）, Agent（invariant 不足）  
単一レイヤーに帰属しない **横断問題**。

### Q3 — Search と Fetch の責務分担は適切ですか？

**部分的に YES（概念）/ 実装 NO（契約）。**  
Discovery vs Fetch の **分離自体は正しい**（OBSERVATION: Case A で正しい URL 選択）。  
しかし Fetch が「transport」で止まっており、Discovery 出力も decision-ready でない（P1–P4）。

### Q4 — Fetch は「取得」だけか「LLM 利用可能形への変換」までか？

**DESIGN PROPOSAL:** **変換まで担当すべき**。  
ただし要約・推論・intent 解釈は LLM。Fetch は **deterministic normalization + quality assessment** まで。

### Q5 — Search は単純 Discovery のままでよいか？

**DESIGN PROPOSAL:** **基本 YES**、ただし **decision-support metadata**（snippet 補完、relevance_hint、backend health）の追加は Discovery 範囲内。  
query expansion や deep ranking は Discovery を超える — 必要最小限に留める。

### Q6 — Agent に Search→Fetch→Evaluate→Answer を任せる設計は適切か？

**HYPOTHESIS:** **Planning は LLM、Enforcement は Agent** の hybrid が適切。  
現状の prompt-only orchestration は **不十分**（CONFIRMED: Case B, F）。  
Evaluate（evidence 評価）の大部分は LLM、**grounding gate** のみ Agent。

### Q7 — 専用 Research Tool は必要か？

**NOT_ESTABLISHED / 現時点 NO。**  
解決対象（P4/P5/P6/P7）は Search/Fetch contract + Agent invariants でカバー可能。  
multi-source round 問題（P8）は将来 D を検討する trigger になりうるが、今は過剰。

### Q8 — 最小限の変更で実用性を大きく改善するには？

**DESIGN PROPOSAL（最小セット）:**

1. Fetch: `main_text` + `quality.fact_ready` / `body_reached`（R1）
2. Agent: 空 search 時の数値回答禁止（R3）
3. Prompt: main_text を根拠に回答する旨（R5）

Search ranking 改善は **次点**。

### Q9 — 将来 Research Agent 化時の障害

- raw contract 前提の eval / prompt
- Tool ごと個別 orchestration（session 概念なし）
- round budget と multi-source の構造的不整合
- extraction なし Fetch（スケール時に LLM コスト爆発）
- backend 固定 3 種（coverage 限界）

### Q10 — 設計責任者として採用する設計は？

**案 C — Hybrid Evidence Pipeline。**

理由: CONFIRMED FACT の主因（non-fact-bearing Fetch, grounding 失敗）に直結しつつ、Research Tool ほど過剰でない。Search/Fetch 分離という **既存 architectural bet を維持** しながら、欠けていた **evidence layer** を追加する。A 単独・B 単独の弱点を補完し、D の過剰設計を避ける。

---

**STOP — Human Review を待つ。**

**Production changes:** NONE  
**Git commit:** NONE
