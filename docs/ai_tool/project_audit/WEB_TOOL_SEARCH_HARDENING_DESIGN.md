# Web Tool Search Hardening — Design & Implementation Planning

**Probe run:** `20260828_220532_web_tool_search_hardening_probe`  
**Git HEAD:** `f4150e9`  
**Inputs:** Phase 3 isolation, Phase 4 diagnosis, live deterministic probe  
**Production changes:** NONE | **Git commit:** NONE

---

## 1. Purpose & STOP

本 Phase の目的は **Search を直すことではない**。Phase 4 診断の Option A（Search layer hardening）について、

- 現行実装の読み取り
- 失敗層の分離
- 修正案の比較
- Human Review 項目
- 承認後の最小変更単位

までを設計し **STOP** する。

---

## 2. Current Search Architecture (CONFIRMED FACT)

### 2.1 Call chain

```text
LLM → search_web() → general_web_search() → backends → rank_hits_for_query() → enrich_hit_for_discovery()
Agent → enrich_web_tool_result("search_web", ...)  [grounding hints only]
```

| Layer | File | Responsibility |
|-------|------|----------------|
| Tool entry | `tools/system/network/search_web.py` | Thin wrapper; `strip()` only |
| Orchestration | `tools/system/network/general_web_search.py` | Backend fan-out, collect, rank, schema |
| Backends | `tools/system/tool_builder/research/web.py` | DDG Instant Answer API, ja Wikipedia OpenSearch |
| en Wikipedia | `general_web_search.search_wikipedia_en()` | en OpenSearch |
| Grounding | `tools/system/network/web_evidence.py` | Policy hints; **no ranking** |

**CONFIRMED FACT:** Agent general Web 経路は Tool Builder `research.web.search_web`（MS Learn + HIT_KEYWORDS）を **呼ばない**（`tests/test_general_web_search.py`）。

### 2.2 Search result schema

```json
{
  "query": "...",
  "hits": [{"title", "snippet", "url", "backend", "relevance_hint"}],
  "backends_tried": ["duckduckgo", "wikipedia-ja", "wikipedia-en"],
  "candidates_collected": N,
  "fetch_limit", "return_limit",
  "grounding": {"web_evidence_available", "empty_search", "discovery_only"}
}
```

### 2.3 Ranking (CONFIRMED FACT)

- `query_tokens()` — whitespace/punctuation split; CJK full phrase appended; **`の` は分割文字に含まれない**
- `score_hit_for_query()` — token-in-title (+3), token-in-blob (+1), full-query match (+5/+3), CJK bonus (+1)
- `rank_hits_for_query()` — sort by score; ties retain collection order; `relevance_hint` from score thresholds (≥5 high, ≥2 medium, ≥1 low)

### 2.4 Query preprocessing (CONFIRMED FACT)

**None beyond `str(query).strip()`** in `general_web_search()`. Normalization / variant expansion **未実装**。

---

## 3. Search Failure Decomposition

| Layer | Osaka case evidence | Classification |
|-------|---------------------|----------------|
| **Query generation** | Phase 2 live: LLM emits `大阪市の人口` not `大阪市 人口` | **CONFIRMED FACT** (trace) — **outside Search tool** |
| **Query normalization** | `query_tokens(大阪市の人口)` → `["大阪市の人口"]` single token; no の-split | **CONFIRMED FACT** (code + probe) |
| **Backend coverage** | DDG: AbstractText_len=0, RelatedTopics=0 for ja queries | **CONFIRMED FACT** (probe) |
| **Backend raw quality** | wiki-ja OpenSearch: space query → title `大阪市`; の query → `大阪市の不祥事`… **`大阪市` page absent** | **CONFIRMED FACT** (probe) |
| **Ranking** | Space variant: all scores=4 → tie → first=`大阪市` by order; Python: NumPy score 17 > Python 9 | **OBSERVATION** — ranking matters when pool is good; **cannot fix missing entity** |
| **Relevance classification** | の-variant all scores=1 → `relevance_hint=low` | **CONFIRMED FACT** — hint correct given scores |
| **Result presentation** | wiki OpenSearch snippet often empty; fallback copies title (`enrich_hit_for_discovery`) | **CONFIRMED FACT** (code) |

### 3.1 Phase 4 diagnosis mapping

| Phase 4 symptom | Search layer mapping |
|-----------------|----------------------|
| `wrong_search_top_result` | backend_raw_quality + query_variant (**not ranking-only**) |
| `search_backend_empty` (DDG) | backend_coverage (Instant Answer API empty) |
| LLM bad query variant | query_generation (**MODEL_CAPABILITY / outside tool**) |

---

## 4. 「大阪市 人口」vs「大阪市の人口」— Deterministic Probe

**Run:** `runs/ai_tool/20260828_220532_web_tool_search_hardening_probe/`

