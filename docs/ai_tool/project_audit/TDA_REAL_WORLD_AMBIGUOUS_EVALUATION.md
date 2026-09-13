# TDA Real-World Ambiguous Tool Development — Phase G

**実行日:** 2026-08-30  
**判定:** `TDA_PRACTICAL_ENTRY_REACHED` — 4/4 ケース PASS  
**Production 変更:** 0 | **新規 C3:** 0

---

## 1. 目的

Phase F で採用した Standard Workflow に、**人間が Tool 名を指定しない曖昧要求**を投入し、TDA が Tool 発見・調査・選定・仕様化まで支援できるかを総合評価する。

---

## 2. Requirement（入力）

```text
LLMの学習内容だけでは難しそうなToolを1つ考えてください。
必要な技術・環境・既存ツールなどをWeb Researchで調査し、
実際に作れそうなところまで持っていってください。
```

**ルール:** 人間側から特定 Tool を誘導していない。

---

## 3. Candidate Generation（TG-1 Primary）

TDA が内部検討した候補（5件）:

| ID | Tool | LLM Gap | Difficulty |
|----|------|---------|------------|
| INT-A | Universal Robots Program Validator | HIGH | HIGH |
| INT-B | Local GPU Model Batch Inference Runner | HIGH | MEDIUM |
| INT-C | Niche DataFrame CSV Processor (Polars) | MEDIUM | MEDIUM |
| INT-D | PDF Table Extraction Assistant | MEDIUM | LOW |
| INT-E | JSON File Reader Utility | LOW | LOW |

各候補に `why_useful` / `why_llm_insufficient` / `required_external_knowledge` / `potential_web_research` を付与。

---

## 4. Selected Tool

**Universal Robots Program Validator**（INT-A）

### Why（選定理由）

専門 API/言語（URScript manual, PolyScope commands）が必要で、LLM-only では捏造リスクが高い。Web Research で公式仕様を確認しながら Tool 化する価値が高い。

### Deciding Factors

- llm_knowledge_gap
- research_value
- official_documentation_need
- implementation_feasibility

Mechanical Score による自動決定は行っていない。

---

## 5. LLM Knowledge Gap

| 項目 | 内容 |
|------|------|
| Gap レベル | HIGH |
| 不足理由 | URScript は Python と異なり、LLM が robot API を hallucinate しやすい |
| 必要外部知識 | URScript manual, PolyScope commands, UR SDK TCP protocol |

---

## 6. Web Research

Standard Workflow（Phase F そのまま）実行:

| Stage | 結果 |
|-------|------|
| Requirement Gate | RESEARCH_REQUIRED |
| L0–L3 Goals | 専門領域 Tool 調査 → 調査資産蓄積 |
| Capability Discovery | API Observation, Research Reuse 等 |
| Research Reuse | no_reuse（初回） |
| Web Research | 3 queries（URScript fixtures） |
| Decision Support | 2 technology candidates |
| Tool Spec | Extended Specification 到達 |

---

## 7. Research Reuse（比較ケース）

| ケース | Reuse | Searches Saved |
|--------|-------|----------------|
| TG-1 Primary | no_reuse | 0 |
| TG-2 LLM-sufficient JSON | no_reuse (gate exit) | N/A |
| TG-3 Seed UR + same ambiguous | full_reuse | 3 |
| TG-4 Env-heavy GPU seed | partial_reuse | 1 |

**合計 Search Reduction:** 4

---

## 8. Decision Factors

Technology Candidate から抽出:

- version / python_compatibility
- license
- official_source
- cuda_compatibility（該当時）
- conflict（version_requirement — **保持、未解決**）
- unknown_count（license 等）

Version Matrix Core は作らず VersionFact + Decision Factor を REUSE。

---

## 9. User Resolution

| Case | 状態 |
|------|------|
| TG-1 | **D** — 2 sources 間 version conflict 保持 |
| TG-2 | **A** — 単一候補（Gate early exit） |
| TG-3 | **D** — conflict 保持 |
| TG-4 | **B/C** — 複数候補 + partial reuse |

Human Review: EXPERIMENTAL_FIRST 判定時のみ推奨 — 機械的強制なし。

---

## 10. Tool Specification（TG-1 最終）

```text
Tool Name: Universal Robots Program Validator
Purpose: Validate URScript against official command set
Environment: Python 3.10+; robot controller network
APIs: movej, movel (observed in official docs)
License: UNKNOWN（Evidence から未取得 — 推測なし）
Unknowns: license
Safety: Robot motion / e-stop awareness — TDA 未検証
Implementation Boundary: Spec draft only — 本 Phase では実装しない
```

