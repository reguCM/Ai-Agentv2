# Web Tool Search Hardening — Autonomous Implementation Decision Log

**Iteration:** 1  
**Previous HEAD:** `f4150e9`  
**Probe baseline:** `20260828_221132_web_tool_search_hardening_probe`  
**Probe after:** `20260828_221314_web_tool_search_hardening_probe`

---

## Observation

```text
Re-ran search hardening probe at HEAD f4150e9
↓
CONFIRMED: 「大阪市 人口」→ first hit 大阪市
CONFIRMED: 「大阪市の人口」→ first hit 大阪市の不祥事 (entity absent from wiki-ja raw)
CONFIRMED: DDG Instant Answer empty for ja fact queries (AbstractText=0)
OBSERVATION: Python query ranks NumPy above Python page (snippet token flooding)
```

---

## Confirmed Facts

1. Wikipedia OpenSearch returns **different title sets** for space vs の-insertion queries
2. For の-variant, entity page **not in primary backend raw pool** — ranking alone cannot fix
3. `query_tokens()` does not split on `の`; single token `大阪市の人口`
4. Search tool applies only `strip()` — no backend query shaping before fix
5. Output schema unchanged; Discovery-only contract preserved

---

## Eliminated Causes

| Cause | Why eliminated |
|-------|----------------|
| Ranking-only fix for Osaka の | Entity absent from candidate pool pre-fix |
| Agent / Prompt change needed for Osaka discovery | Tool-layer fix restores correct hit |
| Registry schema change | Not required for backend fan-out |

---

## Remaining Causes (post-fix)

| Issue | Status |
|-------|--------|
| DDG empty for ja queries | **UNKNOWN** — Instant Answer API limitation; not addressed |
| Paris population all-empty | **UNKNOWN** |
| LLM generates の-variant query | **QUERY_GENERATION** — outside Search tool |
| Fetch skip / hallucination | **Not in scope** — Search hardening only |

---

## Design Options Compared

### Option 1 — Token ranking only (A)

- **Effect:** Python/NumPy partial fix possible; **no Osaka の fix**
- **Rejected:** Insufficient for primary failure

### Option 2 — Wikipedia backend query variant (の→space) (B+E minimal)

- **Effect:** Adds `大阪市 人口` secondary wiki query; entity enters pool
- **Scope:** `general_web_search.py` only
- **Rejected alternatives:** Osaka hardcode, new backend, Agent change

### Option 3 — Full query normalization pipeline

- **Effect:** Broader ja rules
- **Rejected:** Higher site-specific risk; exceeds minimal need for observed failure

### Option 4 — Expose raw backends without ranking (D)

- **Rejected:** Shifts burden to LLM; does not fix pool absence alone

---

## Selected Design

**Option 2 + targeted ranking improvements (Option 1 subset)**

1. `backend_queries_for_discovery()` — Wikipedia-only spaced variant when CJK + `の`
2. `discovery_ranking_tokens()` — rank using tokens from original + spaced variant
3. Exact title / head-token scoring boosts — tie-break + Python/NumPy case

**Why selected:** Minimal change; addresses **confirmed** pool absence; no Registry/Agent/Prompt change; deterministic tests; probe before/after measurable.

---

## Implementation

| File | Change |
|------|--------|
| `tools/system/network/general_web_search.py` | Backend query variants, ranking tokens, score boosts |

**Not implemented:** DDG replacement, Agent fetch gate, Prompt changes, Osaka hardcode

---

## Tests

- `tests/test_general_web_search.py` — 3 new unit tests
- Regression: `test_general_web_search.py`, `test_web_evidence_pipeline.py`, search hardening design tests — **PASS**

---

## Practical Evaluation (before → after)

| Query | Before 1st hit | After 1st hit |
|-------|----------------|---------------|
| 大阪市 人口 | 大阪市 | 大阪市 |
| 大阪市の人口 | 大阪市の不祥事 | **大阪市** |
| Python programming language | NumPy | **Python (programming language)** |
| Paris population | empty | empty (unchanged) |
| empty_control | empty | empty |

---

## Success Criteria

| ID | Criterion | Result |
|----|-----------|--------|
| SC1 | の-variant returns entity as first hit (Osaka) | **PASS** |
| SC2 | Space-variant unchanged regression | **PASS** |
| SC3 | Python primary topic ranked first | **PASS** |
| SC4 | Output schema unchanged | **PASS** |
| SC5 | Existing web tests PASS | **PASS** |
| SC6 | empty_control stays empty | **PASS** |
| SC7 | Paris empty root cause resolved | **FAIL** (UNKNOWN remains) |

**Overall: PARTIAL** — primary Discovery failures fixed; DDG/Paris/LLM layers remain.

---

## Safety

- No new URLs fetched beyond existing Wikipedia/DDG APIs
- Same backends, same `http_get` path
- No SSRF boundary change
- **PASS**

---

## Automation Compatibility

- Probe `entity_in_final_first` detects fix
- `candidates_collected` increases when variant adds hits
- Failure Diagnosis `wrong_search_result` rule can re-run post-fix

---

## Human Review Required

**NO** for this iteration — internal Discovery implementation; contract preserved.

**YES** if future: DDG API change, Registry schema change, Agent policy.

---

## STOP

Iteration 1 complete. Remaining: DDG ja coverage, Paris empty, LLM query generation, Fetch/Agent layers.
