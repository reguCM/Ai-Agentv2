# Web Tool Evidence Extraction Isolation — Phase 4

**Run:** `20260828_223857_web_tool_evidence_extraction_isolation_phase4`  
**Git HEAD:** `5611093cc51ca8dab77c6c27a0395d2fb3f6d403`  
**Production changes:** NONE | **Git commit:** NONE

---

## 1. Executive Summary

Search / Agent / Prompt を介さず、**固定 URL → read_url_text → Evidence → LLM extraction** のパイプラインだけで fact_ready=false 問題を H1–H5 に分離した。

**Overall:** 主要境界は切り分け完了。**Osaka live は H1（Extraction failure）が主因**。H2（heuristic）は fixture で再現。H3 は clean fixture（E4/E5）で正常。H4 は isolated LLM では未再現。H5 は E5a/E5b および E3b/E3c で metadata 効果なし。

---

## 2. Isolation Pipeline

```text
Observation (fixed URL / fixture)
    ↓
Evidence inspection (read_url_text / normalize_html_to_evidence)
    ↓
Fact presence (_contains_target_fact)
    ↓
fact_ready comparison (_fact_ready_reason)
    ↓
LLM extraction (optional, isolated prompt)
    ↓
Supported / Unsupported (numeric_claim_supported_by_evidence)
    ↓
Diagnosis (state A/B/C/D + CONFIRMED/OBSERVATION/HYPOTHESIS/UNKNOWN)
```

**Harness:** `ai_tool/web_tool_evidence_extraction_isolation_phase4.py`  
**Runner:** `ai_tool/run_web_tool_evidence_extraction_isolation_phase4.py`  
**Tests:** `tests/ai_tool/project_audit/test_web_tool_evidence_extraction_isolation_phase4.py` (6 passed)

---

## 3. State Classification (A/B/C/D)

| State | fact in main_text | fact_ready | LLM behavior | Observed |
|-------|-------------------|------------|--------------|----------|
| **A** | yes | true | extracts | E4, E5a, E5b |
| **B** | yes | false | extracts | **Not observed** |
| **C** | no | false | refuses | E4b (記載なし) |
| **D** | no | false | invents | **Not observed** |

**Note:** E3b/E3c は fact 存在 + fact_ready=false だが LLM は「記載なし」→ state B 未達。短い main_text に「大阪市」明示がなく、プロンプトとの entity linkage が不足した可能性（HYPOTHESIS）。

---

## 4. Cases E1–E6 (+ E3b/E3c/E4b)

### E1 — known-good (日本の首都)

- fetch_ok=true, main_text_len=17,317, fact_ready=**true**, fact present
- Fetch-only（live LLM 未実施）

### E2 — Osaka Wikipedia live

- fetch_ok=true, main_text_len=1,008, **人口 absent**, fact_ready=**false**
- main_text = wikidata/infobox JSON 断片
- **H1 CONFIRMED**

**Byte sweep:** max_bytes 65536–524288 いずれも `人口` なし。262144+ では boilerplate heuristic。

### E3 — fixture (wiki-like)

- main_text: `人口\n272万人（2024年）`, fact present, fact_ready=**false** (body_not_reached)
- **H2 CONFIRMED**

### E3b / E3c — E3 + LLM (metadata on vs off)

| Case | metadata | llm_answer |
|------|----------|------------|
| E3b | visible | 記載なし |
| E3c | hidden | 記載なし |

metadata 差なし。**H5 inconclusive** for this fixture.

### E4 / E5 — clean English fixture

- fact_ready=true, LLM extracts 2,750,000 → state **A**
- E5a (metadata) ≈ E5b (no metadata)

### E6 — no fact fixture

- llm_answer=**記載なし** (correct refusal)
- fact_ready=true（heuristic gap — separate issue）

### E4b — Osaka live main_text → LLM

- llm_answer=**記載なし**, state **C**

---

## 5. Hypothesis Matrix

| ID | Verdict | Evidence |
|----|---------|----------|
| H1 Extraction failure | **CONFIRMED** | E2, byte sweep, E4b |
| H2 fact_ready heuristic | **CONFIRMED** (fixture) | E3; Osaka live は H1 が先行 |
| H3 LLM utilization | **Rejected** (clean evidence) | E4, E5 |
| H4 Unsupported generation | **Not observed** (isolated) | E6, E4b |
| H5 Contract mismatch | **Inconclusive** | E5a≈E5b, E3b≈E3c |

---

## 6. Phase 1–3 Causal Chain

| Prior phase | Relationship |
|-------------|--------------|
| Phase 1 HTML/meta | Separate layer |
| Phase 2 fetch=0 | Resolved by Search Hardening |
| Phase 3 Search Hardening | Irrelevant to E2 extraction |
| Phase 3 E2E | Same root — this Phase explains **why** (H1) |
| Phase 4 Diagnosis Automation | Reused for E2 fetch_diagnoses |

---

## 7. Proposed Changes (NOT implemented)

See `runs/ai_tool/20260828_223857_web_tool_evidence_extraction_isolation_phase4/proposals.json` — P1 extraction, P2 heuristic, P3 agent grounding, P4 contract docs.

---

## 8. Success Criteria

| ID | Status |
|----|--------|
| SC1–SC4, SC6–SC8 | ✅ |
| SC5 unsupported observed | ❌ (valid negative observation) |

---

## 9. Human Review

1. Osaka infobox/wikidata extraction — bug or acceptable?
2. fact_ready=false hard block vs soft warning given E4b refuses correctly?
3. E2E hallucination (Phase 3 C/E) needs live agent trace — out of scope here.

**Artifacts:** `runs/ai_tool/20260828_223857_web_tool_evidence_extraction_isolation_phase4/`

---

## 10. STOP

**STOP: YES** — 主要境界切り分け完了。Production 変更不要（原因は extraction + heuristic 層に局所化）。
