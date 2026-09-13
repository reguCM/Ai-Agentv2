# Tool Development Assistance — Practical Decision Support (Phase D)

**実行日:** 2026-08-30  
**Run ID:** `20260830_103640_tool_development_assistance_decision_support`  
**判定:** `STOP_NO_NEW_CORE` — 8/8 ケース PASS、S1–S12 全項目 PASS  
**Production 変更:** なし

---

## 1. Phase の目的（再掲）

Web Research を「Tool候補を検索する機能」から、「ユーザーが Tool の仕様・環境・採用候補を決定するための材料を整理する機能」へ発展させる価値が本当にあるかを**実測**する。

本 Phase では機能追加を成功条件とせず、既存 TDA + Candidate metadata でどこまで Decision Support が成立するかを観測した。

---

## 2. Current Development

| 項目 | 内容 |
|------|------|
| **Observed Problem** | Phase C で Version Matrix / Decision Factors / Research Resume 等が候補として観測されたが、専用 Core を作る前に既存構造で足りるか未検証だった |
| **Root Cause** | 判断材料（Version / Environment / License / Source / Unknown / Conflict）は Phase B の `TechnologyCandidate` に既に存在するが、Decision Factor として明示的に整理・提示する薄い層がなかった |
| **Implementation** | Experimental 薄層のみ追加（Production 非変更）:<br>• `version_facts.py` — 軽量 VersionFact（provenance 付き）<br>• `decision_factors.py` — Candidate metadata から Decision Factor 生成<br>• `decision_presentation.py` — ユーザー向け判断材料表示<br>• `spec_draft.py` — Tool Specification Draft<br>• `api_observation.py` — API 存在観測（FOUND/NOT_FOUND/UNKNOWN）<br>• `research_state.py` — Research Resume 用 Conversation State 拡張<br>• `decision_support_harness.py` — Case A–H + LLM-only vs LLM+Web 比較<br>• `followup.py` — `Aを使いたい` / `Bにしてください` の候補選択解析改善 |
| **Regression** | PoC / Capability Discovery / Phase D テスト 18 passed；Production golden PASS |
| **Production Impact** | なし（agent.py / registry / SYSTEM_PROMPT / production web chain 未変更） |

**実行:**

```bash
python ai_tool/run_tool_development_assistance_decision_support.py
pytest tests/ai_tool/project_audit/test_tool_development_assistance_decision_support.py -q
```

---

## 3. Decision Support — ケース別記録

### Case A (TDS-A) — 一般 Tool

| 項目 | 内容 |
|------|------|
| Requirement | JSON ファイル読込 Tool |
| Candidates | なし（標準ライブラリで十分） |
| Important Factors | — |
| Version / Environment | 不要 |
| Unknown | — |
| Conflict | なし |
| Selected | なし |
| Selection Reason | RESEARCH_NOT_REQUIRED — LLM 一般知識で十分 |
| Source | なし |

**観測:** Gate が正しく `RESEARCH_NOT_REQUIRED`。Web 調査は過剰。

---

### Case B (TDS-B) — ニッチ OSS (Polars)

| 項目 | 内容 |
|------|------|
| Requirement | Polars で CSV 処理 Tool |
| Candidates | Polars Library |
| Important Factors | version, python_compatibility, license, official_source |
| Version / Environment | Python 3.10+（Evidence より） |
| Unknown | cuda 等 |
| Conflict | なし |
| Selected | — |
| Selection Reason | — |
| Source | Official Documentation fixture |

**Research Resume:** `Bについてもう少し調べて` → `ResearchState` が prior queries / known_unknowns を保持。**Conversation State 拡張で十分。**

**LLM-only vs LLM+Web:** Web が version / environment / license 材料を追加。

---

### Case C (TDS-C) — 複数候補 (PDF)

| 項目 | 内容 |
|------|------|
| Requirement | PDF 解析 Tool — 既存ライブラリ調査 |
| Candidates | PyPDF2, pdfplumber, PDF API |
| Important Factors | type 差（Library vs API）, license, environment |
| Version / Environment | 各候補から抽出 |
| Unknown | 一部 cuda 等 |
| Conflict | なし（type 差は保持） |
| Selected | TCB (pdfplumber) — ユーザー選択シミュレーション |
| Selection Reason | user_candidate_preference |
| Source | 各候補の fixture URL |

**観測:** A/B/C 比較提示が自然。Mechanical ranking なし。

---

### Case D (TDS-D) — Version 差

| 項目 | 内容 |
|------|------|
| Requirement | DataFrameLib — Python バージョン要件確認 |
| Candidates | v1.x doc, v2.x doc |
| Important Factors | python_compatibility, version, conflict |
| Version / Environment | v1: Python 3.9–3.11 / v2: Python 3.10–3.13 |
| Unknown | — |
| Conflict | **保持** — DEFINITION_DIFF |
| Selected | — |
| Selection Reason | 環境適合性の説明が決め手になりうる |
| Source | 旧版・新版 fixture |

