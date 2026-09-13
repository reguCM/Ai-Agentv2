# Web Tool Independent Architecture Challenge

**Date:** 2026-08-28  
**Git HEAD:** `21809f9`  
**Run:** `runs/ai_tool/20260828_230700_web_tool_independent_architecture_challenge/`  
**Role:** Independent design only — **no implementation, no Git commit**  
**Analyst stance:** Re-evaluate from observations; do not treat prior human proposals as correct answers.

---

## Cursor-independent vs inherited content

| Source | Examples in this document |
|--------|-------------------------|
| **Independent (this challenge)** | Root cause as "optional research transaction"; Design Options RTT / SEG / SCS; completion matrix emphasis on enforcement gap; rejection of incremental-only sufficiency |
| **Inherited (re-verified facts)** | Osaka wiki extraction failure; Search Hardening の-variant fix; Evidence Contract field names; eval/production boundary gap |

Prior **Hybrid Evidence Pipeline (案 C)** from `WEB_TOOL_ARCHITECTURE_DESIGN_CHALLENGE.md` assumed Evidence Contract **absence**. Since `f4150e9`, contract **exists** — this challenge treats that as a **phase shift**, not a reason to adopt 案 C unchanged.

---

## 1. Current State

### 1.1 Architecture as deployed (HEAD `21809f9`)

```text
User request
    ↓
agent.py — LLM tool loop (MAX_TOOL_ROUNDS)
    ↓
search_web → general_web_search → backends → rank → hits + grounding + web_status
    ↓
read_url_text → HTTP GET → html_normalize → main_text + quality.fact_ready + web_status
    ↓
LLM synthesis (free-form answer)
    ↓
WebSessionTracker → apply_web_answer_boundary → [WEB_STATUS] + final answer
```

Parallel: Failure Diagnosis (`ObservationBundle` → `diagnose()`), extensive eval harnesses (often **without** boundary).

### 1.2 Git evolution (Web-relevant commits)

| Commit | Layer |
|--------|-------|
| `e2826f5` | search_web formal adoption |
| `82fca73` | read_url_text graduation |
| `f4150e9` | Evidence Pipeline (main_text, fact_ready, grounding) |
| `5611093` | Search Hardening (CJK / の-variant discovery) |
| `435b499` | web_status + answer boundary |
| `21809f9` | Live E2E validation harness |

**Net:** Discovery and **failure observability** improved; **evidence content** and **E2E factual success** remain unresolved.

### 1.3 Completion maturity (11 dimensions)

| Dimension | Maturity | Evidence |
|-----------|----------|----------|
| **Search** | PARTIAL | Hardening fixes Osaka の-variant; DDG/composite/Paris weak; env all-empty sessions (Live E2E) |
| **Source Selection** | PARTIAL | LLM picks wiki URL when hits good (E2E Phase3 A/B) |
| **Fetch** | PARTIAL | HTTP ok; byte limits configurable |
| **Evidence Extraction** | **FAIL** (key cases) | Osaka live: infobox/wikidata, no 人口 (Isolation Phase4) |
| **Evidence Utilization** | PARTIAL | Isolated LLM ok on clean fixture; blocked upstream in E2E |
| **Agent** | PARTIAL | Loop + gate + boundary; no "research must complete" invariant |
| **LLM** | PARTIAL | Model must support tools; hallucination under empty search partially bounded |
| **Failure Boundary** | PARTIAL | Agent path only; eval gap; SUCCESS path live unverified |
| **User-visible result** | PARTIAL | `[WEB_STATUS]` stdout; no structured consumer API |
| **Failure Diagnosis** | **GOOD** | Phase4 rules + web_status bridge |
| **Evaluation / Automation** | **GOOD** | Many harnesses; **path fragmentation** weakens comparability |

**Independent conclusion:** The project excels at **observation and diagnosis** but has not closed the loop on **evidence correctness** or **orchestration guarantees**.

---

## 2. Confirmed Facts

