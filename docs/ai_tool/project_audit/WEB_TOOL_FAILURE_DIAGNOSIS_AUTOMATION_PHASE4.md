# Web Tool Failure Diagnosis Automation — Phase 4

**Run:** `20260828_220208_web_tool_failure_diagnosis_phase4`  
**Git HEAD:** `f4150e9`  
**Input:** Phase 3 analysis + Phase 1/2 live traces  
**Production changes:** NONE | **Git commit:** NONE

---

## 1. Executive Summary

Phase 4 は **診断レイヤーの試作** を完了した。Web Tool を修正せず、Phase 3 の観測データから **deterministic rules** で失敗を分類し、改善候補と Human Review パケットを生成する。

**Overall: PASS** — 7 代表失敗ケースすべてを自動検出（28 observations → 27 diagnoses →  proposals）。

**設計原則:**
- Search/Agent/LLM 等の名前は **固定 taxonomy ではない**（`FAILURE_DIAGNOSIS_MODEL.md` 参照）
- 自動修正は **禁止** — Diagnosis → Proposal → Human Review のみ
- 観測不足は `MISSING_OBSERVATION` として UNKNOWN を返す

---

## 2. Diagnostic Engine

| Property | Value |
|----------|-------|
| Rules | 7 deterministic |
| LLM-assisted | **No** (stub only) |
| Same input → same output | **Yes** |
| Module | `ai_tool/web_tool_failure_diagnosis_phase4.py` |

### 2.1 Observation Model

`ObservationBundle` — 診断に必要な最小フィールドのみ。不足時は `missing_observations` に記録。

Adapters:
- `observation_from_live_trace()` — Phase 1/2 eval JSON
- `observation_from_search_row()` — Phase 3 search probe
- `observation_from_fetch_probe()` — Phase 3 fetch probe

### 2.2 Failure Taxonomy

`TOOL_SELECTION` | `TOOL_EXECUTION` | `RESULT_QUALITY` | `RESULT_UTILIZATION` | `AGENT_POLICY` | `PROMPT` | `MODEL_CAPABILITY` | `ENVIRONMENT` | `REGISTRY` | `INTERFACE` | `SECURITY` | `UNKNOWN`

### 2.3 Cause Elimination

各 diagnosis は `eliminated_causes` と `remaining_causes` を保持。

**Example — Fetch 未実行 (Case B):**

```text
Observed: explicit fetch request, fetch_calls=0, agent_blocked=false, trace=[search_web]
Eliminated: Agent blocked, Fetch execution failure
Remaining: TOOL_SELECTION (HIGH)
Missing: search_backend_has_relevant (live trace には per_backend なし)
```

---

## 3. Seven Failure Cases (Phase 3 → Phase 4)

| Case | Detected | Classification | Confidence | Key evidence |
|------|----------|----------------|------------|--------------|
| Fetch not executed | ✅ | TOOL_SELECTION | HIGH | Case B ×2 phases |
| Wrong Search Result | ✅ | RESULT_QUALITY | HIGH/MEDIUM | の-variant probe + low relevance traces |
| Empty Search | ✅ | ENVIRONMENT | HIGH | Paris probe, empty control |
| Hallucinated Number | ✅ | MODEL_CAPABILITY | MEDIUM | Case C/F traces |
| fact_ready=false | ✅ | RESULT_QUALITY | HIGH | 大阪市 wiki fetch probe |
| HTML/meta response | ✅ | RESULT_UTILIZATION | HIGH | Phase1 Case A/G |
| Backend failure | ✅ | ENVIRONMENT | HIGH | duckduckgo empty 7/8 probes |

---

## 4. Deterministic vs LLM vs Human

| Layer | Phase 4 status | Examples |
|-------|----------------|----------|
| **Deterministic** | Implemented | fetch_calls=0 + trace, fact_ready=false, html_meta markers |
| **LLM-assisted** | Design only | Multi-cause disambiguation when all MEDIUM |
| **Human** | Required for all proposals | Production/agent/prompt/registry changes |

`llm_assisted_refine()` は no-op stub — 将来 `structured observations → rules → remaining → LLM → structured diagnosis` 用。

---

## 5. Improvement Proposals

診断 ID ごとに複数 Option を生成（実装は **しない**）。

| Diagnosis | Options |
|-----------|---------|
| fetch_not_executed | A: agent_policy gate / B: prompt_contract / C: tool_selection metadata |
| wrong_search_result | A: ranking hardening / B: query generation steering |
| hallucinated_number | A: agent grounding enforce |
| fact_ready_false | A: extraction quality |

すべて `human_review_required: true`。

---

## 6. Human Review Gate

```text
Diagnosis (27)
    ↓
Proposal (N)
    ↓
Risk assessment (in proposal fields)
    ↓
Human Review — REQUIRED
    ↓
Approved Implementation (future phase)
```

**Human Review 不要と判断できるケース:** Phase 4 では **なし**（production 変更候補はすべて Review 対象）。

---

## 7. MISSING_OBSERVATION Handling

Live trace からの観測では `search_backend_has_relevant` が欠落しがち。診断は UNKNOWN confidence に落とすか、partial elimination のみ行う。

**Example:**

```json
{
  "missing_observations": ["tool_selection_trace"],
  "confidence": "UNKNOWN",
  "suggested_investigation": ["deterministic fixed-search-result test"]
}
```

---

## 8. Automation Loop

```text
Failure → ObservationBundle → diagnose() → proposals → human_review_packet
```

Phase 3 `automation_loop_insights` を **executable rules** に昇格。再実行:

```bash
python ai_tool/run_web_tool_failure_diagnosis_phase4.py
```

---

## 9. Generalization (Section N)

| Domain | Applicability |
|--------|-------------|
| Observation Tool | High — TOOL_EXECUTION + RESULT_QUALITY |
| Tool Calling | High — TOOL_SELECTION rules |
| Registry | Partial — schema observations 要追加 |
| Safety Check | Partial — SECURITY class 予約 |
| Self Repair | Out of scope — diagnosis output only |

詳細: [FAILURE_DIAGNOSIS_MODEL.md](./FAILURE_DIAGNOSIS_MODEL.md)

---

## 10. Artifacts

| Path | Content |
|------|---------|
| `ai_tool/web_tool_failure_diagnosis_phase4.py` | Diagnostic Engine |
| `ai_tool/run_web_tool_failure_diagnosis_phase4.py` | Runner |
| `tests/ai_tool/project_audit/test_web_tool_failure_diagnosis_phase4.py` | 10 tests |
| `docs/ai_tool/project_audit/FAILURE_DIAGNOSIS_MODEL.md` | Cross-domain model |
| `runs/ai_tool/20260828_220208_web_tool_failure_diagnosis_phase4/` | observations, diagnosis, proposals, pytest |

---

## 11. STOP

**YES** — 診断・提案まで完了。実装・Production 変更・Git commit は行わない。

**PROPOSED CHANGE** は `human_review_packet.json` に記録済み。Implementation Phase は Human Review 後に別途。
