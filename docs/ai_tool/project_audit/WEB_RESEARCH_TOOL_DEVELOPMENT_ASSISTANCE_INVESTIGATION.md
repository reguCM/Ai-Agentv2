# Web Research → Tool Development Assistance — Architecture Investigation

**Date:** 2026-08-29  
**Phase:** A — Architecture Investigation（§27 指示）  
**HEAD:** `f881ae8`（調査時点）  
**Production changes:** **NONE**（本 Phase ではコード未作成）

---

## 0. 調査の目的

指示書 §27 に従い、**新規 Production コードを書く前に**、既存 Web Research / Conversation Resolution / Tool Creation パイプラインが、

> 「ユーザーが Tool を作りたいとき、Web Research で技術・仕様・環境・既存実装を調査し、LLM と一緒に Tool 開発案を考える開発補助 Agent」

へ段階拡張できるかを調査する。

**本報告は Investigation のみ。** PoC 実装・Production 接続は次 Phase。

---

## 1. 現在の Production Web Research Chain

### 1.1 確立済みチェーン（C4）

```text
Search (search_web)
  → Fetch (read_url_text)
  → Extraction (html_normalize / main_text)
  → Evidence (enrich_web_tool_result)
  → web_status (WebSessionTracker)
  → Boundary (apply_web_answer_boundary)
  → LLM (agent.py tool loop)
  → User Conversation
```

| コンポーネント | パス | 責務 |
|----------------|------|------|
| Agent 本体 | `agent.py` | gate → enrich → tracker → boundary |
| Search | `tools/system/network/search_web.py` | URL 候補発見 |
| Fetch | `ai_tool/experimental/read_url/reader.py` | HTTP GET + 本文 |
| Extraction | `ai_tool/experimental/read_url/html_normalize.py` | `main_text`, `quality.fact_ready` |
| Evidence enrich | `tools/system/network/web_evidence.py` | `web_status`, `grounding` 付与 |
| web_status | `tools/system/network/web_status.py` | 層別 SUCCESS / NO_EVIDENCE 等 |
| Boundary | `tools/system/network/web_answer_boundary.py` | 未根拠 Web 体裁の抑制 |

**設計思想（SCR-02 / Model B）:** Web は LLM の**拡張**であり置換ではない。Web 情報を機械的「正解」としない。

### 1.2 評価用ミラー（C3 — CC-01）

| コンポーネント | パス |
|----------------|------|
| production_mirror | `ai_tool/agent_integration/production_agent_web_loop.py` |
| CC-01 bridge | `ai_tool/agent_integration/eval_production_parity_bridge.py` |

`run_canonical_web_eval()` が Production 同等経路（gate, enrich, tracker, boundary）で E2E 評価可能。**TDA PoC もこの経路を再利用すべき。**

### 1.3 既に REJECT / 作らないもの

| 項目 | 根拠 |
|------|------|
| Research Transaction Core | `WEB_RESEARCH_TRANSACTION_INVESTIGATION.md` — STOP |
| Mechanical Answer | CC-02 + SCR-02 — 観察のみ |
| Generic Retry/Fallback | 各 Phase で未採用 |
| Production chain 全面改修 | 全 Phase 共通禁止 |

---

## 2. Conversation Resolution 既存実装

### 2.1 モジュール構成（Experimental — C2/C3）

| モジュール | パス | 責務 |
|-----------|------|------|
| models | `ai_tool/experimental/conversation_resolution/models.py` | Source, Evidence, Candidate, ConversationState |
| candidate_builder | `candidate_builder.py` | EvidenceSource → Candidate、関係分類 |
| resolver | `resolver.py` | 初回ターン、follow-up、ユーザー選択 |
| presenter | `presenter.py` | SINGLE/MERGED/MULTI/UNRESOLVED 表示 |
| e2e_adapter | `e2e_adapter.py` | canonical eval → Evidence → Resolution |

### 2.2 実証済み能力（E2E 10/10 PASS）

`WEB_RESEARCH_USER_FACING_RESOLUTION_E2E.md` より:

