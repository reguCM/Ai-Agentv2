# Web Tool Failure Isolation — Phase 3

**Run:** `20260828_215543_web_tool_failure_isolation_phase3`  
**Git HEAD:** `f4150e9`  
**Inputs:** Phase 1 live (`20260828_201538`), Phase 2 live (`20260828_214841`), tool-only probes  
**Production changes:** NONE | **Git commit:** NONE

---

## 1. Executive Summary

Phase 3 は **実装せず**、Search / Agent / LLM / Fetch / Prompt を証拠付きで切り分けた。

**CONFIRMED FACT:** 問題は単一層ではない。Search（query 変形 + backend 依存）、LLM（Fetch 未選択・hallucination）、Prompt（fetch 率への寄与）、Fetch（ページ依存 fact_ready）が **独立に存在** する。

**最重要発見:** `大阪市 人口`（space）は Tool 層で正しい 1 位 URL を返すが、LLM が Phase 2 で `大阪市の人口`（の-insertion）を生成すると **ranking 1 位が無関係** になる（**A3: ranking/backend prefix**）。Fetch 未実行は eval 経路では **LLM tool selection** が原因（Agent block の証拠なし）。

---

## 2. Methodology

| Track | Method | Production change |
|-------|--------|-------------------|
| A Search | 8 general queries, per-backend raw, pre/post rank | NONE |
| B Agent | Phase 1+2 live trace replay | NONE |
| C LLM | Capability bucket matrix from traces | NONE |
| D Fetch | read_url_text on ranked URLs | NONE (existing tool) |
| E Prompt | Phase1 detailed vs Phase2 minimal metrics | NONE |

Classification labels: CONFIRMED FACT / OBSERVATION / HYPOTHESIS / UNKNOWN / DESIGN PROPOSAL

---

## 3. A — Search Failure Isolation

### 3.1 Query variant comparison (CONFIRMED FACT)

| Query | 1st hit | first_hit_relevant | wikipedia-ja 1st | duckduckgo |
|-------|---------|-------------------|------------------|------------|
| `大阪市 人口` | 大阪市 | **true** | 大阪市 | empty |
| `大阪市の人口` | 大阪市の不祥事 | **false** | 不祥事 | empty |
| `東京 人口` | 東京・河口湖号 | true* | 東京-related | empty |
| `富士山 高さ` | 富士山-信仰の対象と芸術の源泉 | true* | world heritage | empty |
| `Python programming language` | Python (DDG) | true | empty | hit |
| `Paris population` | — | empty all | empty | empty |
| `日本 首都` | 日本の首都 | true | 日本の首都 | empty |
| empty control | — | empty | empty | empty |

\*relevance_hint / entity match heuristic; snippet 空は全 probe で common

### 3.2 Evidence chain — の-insertion 問題

```
OBSERVATION: Phase2 Case A LLM generated query 「大阪市の人口」
↓
CONFIRMED FACT: probe 「大阪市の人口」→ 1位「大阪市の不祥事」 (A3_ranking_irrelevant_first)
↓
CONFIRMED FACT: probe 「大阪市 人口」→ 1位「大阪市」 wiki URL (search_ok_at_tool_layer)
↓
HYPOTHESIS: LLM query generation interacts with Wikipedia prefix OpenSearch → wrong discovery
↓
NOT CONFIRMED: LLM would select correct hit if hits included both 大阪市 and 不祥事 (A4 not live-tested)
```

### 3.3 Backend vs ranking vs query

| Sub-problem | Evidence | Classification |
|-------------|----------|----------------|
| duckduckgo empty | 7/8 probes DDG=[] | CONFIRMED FACT — backend coverage gap |
| の-variant ranking | 1 probe irrelevant first | CONFIRMED FACT — ranking/backend prefix |
| composite query empty | Paris population, long ja queries in Phase2 | OBSERVATION |
| LLM query choice | Phase2 A uses bad variant | CONFIRMED FACT (trace) |
| LLM hit selection | Not isolated (fetch skipped before selection matters) | UNKNOWN |

---

## 4. B — Agent Loop Failure Isolation

### 4.1 Post-search decision matrix (Phase 1 + 2)

| Case | P1 decision | P2 decision | Fetch explicit? |
|------|-------------|-------------|---------------|
| A | FETCH_SELECTED | ANSWER_WITHOUT_FETCH | no |
| B | ANSWER_WITHOUT_FETCH | ANSWER_WITHOUT_FETCH | **yes** |
| C | RESEARCH_WITHOUT_FETCH | RESEARCH_WITHOUT_FETCH | no |
| G | FETCH_SELECTED | ANSWER_WITHOUT_FETCH | no |

### 4.2 Fetch 未実行の分解

```
OBSERVATION: Fetch not executed (Phase2: 0/7 cases)
↓
CONFIRMED FACT: eval harness calls execute_registry_tool directly on LLM tool_calls
↓
CONFIRMED FACT: agent_blocked_fetch=false for all traces
↓
CLASSIFICATION: 「LLM did not select read_url_text」— NOT 「Agent blocked Fetch」
↓
UNKNOWN: production agent.py loop with enrich_web_tool_result only (no gate) — same expected behavior
```

**Case B (both phases):** user says「読んで」→ search only → **HIGH confidence LLM layer**

---

## 5. C — LLM Capability Isolation

