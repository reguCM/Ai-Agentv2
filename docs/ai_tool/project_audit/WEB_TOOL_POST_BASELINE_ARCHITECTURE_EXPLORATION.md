# Web Tool Autonomous Improvement — Post-Baseline Architecture Exploration

**Date:** 2026-08-28  
**Initial HEAD:** `ddc34d2`  
**Final HEAD:** `ddc34d2` (no Production change this phase)  
**Run:** `runs/ai_tool/20260828_233836_web_tool_post_baseline_architecture_exploration/`  
**Human Intervention:** 0

---

## Overall: **PASS**

Baseline re-verified end-to-end. Architecture options compared. **No Production change** — STOP-A.

---

## Baseline

| Check | Before (pre-extraction era) | Current (this session) |
|-------|----------------------------|------------------------|
| Golden GT1–GT6 | FAIL (GT1 infobox) | **6/6 PASS** |
| Osaka live Search | intermittent empty | **5 hits** |
| Osaka live Fetch | fact_ready false / noise | **ok, fact_ready=true** |
| Osaka population evidence | missing in main_text | **population in main_text** |
| web_status | PARTIAL | **SUCCESS** |
| production_mirror E2E | FAIL/PARTIAL | **PASS** (search→fetch→LLM) |
| Boundary (empty search) | — | **numeric suppressed, SEARCH_FAILED** |
| pytest web suite | — | **23 passed** |
| Git working tree | — | unchanged HEAD |

Production chain at HEAD `ddc34d2`:

```text
Search → Fetch → Extraction (S4 paragraph-density) → Evidence → web_status → Boundary → LLM
```

Key commits: search hardening `5611093`, evidence `f4150e9`, web_status/boundary `435b499`, extraction normalization `d37e343`.

---

## Current State

Post-extraction-normalization Production baseline is **stable** for the primary factual use case (Osaka municipality population via Wikipedia ja).

| Layer | Status |
|-------|--------|
| Search (大阪市の人口) | 5 hits, no error |
| Fetch | ok, `paragraph_density_mw-content-text` |
| fact_ready | true |
| Evidence | population present in main_text |
| web_status | SUCCESS |
| Boundary | applied on empty search; 275万人 suppressed |
| Live E2E (qwen3_8b) | search_web + read_url_text; answer includes population |

Non-Wikipedia observation (example.com): ok=True, fact_ready=True, method=paragraph_density_body — no confirmed Production defect.

---

## Confirmed Problems

| Problem | Layer | Impact |
|---------|-------|--------|
| `execute_registry_tool` defaults to `_mock_search_web` | Eval / harness | Autonomous metrics diverge from Production (nonsense query: direct 0 hits vs registry 3 mock hits) |
| Eval path lacks WebSessionTracker / `apply_web_answer_boundary` | Eval / harness | Boundary not exercised on registry-direct path; documented in prior Live E2E |

**Not confirmed in Production user path** this session.

---

## Hypotheses

1. Primary Production factual chain is sufficient for baseline Wikipedia ja/en municipality queries.
2. Eval mock default causes false positives in autonomous empty-search probes when `search_web_fn` is omitted.
3. Architecture changes (RTT, structured claims, mechanical answer) have low ROI until SUCCESS wrong-answer rate is measured.

---

## Unknowns

- SUCCESS-class wrong answer rate under live varied queries
- Search backend instability across time (currently OK this session)
- Long-tail JSON-LD / metadata patterns not in strip list
- `agent.py` subprocess parity vs production_mirror for all models
- Question-specific evidence availability vs `fact_ready` semantic gap impact

---

## Architecture Options

### 1. OPT0_NO_ACTION — 現状維持

| Dimension | Assessment |
|-----------|------------|
| Target problems | none (baseline sufficient) |
| Scope | none |
| Regression risk | none |
| Latency | unchanged |
| Maintenance | low |
| Automation fit | high (probes exist) |
| Human review | not required |

### 2. OPT1_EVAL_PRODUCTION_BRIDGE — Evaluation-only bridge

| Dimension | Assessment |
|-----------|------------|
| Target problems | eval mock default, boundary gap on eval path |
| Scope | `ai_tool/agent_integration` harness only |
| Regression risk | low (may affect tests expecting mock) |
| Automation fit | high |
| Human review | not required |

### 3. OPT2_MINIMAL_AGENT_POLICY — Agent fetch gate

| Dimension | Assessment |
|-----------|------------|
| Target problems | fetch skip (historical) |
| Scope | `agent.py` |
| Regression risk | medium |
| Human review | **required** |
| Note | Not reproduced in current live Osaka E2E |

### 4. OPT3_STRUCTURED_MECHANICAL — Structured / mechanical answer layer

| Dimension | Assessment |
|-----------|------------|
| Target problems | SUCCESS wrong-answer, traceability |
| Scope | large |
| Regression risk | high |
| Human review | **required** |
| Note | ROI unproven — wrong-answer rate UNKNOWN |

### 5. OPT4_RTT — Research Transaction abstraction

