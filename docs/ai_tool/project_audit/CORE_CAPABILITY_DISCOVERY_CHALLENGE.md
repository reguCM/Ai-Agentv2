# Core Capability Discovery & Specification Challenge

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Run:** `runs/ai_tool/20260829_144628_core_capability_discovery_challenge/`  
**Human Intervention:** 0  
**Production changes:** NONE

---

## Overall: **PASS**

Golden 6/6 intact. Core Capability discovery completed. Mechanical Verification reassessed. Specification change request identified. **Production changes: NONE.**

---

## 1. Current Architecture Assessment

### Production-integrated Core

| Layer | Components | Role |
|-------|------------|------|
| Search | `search_web` + hardening | Query → ranked URLs |
| Fetch | `read_url_text` + S4 normalization | HTML → clean text |
| Evidence | `web_evidence.enrich_web_tool_result` | Grounding hints for LLM |
| Status | `web_status` + `WebSessionTracker` | Layer-level SUCCESS/FAILURE |
| Boundary | `web_answer_boundary` | Suppress numeric claims on Web failure |
| Agent | `agent_tool_gate` → enrich → session → boundary | Production user path |

**Canonical Production path:**

```text
Search → Fetch → Extraction (S4) → Evidence → web_status → Boundary → LLM
```

### Eval / Observation (non-Production)

| Component | Role |
|-----------|------|
| `production_mirror` (`production_agent_web_loop`) | Eval path mirroring Production |
| `failure_diagnosis_phase4` | Observation bundle for failures |
| `success_class` / `broader_success_class` evaluation | ExpectedFact-based accuracy |
| Autonomous improvement probes | Phase-specific harnesses |
| `mechanical_verification` (experimental) | MATCH/MISMATCH/UNSUPPORTED/UNKNOWN |

### Deferred or Absent

- Research Transaction
- Structured Claim (Production)
- Mechanical Answer (Production)
- Generic Retry/Fallback framework
- Unified Eval Production Parity Bridge
- Capability Lifecycle Registry

### Confirmed Gaps (observation-backed)

1. **`execute_registry_tool` mock default** — returns 3 hits on nonsense query; diverges from Production search.
2. **Eval-direct path** — lacks `WebSessionTracker` / `web_answer_boundary`.
3. **Open-domain verification** — requires `ExpectedFact`; heuristic-only limited to numerics/years.
4. **Live search intermittency** — Web layer symptom, not a Core Capability deficiency.

### Independent Challenge Notes

| Question | Assessment |
|----------|------------|
| 「今は不要」=「将来も不要」? | **Invalid.** CC-02 (verify metadata) has low current need, high future value. |
| 「低ROI」= Core不要? | **Invalid for Production connection.** Experimental prebuild ROI is separate. |
| Prebuild reduces future cost? | **YES** for CC-01 (eval gap), CC-02 (verify module exists). **NO** for RTT / Mechanical Answer. |
| Legacy risk | **MEDIUM** — 15+ harness files; CC-03 lifecycle registry mitigates. |
| Cursor runaway risk | **HIGH** without max-1-per-phase + sunset; policy addresses. |

---

## 2. Discovered Future Capabilities (max 3)

### CC-01 — Eval Production Parity Bridge

| Dimension | Assessment |
|-----------|------------|
| **概要** | Unified eval wrapper forcing `production_mirror` + injectable fixtures for all autonomous PASS/FAIL metrics. |
| **将来用途** | Autonomous loop metric parity; regression without mock-search false positives; agent policy experiments; LLM/model comparison on canonical path. |
| **現在の必要性** | LOW — Production user path OK; eval metrics diverge. |
| **再利用性** | HIGH — all `web_tool_*` harnesses. |
| **防御性** | MEDIUM — prevents wrong autonomous STOP decisions. |
| **コスト** | LOW — harness-only module. |
| **リスク** | LOW — no Production connection. |
| **推奨分類** | **C2 — Investigate** |

**Sunset:** All harnesses migrated OR policy rejects unified path; 2 phases with zero eval-gap observations after migration.

**Combines with:** `production_mirror`, `failure_diagnosis`, `WebSessionTracker`.

---

### CC-02 — Verification Metadata Envelope