---

## 11. Implementation Feasibility

**TG-1:** `EXPERIMENTAL_FIRST`

- 専門領域 + Unknown/Conflict あり
- 小さな Experimental PoC から開始を推奨
- 本 Phase では Production 実装なし

**TG-2 JSON:** `BUILD_NOW`（LLM 一般知識で足りる — Web 不要）

---

## 12. New Ideas（TDA 自然発見 vs Phase C–F 後付け）

| Idea | Origin | Decision |
|------|--------|----------|
| Multi-domain internal brainstorming | **tda_natural** | REUSE |
| LLM gap driven selection | **tda_natural** | EXPERIMENTAL |
| API Observation for URScript | tda_natural | REUSE |
| Research Reuse on TG-3 | tda_natural | REUSE |
| Knowledge Base | phase_prior_catalog | REJECT |
| Vector DB / RAG | phase_prior_catalog | REJECT |

**Phase C–F で見えなかった点:** 曖昧要求から **Internal Tool Candidate Generation** 段階が Standard Workflow の前に必要（Orchestration 追加、Core ではない）。

---

## 13. False Discovery

| Capability | 理由 |
|------------|------|
| Knowledge Base | ResearchStore 十分 |
| Vector DB / RAG | Token matching 十分 |
| Version Matrix Core | VersionFact 十分 |
| Automatic Tool Builder | Phase G 禁止 |
| Generic Resolver | Conflict 保持方針 |

---

## 14. Idea Preservation

`idea_preservation.py` — REJECT/DEFER アイデアを Future Trigger 付きで保持。再評価可能。

---

## 15. Stage Observations（TG-1 抜粋）

| Stage | Observation | Idea | Decision |
|-------|-------------|------|----------|
| Tool Candidate Generation | 5 internal candidates | Multi-domain brainstorming | REUSE |
| Candidate Selection | UR Validator selected | LLM gap selection | EXPERIMENTAL |
| Research Reuse Check | no_reuse | Past research skip | REUSE |
| Web Research | 3 searches | UR official docs | REUSE |
| Capability Discovery | API Observation | Official spec fetch | REUSE |

---

## 16. 成功条件 G1–G12

| ID | 結果 |
|----|------|
| G1 曖昧要求から候補生成 | PASS |
| G2 LLM-only 不足説明 | PASS |
| G3 Web Research 自律定義 | PASS |
| G4 Past Research Reuse | PASS |
| G5 不足分のみ検索 | PASS |
| G6 必要時複数 Candidate | PASS |
| G7 Version/Env/License 材料 | PASS |
| G8 Conflict/Unknown 非解決 | PASS |
| G9 Tool Specification 到達 | PASS |
| G10 「作らない」判断 | PASS |
| G11 Capability 記録 | PASS |
| G12 REJECT/DEFER | PASS |

---

## 17. Production / Core

| 項目 | 値 |
|------|-----|
| Production 変更 | **0** |
| 新規 C3 | **0** |
| 追加（Orchestration） | `internal_tool_candidates.py`, `phase_g_harness.py`, `extended_spec_draft.py`, `implementation_feasibility.py`, `stage_observation.py` |

---

## 18. Final Decision — `TDA_PRACTICAL_ENTRY_REACHED`

> **曖昧な「何か便利な Tool を作りたい」から、LLM 自身が目的を整理し、既存資産を確認し、必要な Web 情報だけを調査し、候補を比較し、Tool Specification + Implementation Feasibility まで到達できる。**

TDA は単なる Web 検索機能ではなく、**Tool Development Assistance として実用的な入口に到達**したと判断する。

---

## 19. 次 Phase 候補

実装 Phase（Human Review 後）:

- 選定 Tool（UR Program Validator）の Experimental PoC 実装
- ResearchStore 永続化（必要時）
- Production 接続は実測問題 + HR 後のみ

---

## 20. 関連ファイル

| 種別 | パス |
|------|------|
| Harness | `ai_tool/experimental/development_assistance/phase_g_harness.py` |
| Internal Candidates | `ai_tool/experimental/development_assistance/internal_tool_candidates.py` |
| Runner | `ai_tool/run_tool_development_assistance_phase_g.py` |
| Tests | `tests/ai_tool/project_audit/test_tool_development_assistance_phase_g.py` |
| Workflow | [Phase F](./TDA_STANDARD_WORKFLOW_ADOPTION.md) |

**実行:**

```bash
python ai_tool/run_tool_development_assistance_phase_g.py
pytest tests/ai_tool/project_audit/test_tool_development_assistance_phase_g.py -q
```
