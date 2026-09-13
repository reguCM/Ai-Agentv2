# Web Tool Autonomous Improvement — Next Iteration Selection

**Date:** 2026-08-28  
**Initial HEAD:** `d37e343`  
**Current HEAD:** `d37e343` (no Production change this iteration)  
**Run:** `runs/ai_tool/20260828_233220_web_tool_autonomous_improvement/`  
**Human Intervention:** 0

---

## Overall: **PASS**

Primary Web Research chain (Osaka population) verified end-to-end. **No Production change** — STOP D.

---

## Current Assessment

Post-`d37e343` extraction normalization, the dominant failure class (infobox/Wikidata in main_text) is **resolved**. Live probes confirm:

| Layer | Status |
|-------|--------|
| Search (Osaka) | 5 hits |
| Fetch | ok |
| Extraction | `paragraph_density_mw-content-text`, fact_ready=true |
| Evidence | population in main_text |
| production_mirror E2E | web_status=SUCCESS, LLM answer includes population |
| Golden GT1–GT6 | 6/6 PASS |

Past Live E2E failures (21809f9 era) were **pre-extraction** and/or **env-transient search empty** — re-probe now PASS.

---

## Observed Problems (re-prioritized)

| Priority | Problem | Classification |
|----------|---------|----------------|
| Low | Eval-direct path lacks WebSessionTracker/boundary | CONFIRMED |
| Low | Search backend session instability | HYPOTHESIS (currently OK) |
| Unknown | SUCCESS-class wrong answer rate | UNKNOWN |
| Deferred | evidence_availability vs fact_ready | HYPOTHESIS (proposal only) |
| Deferred | Agent fetch-skip | Not observed in live Osaka E2E |

**Priority change:** Extraction was P0 → now **closed**. Next P1 is **eval observability**, not user-facing Production.

---

## Candidate Options

| ID | Name | Selected |
|----|------|----------|
| OPT_STOP_D | No Production change | **YES** |
| OPT_EVAL_CANONICAL | Canonical eval via production_mirror | Next iteration |
| OPT_AGENT_FETCH_POLICY | Agent mandatory fetch | Rejected (HR, no evidence) |
| OPT_EVIDENCE_AVAIL | evidence_availability hint | Rejected (HR, deferred) |

---

## Why OPT_STOP_D

1. Golden 6/6 + live E2E PASS — primary goal met for Osaka factual chain
2. Further Production changes lack sufficient ROI vs regression risk
3. Remaining eval gap affects **autonomous metrics**, not Production user path
4. Cursor independently re-verified past hypotheses (Paris search now works; env not empty)

---

## Implementation

**None** (Production unchanged)

Added evaluation infrastructure only:

- `ai_tool/web_tool_autonomous_improvement.py`
- `ai_tool/run_web_tool_autonomous_improvement.py`

---

## Before / After (iteration-level)

| Metric | Pre d37e343 | Post d37e343 (this probe) |
|--------|-------------|---------------------------|
| Osaka live E2E | FAIL/PARTIAL | **PASS** |
| Golden GT1 | FAIL | PASS |
| Eval gap | CONFIRMED | CONFIRMED (unchanged) |

---

## Automation

Observe → Diagnose → Options → Select → STOP loop **validated**:

- Probes run mechanically
- Options generated from assessment
- STOP reason explicit (STOP_D)
- Decision log saved

---

## Git

| Item | Value |
|------|-------|
| Production commit | None this iteration |
| Harness commit | pending (selective) |

---

## STOP

**YES** — STOP D: remaining issues low-priority / eval-only; no safe Production delta identified.

---

## Next Recommended Direction

**Canonical eval harness (OPT_EVAL_CANONICAL)** — wrap evaluations in production_mirror + boundary for autonomous loop metric parity. Evaluation-only, low risk.