- 単一 / 定義差 / 真競合 / ユーザー選択 / 出典提示
- Production mirror 経由 Evidence 抽出
- URL integrity（捏造なし）
- Web / Evidence / Candidate failure 分離

### 2.3 現 Candidate 構造と TDA 要求のギャップ

**現状 `Candidate`:**

```text
candidate_id, label, claim, evidence_id, source_id, url, source_title,
definition_label, numeric_values, years, verification, metadata
```

**TDA 指示の概念 Candidate:**

```text
name, type, description, version, environment, capabilities,
limitations, license, unknowns[], conflicts[]
```

| TDA フィールド | 現状 | 再利用方針 |
|----------------|------|------------|
| name / description | `claim`, `source_title` | **metadata 拡張**で対応 |
| type (OSS/API/SDK/self-build) | なし | `metadata.candidate_type` 追加 |
| version / license / environment | なし | `metadata` + Evidence から LLM 抽出 |
| capabilities / limitations | なし | `metadata` |
| source_ids[] | `source_id`（単一） | 複数 Source は複数 Candidate で表現済み |
| conflicts[] | `classify_candidate_relation` | DEFINITION_DIFF / TRUE_CONFLICT で**概念一致** |
| confidence (機械スコア) | なし | **意図的に作らない**（Source attribution のみ） |

**結論:** 新 Candidate Framework は**不要**。`Candidate.metadata` の拡張 + `candidate_type` 列挙で PoC 可能。

---

## 3. Candidate Builder / Presenter / User Selection

### 3.1 candidate_builder

- `build_candidates_from_sources()` — 1 Source ≒ 1 Candidate
- `classify_candidate_relation()` — AGREEMENT / NUMERIC_NEAR / DEFINITION_DIFF / TRUE_CONFLICT
- `choose_presentation_mode()` — SINGLE / MERGED / MULTI / UNRESOLVED

**TDA への適合:**

| シナリオ | 既存分類 | 例 |
|----------|----------|-----|
| Python 3.11 vs 3.12 | DEFINITION_DIFF | バージョン差 |
| 同一バージョンで矛盾 | TRUE_CONFLICT → UNRESOLVED | License 表記差 |
| 複数 OSS 候補 | MULTI | OSS A / B / C |
| 自作 vs 既存 | MULTI + ユーザー選択 | ADOPT_A/B 拡張 |

**既知の限界:** 数値 heuristic が年号（2024）を人口数値と誤抽出するケースあり（E2E-C06 で観測）。TDA では version 文字列中心のため影響は限定的だが、Mechanical Verification 側で version/entity 一致を優先すべき。

### 3.2 presenter

- 出典リンク + 候補ブロック表示
- MULTI/UNRESOLVED 時に difference_note を会話へ注入

**TDA 拡張:** `DevelopmentProposalPresentation` として presenter を**薄く拡張**可能（新 Framework 不要）。候補ごとに type / environment / license ブロックを追加表示。

### 3.3 resolver / User Selection

既存 follow-up intent:

```text
ADOPT_A, ADOPT_B, COMPARE, SHOW_SOURCE, SHOW_BOTH, CONTINUE
```

**TDA に不足する intent（PoC 最小追加）:**

| Intent | 用途 |
|--------|------|
| `ADOPT_C` … | 3候補以上（label 汎化） |
| `RESEARCH_MORE` | 「A をもっと調べて」— 追加調査ループ |
| `BUILD_CUSTOM` | 自作選択 |
| `DEFER` | 保留 |

`parse_follow_up_intent()` の regex 拡張 + `handle_follow_up()` 分岐追加で足りる。**新 Core 不要。**

---

## 4. CC-01 / CC-02 / Defensive Core Policy

### 4.1 CC-01 — Eval Production Parity Bridge

- Canonical path のみ Production STOP 判断可（SCR-01）
- TDA 評価も **canonical eval 必須**
- Diagnostic direct は観察のみ

### 4.2 CC-02 — Mechanical Verification

**用途（TDA）:**

