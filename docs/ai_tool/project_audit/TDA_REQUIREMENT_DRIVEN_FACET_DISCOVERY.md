# TDA Requirement-driven Facet Discovery (Phase N)

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_173957_requirement_driven_facet_discovery`  
**Production 変更:** 0  
**新規 C3:** 0  
**判定:** `EXPERIMENTAL`（Cue 表の最小 adapter。Reasoning / Graph Core は REJECT）

今回の問いは次の二つ。

1. **Requirement を理解したあと、何を Research から取り出せば判断できるのかを、既存構造から自然に導出できるか。**
2. **「さっき調べた A について、Python 3.12 の場合だけもう少し調べて」を Partial Reuse として扱えるか。**

```bash
python ai_tool/run_tda_requirement_driven_facet_discovery.py
pytest tests/ai_tool/project_audit/test_requirement_driven_facet_discovery.py -q
```

---

## 責務境界（混同しない）

| 層 | 問うこと | 問わないこと |
|----|----------|--------------|
| **Goal Abstraction** | この要求は何を達成したいのか | 何を調べればよいか。実行可能か |
| **Facet Discovery** | その目的を判断するには何について知る必要があるのか | 実行可能 / 安全 / 互換か |
| **Relevant Facet Routing** | 保存済み Research からその Facet の封筒を取り出す | Facet の正誤 |
| **Research Reuse** | 過去 Record を full / partial / no のどれで使うか | 機械的な正解 |
| **Decision Support** | Evidence / Unknown / Conflict を提示する | 安全性・実行可否の判定 |

```text
Requirement
    ↓
Goal Abstraction
    ↓
Facet Discovery     ← 今回の評価対象（Experimental adapter）
    ↓
Relevant Facet Routing
    ↓
Research Reuse
    ↓
