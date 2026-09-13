# Web Research Transaction — Investigation & Wikipedia Extractor Spike

**Date:** 2026-08-28  
**Git HEAD:** `21809f9`  
**Run:** `runs/ai_tool/20260828_231339_web_research_transaction_investigation/`  
**Role:** Pre-implementation technical verification — **no Production / Registry / Agent / Prompt changes, no Git commit**

---

## Executive Summary

固定 URL spike により、大阪市 Wikipedia の失敗は **Case 1（HTML に事実あり、抽出失敗）** と確定した。原因は search ranking ではなく、**infobox / Wikidata JSON が `mw-parser-output` の最初のマッチとして main_text に入る**こと。

**A4（metadata strip + content region）** と **A5（paragraph-density 汎用抽出）** は人口を正しく抽出する。Production A1 は wikidata 断片のみ（1008 chars, `fact_ready=false`）。

**前 Phase の RTT+SEG 推奨を、この Phase は否定する。** 第一優先は **Extraction normalization（汎用 metadata 除去）+ Agent policy（B2）**。RTT は eval 統一・観測性のために **第二段階** で十分。

---

## Cursor Independent Findings vs Inherited

| Cursor Independent (this phase) | Inherited (re-verified) |
|--------------------------------|---------------------------|
| A4/A5 fix Osaka without Wikipedia-only hardcode | Osaka URL, Phase4 H1 classification |
| RTT not required as first production move | Eval/production boundary gap |
| OPT1 Extraction+Policy over OPT2 Full RTT | fact_ready semantics, web_status enum |
| Minimal ResearchResult sufficient for regression | Capital page A1 already SUCCESS |
| LLM blocked by bad evidence (State C on A1) | qwen3:8b tool-calling requirement |

---

## 1. Current State (HEAD `21809f9`)

Production path unchanged since Live E2E validation:

```text
agent.py → search_web / read_url_text → enrich_web_evidence → WebSessionTracker
         → LLM synthesis → apply_web_answer_boundary → [WEB_STATUS]
```

Evidence normalization: `ai_tool/experimental/read_url/html_normalize.py`  
Investigation harness only: `ai_tool/web_research_transaction_investigation.py`

---

## 2. Investigation A — Wikipedia Extraction Spike

**Fixed URL:** `https://ja.wikipedia.org/wiki/大阪市`  
**Raw HTML:** 458,931 bytes; `人口` × 97; infobox present

| Probe | Strategy | main_text len | fact_ready | 人口 | Case |
|-------|----------|---------------|------------|------|------|
| **A1** | Production `normalize_html_to_evidence` | 1008 | false | **no** | **case1** |
| **A2** | `#mw-content-text` | 1008 | false | **no** | **case1** |
| **A3** | `mw-parser-output` (first match) | 1008 | false | **no** | **case1** |
| **A4** | metadata strip + mw-content-text | 620 | **true** | **yes** (2,817,627) | ok |
| **A5** | paragraph-density (generic) | 9212 | **true** | **yes** | ok |

**A1 excerpt (failure):** Wikidata JSON fragment — `{"wt":"[[1938年]]...` — not article body.

**A4 excerpt (success):** `総人口 2,817,627 人` in cleaned infobox-stripped text.

**A5 excerpt (success):** Article lead paragraph with 西日本で最多の人口.

### Extraction case classification (maintained)

| Case | Definition | Osaka |
|------|------------|-------|
| **Case 1** | Fact in HTML, extractor misses | **CONFIRMED** — raw has 人口, A1–A3 miss |
| **Case 2** | Fact absent in HTML | Rejected for Osaka |
| **Case 3** | Text has fact, fact_ready=false | Capital A1 works; Osaka is Case 1 not 3 |
| **Case 4** | Evidence ok, LLM ignores | Not primary; LLM on A5 succeeds (State A) |

### General principles (not Wikipedia hardcode)

1. **Strip structured metadata** (infobox, navbox, `typeof=` spans, embedded JSON) **before** region selection.
2. **First `mw-parser-output` match ≠ article body** on entity pages — nested infobox wins regex.
3. **Paragraph-density** (`<p>` aggregation in article/main) works without site-specific IDs.
4. **Boilerplate heuristic** correctly flags A1 output — problem is input region, not heuristic alone.

### Capital page (GT2 control)

A1 **SUCCESS** — `日本の首都` page returns article prose with 東京. Failure is **page-shape dependent**, not universal Wikipedia breakage.

