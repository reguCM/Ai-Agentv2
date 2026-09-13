# TDA Standard Workflow Adoption — Phase F

**実行日:** 2026-08-30  
**判定:** `ADOPT` — 6/6 ケース PASS  
**Production 変更:** 0 | **新規 C3:** 0

---

## 1. 目的

Phase E で実測された Research Reuse / Hierarchical Discovery を、今後の TDA **Operating Model** として採用可能か検証・文書化する。

---

## 2. Workflow — 旧 vs 新

### 旧 Workflow（Phase B — Legacy）

```text
User Requirement
      ↓
Requirement Gate
      ↓
Web Research（常にフル）
      ↓
Candidate / Proposal
```

**問題:** Goal 抽象化なし、Past Research 未確認、Capability 見落とし、重複検索。

### 新 Standard Workflow（Phase F 採用）

```text
User Requirement
      ↓
Requirement Gate                    ← 不要ならここで終了
      ↓
L0 Immediate Requirement
L1 Immediate Goal
L2 Higher-Level Goal
L3 System Goal（条件付きのみ）
      ↓
Capability Discovery + Existing Check
      ↓
Research Reuse Check                ← Full / Partial / No
      ↓
不足部分のみ Web Research
      ↓
Evidence / Candidate
      ↓
Decision Support
      ↓
Tool Specification Draft
      ↓
（Implementation Investigation → 別段階）
```

**Early Exit 例:**

| ケース | 停止点 | Web Search |
|--------|--------|------------|
| TWF-1 JSON | Requirement Gate | 0 |
| TWF-6 Polars 再要求 | Research Reuse (full) | 0 |
| TWF-4 PyTorch 3.13 | Partial Reuse | 1（不足 facet のみ） |

---

## 3. Reuse 結果（6ケース）

| Mode | 件数 | ケース |
|------|------|--------|
| Full Reuse | 1 | TWF-6 Polars 再要求 |
| Partial Reuse | 1 | TWF-4 PyTorch Python 版差 |
| No Reuse | 4 | TWF-1,2,3,5 |

---

## 4. Search Reduction

| 指標 | 値 |
|------|-----|
| Before（Legacy 合計） | 15 searches |
| After（Standard 合計） | 12 searches |
| **Saved** | **3** |

Reuse ケース（TWF-4, TWF-6）では Web Search 0–1 に削減。初回調査（TWF-2 等）では Legacy と同等（過剰コストなし）。

---

## 5. Capability Discovery

| ケース | L2 Higher Goal | 新規 Derived |
|--------|----------------|--------------|
| TWF-1 JSON | 過剰 Web 回避 | Requirement Gate (REUSE) |
| TWF-2 Polars | 調査資産の再利用 | Research Reuse Search (REUSE) |
| TWF-3 DataFrameLib | 同上 | VersionFact (REUSE) |
| TWF-4 PyTorch | 環境・依存決定 | Environment Profiler (REUSE) |
| TWF-5 URScript | 公式仕様ベース | API Observation (REUSE) |
| TWF-6 Polars reuse | 調査資産蓄積 | Research Record (REUSE) |

---

## 6. False Discovery（作らなかったもの — 成果）

| Capability | Decision | 理由 |
|------------|----------|------|
| Knowledge Base | REJECT | ResearchStore 十分 |
| Vector DB / RAG | REJECT | Token matching 十分 |
| Version Matrix Core | REJECT | VersionFact 十分 |
| Research Transaction | DEFER | ResearchState + Record で PoC |
| Sandbox Runner | DEFER | セキュリティリスク |

---

## 7. Idea Preservation

`idea_preservation.py` — REJECT/DEFER/RECORD アイデアを以下形式で保持:

```text
Idea / Why appeared / Higher-Level Goal / Why not implemented
Existing Alternative / Potential Future Trigger / Re-evaluable
```

**再評価例:** 「sandbox runner」要求 → 過去 DEFER された Sandbox Runner アイデアを再提示（自動実装はしない）。

---

## 8. Complexity（手順増加）

| 指標 | Before | After | 備考 |
|------|--------|-------|------|
| 平均ステージ数 | 2.0 | 7.8 | 多くは skipped 記録 |
| 実効 Web Search | — | Early exit / Reuse で削減 | 遅延ではなく省略 |

L3 は justified 時のみ（TWF-2,4 等）。無意味な抽象化なし（Q2 PASS）。

---

## 9. Standard Development Review（§19）

今後の新 Tool / Core 前チェックリスト:

| Step | 内容 |
|------|------|
| A | Requirement — 何を求められているか |
| B | Goal — L1 達成目標 |
| C | Higher Goal — L2 なぜ必要か |
| D | Existing — 既存で足りないか |
| E | Reuse — Past Research 使えないか |
| F | Research — 不足分のみ Web |
| G | Capability — 新能力は本当に必要か |
| H | Decision — REUSE/RECORD/DEFER/REJECT |
| I | Implementation — 必要なら実装 |

---

## 10. Production / Core

| 項目 | 値 |
|------|-----|
| Production 変更 | **0** |
| 新規 C3 Core | **0** |
| 追加モジュール | `standard_workflow.py`, `idea_preservation.py`, `workflow_adoption_harness.py`（Orchestration のみ） |

---

## 11. Phase F 確認問い（§22）

| 問い | 結果 |
|------|------|
| Q1 上位概念化で見落とし防止 | **PASS** |
| Q2 肥大化しない | **PASS**（L3 条件付き） |
| Q3 Past Research Reuse 標準化 | **PASS** |
| Q4 Partial Reuse で Search 削減 | **PASS**（3 saved） |
| Q5 Existing Check で不要実装防止 | **PASS** |
| Q6 捨てたアイデアの将来再利用 | **PASS** |

---

## 12. Final Decision — `ADOPT`

Phase E 成果を **TDA Standard Operating Model** として採用する。

### 採用限界（Limits）

* ResearchStore は in-memory — 永続化は別 Phase
* Semantic matching / Embedding は未導入
* Implementation / Verification は本 Workflow の外（仕様ドラフトまで）
* Production 接続は実測問題 + Human Review 後

---

## 13. 次 Phase（§26 — Phase G 候補）

実案件型テスト:

> 「LLMの学習データだけでは難しそうな Tool を 1 つ考え、実際に作れるところまで調査してほしい。」

この曖昧要求に対し、Standard Workflow 全体が自然に動作するかを評価する。

---

## 14. 関連ファイル

| 種別 | パス |
|------|------|
| Orchestrator | `ai_tool/experimental/development_assistance/standard_workflow.py` |
| Idea Catalog | `ai_tool/experimental/development_assistance/idea_preservation.py` |
| Harness | `ai_tool/experimental/development_assistance/workflow_adoption_harness.py` |
| Runner | `ai_tool/run_tool_development_assistance_workflow_adoption.py` |
| Tests | `tests/ai_tool/project_audit/test_tool_development_assistance_workflow_adoption.py` |
| Prior | [Phase E](./TOOL_DEVELOPMENT_ASSISTANCE_RESEARCH_REUSE.md) |

**実行:**

```bash
python ai_tool/run_tool_development_assistance_workflow_adoption.py
pytest tests/ai_tool/project_audit/test_tool_development_assistance_workflow_adoption.py -q
```
