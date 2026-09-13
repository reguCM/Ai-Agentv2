# Tool Development Assistance — Research Reuse & Hierarchical Capability Discovery (Phase E)

**実行日:** 2026-08-30  
**Run ID:** `20260830_105108_tool_development_assistance_research_reuse`  
**判定:** `EXPERIMENTAL_RETAIN` — 6/6 ケース PASS（offline）、検索 9 回削減観測  
**Production 変更:** 0

---

## 1. Phase の目的（再掲）

1. **過去 Web Research の再利用**で再検索・ユーザー操作を減らせるか
2. **上位概念への抽象化**で Phase C/D で見落とした Capability を TDA 自身が発見できるか
3. 有効なら今後の標準手順への組み込み可否を判断

---

## 2. 既存構造調査（§5 — 実装前）

| 構造 | 保存内容 | 再利用可能 | ギャップ |
|------|----------|------------|----------|
| TechnologyCandidate | version, environment, license, source, unknowns, conflicts | 技術同一性・事実 | research_id, requirement リンク |
| VersionFact | version/env + observed_at + provenance | 環境比較 | requirement facet |
| ResearchState | 同一セッション resume | 会話継続のみ | セッション横断不可 |
| EvidenceSource | url, title, text | Source 再追跡 | CheckedAt エンベロープ |
| ToolSpecificationDraft | spec フィールド群 | 同一技術の初稿 | 鮮度 |

**結論:** 専用 Database / Knowledge Core 不要。`ResearchRecord` エンベロープ + in-memory `ResearchStore` で Past Research Record を表現可能。

---

## 3. Current Development

| 項目 | 内容 |
|------|------|
| **Observed Problem** | Research Resume は「調査再開」として局所化され、「将来資産としての Research Reuse」という上位概念が Phase C/D で主目的化されていなかった |
| **Root Cause** | 調査結果のセッション横断 identifer / facet 照合 / partial reuse 判定が未整備 |
| **Implementation** | Experimental 薄層のみ:<br>• `research_audit.py` — 構造監査<br>• `research_record.py` — ResearchRecord + ResearchStore<br>• `research_reuse.py` — full/partial/no reuse, freshness, LLM 材料<br>• `goal_abstraction.py` — L0–L3 抽象化 + Derived Capability 評価<br>• `research_reuse_harness.py` — TRE-1..6, A/B/C/D 比較 |
| **Regression** | PoC + Phase D + Phase E テスト 27 passed |
| **Production Impact** | なし |

---

## 4. A. Research Reuse 結果

| モード | 件数 | 代表ケース |
|--------|------|------------|
| **Full Reuse** | 2 | TRE-1 Polars 再要求, TRE-6 URScript 同一要求 |
| **Partial Reuse** | 1+ | TRE-2 PyTorch 3.12→3.13, TRE-5 ToolX + Python 3.13 |
| **No Reuse** | 3 | TRE-3 JSON（無関係 past）, TRE-4 階層のみ |

Partial Reuse が **本 Phase 最重要成功条件** — Python 版のみ不足、CUDA/License/Source は past から再利用。

---

## 5. B. Search Reduction

| 条件 | Web searches |
|------|--------------|
| Without Reuse (mode B 合計) | 16 |
| With Reuse (mode D 合計) | 7 |
| **Saved** | **9** |

Mode 比較（各ケース）:

| Mode | 説明 | searches |
|------|------|----------|
| A | LLM-only | 0 |
| B | LLM + full Web | 2+ |
| C | LLM + Past Research only | 0 |
| D | Past + Partial Web | 0–1 |

---

## 6. C. User Effort（推定）

| フロー | Without Reuse | With Reuse |
|--------|---------------|------------|
| Research 開始 | 毎回 Gate + Query + Search | Reuse Check → スキップ or 部分 Search |
| 候補選択 | 2 ops | 1 op（past 材料あり） |
| 追加質問 | 同一 | 減少（past unknown 既知） |

---

## 7. D. Information Quality（再利用度）

| フィールド | Full | Partial | No |
|------------|------|---------|-----|
| Version | ○ | ○ | — |
| Environment | ○ | △（版差） | — |
| License | ○ | ○ | — |
| API | ○ | ○ | — |
| Source | ○ | ○ | — |
| Unknown | ○ 保持 | ○ 保持 | — |
| Conflict | ○ 保持 | ○ 保持 | — |

過去情報は **Fresh / Possibly stale / Unknown / Needs revalidation** ラベル付き — 固定 30 日ルールなし。

---

## 8. E. Hierarchical Discovery（ケース別）

### TRE-4 — Duplicate Input Guard（指示書の例）

| レベル | 内容 |
|--------|------|
| Request | 前回と同じ文章が来たら LLM に渡さない Tool |
| L0 | Duplicate Input を検出したい |
| L1 | 不要な LLM 処理を減らしたい |
| L2 | LLM 入力の最適化・コスト/遅延削減 |
| L3 | Agent が LLM へ渡す情報を必要最小限に管理 |

Derived: Duplicate Guard (Middleware, **REUSE**), Cache (**RECORD**), Knowledge Base (**REJECT**)