| 検証 | 既存 | TDA 適用 |
|------|------|----------|
| URL integrity | e2e_adapter | 採用 |
| Source existence | EvidenceSource | 採用 |
| Version / Entity 一致 | ExpectedFact 拡張 | **Investigate** |
| Claim coverage | verify_answer | LLM 提案 vs Evidence |
| unsupported detection | boundary 系 | 採用 |

**禁止:** Web 情報を正解として回答生成。**維持。**

### 4.3 Defensive Core Policy

- Model B: 計測問題 → 最小 Production 修正 / 将来 Core → Record → Investigate → Experimental
- **max 1 C3 / phase**
- Q8: LLM extend vs replace — TDA は **extend** に該当

**既存 Core 分類（関連）:**

| ID | 現 Class | TDA 再利用 |
|----|----------|------------|
| CR-CANDIDATE-ENVELOPE | C3 | **直接再利用**（metadata 拡張） |
| CR-SOURCE-PRESENTATION | C2 | 再利用 |
| CR-CONV-RESOLUTION | C2 | follow-up 拡張 |
| CC-01 | C3 | 評価基盤 |
| CC-02 | C3 | 観察基盤 |

**新規 C3 候補（最大1件）:** `TDA-ORCHESTRATION` — Requirement → Research gate → Proposal loop の**薄い orchestration harness** のみ。Search/Fetch/Candidate builder の duplicate は作らない。

---

## 5. Tool Creation Pipeline の現在位置

### 5.1 確立済み（Tool Creation Layer）

```text
Tool Idea / 手動調査 (candidate_research/*.md)
  → JSON Spec (docs/ai_tool/tool_creation/specs/)
  → Validator (schema + safety)
  → Catalog Draft + Test Skeleton
  → [手動] Implementation
  → [手動] registry/tools.json
```

| 能力 | 状態 |
|------|------|
| Spec 構造検証 | ✅ Phase 2 |
| Catalog draft / test skeleton 生成 | ✅ |
| CI pytest | ✅ Phase 3-1 |
| 自然言語 Requirement → Spec | ❌ |
| Web Research → Spec draft | ❌ |
| ユーザー承認ゲート | ❌（手動 HR のみ） |

### 5.2 並立系統（未統合）

| 系統 | パス | 特点 |
|------|------|------|
| Tool Builder | `tools/system/tool_builder/` | DuckDDG/Wikipedia research → **自動 Implementation → Register** |
| research_implement | `research/llm_benchmarks/research_implement.py` | LLM 自律 Tool 作成ベンチ |
| Context Builder | `ai_tool/context_builder/` | **既存 tool_id** 向け開発文脈（Web 非接続） |
| candidate_research | `docs/ai_tool/tool_creation/candidate_research/` | 手動 MCP 調査メモ |

**重要:** Tool Builder / research_implement は **「調査 → 勝手に作る」** 方向。TDA 指示の **「調査 → 提案 → ユーザー選択 → その後 Tool Pipeline」** とは**目的が逆**。接続するなら Phase E 以降、かつ HR 必須。

### 5.3 Tool Spec スキーマとの対応

`tool_spec.schema.json` は `provider`, `side_effect`, `authentication`, `network_access`, `risk_level` 等を既に保持。

TDA Research 結果から Spec draft へ写せる候補フィールド:

| Research 抽出 | Spec フィールド |
|---------------|-----------------|
| OSS/API 種別 | `provider` |
| 説明 | `description`, `purpose` |
| I/O 概要 | `input_schema`, `output_schema`（LLM 草案） |
| 副作用 | `side_effect` |
| 認証 | `authentication` |
| ネットワーク | `network_access` |
| 出典 | `source` |

**ギャップ:** Findings → Spec JSON の**機械マッピング層**が未存在。PoC では LLM が Spec **草案**を生成し、Validator で REJECT/ACCEPT する流れが最小。

---

## 6. 既存機能でどこまで実現可能か

### 6.1 実現可能（再利用のみ — PoC 境界内）

