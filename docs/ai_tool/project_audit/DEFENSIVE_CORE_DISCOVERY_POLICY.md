# Defensive Core Discovery Policy — Integration & Autonomous Development Rule

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Policy version:** `1.0-limits`  
**Run:** `runs/ai_tool/20260829_150127_defensive_core_discovery_policy/`  
**Human Intervention:** 0  
**Production changes:** NONE

---

## Overall: **PASS**

Defensive Core Discovery Policy integrated as evaluation/harness module. Two-track autonomous development rule operational. Golden GT1–GT6: **6/6 PASS**.

---

## Policy Adoption Decision

### **`ADOPT_WITH_LIMITS`**

| Limit | Content |
|-------|---------|
| Max new C3/phase | 1 |
| Policy mutable | Version `1.0-limits` — not fixed architecture rule |
| Production auto-change | Forbidden without C4 + HR |
| Sunset | 2 unused phases triggers KEEP/SIMPLIFY/SUNSET review |
| Self-evaluation | Re-assess after several phases; shrink if benefit < complexity |

**Rationale:** Policy module integrates without Agent/Registry/Production changes; CC-01 reuse validates Track B; no new C3 this phase.

---

## Two-Track Model

### Track A — Current Problem Resolution

```text
Observation → Reproduction → Diagnosis → Minimal Fix → Regression
```

Production change requires measured problem.

### Track B — Future Core Discovery

```text
Q1–Q7 Discovery → C0–C4 Classify → Cost/Benefit → Record / Investigate / Experimental
```

No current problem required. Production connection forbidden unless C4 + HR.

---

## Classification (C0–C4)

| Class | Action |
|-------|--------|
| **C0** | No candidate — build nothing |
| **C1** | Record — design / decision log only |
| **C2** | Investigate — spike only, no Production |
| **C3** | Experimental — isolated module, no Production connection |
| **C4** | Production candidate — measured need + HR |

---

## This Phase — Mandatory Report

### Current Problem Track

| Item | Status |
|------|--------|
| Observed problems | None new |
| Fixed problems | None (policy integration only) |
| Remaining | SCR-01 full project adoption (optional HR) |
| Regression | Golden **6/6 PASS** |

### Future Core Track

| Class | Candidates |
|-------|------------|
| C1 | CC-03 Capability Lifecycle Registry |
| C2 | — |
| C3 | — (no new C3 this phase) |
| C4 | — |
| Rejected | — |

### Existing Core Usage

| ID | Name | Class | Reuse | Production |
|----|------|-------|-------|------------|
| PROD-web_status | web_status + WebSessionTracker | C4 | 12 | ✅ |
| PROD-boundary | web_answer_boundary | C4 | 10 | ✅ |
| CC-01 | Eval Production Parity Bridge | C3 | 8 | ❌ |
| CC-02 | Mechanical Verification | C3 | 3 | ❌ |
| EVAL-production_mirror | production_mirror | C3 | 15 | ❌ |
| EVAL-failure_diagnosis | failure_diagnosis_phase4 | C3 | 4 | ❌ |
| C1-CC-03 | Capability Lifecycle Registry | C1 | 0 | ❌ |

**Total documented reuse count:** 52

### Specification Requests

**SCR-01** — Eval canonical path (harness-level adopted; full project policy HR optional)

**SCR-02** — Web Research / LLM Context Architecture (design philosophy adopted; Production unchanged) — [WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md](./WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md)

### Complexity Check

| Item | Value |
|------|-------|
| Added LOC | ~350 (policy + runner + tests) |
| New modules | `defensive_core_discovery_policy.py` |
| Production coupling | NONE |
| Agent / Registry / Prompt | unchanged |
| Maintenance burden | LOW |

### Phase Decisions

- **CONTINUE**
- **RECORD** (CC-03)
- **NO_CORE_ACTION** (no new C3)
- **HUMAN_REVIEW_REQUIRED** (SCR-01 optional full adoption)

---

## C3 Creation Requirements

- **A** Reuse Potential — ≥2 future uses
- **B** Independent Boundary
- **C** Low Coupling
- **D** Observation First
- **E** Reversible

---

## Mechanical Verification

| Aspect | Status |
|--------|--------|
| Classification | **C3 Experimental — retain** |
| Role (SCR-02) | **Extends LLM** (anomaly detection, claim observation) — **not** Mechanical Answer |
| Production answer replacement | ❌ |
| Warning / Retry / Fallback | Deferred |
| Future | OPT7 Post-LLM Verify Metadata (re-evaluate when measured) |

---

## Anti-Overengineering

- Max 1 new C3+ per phase
- No Core mass production
- Harness creation ≠ success
- "Not used now" ≠ reject — use C1/C2/C3 instead

---

## Human Review Boundary

Production Architecture, Agent policy, Prompt, Registry, Warning/Retry/Fallback, Mechanical Verification Production connection, answer replacement — **HR required**.

Experimental-only (Production disconnected, reversible, low coupling) — **autonomous OK**.

---

## Implementation Artifacts

| Artifact | Path |
|----------|------|
| Policy module | `ai_tool/defensive_core_discovery_policy.py` |
| Runner | `ai_tool/run_defensive_core_discovery_policy.py` |
| Tests | `tests/ai_tool/project_audit/test_defensive_core_discovery_policy.py` |
| Harness delegate | `eval_production_parity_bridge.defensive_core_policy()` → policy module |
| Core registry | `runs/.../core_registry.json` |

---

## Success Criteria Met

- ✅ Track A / Track B separated
- ✅ C0–C4 classification recordable
- ✅ Existing Core reuse tracked
- ✅ Production change not auto-justified
- ✅ No new Core when none warranted (NO_CORE_ACTION)
- ✅ SCR format supported
- ✅ Golden regression maintained
- ✅ Policy self-evaluated as ADOPT_WITH_LIMITS

---

## Future Policy Review (Section 18)

After several phases, evaluate:

- Core candidates actually discovered?
- Prebuild capabilities reused?
- Development speed impact?
- Cursor over-engineering trend?
- Production stability?
- HR load?

If `Core Discovery benefit < complexity cost` → **shrink policy**.

---

## STOP Conditions

None triggered — integration did not require Agent/Registry/Production changes or large registry.