1. **No live E2E PASS** for Osaka population–class factual queries across recorded phases (E2E Phase3 FAIL; Isolation confirms upstream extraction).
2. **Evidence Contract exists** (`main_text`, `quality.*`, `grounding`, `web_status`) — failures are no longer "schema missing" but **wrong main_text region** and **weak enforcement**.
3. **Osaka ja.wikipedia:** fetch ok, `fact_ready=false`, **人口 absent** from main_text; byte sweep 64K–512K unchanged (Isolation Phase4).
4. **Search Hardening (`5611093`):** `大阪市の人口` 1st hit 大阪市の不祥事 → **大阪市** (Search probe + E2E Phase3).
5. **web_status (`435b499`):** machine enum distinguishes SEARCH_FAILED / FETCH_FAILED / EXTRACTION_FAILED / NO_EVIDENCE; boundary suppresses some unsupported numerics (unit + Live E2E Case B).
6. **Eval vs Production:** `execute_registry_tool` has **no** WebSessionTracker / boundary (Live E2E CONFIRMED).
7. **Isolated LLM** refuses without fact in main_text (E4b); **Agent E2E** still shows hallucination_candidate on empty search (Phase3 C/E) — path-dependent behavior.
8. **Subprocess agent.py** fails tool loop unless `AI_AGENT_MODEL` supports tools (Live E2E).
9. **Failure Diagnosis** deterministic engine operational with adapters.

---

## 3. Observations

- **web_status is reactive:** attached post-tool; does not drive retry, alternate URL, or block premature answer.
- **fact_ready** ≈ text-quality heuristic, **not** "evidence answers this question."
- **Observation >> enforcement:** 10+ audit phases; production still relies on LLM + late boundary.
- **Harness proliferation:** mirror / subprocess / eval-direct / isolation — metrics not unified.
- **Environment sensitivity:** Live E2E session had all backends empty — confounds architecture validation.
- **State B (fact in text, fact_ready=false, LLM extracts)** not reproduced live — `fact_ready=false` may over-block Agent even when text usable (Isolation E3b/E3c inconclusive).

---

## 4. Hypotheses

| ID | Hypothesis |
|----|------------|
| H-ARCH | Primary gap: Web research is **optional LLM tool choreography**, not a **verifiable transaction** with pre/postconditions. |
| H-EXT | When discovery succeeds for Wikipedia ja municipalities, **extraction region selection** dominates failure (not search ranking). |
| H-BND | Boundary mitigates **failure-class** numeric hallucination but not **SUCCESS-class** wrong claims if fact_ready=true on irrelevant text. |
| H-ENV | Backend instability **masks** extraction fixes in live E2E — stable-backend test bed needed. |
| H-EVAL | Eval harness without boundary **overstates** LLM hallucination risk relative to production agent path. |

---

## 5. Unknowns

- Live **SUCCESS** end-to-end after `435b499` with stable backends and known-good pages.
- **Intent–evidence alignment** without site-specific extractors or LLM-in-the-loop verification.
- Whether consolidating tools into a Research Transaction **reduces** LLM orchestration errors or hides debugging surface.
- Root cause of **composite / Paris** empty search (backend coverage vs query API vs ranking).
- Optimal split: **SEARCH_EMPTY** vs **SEARCH_ERROR** (currently conflated when `error` string set).
- Whether Agent should **hard-block** answer when `fact_ready=false` but main_text contains target fact (State B).

---

## 6. Root Cause Analysis

### 6.1 Symptom → cause chain (independent reframing)

```text
Symptom: User asks factual web question → no supported answer
    ↓
Immediate: (a) empty search  (b) fetch ok + wrong main_text  (c) LLM skips fetch
             (d) LLM meta/HTML answer  (e) hallucination after empty search
    ↓
Systemic: No layer owns "research transaction completed successfully for this intent"
    ↓
Architectural: Pipeline is LLM-imperative; tools return bytes/hints; correctness is emergent not guaranteed
```

### 6.2 Layer responsibilities vs gaps