| Dimension | Assessment |
|-----------|------------|
| Target problems | orchestration observability |
| Scope | large |
| Regression risk | high |
| Human review | **required** |
| Note | Deferred in prior phases; baseline E2E now passes |

---

## Selected: **OPT0_NO_ACTION**

Baseline re-verified: Golden 6/6, live Osaka chain SUCCESS, boundary on empty search, live E2E PASS. Remaining confirmed issues are eval-path mock default and missing boundary on `execute_registry_tool` — these affect autonomous metrics, not Production user path. ROI of Production change is low.

---

## Rejected

| Option | Reason |
|--------|--------|
| OPT1_EVAL_PRODUCTION_BRIDGE | Valid next candidate but not mandatory this phase; eval-only, defer to optional iteration |
| OPT2_MINIMAL_AGENT_POLICY | Historical fetch-skip not reproduced; agent policy change needs Human Review |
| OPT3_STRUCTURED_MECHANICAL | Large scope, high regression risk, wrong-answer rate unmeasured |
| OPT4_RTT | Prior defer; baseline now passes without orchestration abstraction |

---

## Production Changes

**None.**

---

## Evaluation Changes

Added observation harness only (no eval-path fix this phase):

- `ai_tool/web_tool_post_baseline_architecture_exploration.py`
- `ai_tool/run_web_tool_post_baseline_architecture_exploration.py`
- `tests/ai_tool/project_audit/test_web_tool_post_baseline_architecture_exploration.py`

---

## Tests

| Test | Result |
|------|--------|
| Golden production (GT1–GT6) | 6/6 PASS |
| Live Osaka chain | PASS |
| Boundary probe (empty search) | PASS |
| pytest web suite | 23 passed |
| Unit test (exploration harness) | 2 passed |

---

## Before / After

| Metric | Pre d37e343 | Post d37e343 / ddc34d2 | This session |
|--------|-------------|------------------------|--------------|
| Osaka live E2E | FAIL/PARTIAL | PASS | **PASS** |
| Golden GT1 | FAIL | PASS | PASS |
| Eval mock divergence | CONFIRMED | CONFIRMED | CONFIRMED (unchanged) |
| Production changes | extraction S4 | none (STOP_D) | **none (STOP_A)** |

---

## Human Intervention

**0** — no agent policy, registry, prompt, or security boundary changes proposed or applied.

---

## Git

| Item | Value |
|------|-------|
| initial_head | `ddc34d2` |
| final_head | `ddc34d2` (harness commit pending) |
| production_changes | [] |
| unrelated worktree | preserved (not staged) |

---

## Decision Log

```json
{
  "initial_head": "ddc34d2",
  "final_head": "ddc34d2",
  "baseline_status": "PASS",
  "observations": ["Non-Wikipedia example.com: ok=True fact_ready=True method=paragraph_density_body"],
  "confirmed_causes": [
    "execute_registry_tool uses _mock_search_web by default",
    "execute_registry_tool path has no WebSessionTracker / apply_web_answer_boundary"
  ],
  "hypotheses": [
    "Primary Production factual chain sufficient for baseline Wikipedia queries",
    "Eval mock default causes false positives if search_web_fn omitted",
    "Architecture changes have low ROI until wrong-answer rate measured"
  ],
  "unknowns": [
    "SUCCESS-class wrong answer rate",
    "Search backend time instability",
    "Long-tail JSON-LD patterns",
    "agent.py subprocess parity",
    "fact_ready vs question-specific evidence gap"
  ],
  "options": ["OPT0_NO_ACTION", "OPT1_EVAL_PRODUCTION_BRIDGE", "OPT2_MINIMAL_AGENT_POLICY", "OPT3_STRUCTURED_MECHANICAL", "OPT4_RTT"],
  "selected_option": "OPT0_NO_ACTION",
  "rejected_options": ["OPT1", "OPT2", "OPT3", "OPT4"],
  "production_changes": [],
  "tests": ["golden", "live chain", "boundary", "pytest 23 passed"],
  "human_intervention_count": 0,
  "decision": "NO_ACTION",
  "stop_reason": "STOP_A"
}
```

Full artifact: `runs/ai_tool/20260828_233836_web_tool_post_baseline_architecture_exploration/observations.json`

---

## Remaining Problems

1. **Eval-path mock default** — affects autonomous loop metrics, not Production users.
2. **Eval-path boundary gap** — same scope as above.
3. **UNKNOWN wrong-answer rate** — needs measurement before structured/mechanical investment.

No confirmed Production defect requiring immediate fix.

---

## Next Recommended Direction

**OPT1_EVAL_PRODUCTION_BRIDGE** — optional, low-risk, eval-only iteration to align harness metrics with Production search + boundary. **Not mandatory**; Cursor should re-evaluate ROI in a future phase.

Do **not** pursue RTT, structured claims, or agent fetch gate until new confirmed Production symptoms appear or wrong-answer rate is measured.

---

## STOP

**YES**

**STOP Reason:** **STOP-A** — Production baseline sufficient; remaining confirmed issues are eval-only with low user impact; Architecture change ROI unproven.
