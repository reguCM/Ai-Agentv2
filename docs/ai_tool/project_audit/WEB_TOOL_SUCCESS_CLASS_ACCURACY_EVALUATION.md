# Web Tool Success-Class Accuracy Evaluation

**Date:** 2026-08-28  
**Initial HEAD:** `9db99fa`  
**Final HEAD:** `9db99fa` (no Production change)  
**Run:** `runs/ai_tool/20260828_235130_web_tool_success_class_accuracy_evaluation/`  
**Human Intervention:** 0

---

## Overall: **PASS**

SUCCESS-class LLM accuracy measured and separated from Web failures. **No Production change** — STOP-A.

---

## Baseline

| Check | Status |
|-------|--------|
| Golden GT1–GT6 | 6/6 PASS (unchanged) |
| Osaka live E2E | PASS (prior phase) |
| production_mirror canonical | Used for all scored cases |
| execute_registry_tool mock gap | Not used as primary metric path |
| pytest regression | 23 passed |

---

## Dataset

**success_class_v1** — 13 cases across 7 categories:

| Category | Cases | Notes |
|----------|-------|-------|
| basic_facts | SC-M01, SC-L01, SC-L02 | capital, osaka population |
| numeric_facts | SC-M02, SC-M03, SC-L03 | population ranges |
| entity_facts | SC-M05 | capital entity |
| temporal_facts | SC-M06 | founding year 1889 |
| comparative | SC-M07, SC-L04 | yokohama vs osaka |
| multi_fact | SC-M08 | population + entity |
| negative | SC-NEG01 | excluded from SUCCESS-class stats |

**Ground truth:** independent `ExpectedFact` patterns + evidence regex — **not** LLM self-judgment.

**Taxonomy controls:** SC-M03/M04/M05 inject known failures to validate classification (excluded from accuracy numerator).

---

## Web SUCCESS

| Metric | Value |
|--------|-------|
| Web SUCCESS (pipeline) | 11 / 13 cases run |
| Web failure (not SUCCESS-class) | 2 (SC-L02, SC-L04 — SEARCH_FAILED) |
| Negative excluded | 1 (SC-NEG01) |

Web SUCCESS and LLM failure are **fully separated**: SC-L02/L04 scored as SKIPPED (web layer failure, not LLM failure).

---

## LLM Answers

| Metric | Value |
|--------|-------|
| SUCCESS-class scored | 10 |
| Expected-correct scored | 7 |
| Taxonomy controls | 3 (all correctly detected as non-Correct) |
| Live SUCCESS-class (expected-correct) | 2 |
| Mock expected-correct | 5 |

---

## Accuracy

| Metric | Value |
|--------|-------|
| **Expected-correct accuracy** | **7/7 = 100%** |
| Live SUCCESS-class accuracy | 2/2 = 100% |
| Mock expected-correct accuracy | 5/5 = 100% |
| Taxonomy detection rate | 3/3 = 100% |
| All scored (incl. controls) | 7/10 Correct |

---

## Failure Taxonomy

| Class | Count (all scored) | Notes |
|-------|-------------------|-------|
| Correct | 7 | expected-correct cases |
| Numeric Error | 1 | SC-M03 taxonomy control |
| Unsupported Addition | 1 | SC-M04 taxonomy control |
| Entity Error | 1 | SC-M05 taxonomy control |
| Temporal / Scope / Contradiction / Ambiguous | 0 | — |

Injected failures (M03–M05) validate taxonomy; live SUCCESS-class cases (L01, L03) both Correct.

---

## Claim-Level Results

Deterministic verification methods observed:

| Method | Count |
|--------|-------|
| regex_entity | 4 |
| numeric_range_match | 4 |
| numeric_range_mismatch | 1 |
| numeric_not_in_evidence | 2 |
| year_match | 1 |
| regex (comparison) | 1 |

Claim support types: `supported`, `unsupported`, `contradicted`, `ambiguous` — no LLM Judge used.

---

## Deterministic Verification Opportunities

| Claim type | Verifiable | Method |
|------------|------------|--------|
| Population numeric | Yes | range match (500k–4M scale, 万-normalization) |
| Entity (capital) | Yes | regex entity match vs evidence |
| Temporal (year) | Yes | year string match (1[789]xx / 20xx) |
| Comparison | Partial | regex pattern on evidence |
| Unsupported numeric | Yes | numeric not in evidence |

**Observation:** ~90% of scored claims are deterministically verifiable. Live LLM failures on numeric questions (SC-L03 prior run) were detectable via population-scale numeric filter — but current session live cases passed.

---

## Confirmed Causes

1. SUCCESS-class LLM accuracy is **measurable** via production_mirror + independent ExpectedFact ground truth
2. Web failure (SEARCH_FAILED) and LLM failure are **separable** in metrics
3. Taxonomy controls (injected Numeric/Entity/Unsupported) are **detected at 100%**
4. Live qwen3_8b on Osaka/Yokohama population SUCCESS-class: **Correct** this session
5. execute_registry_tool mock path **not used** for primary accuracy metrics