---

## 3. Investigation B — Research Transaction Necessity

| Model | Orchestration | Testability | First move? |
|-------|---------------|-------------|-------------|
| **B1 Current** | low | fragmented | no |
| **B2 Policy** | medium | medium | **yes (companion)** |
| **B3 RTT** | high | high | **defer** |
| **B4 Hybrid** | medium-high | high | alternative |
| **B5 Extraction-first** | low | medium | **yes (primary)** |

### Independent reassessment of RTT

**RTT necessary when:**

- Eval/production path gap needs single transaction artifact
- Orchestration failures (skip fetch, empty-search answer) persist **after** extraction fix

**RTT unnecessary as first move when:**

- A4-class fix closes Osaka GT1
- B2 policy + boundary handles empty-search class

**Verdict:** RTT は **観測・eval 統一** に有効だが、Osaka SUCCESS の **前提条件ではない**。

---

## 4. Investigation C — ResearchResult Schema

### Minimal (sufficient for this phase)

```json
{
  "query": "大阪市の人口",
  "selected_source": "https://...",
  "status": "EXTRACTION_FAILED | SUCCESS | SEARCH_FAILED",
  "evidence": [{"url": "...", "fact_ready": false, "population_present": false}],
  "trace": [{"step": "fetch", "ok": true}]
}
```

### Extended (deferred)

`claims`, `confidence`, `timestamps` — SCS layer; over-design before extraction fix lands.

**Verdict:** Minimal schema **有効** — golden regression と diagnosis に十分。Production schema **未確定**。

---

## 5. Investigation D — Golden Transactions

| ID | Intent | Fetch | A1 status | Best probe | ResearchResult.status |
|----|--------|-------|-----------|------------|----------------------|
| **GT1** | 大阪市の人口 | OK | EXTRACTION_FAILED | A4 ✓ | EXTRACTION_FAILED (prod) |
| **GT2** | 日本の首都 | OK | SUCCESS | A1 ✓ | SUCCESS |
| **GT3** | 存在不能 query | SKIP | SEARCH_FAILED | — | SEARCH_FAILED |

Golden transactions **improve observability**: GT1 shows prod failure vs spike success in one artifact — supports before/after without full RTT.

---

## 6. Production / Evaluation Boundary

| Path | Tracker | Boundary | Canonical? |
|------|---------|----------|------------|
| `agent.py` subprocess | ✓ | ✓ | Production truth |
| `production_mirror` | ✓ | ✓ | **Recommended eval canonical** |
| `execute_registry_tool` | ✗ | ✗ | Lower-bound diagnostic only |
| Isolation harness | ✗ | direct fetch | Extraction unit tests |

**Proposal:** 今後の E2E / regression は **production_mirror + injectable search/fetch fixtures** を正とする。Tool-only path は残すが PASS/FAIL 判定には使わない。

---

## 7. LLM vs Architecture Boundary

| Path | Result | Layer |
|------|--------|-------|
| Deterministic A1 | no population | **Architecture** |
| Deterministic A5 | population | Architecture (fixed) |
| qwen3:8b on A1 evidence | refuses (State C) | **Blocked by architecture** |
| qwen3:8b on A5 evidence | extracts (State A) | LLM utilization OK |

**Quantification:** Osaka GT1 failure is **≥90% architecture** (extraction region). LLM is not the bottleneck when evidence is clean.

**UNKNOWN:** Agent-path tool-skip rate; empty-search hallucination under mirror E2E (not re-run).

---

## 8. Architecture Options (≥3)

### OPT1 — Extraction + Policy Hybrid (RECOMMENDED)

- Fix: metadata strip + paragraph/region selection in `html_normalize`
- Add: B2 Agent policy (mandatory fetch when search hits)
- RTT: defer

| Solves | Does not solve |
|--------|----------------|
| Osaka GT1, fact_ready false negatives | Empty search env instability |
| Keeps LLM flexibility | Eval path gap (until harness unified) |

### OPT2 — Full RTT (prior phase; deferred)

- Single `web_research` tool + ResearchResult
- Strong automation fit
- **Over-scope for proven extraction root cause**

### OPT3 — SCS First

- Structured claims after extraction fix
- Good hallucination control
- **Depends on OPT1 first**

### OPT4 — Status Quo (REJECTED)

- web_status/boundary only — GT1 remains EXTRACTION_FAILED

---

## 9. Comparison Matrix

