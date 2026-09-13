# LLM-Centered Web Research Architecture Adoption

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Run:** `runs/ai_tool/20260829_154841_llm_centered_web_research_architecture_adoption/`  
**Policy version:** `1.1-llm-centered`  
**Specification:** [WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md](./WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md) (SCR-02)  
**Production changes:** NONE  
**New C3 created:** NO

---

## Overall: **PASS**

Model B を **正式な通常開発方針** として適用。Production Web Tool chain 維持。新規 C3 なし。

---

## 適用内容

| 項目 | 状態 |
|------|------|
| LLM 中心の会話・判断 | **維持**（SCR-02 採用） |
| Web Tool | LLM **拡張**（置換ではない） |
| Production chain | Search → … → Boundary → LLM → Conversation **変更なし** |
| Context Format 全面移行 | **禁止**（Shootout RECORD 反映） |
| Mechanical Verification | observation 継続；Answer replacement **禁止** |
| Q8（拡張 vs 置換） | Core 評価に **必須** |

Policy: `ai_tool/defensive_core_discovery_policy.py` v1.1  
Harness: `ai_tool/normal_development_defensive_core.py`  
Runner: `ai_tool/run_llm_centered_web_research_architecture_adoption.py`

---

## Track A — Current Development

| Item | Result |
|------|--------|
| **Observation** | Golden GT3/GT6 PASS (offline)； measured Production defect なし |
| **Confirmed Problem** | **NONE** |
| **Root Cause** | N/A |
| **Implementation** | NONE |
| **Regression** | pytest PASS（web_status, web_evidence_pipeline, policy, adoption） |
| **Production Impact** | NONE |

---

## Track B — Defensive Core Discovery

| ID | Capability | C0–C4 | Cost | Benefit | Reuse | LLMとの関係 | Decision |
|----|------------|-------|------|---------|-------|-------------|----------|
| CC-03 | Capability Lifecycle Registry | C1 | LOW | MEDIUM | HIGH | 拡張 | RECORD |
| OPT7 | Post-LLM Verify Metadata | C1 | LOW | MEDIUM–HIGH | MEDIUM | 拡張 | RECORD — Warning deferred |
| CTX-PASSAGE | Evidence Passage Selector | C0 | LOW | LOW | MEDIUM | 拡張 | RECORD — no Production change |
| CTX-HYBRID | Hybrid Context Packaging | C1 | MEDIUM | LOW–MEDIUM | MEDIUM | 拡張 | RECORD — not Production candidate |
| CTX-CONFLICT-OBS | Conflict Observation | C1 | MEDIUM | LOW | LOW | 拡張 | RECORD — no Conflict Resolver |
| REJ-RTT | Research Transaction | C0 | HIGH | MEDIUM | MEDIUM | 拡張 | REJECTED |
| REJ-MECH-ANSWER | Mechanical Answer Layer | C0 | HIGH | N/A | LOW | 置換 | REJECTED — Q8 defer |
| CC-01-followup | Eval Parity Bridge | C0 | LOW | HIGH | HIGH | 拡張 | REUSE CC-01 |

**No new Core Capability advanced to C2/C3/C4** — C0/C1 record and observation only.

---

## 作らなかったもの（Phase 成功条件）

| Item | Reason |
|------|--------|
| Production Context Format migration | Shootout RECORD；1-case gap insufficient |
| Mechanical Answer | SCR-02 — Verification ≠ Answer |
| Conflict Resolver (Production) | Live LLM handled conflict without it |
| Generic Retry/Fallback | No measured need |
| Research Transaction Core | High cost；overlap |
| New C3 this phase | Max 1/phase；no C3 bar met |
| Full Architecture redesign | Chain stable |
| Search backend swap | Purposeless change forbidden |

---

## Specification Change Request

| ID | Status | HR |
|----|--------|-----|
| SCR-02 | **ADOPTED** — design philosophy | 不要 |
| SCR-01 | Harness adopted；full project optional | optional |

自動仕様変更なし。

---

## Mechanical Verification

| Aspect | Status |
|--------|--------|
| Location | `ai_tool/experimental/mechanical_verification/` |
| Answer replacement | **FORBIDDEN** |
| Warning / Retry / Fallback | **DEFERRED** |
| Verification / Observation | **CONTINUE** |

---

## Final Decision

| Decision | Rationale |
|----------|-----------|
| **STOP_NO_CHANGE** | No measured Production defect |
| **CONTINUE** | Model B operating model active |
| **RECORD** | C1 candidates + shootout-derived C0/C1 |

**Not selected:** IMPLEMENT, INVESTIGATE, EXPERIMENTAL, HUMAN_REVIEW_REQUIRED

---

## 最重要原則（適用確認）

> Production は最小開発を維持しながら、将来の LLM 能力を拡張できる低コスト Core についてだけ、別レーンで予防的に発見・評価する。

| 区分 | 本 Phase |
|------|----------|
| 今不要 ≠ 将来不要 | CC-03, OPT7, CTX-* を C1/C0 で Record |
| 将来便利 ≠ 今すぐ作る | 新規 C3 なし |
| Experimental ≠ Production | CC-02 維持；接続なし |
| Q8 置換 | REJ-MECH-ANSWER 明示却下 |

---

## Artifacts

| Artifact | Path |
|----------|------|
| Architecture Spec | `docs/ai_tool/project_audit/WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md` |
| Adoption report | 本ファイル |
| Policy module | `ai_tool/defensive_core_discovery_policy.py` |
| Phase harness | `ai_tool/normal_development_defensive_core.py` |
| Runner | `ai_tool/run_llm_centered_web_research_architecture_adoption.py` |
| Tests | `tests/ai_tool/project_audit/test_normal_development_defensive_core.py` |

再実行:

```bash
python ai_tool/run_llm_centered_web_research_architecture_adoption.py
```
