# Tool Development Assistance — Capability Discovery & Practical Observation (Phase C)

**Date:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_101730_tool_development_assistance_capability_discovery/`  
**Prior phases:** [Phase A Investigation](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md) / [Phase B PoC](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_POC.md)  
**Production changes:** **0**  
**New C3 implemented:** **0**（候補のみ記録）

---

## 0. Phase の目的

Phase B PoC を実際に通し、各 Stage で

> 「別の Tool にも使えそうな Capability が自然に必要になったか」

を観測する。**アイデアをすぐ実装しない。** REUSE / RECORD / DEFER / REJECT を意図的に記録する。

---

## 1. 実施 Case（TDC-1〜6）

| ID | 種別 | TDA fixture | Pass | 主な観測 Stage |
|----|------|-------------|------|----------------|
| TDC-1 | 一般 Tool（JSON 読込） | TDA-A | PASS | Research Gate → REUSE |
| TDC-2 | 未知 OSS（Polars） | TDA-B | PASS | Evidence, Candidate |
| TDC-3 | 複数 OSS（PDF） | TDA-C | PASS | Candidate, User Selection |
| TDC-4 | 特殊仕様（URScript） | TDA-G | PASS | Evidence（API 存在） |
| TDC-5 | 複雑環境（PyTorch/GPU） | TDA-H | PASS | Environment |
| TDC-6 | Version/API 変更 | TDA-E | PASS | Candidate（DEFINITION_DIFF） |

**Case pass:** 6/6

---

## 2. Lifecycle サマリ

| 判断 | 件数 | 意味 |
|------|------|------|
| **REUSE** | 24 | 既存機能で代替 — 新 Core 不要 |
| **RECORD** | 10 | 将来有用 — 今は記録のみ |
| **DEFER** | 10 | 価値はあるがコスト/リスク大 |
| **INVESTIGATE** | 0（run 内 heuristics） | Catalog 上 CAP-C は C2 |
| **REJECT** | 0 | — |
| **EXPERIMENTAL** | 0 | 本 Phase では未実装 |

**Total observations:** 44（6 Case × 各 Stage heuristic）

---

## 3. 候補 Catalog A–J 評価

| ID | Capability | 発生 | Class | Decision | 既存代替 |
|----|------------|------|-------|----------|----------|
| CAP-A | Environment Profiler | TDC-1〜6 | **C0** | **REUSE** | get_gpu_status, cpu_status, tech_candidate env |
| CAP-B | Version Compatibility Matrix | TDC-1〜6 | C1 | **RECORD** | classify_candidate_relation（部分） |
| CAP-C | API Existence Observation | TDC-4 中心 | **C2** | **INVESTIGATE** | CC-02 partial |
| CAP-D | Documentation Extractor | TDC-3 中心 | C1 | **DEFER** | read_url extraction |
| CAP-E | License Observation | 複数 Case | **C0** | **REUSE** | technology_candidate license regex |
| CAP-F | Dependency Graph | TDC-5 中心 | **C0** | **REUSE** | flat environment metadata で十分 |
| CAP-G | Doc Version Tracking | TDC-6 中心 | C1 | **RECORD** | definition_label + years |
| CAP-H | Tool Spec Validator | 全 Case | C1 | **DEFER** | tool_creation validator（橋未接続） |
| CAP-I | Research Resume Context | TDC-3〜6 | **C2** | **RECORD** | ConversationState 部分 |
| CAP-J | Sandbox Runner | TDC-2,3,5 | **C0** | **DEFER** | なし（意図的に作らない） |

---

## 4. 代表的 Capability Observation 例

### OBS-TDC-4-CAP-C — API Existence（URScript）

```text
Stage: Evidence
Problem: LLM提案コマンドが公式Docに存在するか確認したい
Idea: API / Function Existence Observation (FOUND/NOT_FOUND/UNKNOWN)
Trigger: movej, movel in URScript fixture evidence
Existing: CC-02 mechanical_verification (partial)
Decision: RECORD → Catalog C2 INVESTIGATE
Reason: 専門言語で価値高。存在の断定は禁止。
```

### OBS-TDC-5-CAP-A — Environment Profiler

```text
Stage: Environment
Problem: Web記載のCUDA/Pythonとローカル実環境の差
Idea: Environment Profiler
Existing: get_gpu_status + cpu_status + tech_candidate regex
Decision: REUSE
Reason: 新 Core 不要。system Tool 組合せで代替。
```

### OBS-TDC-2-CAP-J — Sandbox Runner

```text
Stage: Proposal
Problem: pip install 可能な OSS を実際に試したい
Idea: Experiment/Sandbox Runner
Decision: DEFER
Reason: Security / 環境汚染 / 再現性リスク。本 Phase 禁止。
```

### OBS-TDC-6-CAP-G — Version Tracking

```text
Stage: Candidate
Problem: Python 3.11 vs 3.12 資料の混在
Idea: Documentation Version Tracking
Existing: DEFINITION_DIFF + difference_note
Decision: RECORD
Reason: 「Web=正」とは判定しない。差異保持は既存 CR で部分達成。
```

---

## 5. Case → Capability 発生マップ

| Case | 自然発生した主 Capability | Stage | Final Decision |
|------|---------------------------|-------|----------------|
| TDC-1 | Research Gate, Query Gen | Gate, Query | REUSE |
| TDC-2 | Sandbox（DEFER）, License REUSE | Proposal, Candidate | DEFER / REUSE |
| TDC-3 | Multi-candidate compare, Research Resume | Candidate, Selection | RECORD |
| TDC-4 | API Existence, URScript doc | Evidence | RECORD / INVESTIGATE |
| TDC-5 | Environment Profiler REUSE, Dependency REUSE | Environment | REUSE |
| TDC-6 | Version Matrix RECORD, Version Tracking | Candidate | RECORD |

---

## 6. 汎用性評価

| Capability | TDA専用 | Web Research全体 | Tool Registry | コード生成 | URScript以外 |
|------------|---------|------------------|---------------|------------|--------------|
| CAP-A Environment | No | Yes | Yes | Yes | Yes |
| CAP-B Version Matrix | No | Yes | Yes | Partial | Yes |
| CAP-C API Existence | No | Yes | Partial | Yes | **High for specialized** |
| CAP-I Research Resume | **Partial** | Yes | No | No | Yes |
| CAP-J Sandbox | No | Partial | No | Yes | Yes |

**TDA 専用に閉じる候補は少ない。** 大半は Web Research / Tool Creation 横断で再利用可能。

---

## 7. 捨てた理由（意図的 REUSE / DEFER）

| Capability | 判断 | 捨て/保留理由 |
|------------|------|---------------|
| Environment Profiler | REUSE | GPU/CPU Tool + metadata で足りる |
| License Observation | REUSE | Phase B 実装済み |
| Dependency Graph | REUSE | flat metadata で PoC 十分 — グラフは過剰 |
| Sandbox Runner | DEFER | セキュリティ・環境破壊リスク |
| Documentation Extractor | DEFER | HTML fixture 可。PDF 本格は Extraction 拡張で足りる可能性 |
| Tool Spec Validator | DEFER | Validator 存在。Proposal→Spec **橋**のみ不足 |
| Version Matrix | RECORD | Relation 分類で部分代替。行列は将来 |

---

## 8. C3 候補（最大1件 — 未実装）

| 項目 | 値 |
|------|-----|
| 名称 | **TDA-RESEARCH-RESUME-CONTEXT** |
| 源 | CAP-I Research Resume / Research Context |
| Class | C2 |
| implement_this_phase | **false** |

**選定理由:**
- TDC-3〜6 で「追加調査」「選択後の文脈」ニーズが自然発生
- Research Transaction ではなく ConversationState 拡張で足りる見込み
- コスト MEDIUM / リスク LOW / 汎用性 HIGH

**実装しなかった理由:**
- Phase C は観測 Phase。RESEARCH_MORE intent は Phase B 実装済み
- targeted re-run state 追加は次 Phase の Experimental 候補

---

## 9. 評価次元

| 次元 | 結果 |
|------|------|
| Capability discovery | **自然発生を確認** — 机上 brainstorm ではなく Stage 観測から 44 件 |
| Reuse | **高** — 24/44 が REUSE（既存で代替） |
| Generality | CAP-A,C,I は TDA 外でも有用 |
| Cost | 新規実装 0 — TDA 複雑化なし |
| Complexity | harness + observation のみ追加（小） |
| User Value | Phase B フロー 6/6 PASS を維持 |

---

## 10. Production

| 項目 | 値 |
|------|-----|
| Production 変更 | 0 |
| 新規 C3 実装 | 0 |
| pytest | PASS |
| Golden | PASS |

---

## 11. Phase 終了判断

```text
CONTINUE
```

**理由:**
- Tool 開発補助を実際に通すと Capability Idea が **Stage ごとに自然発生**（44 観測）
- 過半数は **REUSE** — 新 Core 乱立なし
- 最有力次候補 **TDA-RESEARCH-RESUME-CONTEXT**（C2, 未実装）
- CAP-C API Existence は専門言語 Case で **INVESTIGATE** 価値

**採用しなかった判断:**
- `STOP_NO_NEW_CORE` — 有用な RECORD/INVESTIGATE 候補が存在
- `EXPERIMENTAL_RETAIN` — 本 Phase では C3 未実装
- `PROMOTE_PRODUCTION` — 使用禁止

---

## 12. 次 Phase 候補

1. **TDA-RESEARCH-RESUME-CONTEXT** — targeted re-research state（唯一の C3 Experimental 候補）
2. **CAP-C API Existence** — CC-02 拡張として FOUND/NOT_FOUND/UNKNOWN 観察
3. **Proposal→Spec bridge** — tool_creation Validator 接続（DEFER 解除条件: HR）
4. Live web cases — fixture 以外での Search 品質観測

---

## 13. 実装物（観測のみ）

| ファイル | 責務 |
|----------|------|
| `capability_observation.py` | Observation データモデル + Catalog A–J |
| `capability_discovery.py` | 6 Case 実行 + Stage 観測 + Catalog 評価 |
| `run_tool_development_assistance_capability_discovery.py` | Runner |

**Phase B モジュールは変更最小**（新規 Core 追加なし）。

---

## Related

- [WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_POC.md](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_POC.md)
- [WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md](./WEB_RESEARCH_TOOL_DEVELOPMENT_ASSISTANCE_INVESTIGATION.md)
