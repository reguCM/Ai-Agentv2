# Web Tool Extraction Normalization — Production Implementation

**Date:** 2026-08-28  
**Start HEAD:** `3e35a02`  
**Run:** `runs/ai_tool/20260828_232526_web_tool_extraction_normalization_production/`  
**Strategy:** S4 paragraph-density (integrated into Production `html_normalize.py`)

---

## Overall: **PASS**

| Criterion | Status |
|-----------|--------|
| GT1–GT6 golden | 6/6 PASS |
| Regression tests | 23 passed |
| production_mirror E2E | PASS |
| Schema compatibility | Maintained |
| Search/Agent/Prompt/Registry | Unchanged |

---

## Implementation

### Changed file

`ai_tool/experimental/read_url/html_normalize.py`

### Approach (not blind S4 copy)

1. **Metadata strip** before region selection (infobox, navbox, typeof spans, JSON-LD)
2. **Paragraph-density** scoring across `article`, `main`, `mw-content-text`, `body`
3. **Legacy fallback** if paragraph-density yields empty
4. **Truncated fetch refinement:** when `raw_fetch_truncated` and `</body>` absent, still allow `body_reached` if paragraph-density produced ≥500 chars of non-boilerplate text

### Independent refinement vs experiment S4

Truncated HTML at 262144 bytes still contains valid article paragraphs for Wikipedia. Strict `</body>` check caused `fact_ready=false` despite good extraction. Refinement is extraction-layer only; does not change `fact_ready` definition.

---

## Before / After

| Metric | Before | After |
|--------|--------|-------|
| GT1 Osaka | FAIL | PASS |
| GT2 Capital | PASS | PASS |
| GT3 nav-only | PASS | PASS |
| GT4 Yokohama | FAIL | PASS |
| GT5 en Osaka | FAIL | PASS |
| GT6 simple HTML | PASS | PASS |
| Osaka population in main_text | absent | present |
| GT1 fact_ready | false | true |
| GT1 web_status | EXTRACTION_FAILED | SUCCESS |
| fact_ready semantics | unchanged | unchanged |

---

## E2E (production_mirror)

- Tools: `search_web` → `read_url_text`
- `main_text_population`: true
- `fact_ready`: true
- `web_status_overall`: SUCCESS
- `extraction_method`: `paragraph_density_mw-content-text`

---

## Safety

| Layer | Changed |
|-------|---------|
| html_normalize | Yes |
| Search | No |
| Agent | No |
| Prompt | No |
| Registry | No |
| web_status | No (semantics preserved) |

---

## Human Review

`HUMAN_REVIEW_REQUIRED` — Production extraction changed. Artifacts prepared for review.

**Human intervention count:** 0

---

## Remaining Unknowns

- Live `agent.py` subprocess with unstable search backends
- Long-tail JSON-LD sites outside metadata patterns

---

## Next Iteration Candidates

- Live E2E with real search (non-mocked)
- `evidence_availability` grounding hint separate from fact_ready

---

## STOP: **YES**