| Dimension | Assessment |
|-----------|------------|
| **概要** | Post-LLM deterministic verification as structured metadata (MATCH/MISMATCH/UNSUPPORTED/UNKNOWN) — observation-only, no answer replacement. |
| **将来用途** | Success-class eval enrichment; future Warning layer (OPT7); autonomous STOP validation; human review claim packets; combine with `web_status` SUCCESS to detect LLM-layer failures. |
| **現在の必要性** | LOW — numeric_error 7.7%, no Production ROI. |
| **再利用性** | HIGH — any Evidence+LLM path. |
| **防御性** | MEDIUM–HIGH when connected; HIGH as eval. |
| **コスト** | LOW — built on `mechanical_verification`. |
| **リスク** | LOW while experimental. |
| **推奨分類** | **C3 — Experimental Capability** (already built; retain) |

**Sunset:** No harness references for 2 consecutive phases; OR live numeric_error < 5% sustained AND no HR for Warning; OR superseded by Structured Claim (explicit HR).

**Combines with:** `mechanical_verification`, `web_answer_boundary`, success_class eval.

---

### CC-03 — Capability Lifecycle Registry

| Dimension | Assessment |
|-----------|------------|
| **概要** | Machine-readable registry of Experimental Core Capabilities with classification, sunset date, last-used phase, connect/disconnect status. |
| **将来用途** | Prevent harness/Capability proliferation; sunset enforcement for Model B; autonomous loop inventory; human audit of experimental surface. |
| **現在の必要性** | NONE — policy exists in docs only. |
| **再利用性** | HIGH — all future phases. |
| **防御性** | MEDIUM — anti-bloat, anti-runaway. |
| **コスト** | LOW — JSON/markdown registry. |
| **リスク** | LOW. |
| **推奨分類** | **C1 — Record** |

**Sunset:** Never needed if experimental count stays ≤3 active.

**Combines with:** autonomous improvement loop, Decision Log format.

---

### Rejected as Core (explicit)

| Candidate | Reason |
|-----------|--------|
| Research Transaction | Integration cost too high; deferred 3+ phases |
| Mechanical Answer (Production) | ROI insufficient at measured failure rates |
| Generic Retry/Fallback framework | No confirmed Production symptom |

---

## 3. Existing Mechanical Verification Assessment

**Location:** `ai_tool/experimental/mechanical_verification/`  
**Classification:** **C3 — Experimental Capability (retain)**  
**Metrics reference:** `runs/ai_tool/20260829_144008_web_tool_mechanical_verification/`

### Re-evaluation against 7 focus questions

| # | Question | Answer |
|---|----------|--------|
| 1 | Core Capabilityとして十分汎用的か | **YES**, with limits — requires `ExpectedFact` or question-specific patterns for entity/scope; heuristic-only for numerics/years. |
| 2 | Verifier以外の将来用途 | Success-class replay; pre-Production Warning metadata (OPT7); autonomous STOP validation; human review claim packets; combine with `failure_diagnosis` ObservationBundle. |
| 3 | Mechanical Answerとの責務分離 | **CLEAR** — `verify_answer` does not replace LLM output. |
| 4 | Warning / Retry / Fallback に発展可能か | **Warning:** FUTURE if numeric_error > 15%. **Retry:** DEFERRED (HR required). **Fallback:** REJECTED for project scope. |
| 5 | Claim Verification以外と組み合わせ | `web_status` (SUCCESS gate), `web_answer_boundary` (failure vs success-class split), success_class `ExpectedFact`, `failure_diagnosis`. |
| 6 | Production接続なしで先行保有する価値 | **YES** — 92.6% scenario pass, FP=0, FN=0; low cost; enables OPT7 without Production commit. |
| 7 | Sunset条件 | No harness invocation for 2 consecutive eval phases; live numeric_error < 5% for 3 consecutive broader eval runs AND no Warning HR; superseded by Structured Claim (explicit HR + migration). |

**Production connection:** NOT RECOMMENDED at current measured failure rates.

---

## 4. Specification Change Requests

### SCR-01 — Eval Canonical Path Policy

