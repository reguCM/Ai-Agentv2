# Web Research Benchmark — Independent Comparative Evaluation

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Run:** `runs/ai_tool/20260829_151650_web_research_benchmark/`  
**Production changes:** NONE

---

## Executive Summary

| Item | Result |
|------|--------|
| **Benchmark result** | **RESULT_C** — Layer-specific strengths |
| **Golden GT1–GT6** | **6/6 PASS** |
| **Self tool-layer pass rate** | **11/15 (73.3%)** |
| **External paid APIs** | **REQUIRES_CREDENTIAL** (not run) |
| **Decision** | **CONTINUE** (investigation complete; no Production change) |

---

## 1. Baseline Result

Production tool chain: `search_web → read_url_text → enrich → web_status`

| Metric | Value |
|--------|-------|
| Cases | 15 (7 live + 8 fixture) |
| Tool-layer PASS | 11/15 |
| Avg latency | ~1148 ms/case |
| Golden regression | **6/6 PASS** |

### Live cases

| Case | Category | Tool PASS | Failure layer |
|------|----------|-----------|---------------|
| WRB-L01 Osaka pop | B01 | ✅ | — |
| WRB-L02 Japan capital | B01 | ✅ | — |
| WRB-L03 Yokohama | B04 | ✅ | — |
| WRB-L04 Japan area | B02 | ❌ | EXTRACTION |
| WRB-L05 English Osaka | B05 | ❌ | SEARCH |
| WRB-L06 Non-Wikipedia | B06 | ❌ | SEARCH |
| WRB-L07 Largest city | B07 | ❌ | SEARCH |

### Fixture cases: **8/8 PASS**

---

## 2. External Targets

| Target | Status |
|--------|--------|
| Tavily | REQUIRES_CREDENTIAL |
| Serper | REQUIRES_CREDENTIAL |
| Brave Search | REQUIRES_CREDENTIAL |
| DuckDuckGo (OSS) | AVAILABLE — search-only baseline |
| Wikipedia OpenSearch | AVAILABLE (via production backends) |
| LangChain Tavily Agent | REQUIRES_HUMAN_ACTION |

**Comparison mode:** SELF + OSS_SEARCH_ONLY_BASELINE

---

## 3. Dataset

15 cases across B01–B08. Fixture: `ai_tool/fixtures/web_research_benchmark_cases.json`

Ground truth: ExpectedFact + deterministic matchers.  
Judgment modes: DETERMINISTIC / PARTIAL / MANUAL_REQUIRED (WRB-L06).

**No LLM Judge as ground truth.**

---

## 4–8. Layer Comparisons

### Search

- **Self (production search_web):** 4/7 live failures at SEARCH layer (L05–L07, complex queries)
- **Self strong on:** simple factual Wikipedia queries (L01–L03)
- **DDG baseline:** 0 hits on sampled live queries in this run — production search **superior** on those cases

### Fetch

- Live Wikipedia fetch: success when search hits (L01–L03)
- Failures primarily upstream (SEARCH) not FETCH

### Extraction

- WRB-L04 (Japan area): EXTRACTION — fact not matched in main_text patterns
- Fixture extraction: 100% when HTML controlled

### Evidence

- `fact_ready` + ExpectedFact in evidence: strong on fixture + simple live
- `enrich_web_tool_result` operational

### LLM (mock sample, fixture only)

- Canonical eval mock LLM: mixed — mock answer quality limits taxonomy sample
- Live LLM full benchmark: **not run** (optional future phase)

---

## 9. Evidence → LLM Separation

| Path | Search | Extracted content | Boundary | Verify |
|------|--------|-------------------|----------|--------|
| Self production chain | ✅ | ✅ main_text | ✅ canonical | ✅ experimental |
| DDG OSS baseline | partial | ❌ | ❌ | ❌ |
| Paid API (Tavily etc.) | UNKNOWN | UNKNOWN | ❌ | ❌ |

---

## 10. Orchestration

Composite fixture WRB-F06 (area + population): **PASS** at tool layer.  
Live multi-step (L07): SEARCH failure — orchestration not primary bottleneck; search query formulation is.

External orchestration: **UNKNOWN** (no API access).

---

## 11. Failure Taxonomy

| Layer | Count |
|-------|-------|
| SEARCH | 3 |
| EXTRACTION | 1 |
| FETCH | 0 |
| EVIDENCE | 0 (tool-layer) |

**Web failed vs LLM failed:** Tool-layer benchmark isolates Web; LLM sample separate.

---

## 12. Cost / Latency

- Self avg ~1.1s/case (search + fetch)
- External API cost: **N/A** (not invoked)
- No paid API consumption

---

## 13. Unique Capabilities — Self

- WebSessionTracker + web_status layer gating
- web_answer_boundary (canonical path)
- enrich_web_tool_result + fact_ready
- Eval Production Parity Bridge (SCR-01)
- Mechanical Verification (experimental, no answer replacement)

---

## 14. Unique Capabilities — External

- Paid research APIs: likely pre-extracted passages ( **UNKNOWN** without credentials)
- SaaS orchestration: **UNKNOWN**
- DDG instant: search-only, no evidence pipeline

---

## 15. Core Capability Discovery

| ID | Name | Class | Notes |
|----|------|-------|-------|
| CAND-B | Search reranking | **C2** if search failures persist; else C1 | 3 SEARCH failures |
| CAND-H | Post-LLM verify (OPT7) | **C1** | Extend CC-02 |
| CAND-F | Multi-step orchestration | **C1** | External not benchmarked |
| CAND-I | Research transaction | **C0** | Duplicate of mirror + diagnosis |

**New C3 this phase:** NONE

---

## 16. Architecture Options (PROPOSE only)

| ID | Status |
|----|--------|
| OPT_KEEP | **PROPOSE** — maintain current chain |
| OPT_EXT_API | **RECORD** — optional backend; HR + credentials |
| OPT_OPT7 | **RECORD** — extend Mechanical Verification |

**No IMPLEMENT this phase.**

---

## 17. Selected Decision

**CONTINUE** — benchmark complete; no Production architecture change warranted.

Benchmark classification: **RESULT_C** (layer-specific: self Evidence/Boundary strong; search weak on complex live queries; external paid compare incomplete).

---

## 18. Production Changes

**NONE**

---

## 19. Human Review

**Not required** for this phase.

Optional future HR:
- Tavily/Serper trial API for full external compare
- OPT7 Production Warning promotion

---

## 20. Remaining Unknowns

- Paid API comparative performance
- Live LLM answer accuracy on full 15-case set
- External SaaS evidence/passage format
- WRB-L06 non-Wikipedia (MANUAL_REQUIRED)

---

## 21. Next Recommended Phase

Optional: HR-approved Tavily trial on same 15-case dataset to validate RESULT_C with external evidence pipeline.

---

## Artifacts

| File | Path |
|------|------|
| Harness | `ai_tool/web_research_benchmark.py` |
| Dataset | `ai_tool/fixtures/web_research_benchmark_cases.json` |
| Runner | `ai_tool/run_web_research_benchmark.py` |
| Tests | `tests/ai_tool/project_audit/test_web_research_benchmark.py` |

---

## STOP Conditions

None triggered. Golden PASS. No Production changes required.

---

## Philosophy Applied

- Goal was **layer objective judgment**, not winning against public tools
- Paid APIs not assumed; credential requirement recorded
- 「今不要」≠「将来不要」 — CAND-H/CAND-F recorded as C1
- 「公開Toolに存在」 alone did not add Core — CAND-I rejected as C0