Decision Support
```

**Facet Discovery ≠ Decision。** 出力に `verdict` / `feasible` / `safe` / `compatible` / `executable` は無い（全ケースでテスト保証）。

---

## N-1 Goal Abstraction 監査（実測）

Handoff 要求に対する既存 L0–L3:

| レベル | 内容 |
|--------|------|
| L0 | 専門ロボット言語/APIのToolを調査 |
| L1 | 公式仕様に基づくTool設計材料を得る |
| L2 | LLM一般知識との混同を避けつつ仕様決定 |
| L3 | 専門領域の調査結果を将来の同領域Tool開発に再利用 |

| スロット | 保持できるか |
|----------|----------------|
| 対象 / 操作 / 条件 | **否** |
| Version / Environment | **否** |
| Capability / 制約 / 成功条件 | **否** |
| 不確実性 / 比較対象 / 追調査条件 | **否** |

実際に保持しているのは **定型の目標散文** と derived capability 名（API Observation, Research Reuse, Mechanical Validator REJECT）だけ。  
`RequirementFacets` も technologies / python / cuda / os / license / topic_tokens のみ。Handoff 要求では **空**。

**Goal Abstraction を Facet Discovery の代用にするのは REJECT。**

---

## N-14 Three-Way Comparison（実測）

同一 Requirement。Mode A = 既存 Goal + RequirementFacets。Mode B = 全 `facet_records`。Mode C = Discovery → Routing（`needed_facet_ids`）→ Reuse plan。

| Metric | Mode A | Mode B | Mode C |
|--------|--------|--------|--------|
| Relevant Recall | **0.38** | 1.00 | **1.00** |
| Irrelevant Suppression | 1.00（出さないことによる） | **0.27** | **1.00** |

Mode A の 0.38 は N4/N5/N10 で「Python 3.12」が既存 `extract_requirement_facets` に載るため。N3-A Handoff は **A=0 / C=1**。Cycle Unknown は **A=Gate 落ち / C=到達**。

---

## ケース実測

### N3 基本

| Case | Mode A | Mode C |
|------|--------|--------|
| **N3-A** Handoff | recall 0。Transport も Authority も出ない | **1.00** — transport, authority, mode, mode_source, program_state, safety_state, handoff（暗黙条件を cue 表で列挙） |
| **N3-B** URScript 実行 | 0.20（`urscript` 技術名のみ） | **1.00** — 加えて program_state / execution / version / ursim。Phase M の「実行できるか ≠ 実行可能 alias」を Discovery 側で補う |
| **N3-C** Docker 環境 | 0 | **1.00** — Docker + WSL2 / RAM / Storage / Ports を implicit need として列挙 |

粒度はいずれも `useful`（全部 Safety にも、カタログ全件にもならない）。

### N-4 Follow-up（重要ケース）

> さっき調べたAについて、今度はPython 3.12の場合だけもう少し調べて

| 確認 | 結果 |
|------|------|
| A を過去 Research から特定 | **RR-A** |
| Python を対象 Facet | **python_version** |
| 3.12 を Version 条件 | **requested_version=3.12** |
| 「もう少し」を Full Re-research にしない | **full_reresearch=False** |
| 既存 Evidence 再利用 | cuda / license / PyTorch |
| 3.12 固有だけ不足 | **missing: python 3.12 evidence** |

### N-5 Version-constrained

PyTorch を Python 3.12 だけで再評価。requested_version は 3.12。Record 上の 3.13 を 3.12 へコピーしない。

### N-6 Negative Constraint

Docker は `excluded`。URScript / URSim / Version / Execution / Program State は残る。Mode B は Docker を捨てられない。

### N-7 Comparative

5.15.2 と 5.25.2 を **comparison=True**。単一 Version 扱いにしない。`conflict` / `compatibility` / `feature` を概念として保持。「この機能」は名前が無いので feature は概念止まり（推測で埋めない）。

### N-8 Capability

「Safety」単独にはしない。到達概念:

`llm_limitation` → `external_evidence` → `validation_capability` → `observation` → `decision_boundary` → `human_review`

LLM に Safety 判定させる仕組みは作っていない。

### N-9 Ambiguous（Phase G 文面）

候補概念（target / capability / difficulty / external_knowledge_need / environment / existing_tool / version / evidence / feasibility）は Discovery できる。  
**候補を増やすこと自体は成功にしていない。** ロボット catalog 全件は出さない。粒度 `useful`。Tool を一つに決めない。

### N-10 Reuse Discovery

既存: PyTorch / CUDA 12.3 / License Y、Python 3.13。  
新要求: Python 3.12。  
Version-sensitive は Python。CUDA/License/PyTorch は reusable。

### N-11 Facet Dependency

```text
python_version → pytorch_compatibility → cuda_compatibility → environment_feasibility
```

を **metadata の list** として記録。Graph Database は不要（**REUSE**）。Graph Core は **REJECT**。

### N-12 Unknown / Gate

既存 Gate: `RESEARCH_NOT_REQUIRED`（Cycle / 外部トリガが niche marker に無い）。  
Discovery: `research_needed=True`、cycle_controller / safety_state / operational_mode / program_state / execution を need。  
Mode C は Gate で落とさず Routing まで届ける。判定（実行できる）はしない。

### N-13 Discovery vs Decision

全ケース `not_a_decision=True`。

### N-15 連続 Follow-up

| 段 | 結果 |
|----|------|
| 初回 PyTorch | research_needed。Follow-up plan ではない |
| Python 3.12 だけ | partial。searches=1。missing python 3.12。PyTorch/License 再利用 |
| CUDA 12.3 だけ | partial。searches=1。**python 3.12 は消さない** |
| 毎回全検索 | **否** |

### N-16 Conversational Reference

| 表現 | 結果 |
|------|------|
| さっきのA | **RR-A**（推測ではない。label/id） |
| そのPython版 | **Unresolved** + clarification |
| 3.12の方だけ | 先行比較が無ければ clarification |
| DockerじゃなくてVMの方 | VM Record が無ければ **Unresolved**（Docker から推測しない） |
| 前に調べたURSim | PyTorch-only store では Unresolved |

### N-17 Over-Abstraction

N3-B で Docker 全スタックを出さない。N8 で Safety だけにしない。N9 で catalog 全件にしない。粒度フラグは測定ケースで `useful`。

### N-18 Mapping Coverage（実測 bool）

明示条件 / 暗黙 need / Version / Environment / Capability / Comparison / Follow-up / Negative / Unknown / Conflict — **すべて True**（cue 表の範囲）。汎用推論ではない。

---

## N-19 New Core Gate

| 対象 | 判定 |
|------|------|
| 既存 Goal Abstraction + RequirementFacets だけで十分 | **REJECT**（Handoff / Cycle / 比較 / 否定制約が欠ける） |
| 最小 Facet Discovery Adapter | **EXPERIMENTAL** |
| Workflow デフォルト統合 | まだしない（RECORD 寄り。default は off） |
| Reasoning Core | **REJECT** |
| Graph / Matrix / Knowledge Graph / Vector DB / RAG | **REJECT** |
| 関係の metadata list | **REUSE** |

悪かったからといって Core を増やしていない。

---

## N-20 最終回答

> Requirement を理解したあと、何を Research から取り出せば判断できるのかを、既存構造から自然に導出できるか？

**既存 Goal Abstraction / RequirementFacets だけでは否。** L0–L3 は目標散文であり、必要 Facet のスロットを持たない。  
**Cue 表の Experimental adapter なら、評価範囲では導出できる。** それは Reasoning Core ではない。

> 「さっき調べた A について、Python 3.12 の場合だけもう少し調べて」を Partial Reuse にできるか？

**できる（実測）。** RR-A を特定し、3.12 だけを missing、既存 CUDA/License を reusable、「もう少し」を full re-research にしない。連続 Follow-up でも前回結果を消さない。

Standard Workflow のデフォルトにはまだしない。Discovery は「何を知る必要があるか」まで。真偽・安全性の判断は Decision Support の材料提示に留める。
