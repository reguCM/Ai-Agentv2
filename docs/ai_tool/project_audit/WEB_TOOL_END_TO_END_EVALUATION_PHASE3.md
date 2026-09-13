# Web Tool End-to-End Practical Evaluation — Phase 3

**Run:** `20260828_222738_web_tool_end_to_end_evaluation_phase3`  
**Git HEAD:** `5611093` (includes Search Hardening)  
**Model:** qwen3:8b | **Prompt:** production mirror (agent.py semantics)  
**Production changes this phase:** NONE

---

## 1. Executive Summary

**Overall live E2E: FAIL** | **Tool-only lane: PARTIAL**

Search Hardening（`5611093`）は **Discovery 層を改善** したが、End-to-End 成功には **Fetch fact_ready** と **LLM synthesis / empty search** が依然ボトルネック。

| Improvement vs Phase 2 | Evidence |
|------------------------|----------|
| Search 1st hit | 大阪市の不祥事 → **大阪市** (Case A/B) |
| Case B Fetch | Phase2 fetch=0 → Phase3 **fetch=1** |
| Explicit fetch skip | Phase2 → Phase3 **fetch_omission=false** (Case B) |

| Still failing | Layer |
|---------------|-------|
| fact_ready=false (大阪市 wiki) | Fetch / Evidence |
| Composite query empty (Case C) | Search / ENVIRONMENT |
| Numeric unsupported (Case C/E) | MODEL_CAPABILITY |
| E2E PASS none | All stages |

---

## 2. Evaluation Lanes

| Lane | Purpose |
|------|---------|
| **tool_only_auto** | search(大阪市の人口) + auto-fetch 1st hit — tool layer without LLM |
| **live_llm** | production_web_eval_system_prompt + qwen3:8b |
| **deterministic_mock** | mock tool calls — routing only |

---

## 3. Case Results (Live E2E)

| Case | E2E | Search | Fetch | fact_ready | Notes |
|------|-----|--------|-------|------------|-------|
| A | PARTIAL | PASS | 1 | FAIL | 大阪市 1st hit; fetch ok |
| B | FAIL* | PASS | 1 | FAIL | Fetch executed; fact_ready blocks E2E |
| C | FAIL | FAIL | 0 | — | empty search; hallucination_candidate |
| D | FAIL | FAIL | 0 | — | empty search |
| E | FAIL | FAIL | 0 | — | empty search; hallucination_candidate |
| F | FAIL | FAIL | 0 | — | empty search |
| G | FAIL | FAIL | 0 | — | empty search |

\*Case B: harness_overall **PASS** (tool selection + utilization) but E2E **FAIL** due to fact_ready gate.

---

## 4. Layer Diagnosis

### SEARCH — PARTIAL

**CONFIRMED FACT:**
- Search Hardening fixes の-variant 1st hit to 大阪市 (A/B live + all tool-only)
- Composite query `大阪市 人口 統計` returns **empty** (Case C live)

**UNKNOWN:** Why multi-token ja queries empty while `大阪市の人口` works

### SOURCE_SELECTION — PARTIAL

**CONFIRMED FACT:** When hits exist, LLM selects 大阪市 wiki URL (Case A/B)

**OBSERVATION:** Cases C–G empty search → no source to select

### FETCH — PARTIAL

**CONFIRMED FACT:**
- Case B fetch now executes (vs Phase 2)
- All tool-only fetches: fact_ready=**false**, warning boilerplate/metadata

### EVIDENCE — FAIL

**CONFIRMED FACT:** 大阪市 wiki main_text_len≈1008, fact_ready=false

### LLM — PARTIAL

**CONFIRMED FACT:** Case B selects search_web + read_url_text with production prompt  
**OBSERVATION:** Case C/E hallucination_candidate with empty search  
**HYPOTHESIS:** LLM fills numeric from general knowledge when grounding.insufficient

### AGENT — OBSERVATION

Eval harness: agent_blocked=false always; no production agent.py enforcement in eval path

---

## 5. Search Hardening / Evidence Pipeline Effect (S8)

| Failure | Pre-hardening (Phase 2) | Post-hardening (Phase 3) |
|---------|-------------------------|--------------------------|
| Irrelevant 1st hit | 大阪市の不祥事 | **大阪市** |
| Case B fetch skip | fetch=0 | **fetch=1** |
| fact_ready | false | **still false** |
| HTML meta answer | 0 (Phase 2) | 0 |
| Empty composite search | — | **still fails** (Case C) |

---

## 6. Failure Diagnosis (Phase 4 integration)

Per-case `diagnosis[]` in live traces. Aggregated findings:

- **CONFIRMED FACT:** fact_ready=false across tool-only fetches
- **OBSERVATION:** hallucination_candidate Case C/E
- **UNKNOWN:** composite query backend behavior

---

## 7. Proposed Next Iteration

1. **Improve fact_ready for Wikipedia entity pages** (RESULT_QUALITY) — Human Review  
2. **Grounding enforce on empty search** (MODEL_CAPABILITY / AGENT_POLICY) — Human Review  
3. **Investigate composite ja query empty** (SEARCH_BACKEND) — probe first  

**Recommended next:** #2 + #1 (fact_ready blocks synthesis even when Fetch runs)

---

## 8. Success Criteria

| ID | Status |
|----|--------|
| S1 Case A–G observed | PASS |
| S2 Stage separation | PASS |
| S3 Fetch vs quality | PASS |
| S4 Search vs tool selection | PASS (Case B improved) |
| S5 Hallucination detect | PASS (C/E) |
| S6 Failure Diagnosis | PASS |
| S7 UNKNOWN preserved | PASS |
| S8 Hardening effect | PASS |
| S9 Automation observation | PASS |
| S10 Prioritized proposals | PASS |

---

## 9. Automation Observation

**Cursor autonomous:** re-probe, Phase 4 diagnosis, Phase 2 compare, no prod changes  
**Human intervention:** 0 (SPECIFICATION via user query only)

---

## 10. Artifacts

| Path | Content |
|------|---------|
| `ai_tool/web_tool_end_to_end_evaluation_phase3.py` | Harness |
| `ai_tool/run_web_tool_end_to_end_evaluation_phase3.py` | Runner |
| `tests/ai_tool/project_audit/test_web_tool_end_to_end_evaluation_phase3.py` | 5 tests |
| `runs/ai_tool/20260828_222738_web_tool_end_to_end_evaluation_phase3/` | observations, traces, diagnosis, proposals |

---

## 11. STOP

Evaluation complete. No production changes. Implementation deferred pending Human Review.