| 指示書要件 | 既存で足りる部分 |
|------------|------------------|
| Search → Fetch → Evidence | Production chain + CC-01 |
| 複数 Source / Candidate 保持 | conversation_resolution + e2e_adapter |
| 定義差・競合を潰さない | classify_candidate_relation |
| ユーザー選択 | resolver ADOPT_A/B + state |
| 出典提示 | presenter + SHOW_SOURCE |
| 追加調査ループ（最小） | resolver follow-up 拡張 |
| Mechanical 観察 | CC-02 + URL integrity |
| 評価・Regression | golden + canonical eval harness |
| UNKNOWN 許容 | Context Builder / Tool Creation 方針と一致 |

### 6.2 部分実現（薄い拡張が必要 — Experimental のみ）

| 要件 | 不足 | 最小追加 |
|------|------|----------|
| Requirement extraction | なし | LLM prompt + structured output（harness 内） |
| 「Web 調査が必要か」判定 | なし | heuristic + LLM gate（毎回 Search しない） |
| Technology Candidate 型 | metadata のみ | `candidate_type`, `environment`, `license` in metadata |
| OSS vs API vs 自作比較 | claim 中心 | presenter テンプレ + LLM proposal schema |
| Development Proposal 会話 | proxy_llm のみ | resolution prompt 差し替え |
| Search query generation | なし | Requirement → 1–3 query（LLM or template） |
| Targeted re-research | 部分 | `RESEARCH_MORE` intent + 追加 canonical eval |
| Spec draft 生成 | なし | LLM → JSON → 既存 Validator |

### 6.3 未実現（本 Phase スコープ外）

| 要件 | 理由 |
|------|------|
| Tool 自動実装 | §17 — ユーザー選択前は作らない |
| Registry 自動登録 | Tool Creation Policy |
| 実機制御（UR 等） | §12 — Research → Proposal のみ |
| Research Planner / Transaction | 既に REJECT |
| Production Agent 統合 | HR + E2E 未了 |

### 6.4 総合判定

```text
Orchestration / Conversation / Source / Selection : 70–80% 再利用可能
Domain model (Technology vs Fact Candidate)       : metadata 拡張で対応
Requirement → Spec pipeline                       : 0% — 新規薄层が必要
Search 品質（技術ドキュメント発見）              : 未評価 — ボトルネック候補
```

---

## 7. 重複実装候補（作ってはいけないもの）

| 重複候補 | 既存代替 | 判断 |
|----------|----------|------|
| 新 Search/Fetch パイプライン | `search_web` + `read_url_text` + enrich | **不採用** |
| 新 Evidence パッケージ | `evidence_context/packager.py` | **不採用** |
| 新 Mechanical Answer | CC-02 観察 | **禁止** |
| Research Transaction | REJECT 済み | **不採用** |
| 新 Web research loop | `production_agent_web_loop` | **不採用** |
| DuckDDG 専用 research | `tool_builder/research/web.py` | **参考のみ** — Production search と統合しない |
| 自動 Implementation パイプ | `research_implement.py` | **Phase E まで接続しない** |
| 新 Context Builder | `ai_tool/context_builder/` | **別ドメイン** — 出力形式のみ参考 |
| Candidate Framework 抽象化 | `conversation_resolution/models.py` | **不採用** — metadata 拡張 |
| Source Score / 真実度 | SCR-02 | **禁止** |

---

## 8. 不足している最小 Capability

優先度順。**新規 C3 は最大1件（TDA orchestration harness）。**

| ID | Capability | 種別 | Cost | 説明 |
|----|------------|------|------|------|
| **MC-1** | Requirement + Research Gate | Experimental harness | LOW | ユーザー要求 → 調査要否判定。毎回 Search しない |
| **MC-2** | Technology Candidate metadata | metadata 拡張 | LOW | `candidate_type`, `environment`, `license`, `unknowns` |
| **MC-3** | Query generation | harness function | LOW | Requirement → search queries（1–3件） |
| **MC-4** | Development Proposal presenter | presenter 拡張 | LOW | OSS/API/自作比較テンプレ |
| **MC-5** | Follow-up intents 拡張 | resolver 拡張 | LOW | RESEARCH_MORE, BUILD_CUSTOM, ADOPT_* 汎化 |
| **MC-6** | TDA orchestration harness | **唯一の C3 候補** | MEDIUM | MC-1〜5 を接続する evaluation entry |
| **MC-7** | Spec draft bridge | Experimental | MEDIUM | Proposal → `tool_spec.schema.json` 草案 → Validator |
| **MC-8** | Version/License mechanical check | CC-02 拡張 | MEDIUM | ExpectedFact 型拡張 — Investigate |