### TRE-2 — PyTorch 環境

L3: 将来再利用可能な調査資産の蓄積 → **Research Record**, **Research Reuse** が自然発生

---

## 9. F. Missed Idea Analysis（Phase C/D → Phase E）

| Phase C/D の扱い | Phase E 上位概念化後 |
|------------------|----------------------|
| Research Resume = 会話再開 | **Research Reuse** = 将来資産としての調査再利用 |
| VersionFact = Decision 材料 | **Research Record** の一部として横断保存 |
| 個別 Capability 評価 | **Goal L2/L3** から Derived Capability が連鎖 |

**Phase C/D で見えていなかった上位 Capability:** `Research Reuse Search`（Past Requirement 照合 → 不足分のみ Web）

---

## 10. G. False Discovery（重要な成功）

| 発見 | 判定 | 理由 |
|------|------|------|
| Knowledge Base | REJECT | ResearchStore で十分 |
| Vector DB / RAG | REJECT | Embedding 必要性未実測 |
| Version Matrix Core | REJECT | VersionFact で十分 |
| Research Transaction | REJECT | Conversation State + Record で PoC 可能 |
| Mechanical API Validator | REJECT | Mechanical Answer 禁止 |

---

## 11. H. Core Discovery（C0–C4）

| 分類 | 項目 |
|------|------|
| **C0 Helpers** | research_record, research_reuse, goal_abstraction |
| **C3 Implemented** | 0 |
| **REJECTED Cores** | Knowledge Base, Vector DB, Research Transaction |
| **RECORD** | Research Resume Context（C2）— Research Reuse のサブセットとして位置づけ |

---

## 12. I. Production

**Production 変更数: 0**

---

## 13. 成功条件 S1–S13

| ID | 結果 |
|----|------|
| S1 過去 Research 識別 | PASS |
| S2 関連性観測 | PASS |
| S3 既存のみで足りる判定 | PASS |
| S4 不足分のみ Web | PASS |
| S5 Source 追跡 | PASS |
| S6 過去/新規区別 | PASS |
| S7 無条件最新扱い禁止 | PASS |
| S8 検索削減測定 | PASS（9 searches saved） |
| S9 LLM 会話材料 | PASS |
| S10 Research→Spec 維持 | PASS |
| S11 上位概念で Capability 発見 | PASS |
| S12 REUSE/RECORD/DEFER/REJECT | PASS |
| S13 肥大化しない | PASS（L3 は justified 時のみ） |

---

## 14. 最終問いへの回答

| 問い | 回答 |
|------|------|
| **Q1** 再利用で繰り返し調査を減らせるか | **はい** — Full/Partial で 9 searches 削減 |
| **Q2** 不足情報だけ Web 取得か | **はい** — Partial Reuse + mode D |
| **Q3** 調査資産として扱えるか | **はい** — ResearchRecord エンベロープ |
| **Q4** 上位抽象化で Capability 発見か | **はい** — Research Reuse が L3 から自然発生 |
| **Q5** REUSE/REJECT できるか | **はい** — KB/Vector DB/Matrix Core を REJECT |
| **Q6** 標準化で埋もれを減らせるか | **推奨** — 下記ワークフロー |
| **Q7** 肥大化しないか | **はい** — C3=0, 固定鮮度ルールなし |

---

## 15. J. Final Decision — `EXPERIMENTAL_RETAIN`

Research Reuse + Hierarchical Discovery が実測で有効。**新 C3 Core は不要。**

### 標準ワークフロー組み込み（§24 推奨）

```text
Requirement
 ↓
Requirement Gate
 ↓
Immediate Goal (L0–L1)
 ↓
Higher-Level Goal (L2, 必要時 L3)
 ↓
Capability Discovery
 ↓
Existing Capability Check
 ↓
Research Reuse Check        ← NEW
 ↓
Web Research (不足分のみ)
 ↓
Candidate
 ↓
Decision Support
 ↓
Tool Specification
```

内部 Development Observation として保持（ユーザー毎回表示は不要）:

1. Requested Capability  
2. Immediate Goal  
3. Higher-Level Goal  
4. Derived Capabilities  
5. Existing Alternatives  
6. New Capability Candidates  
7. Rejected Ideas  
8. Future Ideas  

---

## 16. 関連ファイル

| 種別 | パス |
|------|------|
| Harness | `ai_tool/experimental/development_assistance/research_reuse_harness.py` |
| Runner | `ai_tool/run_tool_development_assistance_research_reuse.py` |
| Tests | `tests/ai_tool/project_audit/test_tool_development_assistance_research_reuse.py` |
| Run | `runs/ai_tool/20260830_105108_tool_development_assistance_research_reuse/` |
| Prior | [Phase D](./TOOL_DEVELOPMENT_ASSISTANCE_PRACTICAL_DECISION_SUPPORT.md) |

**実行:**

```bash
python ai_tool/run_tool_development_assistance_research_reuse.py
pytest tests/ai_tool/project_audit/test_tool_development_assistance_research_reuse.py -q
```