| Layer | Owns today | Does NOT own |
|-------|------------|--------------|
| search_web | Discovery candidates | Relevance to user intent; retry policy |
| read_url_text | HTTP + normalize + fact_ready | Site-specific body extraction; intent match |
| web_status | Post-hoc status enum | Orchestration decisions |
| boundary | Final numeric suppression on failure states | Claim–evidence verification on SUCCESS |
| LLM | Query, tool choice, synthesis | Should not own "did research succeed?" — but does |
| Diagnosis | Post-mortem classification | Prevention |

### 6.3 Rejection of single-layer root cause

| Prior framing | Current assessment |
|---------------|-------------------|
| "Evidence Contract missing" | **Outdated** post-f4150e9 |
| "Search only" | **Insufficient** — hardening helped; extraction still fails |
| "LLM only" | **Partial** — isolated LLM behaves; orchestration path differs |
| "Prompt only" | **Insufficient** — prompt exists; enforcement weak |

**Independent root cause statement:**

> The Web Tool lacks a **Research Transaction** abstraction with machine-verifiable completion criteria tied to **user intent**, while **extraction** remains a generic HTML heuristic inadequate for dominant sources (Wikipedia ja).

---

## 7. Design Options

### Option RTT — Research Transaction Tool (orchestrated macro-tool)

**Idea:** Replace LLM-driven search→fetch choreography with one registry tool `web_research(query, intent)` that **internally** runs deterministic orchestration:

```text
web_research
  → search (existing)
  → deterministic URL pick (rank + entity tokens, not LLM)
  → fetch top-k
  → extract + intent pattern check
  → return ResearchResult { status, evidence[], gaps[], web_status }
```

LLM receives **ResearchResult** only; synthesis prompt forbids claims outside `evidence[]`.

| Criterion | Assessment |
|-----------|------------|
| Solves | Orchestration gap; eval/production parity; observability |
| Does not solve | Wikipedia extraction without extractor plugin; backend env |
| Changes | New tool + orchestrator module; Agent prompt simplification |
| Side effects | Less LLM visibility into raw hits; debugging via transaction log |
| Automation fit | **HIGH** — single artifact to test |
| Human intervention reduction | **HIGH** — LLM no longer picks URL |
| Testability | **HIGH** — fixture backends + golden ResearchResult |
| Diagnosis connection | Natural — one ObservationBundle per transaction |
| Self-repair fit | **HIGH** — retry policies machine-defined |
| New UNKNOWNs | Intent schema design; backward compat with search_web |

---

### Option SEG — Site Extractor Plugins (extraction-first)

**Idea:** Keep search_web + read_url_text surface; add **SiteProfile** registry (wikipedia-ja, wikipedia-en, generic-fallback). Fetch path selects extractor by URL/host. Wikipedia plugin targets `#mw-content-text` / article paragraphs, skips infobox JSON.

| Criterion | Assessment |
|-----------|------------|
| Solves | Osaka-class H1 failure directly |
| Does not solve | LLM orchestration; empty search; hallucination |
| Changes | html_normalize → profile router; site-specific tests |
| Side effects | Maintenance per site; overfitting risk |
| Automation fit | **MEDIUM** — golden HTML fixtures per profile |
| Human intervention | **MEDIUM** — new sites need profiles |
| Testability | **HIGH** for extraction; low for E2E |
| Diagnosis | Maps to EXTRACTION_FAILED vs FETCH_FAILED clearly |
| Self-repair | **MEDIUM** — plugin swap on failure class |
| New UNKNOWNs | Generic web long-tail quality |

---

### Option SCS — Structured Claim Synthesis (answer decoupling)

**Idea:** Split pipeline into (1) **ClaimExtractor** — LLM or rules emit `{claim, quote, source_url, confidence}` JSON from main_text only; (2) **AnswerRenderer** — deterministic template from verified claims. No free-form factual prose from LLM.

| Criterion | Assessment |
|-----------|------------|
| Solves | Hallucination; evidence traceability; user-visible citations |
| Does not solve | Empty main_text; bad extraction input |
| Changes | Agent answer path; new structured schema |
| Side effects | Rigid UX; multi-claim questions harder |
| Automation fit | **HIGH** — schema validation |
| Human intervention | **LOW** after schema stable |
| Testability | **HIGH** — JSON assertions |
| Diagnosis | Claim-level failure taxonomy |
| Self-repair | **MEDIUM** — re-extract on low confidence |
| New UNKNOWNs | LLM structured output reliability |