**わざと後回し:** Research Planner、Multi-hop search evaluator、自動 Tool generation。

---

## 9. Tool Development Assistance PoC 境界（提案）

### 9.1 スコープ

```text
[In Scope — Phase B PoC]
experimental/development_assistance/   # 新ディレクトリ（小）
  requirement_gate.py                  # MC-1
  tech_candidate.py                    # MC-2 metadata helpers
  query_gen.py                         # MC-3
  proposal_resolver.py                 # MC-4,5 — conversation_resolution を wrap
  harness.py + run_*.py                # MC-6
  tests/ + docs/

[Reuse — 変更最小]
conversation_resolution/*              # metadata / intent 拡張のみ
e2e_adapter.py                         # そのまま
eval_production_parity_bridge          # そのまま
mechanical_verification                # 観察のみ

[Out of Scope]
agent.py, registry, SYSTEM_PROMPT
tool_builder auto-register
research_implement auto-impl
Production 接続
UR 実機 / safety コード生成
```

### 9.2 PoC フロー（最小）

```text
User: 「○○する Tool が欲しい」
  ↓
requirement_gate (LLM: 調査要否)
  ↓ [必要時]
query_gen → run_canonical_web_eval (1–2 round)
  ↓
evidence_sources_from_loop
  ↓
build_candidates_from_sources (+ tech metadata)
  ↓
resolve_initial_turn (Development Proposal prompt)
  ↓
User: 「A を採用 / もっと調べて / 自作」
  ↓
handle_follow_up (RESEARCH_MORE → targeted eval)
  ↓
[Optional Phase B2] Spec draft → Validator (MC-7)
```

### 9.3 評価ケース（§20 対応）

| Case | 内容 | 初期データ |
|------|------|------------|
| A | LLM が十分知る一般 Tool | 「JSON ファイルを読む Tool」— LLM-only baseline |
| B | 新しい Library | 比較的新しい OSS（fixture + live 1件） |
| C | 複数 OSS | read_url 2ソース — 既存 E2E パターン流用 |
| D | 既存 vs 自作 | MULTI + user selection |
| E | バージョン差 | DEFINITION_DIFF — Python 3.11/3.12 fixture |
| F | Source 矛盾 | TRUE_CONFLICT / UNRESOLVED |
| G | 専門言語 | URScript — 公式 manual URL fixture |
| H | 複雑環境 | CUDA/PyTorch 要件 — UNKNOWN 許容 fixture |

各ケース: **LLM-only vs LLM+Web** を deterministic + proxy で比較（LLM Judge を GT にしない）。

### 9.4 URScript（§11）

- **目的:** 一般言語バイアスを避け、公式仕様参照の会話能力評価
- **範囲:** Research → Proposal のみ。コード生成・実機は **明示除外**
- **データ:** Universal Robots 公式ドキュメント URL（fixture HTML + optional live）

---

## 10. §28 STOP 条件チェック

| STOP 条件 | 現状 | 判定 |
|-----------|------|------|
| 既存 CR だけで PoC 可能 | metadata + intent 拡張で可 | **STOP しない** — 拡張は最小 |
| 新規 Core 不要で Candidate/Source 再利用可 | Yes | **STOP しない** |
| Production 変更が必要 | PoC では不要 | **STOP しない** |
| 新規 C3 が 2件以上必要 | MC-6 のみ C3 候補 | **STOP しない** |
| Search 品質がボトルネック | **未評価** — Phase B で計測 | **Monitor** |
| LLM が Research を利用できない | E2E で会話利用は実証済み（fact 域） | **Monitor**（TDA 域は未） |
| 単なる Web 要約 | 設計上 Proposal 構造で回避 | **設計注意** |

