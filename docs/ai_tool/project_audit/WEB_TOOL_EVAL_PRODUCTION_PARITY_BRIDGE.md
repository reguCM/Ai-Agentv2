# Web Tool — Eval Production Parity Bridge & Defensive Core Policy

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Run:** `runs/ai_tool/20260829_145026_eval_production_parity_bridge/`  
**Human Intervention:** 0  
**Production changes:** NONE

---

## Overall: **PASS**

CC-01 Eval Production Parity Bridge implemented as Evaluation infrastructure. SCR-01 adopted at harness level. Golden GT1–GT6: **6/6 PASS**. Path separation and STOP integrity verified.

---

## 1. CC-01 Implementation

| Item | Status |
|------|--------|
| CC-01 implemented | **YES** |
| Module | `ai_tool/agent_integration/eval_production_parity_bridge.py` |
| Evaluation harness | `ai_tool/eval_production_parity_bridge_evaluation.py` |
| Runner | `ai_tool/run_eval_production_parity_bridge.py` |
| Tests | `tests/ai_tool/agent_integration/test_eval_production_parity_bridge.py` |

### Bridge API

| Function | Purpose |
|----------|---------|
| `run_canonical_web_eval()` | Production-equivalent path (gate → enrich → tracker → boundary) |
| `run_diagnostic_direct_eval()` | `execute_registry_tool` direct — diagnostic only |
| `compare_path_divergence()` | Demonstrate mock default vs canonical gap |
| `validate_stop_decision_integrity()` | Block diagnostic path from Production STOP |
| `defensive_core_policy()` | Model B policy as structured data |

### Path metadata (minimal, aligned with existing schema)

| Field | Canonical | Diagnostic |
|-------|-----------|------------|
| `path_label` | `eval_parity_bridge` / `production_mirror` | `eval_harness_direct` |
| `production_equivalent` | `true` | `false` |
| `boundary_applied` | `true` (when applicable) | `false` |
| `web_session_tracker` | `true` | `false` |
| `mock_or_live` | `mock` / `fixture` / `live` | `mock` (trial_mock default) |
| `backend` | from search result | `trial_mock` |
| `diagnostic_only` | `false` | `true` |
| `scored` | `true` for PASS/FAIL metrics | `false` |

---

## 2. Production / Registry / Agent / Prompt Changes

| Category | Changed |
|----------|---------|
| Production code | **NO** |
| Registry | **NO** |
| Agent | **NO** |
| Prompt | **NO** |

Bridge wraps existing `production_agent_web_loop` and `execute_registry_tool` without modifying their semantics.

---

## 3. SCR-01 — Eval Canonical Path Policy

### Adopted (harness level)

- **Canonical (scored):** `production_mirror` or `eval_parity_bridge` via `run_canonical_web_eval()`
- **Diagnostic:** `execute_registry_tool` direct via `run_diagnostic_direct_eval()`
- **Rule:** direct mock PASS ≠ Production PASS

### Verified

| Check | Result |
|-------|--------|
| Canonical `production_equivalent` | ✅ |
| Diagnostic not production-equivalent | ✅ |
| Canonical has boundary + tracker | ✅ |
| Diagnostic lacks boundary + tracker | ✅ |
| Nonsense query: diagnostic 3 hits (trial_mock) vs canonical 0 (fixture) | ✅ |
| `STOP_NO_CHANGE` blocked on diagnostic path | ✅ |
| `STOP_NO_CHANGE` allowed on canonical path | ✅ |

---

## 4. Metrics Integrity

### Path separation (`compare_path_divergence`)

```text
query: zzzz_nonexistent_xyz_12345
diagnostic: 3 hits, backend=trial_mock, boundary=false
canonical:  0 hits, boundary=true (empty-search fixture)
mock PASS → production PASS: FALSE
```

### STOP decision integrity

Production-level decisions (`STOP_NO_CHANGE`, `STOP_D`, etc.) require `path_meta.can_drive_production_decision() == true`.

Diagnostic observations (`DIAGNOSTIC_OBSERVATION`) remain allowed on any path.

---

## 5. Golden Regression

| Metric | Result |
|--------|--------|
| GT1–GT6 | **6/6 PASS** |
| Production chain unchanged | ✅ |

---

## 6. Defensive Core Policy (Model B)

Integrated in `defensive_core_policy()`:

| Stage | Action |
|-------|--------|
| **C1 — RECORD** | Future value; document only (e.g. CC-03 Lifecycle Registry) |
| **C2 — INVESTIGATE** | Low-cost probe; no Production |
| **C3 — EXPERIMENTAL** | Isolated prebuild (`ai_tool/experimental/`) |
| **C4 — PRODUCTION** | Measured defect + Human Review |

### Separation rules

- Experimental prebuild ≠ Production connection
- Low current need ≠ no future value
- Future usefulness ≠ build now for Production

### Mechanical Verification

| Aspect | Status |
|--------|--------|
| Retain experimental | ✅ |
| Production answer replacement | ❌ |
| Production Warning / Retry / Fallback | Deferred |
| Sunset | 2 unused phases OR numeric_error < 5% sustained |

### Anti-overengineering

- Max 1 new Core Capability per phase
- Harness proliferation without sunset = failure
- No Production change under prevention-only rationale

---

## 7. Future Capability Candidates

| ID | Name | Classification | Notes |
|----|------|----------------|-------|
| CC-03 | Capability Lifecycle Registry | **C1 — Record** | When active experimental > 3 |
| CC-02 | Verification Metadata Envelope | **C3 — Experimental** | Retain `mechanical_verification` |

No new Core implemented this phase beyond CC-01 bridge.

---

## 8. Human Review

| Item | Required |
|------|----------|
| SCR-01 full project policy adoption | Optional — harness-level adoption complete |
| Migrate phase1/2/3 eval-direct harnesses | Recommended next; not blocking |
| Production connection of any Capability | **YES** when requested |

This phase: **Human Review NOT required** for bridge deployment (Evaluation-only).

---

## 9. pytest

```
11 passed (test_eval_production_parity_bridge)
+ web_status + core_capability_discovery regression in runner
pytest exit: 0
```

---

## 10. Decision

| Decision | Rationale |
|----------|-----------|
| **STOP_NO_CHANGE** | Production unchanged |
| **EXPERIMENTAL_CAPABILITY** | CC-01 bridge deployed |
| **RECORD_FUTURE_CAPABILITIES** | CC-03 remains C1 |

**STOP reason:** None — all integrity checks passed.

---

## 11. Next Phase Candidates

1. Migrate `web_tool_practical_evaluation*.py` and `web_tool_end_to_end_evaluation_phase3.py` to `run_canonical_web_eval()`
2. CC-03 Capability Lifecycle Registry when experimental count exceeds manageable manual tracking
3. Optional: project-wide SCR-01 policy document in `docs/ai_tool/project_audit/README.md` (Human decision)

---

## Artifacts

| Artifact | Path |
|----------|------|
| Bridge module | `ai_tool/agent_integration/eval_production_parity_bridge.py` |
| Evaluation | `ai_tool/eval_production_parity_bridge_evaluation.py` |
| Runner | `ai_tool/run_eval_production_parity_bridge.py` |
| Tests | `tests/ai_tool/agent_integration/test_eval_production_parity_bridge.py` |
| Run output | `runs/ai_tool/20260829_145026_eval_production_parity_bridge/` |

---

## Success Criteria Met

- Evaluation と Production の境界を機械的に分離
- mock path だけで Production STOP できないことを検証
- Defensive Core Policy (Model B) を実装可能な形で整理
- Production 変更なし
- Golden 6/6 維持