---

### Option INC — Incremental enforcement (status quo extension)

**Idea:** Keep current tools; strengthen web_status-driven gates in Agent (mandatory fetch, block answer if !SUCCESS, split SEARCH_EMPTY/ERROR).

| Criterion | Assessment |
|-----------|------------|
| Solves | Some Agent-policy gaps cheaply |
| Does not solve | Extraction content; intent alignment |
| Changes | agent.py policy only |
| Side effects | False negatives; prompt fights |
| Automation fit | **MEDIUM** |
| Human intervention | **LOW** |

**This challenge explicitly rejects INC as sufficient** — it repeats the pattern "observe more, enforce slightly" without fixing extraction or transaction model.

---

## 8. Comparison Matrix

| Criterion | RTT | SEG | SCS | INC |
|-----------|-----|-----|-----|-----|
| Fixes Osaka extraction | indirect | **direct** | indirect | no |
| Fixes orchestration | **direct** | no | partial | partial |
| Fixes hallucination | partial | no | **direct** | partial |
| Implementation scope | Large | Medium | Large | Small |
| Automation / self-dev fit | **High** | Med | **High** | Med |
| Web Tool quality ceiling | **High** | Med | **High** | Low |
| Preserves LLM flexibility | Med | High | Low | High |
| Eval/production unify | **High** | Med | Med | Med |
| Risk | transaction design | site maintenance | schema rigidity | stagnation |

---

## 9. Automation Compatibility

For Cursor-autonomous develop loops, desirable properties:

| Property | RTT | SEG | SCS |
|----------|-----|-----|-----|
| Single observable artifact per run | ✅ ResearchResult | ⚠️ per-fetch | ✅ ClaimSet |
| Deterministic failure enum | ✅ | ✅ | ✅ |
| Golden fixtures | ✅ | ✅✅ | ✅ |
| Reduces LLM non-determinism in critical path | ✅ | ⚠️ | ✅ |
| Diagnosis → fix loop closable | ✅ | ✅ | ⚠️ |

**Independent insight:** Automation maturity of **diagnosis** exceeds **orchestration**. Next phase should optimize for **one transaction boundary** machines can regression-test, not more isolated probes.

---

## 10. Recommended Design

### Recommendation: **RTT + SEG (phased hybrid)** — with investigation gate

**Not** a full commitment to implement — **recommended direction** pending Phase N investigation.

**Phase N1 (investigation):** SEG for Wikipedia ja only — prove E2E SUCCESS on fixed URLs + live Osaka with stable search.  
**Phase N2 (architecture):** RTT wrapper — internal orchestration calls existing search/fetch; external single ResearchResult.

**Why not SCS alone?** Structured claims help synthesis but **garbage in** from extraction remains; SCS is best as **layer on top of RTT+SEG**, not first move.

**Why not INC alone?** Twelve phases of observation show enforcement without extraction fix cannot reach "complete."

**Why not prior 案 C unchanged?** Evidence Contract now exists; 案 C's problem statement is partially solved. Remaining gap is **transaction + extraction**, not contract definition.

**Why RTT over pure SEG?** SEG fixes one failure class; RTT fixes **system shape** for automation and eval parity.

### Decision status

| Item | Status |
|------|--------|
| RTT+SEG direction | **Recommended** (independent) |
| SCS as Phase N3 | **Hypothesis** |
| INC sufficient | **Rejected** |
| Full architecture lock | **Deferred** — investigation gate below |

---

## 11. Rejected Designs

| Design | Reason |
|--------|--------|
| LLM re-prompt on failure | Trusts LLM for failure detection (policy violation) |
| Parse "検索できません" from answer | Same |
| INC-only continuation | Repeats observation-enforcement gap |
| Prior 案 C as-is | Evidence Contract already shipped |
| UI-first failure display | Does not fix evidence |
| Dedicated Research Tool (separate product) | Scope explosion without transaction model |
| Hard-block all answers on any web failure | Over-aggressive; breaks non-factual chat |