```text
SPECIFICATION_CHANGE_REQUEST

Current specification:
Web tool evaluation harnesses may use execute_registry_tool directly
or production_mirror interchangeably; no project-wide canonical eval path.

Observed / projected problem:
CONFIRMED across phases: execute_registry_tool defaults to mock search (3 hits
on nonsense query); no WebSessionTracker/boundary on eval-direct path.
Autonomous metrics can diverge from Production without indicating failure.

Proposed specification:
Project policy: PASS/FAIL metrics for Web Research autonomous evaluation
MUST use production_mirror (or Eval Production Parity Bridge wrapper).
execute_registry_tool direct path is diagnostic-only and MUST NOT drive
STOP/Architecture decisions.

Why current specification may become limiting:
Without canonical eval spec, Cursor can pass autonomous phases while
Production and eval paths diverge — undermines self-improvement loop integrity.

Benefits:
- Autonomous STOP decisions align with Production behavior
- Reduces false Architecture conclusions
- Single wrapper (CC-01) implementable without Production change

Costs:
- Harness migration effort
- Tests expecting mock-default behavior may need update
- Slightly longer eval runs (live search when not fixture-injected)

Risks:
- Over-constraining quick diagnostic probes
- Live search flakiness affects eval PASS rate

Alternative: keep current specification
Keep dual paths but require explicit path_label in Decision Log and
forbid STOP_D based on eval-direct metrics alone.

Recommendation:
Adopt proposed specification OR alternative with path_label mandate.
Does not require Production code change — policy + harness only.

Human decision required: YES
```

---

## 5. Autonomous Development Policy Recommendation

### Auto-implement (Production)

- Measured Failure on Production user path
- Golden + live E2E regression protection
- Minimal diff scope

### Experimental prebuild allowed

- Core system capability (not End Tool)
- ≥2 concrete future use cases documented
- Independent module under `ai_tool/experimental/`
- Observation-only first; no Production import from Production side
- Automatic tests; reversible; **max 1 new Core per phase**

### Ask user

- Specification changes (SCR-*)
- Agent policy / Prompt / Registry changes
- Production Warning/Retry/Fallback connection
- Architecture with Human Review flag

### STOP without implement

- No measured Production defect
- ROI unproven for Production connection
- Capability count would exceed 3 active without sunset
- Duplicate of existing capability

### Decision model (extended)

```text
Observation
→ Diagnosis
→ Current Fix Candidate
→ Core Capability Discovery (max 3)
→ Future Scenario Analysis
→ Cost/Risk/Reuse Evaluation
→ Capability/Production Separation
→ Options
→ Select → Implement / Experimental / Defer / Reject / Ask User
→ Regression
→ STOP
```

### Anti-runaway rules

- Max 3 Core candidates recorded per phase
- Max 1 new Experimental Core implementation per phase
- Sunset after 2 unused phases
- Production connection requires measured failure + HR matrix
- Harness creation alone is not success

---

## 6. Decision

| Decision | Rationale |
|----------|-----------|
| **STOP_NO_CHANGE** | No Production defect; no C4 Production Candidate. |
| **RECORD_FUTURE_CAPABILITIES** | CC-03 Capability Lifecycle Registry (C1). |
| **INVESTIGATE** | CC-01 Eval Production Parity Bridge (C2) — prototype before Production touch. |
| **EXPERIMENTAL_CAPABILITY** | CC-02 / Mechanical Verification retained (C3); already built. |
| **HUMAN_REVIEW_REQUIRED** | SCR-01 eval canonical path policy. |
| **SPECIFICATION_CHANGE_REQUEST** | SCR-01 — eval path divergence confirmed across 3+ phases. |

**Production changes:** `[]`  
**Experimental changes:** `[]` (this phase evaluates only; CC-02 built in prior phase)

---

## Artifacts

| Artifact | Path |
|----------|------|
| Harness | `ai_tool/core_capability_discovery_challenge.py` |
| Runner | `ai_tool/run_core_capability_discovery_challenge.py` |
| Tests | `tests/ai_tool/project_audit/test_core_capability_discovery_challenge.py` |
| Run output | `runs/ai_tool/20260829_144628_core_capability_discovery_challenge/` |
| Observations | `.../observations.json` |
| Decision log | `.../decision.json` |
| Candidates | `.../capability_candidates.json` |

---

## Success Criteria Met

- 「今は不要」と「将来も不要」を区別した（CC-02, CC-03）
- 「将来便利そう」と「今すぐ作るべき」を区別した（CC-01 C2 vs CC-02 C3 vs CC-03 C1）
- Record → Investigate → Experimental → Production の段階を適用した
- Mechanical Verification を独立再評価した
- 仕様変更要求（SCR-01）をユーザー判断事項として分離した
- Production 変更なしで判断体系を検証した

**本 Phase の成功 = 新機能追加ではなく、判断体系そのものの設計・検証。**