| Criterion | OPT1 | OPT2 RTT | OPT3 SCS | OPT4 |
|-----------|------|----------|----------|------|
| Fixes Osaka | **direct** | indirect | indirect | no |
| Implementation scope | medium | large | large | small |
| Automation fit | medium | **high** | high | low |
| Web Tool quality | **high** | high | high | low |
| Contradicts prior RTT+SEG | yes | no | partial | yes |

---

## 10. Automation Compatibility

| Capability | OPT1 | RTT deferred |
|------------|------|--------------|
| Mechanical failure detection | ✓ golden GT1 | ✓ |
| Diagnosis hook | ✓ EXTRACTION_FAILED | ✓ |
| Before/after compare | ✓ A1 vs A4 | ✓ |
| Regression | ✓ fixed URL suite | ✓ |
| Cursor safe fix | ✓ isolated normalize | medium |
| Human Review reduction | medium | high later |

**Quality first:** Automation favors RTT long-term; **extraction fix has higher immediate quality ROI**.

---

## 11. Recommended Architecture

**Selected: OPT1 — Extraction normalization + Agent policy (B2), RTT deferred**

### Why selected

1. Spike **proves** population extractable via general metadata-strip principle (A4, A5).
2. LLM **already works** when evidence is clean (A5 → State A).
3. Full RTT adds schema/orchestration scope **before** closing proven extraction gap.
4. **Contradicts** prior Independent Architecture Challenge RTT+SEG first move — **data-driven revision**.

### Why RTT+SEG not selected now

- SEG as separate plugin registry is **unnecessary** if A4 logic lives in generic normalize.
- RTT is second-phase eval unification, not Osaka blocker.

### Human Review Required (before Production)

1. `html_normalize.py` change scope — infobox/JSON strip patterns
2. Agent policy gates — `agent.py` vs prompt-only
3. Regression suite — GT1/GT2/GT3 golden URLs
4. byte limit interaction (fetch truncated at 262144 — still sufficient this run)

---

## 12. Rejected Designs

| Design | Reason |
|--------|--------|
| OPT2 RTT first | Extraction fix unblocked without it |
| OPT4 status quo | GT1 confirmed fail |
| Wikipedia-only `#mw-content-text` hardcode alone | A4 principle generalizes; A5 works without IDs |
| SCS before extraction | garbage-in remains on A1 |

---

## 13. Unknowns

- A4/A5 generalization to non-Wikipedia sites with JSON-LD
- Live E2E SUCCESS after extraction fix (search + agent path)
- Agent tool-skip rate
- Optimal fetch byte limit after metadata strip
- SCS reliability on qwen3:8b for multi-claim queries

---

## 14. Proposed Next Phase

**Phase name:** Extraction Normalization — Experimental Prototype & Golden Regression

| Step | Deliverable | Production |
|------|-------------|------------|
| 1 | Prototype A4 logic in experimental module | None |
| 2 | Golden GT1–GT3 pytest with fixed HTML fixtures | None |
| 3 | production_mirror GT1 re-run | Harness only |
| 4 | Human Review packet for html_normalize merge | Review gate |
| 5 | RTT design sketch (eval only) | None |

**STOP when:** GT1 A1-equivalent path shows population OR Human Review rejects scope.

---

## 15. STOP Criteria

| Criterion | Met |
|-----------|-----|
| Wikipedia fixed-URL spike | ✓ |
| Case 1–4 separation | ✓ |
| RTT necessity re-evaluated | ✓ (defer) |
| ResearchResult validity | ✓ minimal |
| Golden transactions ≥3 | ✓ GT1–GT3 |
| Path boundary documented | ✓ |
| LLM vs architecture | ✓ partial |
| Architecture options ≥3 | ✓ OPT1–4 |
| Automation evaluated | ✓ |
| UNKNOWNs explicit | ✓ |
| Human Review packet | ✓ |
| No implementation / commit | ✓ |

**STOP: YES** — Do not proceed to Production without Human Review.

---

## Appendix — Artifacts

| File | Content |
|------|---------|
| `observations.json` | Full investigation output |
| `extraction_results.json` | Investigation A |
| `golden_transactions.json` | Investigation D |
| `comparisons.json` | B models + LLM boundary |
| `recommendation.json` | OPT1 selection |
| `decision.json` | STOP + next phase |
| `human_review_packet.json` | Review items |

**Run tests:** `python ai_tool/run_web_research_transaction_investigation.py`