---

## 12. Additional Investigation

Before implementation, Cursor (or human) should run:

1. **Stable-backend SUCCESS baseline** — fixture/mock search returning known URLs; verify full chain post-435b499.
2. **SEG spike on Osaka HTML** — measure 人口 in main_text with `#mw-content-text` selector only (read-only spike doc, no production).
3. **RTT interface draft** — ResearchResult JSON schema + 3 golden transactions (SUCCESS, EXTRACTION_FAILED, SEARCH_FAILED).
4. **Intent pattern library** — minimal non-site-specific patterns (population, capital, height) for machine check vs fact_ready.
5. **Production boundary on fact_ready=false + fetch ok** — live mirror when search succeeds (blocked by env in last run).
6. **Unified eval entrypoint** — all harnesses through boundary + WebSessionTracker for comparable metrics.
7. **LLM vs architecture boundary** — same cases on qwen3_8b vs tool-less model to quantify MODEL_CAPABILITY floor.

### Production vs Evaluation path

| Path | Boundary | Tracker | Use |
|------|----------|---------|-----|
| agent.py | Yes | Yes | Production truth |
| production_mirror | Yes | Yes | E2E with raw/final |
| execute_registry_tool | No | No | **Misleading for safety** |

### LLM vs Architecture boundary

| Phenomenon | Likely layer |
|------------|--------------|
| Empty search → numeric answer | Architecture (boundary) + LLM |
| Fetch skipped despite prompt | LLM tool selection |
| HTML meta answer | LLM utilization + bad main_text |
| Wrong wiki region in main_text | **Architecture (extraction)** |
| の-variant wrong hit | **Architecture (search)** — mitigated |

---

## 13. Proposed Next Phase

**Phase name:** Web Research Transaction — Investigation & Wikipedia Extractor Spike

**Scope:** Design + spike only; no production merge without Human Review.

| Step | Deliverable | Production change |
|------|-------------|-------------------|
| 1 | ResearchResult schema + 3 golden fixtures | None |
| 2 | Wikipedia ja extractor spike (offline HTML) | None |
| 3 | Unified eval runner (all paths use boundary) | Harness only |
| 4 | Live E2E with mock-stable search backend | Harness only |
| 5 | RTT design doc vs Agent integration options | None |

**STOP for that phase when:** Osaka fixed-URL shows 人口 in extracted text OR spike proves selector insufficient (UNKNOWN escalated).

---

## 14. STOP Criteria (this challenge)

| Criterion | Met |
|-----------|-----|
| Current state re-evaluated | ✅ |
| Residual problems classified | ✅ |
| Root causes reorganized | ✅ |
| ≥3 independent design options | ✅ (RTT, SEG, SCS; INC rejected) |
| Comparison matrix | ✅ |
| Automation fit evaluated | ✅ |
| Recommendation or defer | ✅ RTT+SEG with investigation gate |
| UNKNOWNs explicit | ✅ |
| Next phase proposed | ✅ |
| Decision log saved | ✅ |
| **No implementation** | ✅ |
| **No Git commit** | ✅ |

**STOP: YES** — Do not proceed to implementation from this document alone.

---

## Appendix — Phase artifact index

| Phase doc | Key independent signal |
|-----------|------------------------|
| Failure Analysis | Multi-layer negative chain |
| Architecture Challenge (old) | Contract absence — **superseded post-f4150e9** |
| Evidence Pipeline | main_text + fact_ready introduced |
| Practical Eval 2 | Prompt variant effects |
| Failure Isolation 3 | の-variant / fetch skip / LLM matrix |
| Diagnosis Phase 4 | Deterministic taxonomy |
| Search Hardening | Discovery fix scope limits |
| E2E Phase 3 | fetch=1 but fact_ready blocks |
| Extraction Isolation 4 | H1 extraction confirmed |
| Web Status | Machine enum + boundary |
| Live E2E | Eval gap + env sensitivity |

**Run artifacts:** `observations.json`, this document.