| Bucket | Cases (examples) | Interpretation |
|--------|------------------|----------------|
| FETCH_BUT_META_RESPONSE | P1-A | Understands fetch; fails utilization (pre-Evidence) |
| SEARCH_POOR_OR_MISUNDERSTOOD | P1-B, P2-B | Skips fetch after poor hits |
| HALLUCINATES_ON_EMPTY | P2-C, P1/P2-F | Supplements when search empty |
| GROUNDED_OR_UNCERTAIN_OK | P1-D, P2-D, P2-G | Can refuse when no evidence |
| NO_FINAL_ANSWER | P1-C | max rounds |

**Prompt-only fixable?** HYPOTHESIS: partial for fetch rate; **NOT** for search quality or fact_ready.

---

## 6. D — Fetch Failure Isolation

| URL source | fact_ready | Note |
|------------|------------|------|
| 大阪市 (good rank) | **false** | wikidata/boilerplate warnings |
| 東京・河口湖号 | **true** | 6335 chars main_text |
| 日本の首都 | **true** | 17317 chars |
| 大阪市の不祥事 (bad rank) | **true** | wrong page but fetch works |
| DDG NumPy redirect | false | body not reached |

**CONFIRMED FACT:** Fetch failure modes are **separable**:
1. Fetch not called (LLM) — Phase2 live
2. Fetch ok, fact_ready=false (大阪市 wiki) — tool probe
3. Fetch ok, fact_ready=true on **wrong** page (不祥事) — Search sent bad URL

---

## 7. E — Prompt Contribution

| Metric | Phase1 detailed | Phase2 minimal |
|--------|-----------------|----------------|
| fetch_rate | 0.29 (2/7) | **0.00** |
| html_meta answers | 2 | **0** |
| hallucination signals | 2 | 2 |
| answer_without_fetch | 1 | 5 |

**CONFIRMED FACT:** Detailed prompt **increases fetch rate** but did not prevent HTML meta (P1-A,G).  
**CONFIRMED FACT:** Evidence Pipeline removed HTML meta regardless of prompt.  
**HYPOTHESIS:** Prompt alone cannot fix Search ranking or fact_ready.

---

## 8. Root Cause Table

| Problem | Layer | Evidence | Confidence | Impact | Proposed next action |
|---------|-------|----------|------------|--------|----------------------|
| の-variant query → irrelevant 1st hit | Search | probe + Phase2 trace | HIGH | HIGH | PROPOSED CHANGE: ranking/backend (Human Review) |
| duckduckgo empty 7/8 probes | Search | tool probe | HIGH | MEDIUM | PROPOSED CHANGE: backend investigation |
| LLM skips Fetch when user asks「読んで」 | LLM | Case B ×2 phases, no Agent block | HIGH | HIGH | PROPOSED CHANGE: fetch gate (Human Review) |
| Numeric hallucination on empty search | LLM | C/F traces | MEDIUM | HIGH | PROPOSED CHANGE: Agent enforce |
| Detailed prompt raises fetch rate | Prompt | 0.29 vs 0.00 | HIGH | MEDIUM | Contract hints, not step list |
| Eval path lacks Agent enforcement | Agent | execute_registry_tool design | HIGH | MEDIUM | PROPOSED: prod vs eval test split |
| 大阪市 wiki fact_ready=false | Fetch | probe | MEDIUM | MEDIUM | PROPOSED: extraction (Human Review) |

---

## 9. Proposed Options (not implemented)

### Option A — Search layer hardening
- **Targets:** ranking, Wikipedia prefix handling, backend coverage
- **Side effects:** site-specific tuning risk
- **Safety:** LOW | **Scale:** MEDIUM | **Automation fit:** HIGH

### Option B — Agent loop policy
- **Targets:** fetch gate, empty-search numeric block
- **Side effects:** over-fetch if hits low-quality
- **Safety:** MEDIUM | **Scale:** SMALL-MEDIUM | **Automation fit:** MEDIUM

### Option C — Fetch extraction quality
- **Targets:** 大阪市 fact_ready=false
- **Side effects:** maintenance burden
- **Safety:** LOW-MEDIUM | **Scale:** MEDIUM | **Automation fit:** HIGH

---

## 10. Automation Loop Insights

```text
Symptom: Fetch not executed
  Required observation: selected_tools, fetch markers in user_request, search hits
  Decision rule: IF explicit_fetch AND fetch_calls=0 AND NOT agent_blocked → LLM
  Human Review: YES

Symptom: Wrong first hit
  Required observation: query string, per_backend titles, pre_rank scores
  Decision rule: IF backend_has_entity AND ranked_first_wrong → Search ranking
  Human Review: YES

Symptom: Hallucinated number
  Required observation: empty_search flag, numeric regex, uncertainty phrases
  Decision rule: IF empty_search AND numeric AND NOT uncertainty → LLM (+ Agent enforce candidate)
  Human Review: YES
```

---

## 11. Artifacts

| Path | Content |
|------|---------|
| `ai_tool/web_tool_failure_isolation_phase3.py` | harness |
| `ai_tool/run_web_tool_failure_isolation_phase3.py` | runner |
| `tests/ai_tool/project_audit/test_web_tool_failure_isolation_phase3.py` | tests (6 passed) |
| `runs/ai_tool/20260828_215543_web_tool_failure_isolation_phase3/` | raw JSON + pytest log |

---

## 12. Human Review Required

**YES** — any PROPOSED CHANGE above requires Human Review before implementation.

**STOP:** Implementation not performed in this Phase.