**Version Matrix 評価:** 専用 Matrix 不要。`VersionFact` + provenance で十分。

---

### Case E (TDS-E) — 環境依存

| 項目 | 内容 |
|------|------|
| Requirement | PyTorch GPU 推論 Tool |
| User Constraints | Windows, Python 3.12, RTX 3060, CUDA 12 |
| Candidates | PyTorch, CUDA requirements |
| Important Factors | python_compatibility, cuda_compatibility, gpu |
| Version / Environment | python / cuda / gpu を Evidence から |
| Unknown | 特定 CUDA 12.3 等 |
| Conflict | なし |
| Selected | — |
| Selection Reason | 環境適合情報の多さ |

**観測:** 「動く」と断定せず、公式記載との partial match を説明。

---

### Case F (TDS-F) — License 差

| 項目 | 内容 |
|------|------|
| Requirement | ToolX ライブラリ Tool |
| User Constraints | license_preference: MIT |
| Candidates | ToolX-A (MIT), ToolX-B (GPL) |
| Important Factors | license, official_source |
| Version / Environment | — |
| Unknown | environment 等 |
| Conflict | License 差を保持 |
| Selected | TCB — `Bにしてください` |
| Selection Reason | user_candidate_preference（ユーザーが GPL を明示選択） |

**観測:** License を Decision Factor として提示可能。過剰解釈（GPL=禁止等）は行わない。

---

### Case G (TDS-G) — 情報源 Conflict

| 項目 | 内容 |
|------|------|
| Requirement | ToolX（TDA-F と同一 fixture、Conflict 観測に焦点） |
| Candidates | 矛盾する License / 環境記載 |
| Important Factors | conflict, unknown_count |
| Conflict | **Mechanical Resolver なしで保持** |
| Selected | — |
| Selection Reason | — |
| Source | 2 ソース間の差異を LLM が説明可能 |

---

### Case H (TDS-H) — 専門 Tool (URScript)

| 項目 | 内容 |
|------|------|
| Requirement | Universal Robots ロボットコード Tool |
| Candidates | URScript Manual, UR SDK |
| API Observation | movej/movel: FOUND, pandas.read_csv: NOT_FOUND |
| Important Factors | official_source, api availability |
| Version / Environment | SDK version |
| Unknown | 実行環境 |
| Conflict | なし |
| Selected | TCA — `Aを使いたい` |
| Selection Reason | official_source_availability, user_candidate_preference |
| Source | 公式 Manual fixture |

**観測:** LLM が Python 風 API を捏造しやすい領域で、公式資料に存在する API のみ観測材料として提示可能。

---

## 4. Capability Discovery

| Capability | Observed Stage | Why useful | Existing alternative | Benefit | Cost | Risk | Decision |
|------------|----------------|------------|----------------------|---------|------|------|----------|
| Version Matrix | Decision | Version/Env 比較 | VersionFact + TechnologyCandidate | 判断材料 | 低 | 過剰互換判定 | **REUSE** |
| Decision Factors | Decision | 選択理由構造化 | compute_decision_factors() | ユーザー説明 | 低 | 機械ランキング化 | **REUSE** |
| Research Resume | Follow-up | 追加調査文脈 | ResearchState dataclass | 会話継続 | 低 | Transaction 複雑化 | **RECORD** (C2) |
| API Existence Observation | Specialized | LLM 捏造防止 | api_observation.py | 公式 API 確認材料 | 低 | Mechanical Answer 化 | **REUSE** |
| Tool Spec Draft | Specification | 実装前仕様書 | build_spec_draft() | 仕様書初稿 | 低 | 自動実装混同 | **REUSE** |
| Sandbox Runner | Execution | 実環境検証 | なし | 動作確認 | 高 | セキュリティ | **DEFER** |
| Documentation Version Tracking | Evidence | 根拠 doc version | source_category + VersionFact | 出典追跡 | 低 | — | **REUSE** (既存 metadata) |
| Environment Profile | Decision | ユーザー env vs 候補 | UserConstraints + decision_factors | 適合説明 | 低 | 断定 | **REUSE** |
| Source Reliability Metadata | Evidence | 公式性 | source_category (Official/Other) | 出典種別 | 低 | 点数化 | **REUSE** (Mechanical Score 禁止) |

**C3 実装数:** 0 / 上限 1  
**Phase C 候補 `TDA-RESEARCH-RESUME-CONTEXT`:** RECORD — `ResearchState` で PoC 可能、専用 Core は不要

---

## 5. Version Matrix 評価

| 問い | 回答 |
|------|------|
| 単なる保存で十分か | **はい** — VersionFact 程度の軽量 envelope で十分 |
| Decision Factor として有用か | **はい** — python / cuda / license / version が選択説明に使える |
| 専用 Matrix が必要か | **いいえ** — 互換性エンジン・断定ロジックは禁止方針と矛盾 |
| 既存 Candidate metadata で足りるか | **はい** — `TechnologyCandidate.version/environment/license` + 薄い変換層で成立 |