| Field | 大阪市 人口 | 大阪市の人口 |
|-------|------------|-------------|
| query_tokens | `["大阪市","人口","大阪市 人口"]` | `["大阪市の人口"]` |
| wiki-ja raw 1st | **大阪市** | **大阪市の不祥事** |
| entity exact in raw | **true** | **false** |
| top score | 4 | 1 |
| final 1st | 大阪市 | 大阪市の不祥事 |
| relevance_hint | medium | low |
| DDG hits | 0 | 0 |

### 4.1 Evidence chain

```text
OBSERVATION: LLM may generate の-insertion query (Phase 2 trace)
↓
CONFIRMED FACT: wiki-ja OpenSearch returns different title sets (probe 20260828_220532)
↓
CONFIRMED FACT: expected entity page absent from raw pool for の-variant
↓
CLASSIFICATION: NOT ranking-only — reordering cannot surface 大阪市
↓
HYPOTHESIS: Wikipedia OpenSearch prefix-matches 「大阪市の*」 articles before entity page
↓
UNKNOWN: formal Wikipedia API documentation citation in-repo (behavior inferred from probe)
```

### 4.2 Responsibility split

| Question | Answer |
|----------|--------|
| 検索エンジン（ranking）が悪い？ | **Partial** — ties weak; NumPy case shows mis-rank; **Osaka の case is NOT ranking** |
| backend adapter が悪い？ | **Partial** — adapter faithfully returns OpenSearch results; **query sensitivity is backend API semantics** |
| ranking が悪い？ | **No** for の-variant (entity not in pool) |
| query variant が悪い？ | **Yes** — variant changes raw backend results |

---

## 5. DuckDuckGo Empty — Investigation

### 5.1 CONFIRMED FACT (probe `ddg_raw_matrix.json`)

| Query | AbstractText_len | RelatedTopics_count | DDG adapter hits |
|-------|------------------|---------------------|------------------|
| 大阪市 人口 | 0 | 0 | 0 |
| 大阪市の人口 | 0 | 0 | 0 |
| 東京 人口 | 0 | 0 | 0 |
| Paris population | 0 | 0 | 0 |
| Python programming language | 952 | 21 | 5 |
| empty_control | 0 | 0 | 0 |

- Adapter uses **`https://api.duckduckgo.com/` Instant Answer API** (`research/web.py:search_duckduckgo`)
- No HTTP error in probe — **empty structured response**, not exception
- Japanese fact queries: **consistent empty** in this environment

### 5.2 Classification

| Hypothesis | Status |
|------------|--------|
| transient failure | **Unlikely** in single run — reproducible empty for ja queries |
| query format | **OBSERVATION** — en entity query works; ja fact queries do not |
| API spec (Instant Answer ≠ web search) | **CONFIRMED FACT** — API returns Abstract/RelatedTopics; not full SERP |
| backend adapter bug | **UNKNOWN** — adapter may be correct for IA API; **full web search not implemented** |
| environment / network | **UNKNOWN** — no error; cannot distinguish policy vs locale vs API design without external doc run |

### 5.3 Required observation for future

- DDG HTML/lite API vs Instant Answer comparison
- Rate-limit / geo response headers
- **Human Review** before changing DDG integration strategy

---

## 6. Ranking Hardening Options — Comparison

| Option | Description | Effect on Osaka の | Side effects | Scale | Site-specific risk | Automation fit | Regression risk | UNKNOWN |
|--------|-------------|-------------------|--------------|-------|-------------------|----------------|-----------------|---------|
| **A** | Improve token-based ranking | **None** — entity not in pool | NumPy-style fixes possible | S | Low | High (unit tests) | Medium | Optimal tie-break rules |
| **B** | Query normalization before backends | **High** — if の→space or entity split | Wrong normalization harms other queries | S–M | **High** (ja particles) | High (probe matrix) | Medium | General rules vs locale |
| **C** | Entity/intent-aware scoring | Medium if entity extracted | False boosts; scope creep (S6 violation) | M–L | High | Medium | High | Entity extraction without LLM |
| **D** | Minimal ranking; expose raw backends | Surfaces low-score hits; **still no 大阪市** unless multi-query | LLM selection burden ↑ | S | Low | High | Low | LLM hit selection quality |
| **E** | Backend-specific rules (wiki dual-query) | **High** — secondary OpenSearch for entity token | Multi-query latency; backend maintenance | M | Medium (wiki-specific) | High (per-backend probes) | Medium | Optimal dual-query set |

### 6.1 Recommendation (design only — **not implemented**)

**Primary: Option B + E (query shaping + Wikipedia dual-query)**  
**Secondary: Option A (tie-break + token weighting)** for cases like Python/NumPy where entity **is** in pool

