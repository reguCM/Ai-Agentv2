# Web Research → Tool Development Assistance — Phase B PoC Report

**Date:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_100721_tool_development_assistance/`  
**Model:** qwen3:8b (live proposal) + deterministic proxy (offline CI)  
**Production changes:** **0**  
**Prior Investigation:** [WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md)

---

## 目的

「Web 上の情報を答える検索」から「**新しい Tool を作る際の調査・設計判断を補助する Web Research**」へ、Production を変更せず Experimental 層で段階拡張できるかを実証する。

**Tool 自動実装はスコープ外。**

---

## Architecture

```text
User Requirement
      ↓
Requirement Gate (assess_research_requirement)
      ↓
Query Generator (1–3 queries)
      ↓
run_canonical_web_eval (CC-01 — existing)
      ↓
evidence_sources_from_loop
      ↓
build_technology_candidates (+ optional Custom Build)
      ↓
build_development_proposal
      ↓
handle_tda_follow_up (User Selection / RESEARCH_MORE)
```

**新規 Experimental モジュール:** `ai_tool/experimental/development_assistance/`

| ファイル | 責務 |
|----------|------|
| `requirement_gate.py` | Research 要否判定 |
| `query_generator.py` | 検索クエリ 1–3 件 |
| `technology_candidate.py` | Evidence → Technology Candidate + conflicts |
| `proposal.py` | Development Proposal 生成 |
| `followup.py` | TDA follow-up intents |
| `fixtures.py` | 評価ケース A–H |
| `harness.py` | PoC 実行・LLM-only vs Web 比較 |

**再利用（変更最小）:** `conversation_resolution`, `e2e_adapter`, CC-01, CC-02 方針

---

## 評価ケース A–H

| Case | 内容 | Web Pass |
|------|------|----------|
| TDA-A | 一般 Tool（JSON 読込）— Research 不要 | N/A (gate only) |
| TDA-B | 新 OSS（Polars） | PASS |
| TDA-C | 複数 PDF ライブラリ/API | PASS |
| TDA-D | 既存 vs Custom Build | PASS |
| TDA-E | Python 3.11 vs 3.12 バージョン差 | PASS |
| TDA-F | License 矛盾（MIT vs GPL） | PASS |
| TDA-G | URScript 専門言語 | PASS |
| TDA-H | PyTorch/CUDA 複雑環境 | PASS |

**Web path pass:** 7/7（Research 必要ケース）

---

## 成功条件 S1–S10

| ID | 結果 | 根拠 |
|----|------|------|
| S1 Research gate | **PASS** | TDA-A → RESEARCH_NOT_REQUIRED |
| S2 Useful extraction | **PASS** | 7/7 fixture から Candidate 抽出 |
| S3 Candidate organization | **PASS** | OSS/API/Library/Custom Build 整理 |
| S4 Environment | **PASS** | TDA-H python/cuda/gpu metadata |
| S5 Metadata retention | **PASS** | URL integrity 維持 |
| S6 Conflict preserved | **PASS** | TDA-E/F conflicts 保持 |
| S7 LLM uses research | **PASS** | LLM+Web が LLM-only より多次元で優位 |
| S8 User selection | **PASS** | TDA-D/G follow-up 選択 |
| S9 Follow-up research | **PARTIAL** | RESEARCH_MORE intent 実装済、targeted re-run は次 Phase |
| S10 Production intact | **PASS** | golden + pytest PASS |

---

## LLM-only vs LLM+Web

| 比較次元 | LLM+Web 優位ケース数 |
|----------|---------------------|
| candidate_discovery | B, C, D, E, F, G, H |
| source_attribution | B–H |
| conflict_awareness | E, F |
| environment_metadata | H |

**結論:** ニッチ OSS・複数候補・バージョン差・専門言語・環境要件では **LLM+Web が LLM-only より有用**（fixture 実証）。

---

## Core Discovery

| Capability | Class | 判断 |
|------------|-------|------|
| TDA-ORCHESTRATION | **C3** | Requirement→Gate→Query→Research→Proposal loop 実証 |
| CR-CANDIDATE-ENVELOPE | C3（既存） | Technology metadata 拡張で再利用 |
| CR-CONV-RESOLUTION | C2 | follow-up 拡張で再利用 |

**新規 C3:** 1 件（TDA-ORCHESTRATION のみ）

---

## Production

| 項目 | 値 |
|------|-----|
| agent.py 変更 | 0 |
| Registry 変更 | 0 |
| Prompt 変更 | 0 |
| Search/Fetch/Evidence 変更 | 0 |
| pytest | PASS |

---

## 意図的に作らなかったもの

- Tool 自動実装 / Registry 登録
- Research Transaction / Research Planner
- Mechanical Answer / Source Score
- Production Agent 接続
- UR 実機制御
- 新 Search/Fetch pipeline

---

## Phase 終了判断

```text
CONTINUE
```

Tool Development Assistance として **Experimental 層で有用性を確認**。

次 Phase 候補:
1. Targeted re-research loop（RESEARCH_MORE → 追加 canonical eval）
2. Live web cases（fixture 以外）
3. Spec draft bridge → Tool Creation Validator
4. Search 品質が live でボトルネックなら Search Investigate

**PROMOTE_PRODUCTION は使用しない。**

---

## 実行方法

```bash
python ai_tool/run_tool_development_assistance_poc.py
pytest tests/ai_tool/project_audit/test_tool_development_assistance_poc.py -q
```

---

## Related

- [WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md) — Phase A
- [WEB_RESEARCH_USER_FACING_RESOLUTION_E2E.md](./WEB_RESEARCH_USER_FACING_RESOLUTION_E2E.md) — Conversation Resolution E2E
