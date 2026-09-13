# Failure Diagnosis Model (Cross-Domain)

Reusable diagnostic structure extracted from Web Tool Failure Diagnosis Phase 4.  
Web Tool is the **first adapter**, not the fixed taxonomy.

---

## 1. Pipeline

```text
Test / Execution
      ↓
Failure (symptom)
      ↓
ObservationBundle (structured facts + MISSING_OBSERVATION)
      ↓
Deterministic Rules → Diagnosis[]
      ↓
(Optional) LLM-assisted refine
      ↓
ImprovementProposal[]
      ↓
Human Review Packet
      ↓
Approved Implementation (future phase — not Phase 4)
```

---

## 2. ObservationBundle (minimal fields)

| Field | Purpose | Required |
|-------|---------|----------|
| `execution_id` | Trace identity | YES |
| `source` | Run / probe origin | YES |
| `tool_calls` | tool_name → count | Often |
| `tool_selection_trace` | Ordered tool names LLM chose | When diagnosing selection |
| `agent_blocked` | Policy blocks (e.g. fetch) | When diagnosing Agent vs LLM |
| `user_intent_markers` | Derived from user_request | When diagnosing selection |
| `search_*` / `fetch_*` | Tool result quality | Domain-specific adapters |
| `final_answer` | Outcome text | When diagnosing utilization |
| `missing_observations` | Computed gaps | Always computed |

**Rule:** If a field needed for elimination is absent, record `MISSING_OBSERVATION` — do not guess.

---

## 3. Failure Taxonomy

| Class | Meaning |
|-------|---------|
| `TOOL_SELECTION` | Wrong or missing tool chosen |
| `TOOL_EXECUTION` | Tool called but failed |
| `RESULT_QUALITY` | Tool returned low-quality output |
| `RESULT_UTILIZATION` | Output not used correctly in answer |
| `AGENT_POLICY` | Agent loop blocked or failed to enforce |
| `PROMPT` | Instruction layer insufficient |
| `MODEL_CAPABILITY` | LLM reasoning / grounding failure |
| `ENVIRONMENT` | Backend, network, external dependency |
| `REGISTRY` | Tool registration / schema |
| `INTERFACE` | Contract mismatch |
| `SECURITY` | Policy violation |
| `UNKNOWN` | Insufficient evidence |

Taxonomy is **not** tied to Search/Agent/LLM/Fetch/Prompt names.

---

## 4. Diagnosis record

Each diagnosis MUST include:

- `symptom` — observable failure label
- `evidence` — list of fact strings
- `classification` — taxonomy class
- `confidence` — HIGH | MEDIUM | LOW | UNKNOWN
- `confidence_reason` — explicit criterion
- `knowledge_type` — CONFIRMED_FACT | OBSERVATION | HYPOTHESIS | UNKNOWN
- `eliminated_causes` — what evidence ruled out
- `remaining_causes` — candidates still open
- `missing_observations` — gaps
- `suggested_investigation` — next probe
- `deterministic` — rule-based or not

---

## 5. Confidence criteria

| Level | Criterion |
|-------|-----------|
| HIGH | Multiple independent observations support one cause; alternatives eliminated |
| MEDIUM | Observations support cause; alternatives partially open |
| LOW | Plausible hypothesis; direct evidence thin |
| UNKNOWN | Required observation missing |

---

## 6. Deterministic vs LLM vs Human

| Layer | Examples |
|-------|----------|
| **Deterministic** | `fetch_calls=0` + trace lacks fetch + `agent_blocked=false` |
| **LLM-assisted (future)** | Compare multiple MEDIUM-confidence causes in complex traces |
| **Human** | Any production change approval; security; high-impact proposals |

Phase 4 implements deterministic rules only. LLM hook is a no-op stub.

---

## 7. ImprovementProposal

Each proposal includes: `target`, `expected_benefit`, `risk`, `compatibility`, `implementation_scope`, `regression_risk`, `automation_suitability`, `remaining_unknowns`, `human_review_required`.

**Phase 4:** all proposals set `human_review_required=true`.

---

## 8. Adapter pattern

```text
Domain trace (JSON / pytest / live run)
    → observation_from_*()
    → ObservationBundle
    → diagnose()
    → domain-agnostic Diagnosis
```

Web Tool adapters: `observation_from_live_trace`, `observation_from_search_row`, `observation_from_fetch_probe`.

---

## 9. Generalization (Phase 4 assessment)

| Domain | Fit |
|--------|-----|
| Observation Tool | High — same execution + RESULT_QUALITY pattern |
| Tool Calling | High — TOOL_SELECTION rules |
| Registry | Partial — extend observations with schema metadata |
| Safety Check | Partial — SECURITY class reserved |
| Self Repair | Out of scope — diagnosis feeds future implementation |

---

## 10. Implementation reference

- Engine: `ai_tool/web_tool_failure_diagnosis_phase4.py`
- Runner: `ai_tool/run_web_tool_failure_diagnosis_phase4.py`
- Tests: `tests/ai_tool/project_audit/test_web_tool_failure_diagnosis_phase4.py`
