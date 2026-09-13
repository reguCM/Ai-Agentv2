# Web Tool Status Boundary — Live E2E Validation

**Run:** `20260828_230030_web_tool_status_boundary_live_e2e`  
**Git HEAD:** `435b499`  
**Production changes:** NONE  
**HUMAN_INTERVENTION_COUNT:** `0`

---

## Executive Summary

**Overall: PARTIAL** — `web_status` / boundary / `[WEB_STATUS]` は **production_mirror** 経路で CONFIRMED。**true agent.py subprocess** は初期設定不足（`AI_AGENT_MODEL`）で tool loop 未到達だったが、ハーネス修正後 **exit 0 + boundary_applied** を確認。

---

## Production vs Eval Gap (CONFIRMED)

| 経路 | WebSessionTracker | apply_web_answer_boundary | raw vs final 比較 |
|------|-------------------|---------------------------|-------------------|
| **agent.py / production_mirror** | Yes | Yes | Yes |
| **execute_registry_tool (eval harness)** | No | No | No |

---

## Case Results (production_mirror, live qwen3_8b)

| Case | Grade | observed | boundary | raw→final |
|------|-------|----------|----------|-----------|
| A | PARTIAL | SEARCH_FAILED* | true | LLM refuse → safe template |
| B | PASS | SEARCH_FAILED | true | numeric in raw → suppressed |
| C | PASS | FETCH_FAILED | false | LLM refused numeric (voluntary) |
| D | PARTIAL | SEARCH_FAILED* | true | extraction not reached (search env) |
| E | PARTIAL | NOT_APPLICABLE | false | LLM skipped tools |
| F | PARTIAL | NOT_APPLICABLE | false | LLM skipped tools |
| G | PASS | SEARCH_FAILED | true | raw safe; final = system template |

\* 本 run では live search が全 backend `検索結果がありません`（ENVIRONMENT）。SUCCESS 検証は別 run / mock が必要。

---

## Subprocess agent.py (true production)

- **Initial failure:** default model `deepseek-coder-v2:16b` → `does not support tools` (exit 1)
- **After harness env `AI_AGENT_MODEL=qwen3_8b`:** exit 0, `boundary_applied=true`
- **Proposal:** E2E runner は subprocess にも tool-capable model を必須指定（Production 変更不要）

---

## Failure Diagnosis

- Cases A/B/D/G: `diagnose()` → `empty_search` (ENVIRONMENT)
- ObservationBundle bridge from `observation_from_web_session()` — **works**

---

## HUMAN_INTERVENTION_COUNT Definition

| Value | Meaning |
|-------|---------|
| 0 | Autonomous observation only (this run) |
| 1 | Human design judgment |
| 2 | Human code fix required |
| 3 | Manual problem resolution |

---

## Findings

### CONFIRMED
- web_status on tool results in mirror loop
- WebSessionTracker aggregation (SEARCH_FAILED vs FETCH_FAILED in Case C)
- apply_web_answer_boundary replaces final answer (Case B)
- user_visible_status system notice on failures
- Failure Diagnosis connected via ObservationBundle
- Eval harness lacks boundary (by design gap)

### OBSERVATION
- Live search backends all empty this session (not web_status bug)
- Case E/F: live LLM did not invoke tools (Agent tool selection)
- Subprocess requires AI_AGENT_MODEL for tool calling
- Case G: LLM avoided 1900万 voluntarily; boundary still normalized answer

### HYPOTHESIS
- Production subprocess failures in first run were MODEL_CAPABILITY not boundary regression
- Case A SUCCESS requires stable network/backend (ENVIRONMENT)

### UNKNOWN
- Extraction failure (Osaka) on live mirror when search succeeds
- Whether boundary should apply when LLM already refuses without numeric

### REJECTED
- Using LLM "検索できませんでした" as web status source

### PROPOSED (Human Review)
1. Document subprocess E2E requires `AI_AGENT_MODEL` with tools support
2. Optional: force tool-use prompt for E2E cases E/F
3. Separate SEARCH_EMPTY vs SEARCH_ERROR in web_status layer
4. Log raw_llm_answer in agent.py stdout (future — not this phase)

---

## STOP

**STOP: YES** — S1–S12 satisfied at PARTIAL level; Production unchanged; proposals documented.