**総合:** Phase B PoC 進行可。Search 品質または LLM 利用不足が露呈したら **Search / Context Investigate** へ pivot（§28）。

---

## 11. 成功条件 S1–S10 マッピング

| ID | 条件 | 現状 | Phase B で確認 |
|----|------|------|----------------|
| S1 | 不十分対象を Research に回せる | gate 未実装 | MC-1 |
| S2 | 有用情報抽出 | Evidence 链 OK | 技術ドキュメント case |
| S3 | OSS/API/自作候補整理 | CR 再利用 | MC-2,4 |
| S4 | 必要環境把握 | 未 | metadata + UNKNOWN |
| S5 | Version/Source/License 保持 | 部分 | metadata + presenter |
| S6 | Conflict を潰さない | **実証済** | Case E,F |
| S7 | LLM が Research を会話利用 | fact 域実証 | Case B,G |
| S8 | ユーザー選択 | **実証済** | Case D + intent 拡張 |
| S9 | 追加調査 | 部分 | RESEARCH_MORE |
| S10 | Production 破壊なし | **維持** | golden + canonical regression |

---

## 12. 実装順序（§25 対応）

| Phase | 内容 | 本調査後の判断 |
|-------|------|----------------|
| **A** | Architecture Investigation | **本報告で完了** |
| **B** | Development Assistance PoC | **次アクション** — MC-1〜6、Case A–D fixture |
| **C** | Candidate Comparison | B に含めてよい（既存 CR） |
| **D** | User Selection | B に含めてよい（intent 拡張） |
| **E** | Tool Creation Handoff | MC-7 — B 成功後 |

---

## 13. 外部・既存資産比較

| 資産 | 分類 | TDA への位置 |
|------|------|--------------|
| Production Web chain | **採用** | Research 実行基盤 |
| conversation_resolution | **採用** | Candidate/会話/選択 |
| CC-01 / CC-02 | **採用** | 評価・観察 |
| Tool Creation Validator | **採用** | Spec draft 検証（Phase B2） |
| Context Builder | **参考** | EHP レイアウト、UNKNOWN 方針 |
| tool_builder/web.py | **参考** | query パターンのみ。Production search と二重化しない |
| research_implement | **不採用（現段階）** | 自動実装方向が TDA と不一致 |
| LangChain / Perplexity 型 | **参考** | citation UX のみ（E2E 報告と同様） |

---

## 14. 最終 Decision

```text
CONTINUE_INVESTIGATION → Phase B (Experimental PoC)
```

| 項目 | 判断 |
|------|------|
| Production 変更 | **不要** |
| 新規 Core | **最大1件**（TDA orchestration harness = C3 候補） |
| 新 Framework | **禁止** — CR metadata 拡張 |
| Research Transaction | **不採用** |
| 自動 Tool 実装 | **Phase E まで禁止** |

---

## 15. 次 Cursor 作業（Phase B 指示 — 未着手）

1. `ai_tool/experimental/development_assistance/` に MC-1〜6 の最小 PoC
2. `conversation_resolution` に metadata + intent 拡張（Production 非接触）
3. Case A–H fixture 定義 + LLM-only baseline 比較 harness
4. `run_web_research_tool_development_assistance_poc.py` + tests + report
5. Golden / canonical regression 維持

**Phase B 開始条件:** 本 Investigation のレビュー完了（Human）。

---

## Related

- [WEB_RESEARCH_USER_FACING_RESOLUTION_E2E.md](./WEB_RESEARCH_USER_FACING_RESOLUTION_E2E.md)
- [WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md](./WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md)
- [DEFENSIVE_CORE_DISCOVERY_POLICY.md](./DEFENSIVE_CORE_DISCOVERY_POLICY.md)
- [WEB_RESEARCH_TRANSACTION_INVESTIGATION.md](./WEB_RESEARCH_TRANSACTION_INVESTIGATION.md)
- [../tool_creation/README.md](../tool_creation/README.md)
- [../context_builder/OVERLAP_ANALYSIS.md](../context_builder/OVERLAP_ANALYSIS.md)
