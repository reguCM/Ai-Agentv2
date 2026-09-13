# Web Tool Extraction Normalization — Experimental Prototype & Golden Regression

**Date:** 2026-08-28  
**Git HEAD (start):** `21809f9`  
**Run:** `runs/ai_tool/20260828_231915_web_tool_extraction_normalization_experiment/`  
**Production changes:** None — experimental module only

---

## Overall: **PASS**

| Area | Result |
|------|--------|
| GT1 Osaka population | Fixed by S3/S4/S5/S7 (Production S0 FAIL) |
| GT2 capital regression | All safe strategies PASS |
| GT3 no false evidence | PASS |
| LLM utilization | PASS (Cases A/B/C) |
| fact_ready semantics | Unchanged |

---

## Extraction

### Strategies compared (9)

| ID | Description |
|----|-------------|
| S0 | Production `normalize_html_to_evidence` |
| S1 | `#mw-content-text` |
| S2 | First `mw-parser-output` (failure baseline) |
| S3 | Metadata strip + mw-content-text (A4-class) |
| S4 | Paragraph-density in semantic regions |
| S5 | Semantic HTML main/article |
| S6 | Wikipedia merged parser outputs |
| S7 | Largest text block after metadata strip |
| S8 | Metadata strip then production selectors |

### Live golden pass counts (GT1–GT6)

| Strategy | PASS | FAIL |
|----------|------|------|
| S0_PRODUCTION | 3 | 3 |
| S1/S2/S8 | 3 | 3 |
| **S3/S4/S5/S7** | **6** | **0** |
| S6_WIKI_MERGED | 5 | 1 (GT5 en.wikipedia) |

### Best candidate: **S4_PARAGRAPH_DENSITY**

**Confidence:** high (6/6 mechanical PASS, GT2/GT3 safe)

**Tied at 6/6:** S3, S4, S5, S7 — tie-break prefers **most generic** (paragraph-density over metadata-only).

**Why not S3 (A4) blindly:** S3 equals S4 on score but S4 uses semantic `<p>` aggregation applicable beyond Wikipedia IDs. S3 is simpler but tied; S4 selected for generality.

**Why not S6:** Wikipedia-specific; fails GT5 (en Osaka) population pattern.

**Why not S0:** GT1/GT4/GT5 FAIL — wikidata/infobox center.

---

## Golden Transactions

| Case | URL | S0 | Best (S4) |
|------|-----|-----|-----------|
| GT1 | ja.wikipedia 大阪市 | FAIL | PASS + population |
| GT2 | ja.wikipedia 日本の首都 | PASS | PASS + capital |
| GT3 | nav fixture | PASS | PASS (no false facts) |
| GT4 | ja.wikipedia 横浜市 | FAIL | PASS |
| GT5 | en.wikipedia Osaka | FAIL | PASS |
| GT6 | simple HTML main | PASS | PASS |

**Before → After artifact:** each case stores `before_after.S0_PRODUCTION` vs `best_passing` in run JSON.

---

## LLM (qwen3:8b, isolated)

| Case | Input | Result |
|------|-------|--------|
| A | S3 evidence with population | Extracts (State A) PASS |
| B | S0 evidence without population | Refuses (State C) PASS |
| C | Empty/irrelevant text | No invention (State C) PASS |

Architecture fix → LLM utilization normalizes without prompt change.

---

## fact_ready

| Item | Status |
|------|--------|
| Production semantics changed | **No** |
| `evidence_presence` (experimental) | Separate question-specific field |
| case3 on GT1 | Some strategies: population true + fact_ready true after fix |
| Proposal | `PROPOSED_CHANGE_EVIDENCE_AVAIL` — future grounding hint only |

---

## Automation

| Stage | Capability |
|-------|------------|
| Observation | `evidence_presence`, `wikidata_boilerplate`, mechanical_grade |
| Diagnosis | EXTRACTION_FAILED + wikidata_boilerplate → infobox selection |
| Proposal | PROPOSED_CHANGE_1 → html_normalize merge |
| Regression | GT1–GT6 pytest + golden JSON |

**Loop validated:** observation → experiment → compare → proposal → STOP (no auto-implement).

---

## Proposed Production Changes (NOT implemented)

### PROPOSED_CHANGE_1

| Field | Value |
|-------|-------|
| Layer | `html_normalize.py` |
| Change | Metadata strip + paragraph-density path (S4 principles) |
| Expected | GT1/GT4/GT5 population; GT2 preserved |
| Risk | Aggressive metadata strip on non-wiki JSON-LD |
| Human Review | **Required** |

### PROPOSED_CHANGE_EVIDENCE_AVAIL

| Field | Value |
|-------|-------|
| Layer | web_evidence / diagnosis (future) |
| Change | Separate evidence_availability from fact_ready |
| Human Review | **Required** |

---

## Rejected Alternatives

| Alternative | Reason |
|-------------|--------|
| S6 Wikipedia-only merge | GT5 fail; maintenance burden |
| S2/S8 prestrip-only | Still fails GT1 (same first-match issue) |
| Adopt S3 as final without comparison | S4/S5/S7 equal; S4 more generic |
| Change fact_ready now | Out of scope; separate concept proposed |
| Production implement this phase | Explicitly forbidden |

---

## Remaining Unknowns

- Long-tail sites with JSON-LD not matching metadata patterns
- Live Agent E2E after PROPOSED_CHANGE_1
- Optimal tie between S3 vs S4 on non-Wikipedia corpus
- GT5 S6 failure root (en population wording vs pattern)

---

## Decision Log

Saved: `runs/ai_tool/20260828_231915_web_tool_extraction_normalization_experiment/decision_log.json`

### Initial hypothesis

Metadata strip fixes Osaka without Wikipedia hardcode.

### Confirmed facts

- S0 fails GT1 (Case 1 extraction failure)
- S3/S4/S5/S7 pass all 6 golden cases
- LLM works when evidence clean

### Rejected

- S6 as default strategy
- Blind A4 adoption without tie analysis

---

## Artifacts

| Path | Role |
|------|------|
| `ai_tool/experimental/read_url/extraction_prototype.py` | 9 strategies |
| `ai_tool/web_tool_extraction_normalization_experiment.py` | Harness |
| `ai_tool/run_web_tool_extraction_normalization_experiment.py` | Runner |
| `tests/ai_tool/experimental/test_extraction_prototype.py` | Unit tests |
| `tests/ai_tool/project_audit/test_web_tool_extraction_normalization_experiment.py` | Harness tests |

**Re-run:** `python ai_tool/run_web_tool_extraction_normalization_experiment.py`

---

## STOP: **YES**

Do not proceed to Production implementation without Human Review.