Provenance ラベル: `officially_documented` / `observed_from_source` / `inferred` / `unknown` / `actually_tested`

---

## 6. Research Resume 評価

| 問い | 回答 |
|------|------|
| Conversation State だけで十分か | **ほぼ十分** — queries / candidates / unknowns / conflicts を保持すれば resume context 生成可能 |
| 専用 State が必要か | **現時点では不要** — Research Transaction Core は作らない |
| ギャップ | 追加検索の自動再実行（targeted re-run）は Phase B 同様 PARTIAL — 意図検出は可能、完全な stateful re-query は RECORD |

---

## 7. Tool Specification 評価

| 問い | 回答 |
|------|------|
| Research → Proposal → Tool Spec が自然に繋がるか | **はい** — 候補選択後 `build_spec_draft()` で初稿生成可能 |
| 既存 Proposal で十分か | **不足** — Proposal は会話向け、Spec Draft は実装者向けフィールド（dependencies, constraints, api_notes）が必要 |
| 自動実装 | **行わない** — 仕様書作成支援のみ |

---

## 8. LLM-only vs LLM+Web 比較

| 観点 | LLM-only | LLM+Web | 観測 |
|------|----------|---------|------|
| 候補発見 | 一般論 | Evidence ベース候補 | Web 優位（B/C/H） |
| 情報量 | 低 | 高 | Web 優位 |
| Version | UNKNOWN 多 | Evidence から抽出 | Web 優位 |
| Environment | 推測 | 記載ベース | Web 優位 |
| License | 推測 | 抽出 or UNKNOWN | Web 優位 |
| API | 捏造リスク | 観測ベース | Web 優位（H） |
| Unknown 明示 | 少ない | unknowns フィールド | Web 優位 |
| Conflict 保持 | なし | 保持 | Web 優位（D/F/G） |
| Decision Support | 一般論 | 判断材料が構造化 | **Web 優位（Research 必要ケース）** |
| Case A | **十分** | 過剰 | LLM-only 正しい |

**評価基準:** 機械的正解ではなく「ユーザー判断材料が増えたか」— Research 必要ケースで LLM+Web が一貫して材料を追加。

---

## 9. 成功条件 (S1–S12)

| ID | 内容 | 結果 |
|----|------|------|
| S1 | 複数ケース処理 | 8/8 PASS |
| S2 | Version/Env 保持 | 8/8 PASS |
| S3 | Decision Factor 利用 | 8/8 PASS |
| S4 | Unknown/Conflict 非解決 | 8/8 PASS |
| S5 | Source 確認可能 | 8/8 PASS |
| S6 | LLM 会話材料 | 8/8 PASS |
| S7 | ユーザー選択 | 8/8 PASS |
| S8 | 選択状態維持 | 8/8 PASS |
| S9 | Research Resume | 8/8 PASS |
| S10 | Tool Spec Draft | 8/8 PASS |
| S11 | LLM+Web 優位（必要時） | 8/8 PASS |
| S12 | REUSE/DEFER | 8/8 PASS |

---

## 10. 最終問いへの回答

### Q1: Web Research は Tool を探すだけか、Decision Support として成立するか？

**成立する。** Version / Environment / License / Source / Unknown / Conflict を Candidate metadata として保持し、Decision Factor としてユーザー会話に組み込めることを 8 ケースで実測した。ただし Research 不要ケース（A）では Web は過剰であり、Gate による分岐が重要。

### Q2: 新しい Core が必要か、既存拡張で十分か？

**既存拡張で十分。** 専用 Version Matrix Core / Decision Matrix Core / Research Transaction Core は不要。Phase D で追加したのは Candidate/Evidence/Conversation Resolution の上に載る**薄い Experimental ヘルパー**のみ。

---

## 11. STOP 判定

以下が確認されたため **STOP_NO_NEW_CORE**:

- 現在の Candidate metadata で Decision Support 成立
- Version Matrix 専用構造不要
- Decision Factor の独立 Core 不要（関数レベルで十分）
- Research Resume は ResearchState レベルで PoC 可能
- Tool Spec Draft は build_spec_draft() で接続可能
- Sandbox Runner は今回も DEFER（実測必要性なし）
- Production 変更の必要性なし

**STOP は失敗ではない** — 観測により新 Core 実装を正当に見送った。

---

## 12. 関連ファイル

| 種別 | パス |
|------|------|
| Harness | `ai_tool/experimental/development_assistance/decision_support_harness.py` |
| Runner | `ai_tool/run_tool_development_assistance_decision_support.py` |
| Tests | `tests/ai_tool/project_audit/test_tool_development_assistance_decision_support.py` |
| Run artifacts | `runs/ai_tool/20260830_103640_tool_development_assistance_decision_support/` |
| Prior phases | [Phase B PoC](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_POC.md), [Phase C](./TOOL_DEVELOPMENT_ASSISTANCE_CAPABILITY_DISCOVERY.md) |
