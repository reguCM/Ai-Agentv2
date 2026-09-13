# Web Tool Web-Status & Failure Boundary — Decision Log

**Run:** `20260828_225027_web_tool_web_status_evaluation`  
**Git HEAD (start):** `5611093cc51ca8dab77c6c27a0395d2fb3f6d403`  
**Production scope:** Web Status layer + Agent answer boundary (minimal)

---

## Initial State

- `search_web` / `read_url_text` return Evidence Contract fields + `grounding` hints
- No machine-readable pipeline status; LLM self-report only for failure
- Phase 4 Evidence Isolation confirmed: Osaka live = EXTRACTION_FAILED pattern
- Agent prompt mentions `grounding` but no programmatic enforcement

## Observed Problem

Web search failure was expressed via LLM natural language ("検索できませんでした"), allowing:
- General-knowledge numeric fill-in after empty search
- Conflation of search failure / fetch failure / extraction failure
- No user-visible system-generated status independent of LLM

## Confirmed Facts

- `enrich_web_tool_result` is the single enrichment point (agent + e2e)
- `ObservationBundle` exists for Failure Diagnosis but lacked `web_status_*` fields
- Isolated LLM can refuse when evidence absent (Phase 4 E4b); E2E hallucination is Agent-path
- `classify_search_web_outcome` only covers search layer (empty/hits/error)

## Hypotheses

- Machine-readable status on tool results + session aggregation enables boundary without LLM trust
- Answer boundary via template replacement (not LLM re-prompt) is sufficient for v1
- UI change not required — stdout `[WEB_STATUS]` + tool result metadata sufficient

## Design Alternatives

| Alt | Description | Verdict |
|-----|-------------|---------|
| A | LLM re-prompt on failure | **Rejected** — trusts LLM again |
| B | Parse LLM answer for "検索できません" | **Rejected** — violates policy |
| C | `web_status` on tool result + `WebSessionTracker` + boundary | **Selected** |
| D | Registry schema break for new tool | **Rejected** — scope too large |

## Rejected Alternatives

- LLM-authored failure messages as primary signal
- Hardcoding Osaka/Wikipedia paths
- Blocking all answers on any web failure (too aggressive)

## Selected Design

### Modules

| Module | Role |
|--------|------|
| `tools/system/network/web_status.py` | Layer + overall status derivation, session aggregation |
| `tools/system/network/web_answer_boundary.py` | Numeric/web-claim suppression on failure states |
| `tools/system/network/web_evidence.py` | Attach `web_status` + extend `grounding` |
| `agent.py` | Track session, apply boundary, print `[WEB_STATUS]` |
| `ai_tool/web_tool_web_status_evaluation.py` | Cases C1–C7 |

### Status taxonomy

**Overall:** `SUCCESS | PARTIAL | NO_EVIDENCE | SEARCH_FAILED | FETCH_FAILED | EXTRACTION_FAILED | NOT_APPLICABLE | UNKNOWN`

**Layers:** `search`, `fetch`, `extraction`, `evidence` — each with distinct codes.

**Distinctions enforced:**
- `SEARCH_FAILED` ≠ `NO_EVIDENCE` ≠ `FETCH_FAILED` ≠ `EXTRACTION_FAILED`

## Why Selected

- Minimal diff at existing enrichment point
- Reuses Evidence Contract (`quality.fact_ready`, warnings) without breaking it
- Deterministic — same tool results → same status
- Connects to Failure Diagnosis via `observation_from_web_session()`

## Implementation Scope

**Changed:**
- `tools/system/network/web_status.py` (new)
- `tools/system/network/web_answer_boundary.py` (new)
- `tools/system/network/web_evidence.py`
- `agent.py` (session tracker + boundary + stdout)
- `tools/system/capability_route_obs.py` (trial digest)
- `ai_tool/web_tool_failure_diagnosis_phase4.py` (bridge)
- Evaluation harness + tests

**Not changed:**
- Registry schema
- search_web / read_url_text core logic
- UI components
- HTML extraction for Wikipedia

## Tests

- `tests/test_web_status.py` — 9 tests
- `tests/test_web_evidence_pipeline.py` — updated
- `tests/ai_tool/project_audit/test_web_tool_web_status_evaluation.py` — 4 tests
- Failure diagnosis tests — regression pass

## Evaluation (C1–C7)

| Case | Expected | Result |
|------|----------|--------|
| C1 SUCCESS | SUCCESS | PASS |
| C2 empty search | SEARCH_FAILED + boundary | PASS |
| C3 fetch failed | FETCH_FAILED + boundary | PASS |
| C4 extraction | EXTRACTION_FAILED | PASS |
| C5 no evidence | NO_EVIDENCE | PASS (after fixture fix) |
| C6 partial | PARTIAL | PASS |
| C7 hallucination | boundary suppresses numeric | PASS |

## Before / After

| Aspect | Before | After |
|--------|--------|-------|
| Tool result status | grounding hints only | `web_status` struct |
| Failure types | implicit / LLM text | 5 distinct overall codes |
| Answer control | prompt only | programmatic boundary |
| User visibility | LLM prose | `[WEB_STATUS]` system line |
| Diagnosis input | manual ObservationBundle | `observation_from_web_session()` |

## Remaining Unknowns

- Live E2E with qwen3_8b under boundary (unit tests use synthetic answers)
- PARTIAL + numeric when fact_ready_count=1 — boundary policy may need refinement
- Question-target-aware NO_EVIDENCE (requires intent/fact pattern — out of scope)
- API/UI surfacing beyond stdout

## Known Limitations

- `NO_EVIDENCE` uses `fact_ready=false` heuristic, not semantic fact matching
- Boundary replaces entire answer on unsupported claim (conservative)
- Search-only session ending in PARTIAL until fetch attempted

## Safety

- No force-push, no registry break
- Boundary only activates when web tools were used
- SUCCESS path unchanged

## Regression

- Existing web evidence pipeline tests pass
- Failure diagnosis phase4 tests pass

## Git Commit

Selective commit of web status files only (see final report).

## Next Candidate

- Live agent E2E with boundary metrics
- Extend ObservationBundle with first-class `web_status_*` fields
- Softer PARTIAL boundary (preserve non-numeric portions)

## STOP Reason

**SUCCESSFUL STOP** — S1–S10 substantially met; regression clean; no human-review blockers.