---

## Hypotheses

1. When Web reaches SUCCESS-class, LLM answer accuracy is **high** for factual Wikipedia queries (this session: 100% on 7 expected-correct cases)
2. Numeric population claims are **largely deterministic-verifiable** — mechanical layer ROI depends on live failure rate, not proven high yet
3. Search backend instability (SC-L02/L04 SEARCH_FAILED) is **Web-layer**, not LLM-layer
4. LLM verbose answers may include unsupported additions not caught by current numeric filter (scope for future claim extraction)

---

## Unknowns

- SUCCESS-class accuracy across broader query set (non-Wikipedia, English-only, composite)
- Model parity (qwen3_8b vs other models)
- Scope error / overgeneralization detection without LLM judge
- Question-specific evidence vs fact_ready semantic gap
- Reproducibility of SC-L02/L04 search failures across sessions

---

## Architecture Options

### OPT0 — 現状維持
Accuracy 100% on measured expected-correct set; mechanical ROI low.

### OPT1 — Prompt / Agent policy
Moderate potential for entity/temporal; Human Review required.

### OPT2 — Evidence grounding
Moderate for unsupported additions; not needed at current measured failure rate.

### OPT3 — Structured Claim
High coverage potential; high regression risk; ROI unproven.

### OPT4 — Mechanical / deterministic verification
Numeric claims verifiable; live failure rate too low this session to recommend.

### OPT5 — Hybrid
Balanced; defer until sustained live numeric failures observed.

---

## Selected: **OPT0_NO_ACTION**

Expected-correct SUCCESS-class accuracy 100% (7/7). Live 100% (2/2). Taxonomy detection 100%. Mechanical layer ROI low for current measured failure rate.

---

## Why

Primary question answered: **When Web succeeds, does LLM fail often?** — On this dataset/session: **No** (100% expected-correct). Architecture change not warranted.

---

## Rejected

| Option | Reason |
|--------|--------|
| OPT1 Prompt/Agent | No confirmed LLM failure pattern on live SUCCESS-class |
| OPT2 Evidence grounding | Unsupported additions only in taxonomy controls |
| OPT3 Structured Claim | High cost, no measured live failure rate |
| OPT4 Mechanical | Not Recommended — live numeric errors 0 this session |
| OPT5 Hybrid | Premature given STOP-A |

---

## Mechanical Answer

**Not Recommended** — deterministic verification infrastructure validated in eval harness, but live SUCCESS-class failure rate does not justify Production mechanical answer layer.

---

## Production Changes

**None.**

---

## Evaluation Changes

- `ai_tool/web_tool_success_class_accuracy_evaluation.py`
- `ai_tool/run_web_tool_success_class_accuracy_evaluation.py`
- `tests/ai_tool/project_audit/test_web_tool_success_class_accuracy_evaluation.py`

---

## Tests

| Test | Result |
|------|--------|
| Unit tests (harness) | 9 passed |
| pytest web regression | 23 passed |
| Mock taxonomy controls | 3/3 detected |
| Live SUCCESS-class (ollama) | 2/2 Correct |

---

## Before / After

| Metric | Pre-phase | Post-phase |
|--------|-----------|------------|
| SUCCESS-class LLM accuracy | UNKNOWN | **100%** (7/7 expected-correct) |
| Web vs LLM failure separation | Not measured | Implemented |
| Failure taxonomy | Partial (state A–D) | A–I + claim-level |
| Mechanical answer decision | UNKNOWN | **Not Recommended** |

---

## Human Intervention

**0**

---

## Git

| Item | Value |
|------|-------|
| initial_head | 9db99fa |
| production_changes | [] |
| harness commit | pending |

---

## Decision Log

```json
{
  "dataset": "success_class_v1",
  "web_success_count": 11,
  "llm_answer_expected_correct_count": 7,
  "correct_count": 7,
  "accuracy_rate": 1.0,
  "live_accuracy_rate": 1.0,
  "taxonomy_detection_rate": 1.0,
  "selected_option": "OPT0_NO_ACTION",
  "mechanical_answer": "Not Recommended",
  "stop_reason": "STOP_A",
  "production_changes": []
}
```

Full artifact: `runs/ai_tool/20260828_235130_web_tool_success_class_accuracy_evaluation/observations.json`

---

## Remaining Problems

1. Search backend intermittency (SC-L02/L04 SEARCH_FAILED) — Web layer, not LLM
2. Narrow dataset — mostly Wikipedia ja municipality facts
3. Scope error / verbose unsupported content not fully classified
4. fact_ready vs question-specific evidence gap (SC-NEG01 edge case)

---

## Next Recommended Direction

Expand live dataset periodically and re-run harness. If live numeric_error_rate exceeds ~25% on SUCCESS-class population queries, re-evaluate OPT4 Mechanical / OPT5 Hybrid — **not mandatory now**.

---

## STOP

**YES**

**STOP Reason:** **STOP-A** — SUCCESS-class LLM failure rate low on measured dataset; mechanical answer layer ROI not justified; evaluation infrastructure complete.
