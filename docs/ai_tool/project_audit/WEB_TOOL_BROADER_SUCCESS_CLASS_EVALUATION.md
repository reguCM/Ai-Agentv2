# Web Tool Broader Success-Class Evaluation

**Date:** 2026-08-29  
**Initial HEAD:** `571c092`  
**Final HEAD:** `571c092` (no Production change)  
**Run:** `runs/ai_tool/20260829_001001_web_tool_broader_success_class_evaluation/`  
**Human Intervention:** 0

---

## Overall: **PASS**

Baseline intact. Broader SUCCESS-class dataset evaluated. **STOP_NO_CHANGE** — no Production Architecture change warranted.

---

## Baseline

| Check | Result |
|-------|--------|
| Golden GT1–GT6 | **6/6 PASS** |
| Osaka live chain | ok (prior phases) |
| pytest web regression | **32 passed** |
| Production | unchanged at `571c092` |

---

## Evaluation

**Dataset:** `success_class_v2_broader` — extends v1 with entity/prefecture/organization, area numeric, temporal scope, largest-city scope, English page, non-Wikipedia portal, taxonomy controls, and 4 live cases.

| Metric | Value |
|--------|-------|
| Dataset size | 22 cases defined |
| Cases run | 22 |
| Mock/fixture | 18 |
| Live (qwen3_8b) | 4 |

**Categories covered:** entity, numeric, temporal, scope, english, non_wikipedia, comparative, multi_fact, negative, basic_facts + taxonomy controls.

**Ground truth:** structured `ExpectedFact` (entity patterns, numeric ranges, year, scope) — **not** LLM Judge.

---

## Failure Rates (expected-correct SUCCESS-class, n=13)

| Rate | Value |
|------|-------|
| **accuracy_rate** | **84.6%** (11/13) |
| numeric_error_rate | 7.7% |
| entity_error_rate | 0% |
| temporal_error_rate | 0% |
| scope_error_rate | 0% |
| unsupported_addition_rate | 0% |
| contradiction_rate | 7.7% |
| evidence_mismatch_rate | 7.1% (claim-level) |
| claim_unsupported_rate | 0% |
| taxonomy detection | 100% (5/5 controls) |

---

## Web vs LLM

| Layer | Count | Cases |
|-------|-------|-------|
| **Web failure** (not SUCCESS-class) | 3 | BC-L01, BC-L03, BC-L04 (SEARCH_FAILED) |
| **LLM failure** (Web SUCCESS, wrong answer) | 2 | BC-EN01*, BC-L02 |
| Mock SUCCESS-class | 15/15 web SUCCESS on fixture path | — |

\*BC-EN01: eval harness initially failed to parse English "2.75 million" — fixed in harness (`million` pattern); re-classification would be Correct. Recorded as harness gap, not Production LLM failure.

**BC-L02 (live):** Genuine LLM failure — verbose geographic summary without correct area (377,975 km²); wrong numeric matched (630).

Web failures are **not** counted in LLM failure metrics.

---

## Architecture Options

| ID | Name | ROI (this session) |
|----|------|-------------------|
| OPT0 | 現状維持 | **High** |
| OPT1 | Prompt / Agent policy | Low |
| OPT2 | Evidence grounding | Low |
| OPT3 | Structured Claim | Low (high cost) |
| OPT4 | Mechanical / deterministic verification | Low (numeric_error 7.7%) |
| OPT5 | Hybrid | Low |
| OPT6 | Post-LLM claim verification (verify, not replace) | Medium — defer |
| OPT7 | Eval canonical production_mirror bridge | Medium (3 web failures on live search) |

---

## Selected Option: **OPT0_NO_CHANGE**

Broader SUCCESS-class accuracy 85% (11/13). numeric_error_rate 7.7%. Live LLM failures=1 confirmed (BC-L02). No Production change with sufficient ROI.

---

## Rejected Options

| Option | Reason |
|--------|--------|
| OPT1 Prompt/Agent | entity_error 0%; no pattern |
| OPT2 Evidence grounding | unsupported_addition 0% on expected-correct |
| OPT3 Structured Claim | high cost, failure rate insufficient |
| OPT4 Mechanical | numeric_error_rate 7.7% << 25% threshold |
| OPT5 Hybrid | premature |
| OPT6 Post-LLM verify | defer — single live numeric failure; eval prototype only |
| OPT7 Eval bridge | valid for observability; not Production Architecture |

---

## Mechanical Answer

**DEFERRED**

- numeric_error_rate = 7.7% on SUCCESS-class expected-correct cases
- Threshold for Mechanical ROI: ~25% sustained numeric errors on verifiable claims
- BC-L02 confirms LLM can miss numeric facts on verbose answers — **one live case**, insufficient for Production layer
- OPT6 (verify-only, not replace) noted as future candidate if rate rises

---

## Human Intervention

**0**

---

## Production Changes

**NONE**

---

## Git

| Item | Value |
|------|-------|
| initial_head | 571c092 |
| harness commit | pending |
| unrelated worktree | preserved |

---

## Remaining Unknowns

- Live search intermittency (BC-L01/L03/L04 SEARCH_FAILED this session)
- English query search ranking reliability
- Scope error on verbose LLM answers (BC-L02 style)
- Non-Wikipedia live fetch coverage
- fact_ready vs question-specific evidence on edge cases

---

## Next Iteration

1. Periodic re-run of broader harness (monthly or on Production change)
2. OPT7 eval canonical bridge if autonomous metrics diverge (eval-only)
3. Re-evaluate OPT6 if live numeric_error_rate exceeds 15% on expanded dataset

---

## Decision

```json
{
  "decision": "STOP_NO_CHANGE",
  "selected_option": "OPT0_NO_CHANGE",
  "mechanical_answer": "DEFERRED",
  "accuracy_rate": 0.8462,
  "numeric_error_rate": 0.0769,
  "web_failure_count": 3,
  "llm_failure_count": 2,
  "production_changes": []
}
```

**STOP** — do not proceed to Production Architecture change without new confirmed failure patterns.