**Not recommended alone:** Option A only — Phase 4 + probe prove **ranking-only insufficient** for の-variant.

**Rationale:**
- Probe shows **raw pool difference** before ranking
- `relevance_hint=low` already signals bad hits — ranking is not the first failure
- Option B+E stays within **Discovery** scope (S6) if limited to query shaping, not answer generation

---

## 7. Success Criteria (S1–S8)

| ID | Criterion | Design status |
|----|-----------|---------------|
| S1 | Query variant quality measurable | ✅ `web_tool_search_hardening_probe.py` |
| S2 | Raw backend vs ranking separable | ✅ `entity_in_raw_backend`, `pre_rank_scored`, `final_hits` |
| S3 | Relevance basis stored | ✅ score + relevance_hint in probe JSON |
| S4 | Before/after comparable | ✅ probe re-run + diff JSON |
| S5 | Regression queries | ✅ `empty_control`, `en_python` in DEFAULT_PROBE_QUERIES |
| S6 | No semantic answering in Search | ✅ design scope = Discovery only |
| S7 | UNKNOWN not forced to PASS | ⚠️ Paris all-empty root cause remains UNKNOWN |
| S8 | Failure Diagnosis compatible | ✅ decomposition labels + ObservationBundle fields |

---

## 8. Automation Loop Integration

```text
Failure (wrong_search_top_result)
  → probe_query_variant() / run_search_hardening_probe()
  → entity_in_raw_backend false + entity_in_raw_a true
  → Diagnosis: RESULT_QUALITY / backend_raw_quality + query_variant
  → Proposal: Option B+E
  → Human Review
  → Implementation (future)
  → Re-probe (same RUN_ID pattern)
```

**Metrics for auto-eval:**
- `entity_in_final_first` (exact title match)
- `entity_in_raw_backend`
- `top_score` / `relevance_hint` distribution
- `duckduckgo_raw_matrix` fields
- Regression: `empty_control` stays empty; `en_python` first hit contains "Python"

---

## 9. Human Review Required (before implementation)

| Item | Why |
|------|-----|
| Query normalization rules | Language-specific; over-normalization risk |
| Multi-query Wikipedia strategy | Latency, API etiquette, dedup |
| DDG role | Keep IA API vs replace vs demote to optional |
| Entity exact-match boost | Definition of entity vs substring (probe uses exact title) |
| Interaction with LLM query generation | Search fix does not replace Prompt/Agent for query choice |
| Paris / all-empty queries | UNKNOWN root cause — do not block Osaka fix on Paris |

---

## 10. Minimal Implementation Scope (PROPOSED — not executed)

**If approved, smallest defensible change set:**

1. **`general_web_search.py` only** — add optional query shaping hook (e.g. `expand_backend_queries(query) -> list[str]`) with **no Agent/Prompt change**
2. Wikipedia-ja: primary query + **entity-spaced variant** when CJK + particle pattern detected
3. Unit tests: Osaka pair + Python regression + empty_control
4. Probe re-run as acceptance gate
5. **Explicitly out of scope v1:** DDG replacement, LLM query rewriting, Fetch/Agent changes

**Estimated touch surface:** 1–2 files + tests + probe baseline update  
**Registry / schema change:** Prefer **none** — internal multi-query transparent to LLM

---

## 11. Artifacts

| Path | Role |
|------|------|
| `docs/ai_tool/project_audit/WEB_TOOL_SEARCH_HARDENING_DESIGN.md` | This document |
| `ai_tool/web_tool_search_hardening_probe.py` | Deterministic probe |
| `ai_tool/run_web_tool_search_hardening_probe.py` | Runner |
| `tests/ai_tool/project_audit/test_web_tool_search_hardening_design.py` | 6 tests |
| `runs/ai_tool/20260828_220532_web_tool_search_hardening_probe/` | Live probe JSON |

---

## 12. Unresolved UNKNOWNs

1. Paris population — all backends empty (wiki-en also 0 hits in probe); transient vs query vs API limit **UNKNOWN**
2. DDG — whether alternate DDG endpoint would help ja queries **UNKNOWN** without approved API investigation
3. LLM query generation — how often の-variant occurs across full benchmark **UNKNOWN** outside Phase 2 traces
4. Optimal normalization — general ja particle rules vs minimal Osaka-specific **UNKNOWN** — Human Review

---

## 13. STOP

**Production / Registry / Agent / Prompt / Search 実装変更: NONE**  
**Git commit: NONE**

**推奨 Option:** B + E (query shaping + Wikipedia dual-query), with A for in-pool ranking ties  
**代替 Option:** D (minimal ranking, richer candidate exposure) — shifts burden to LLM  
**実装最小範囲:** `general_web_search.py` query expansion + tests + probe gate  
**Human Review:** REQUIRED before any implementation
