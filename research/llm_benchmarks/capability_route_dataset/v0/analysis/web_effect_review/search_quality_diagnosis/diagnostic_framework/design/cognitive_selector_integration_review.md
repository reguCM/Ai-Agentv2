# Cognitive Layer / Diagnostic Selector 統合設計レビュー

**status:** design review（参照用）。Phase 1 実装は `cognitive_phase1_notes.md`  
**date:** 2026-08-26  
**scope:** 配置・境界・接続可能性。実装詳細は Phase 1 メモへ  
**制約遵守:** 本番 Tool / 既存 Selector 本体 / Knowledge Base / 過去実験は未変更・未上書き

---

## 0. 結論（先に）

1. **Cognitive Layer と Diagnostic Selector は責務を分離すべき**であり、指示書の分担表は現行コードと整合する。  
2. Cognitive Layer の自然な正本ストアは既存 **`TaskState` + `open_questions` +（証拠は）`ResearchHistory`**。Agent の `messages[]` に閉じない。  
3. Selector への入力は Cognitive State 全体ではなく、既存 Selector が既に使う **`features` 付き Task Fingerprint**（`problems/*.json` と同型）へ射影する。  
4. Phase 1 では Selector 自動起動・GPT エスカレーション・自動修正を実装しない。できるのは「将来 Selector が読める Fingerprint 候補をログに残す」まで。  
5. Method と Model は catalog 上まだ完全分離されていない（`small_llm_local` と `gpt_external` が method_id として並ぶ）。将来スキーマで分離する余地はあるが Phase 1 では確定しない。

---

## 1. 現在の Agent 構造

リポジトリには **入口が二系統**ある（`docs/current_system_specification.md` / `docs/autonomous_research_architecture.md`）。

### 1.1 PROJECT_AGENT（`agent.py`）

```text
USER_REQUEST
  → Clarity Gate → TaskState
  → system prompt に snapshot_state(task_state) 埋め込み
  → chat(tools=...) ループ
  → execute_tool → messages.append(role=tool, raw result)
  → stdout 要約は別経路（能力経路と分離）
```

- Clarity 後に `task_state` を保持（`agent.py` 付近）。  
- Tool 結果の LLM handoff は `messages.append` + `json.dumps(result)`（約 L850–859）。  
- **Research パイプラインは呼ばない。** TaskState は Clarity 由来の薄い利用が中心。

### 1.2 RESEARCH_PIPELINE（`research/llm_benchmarks/research_implement.py`）

```text
Case / Clarity → TaskState
  → Research ↔ Judge ループ
  → Partial Judge (rule_partial) → StatePatch / History
  →（必要時）Global Judge
  → context_allocation で提示材料を組む
```

- 正本の認知・未解決・履歴はこちら。  
- **History ≠ Prompt**（`task_state.py` / アーキテクチャ文書）。  
- LLM は全履歴を持たず、Current State + 配分された materials で次 Action を決める設計。

### 1.3 Diagnostic 実験系（本レビューの Selector 側）

```text
diagnostic_framework/
  knowledge_base/     # 実験統合知識（上書き禁止対象）
  selector/           # ルールベース Selector（実験用）
  runs/               # 過去実験（変更禁止）
  design/             # 本レビュー（新規）
```

本番 Agent / Tool 実行経路とは **現状非接続**。診断実験・Selector 評価専用。

---

## 2. Cognitive Layer の配置案

### 2.1 推奨配置（大規模リファクタなし）

| 優先 | 位置 | 理由 |
|------|------|------|
| 1 | Clarity 確定直後〜ループ前 | 既に `TaskState` がある。Goal/Intent/Claims の構造化を載せやすい |
| 2 | Research の Partial Judge 前後 | 仮説更新・未解決・証拠の機械 patch と同型 |
| 3 | `prepare_context_allocation_call` 直前 | 「何を見せるか」と認知要約の相性が良い |

**避ける:** `agent.py` の `messages[]` だけに認知を閉じる（Research State と二重化、History≠Prompt と衝突）。

### 2.2 Phase 1 の置き方（推奨）

```text
Conversation / Clarity
  ↓
Cognitive Layer（薄い観測・整理）
  ↓ 書き込みは TaskState 拡張フィールド or 別ログ JSON
人間が確認可能な Cognitive State スナップショット
  ↓（まだ呼ばない）
Task Fingerprint 候補をログのみ生成（Selector 未起動）
```

Phase 1 成功条件は指示書どおり:

```text
会話 → Cognitive State → State 更新 → 人間確認
```

Selector 自動起動はしない。

### 2.3 既存との責務重複

| 既存 | 重複しうる点 | 扱い |
|------|--------------|------|
| `TaskState.task` / decisions | Goal の一部 | Cognitive Goal は拡張として明示。二重の「別 task 文字列」を増やさない |
| `open_questions` | Unresolved Questions | **そのまま再利用**を第一候補。別名ストアを新設しない |
| `facts` / `selected_findings` | Evidence / Claims の一部 | FACT 昇格は既存どおり機械側（`decision_store`） |
| `decision_confidence` / KSS 観測 | Confidence | 観測専用。Selector の主信号にしない（不確実性実験 H5 と整合） |
| `SearchIntent` (`query_intent.py`) | Intent | 検索クエリ用。認知 Intent とは別物として境界を書く |
| Hypothesis | **本番 State に無し** | Cognitive Layer の新規領域。実験ベンチの H* と混同しない |

---

## 3. Cognitive State（案）

指示書の要素を、既存 TaskState との対応で整理する。

| Cognitive 要素 | 既存対応 | Phase 1 |
|----------------|----------|---------|
| Goal | `task` + Clarity decisions | 既存を正とし、必要なら注釈フィールド |
| Intent | （弱）SearchIntent とは分離 | 新規。会話意図の短い構造化 |
| Claims | `facts` / `decisions` に近い | 「主張」は promote 前は候補扱い |
| Hypotheses | なし | 新規リスト（status: open/supported/rejected） |
| Concepts | なし | 任意・最小 |
| Evidence | History + findings | 参照 ID のみ State、全文は History |
| Unresolved Questions | `open_questions` | **既存を使う** |
| Confidence | KSS 観測あり | 記録可。行動・Selector 主信号にしない |

**保存場所の推奨**

- 正本: `TaskState`（prompt 用は `snapshot()`、永続は `persistence_snapshot()`）  
- 詳細証拠・診断 run 参照: `ResearchHistory` または診断側 `reuse_index` パス  
- 会話専用の別 DB を Phase 1 で新設しない  

**会話 State と Tool 実行 State**

- **分離すべき。**  
  - 会話/認知: TaskState + Cognitive 拡張  
  - Tool 実行瞬時: `messages` / trial 記録 / tool return  
  - 診断実験: `diagnostic_framework/runs/...`（本番と混ぜない）

---

## 4. Task Model / Task Fingerprint

### 4.1 Cognitive → Selector に渡すもの

Selector は **問題特徴のブール／列挙**を期待する（現行 `DiagnosticSelector.select(problem)`）。

既存入力例（`selector/problems/search_web_quality.json`）:

```json
"features": {
  "has_runtime_logs": true,
  "code_available": true,
  "path_unknown_or_untrusted": true,
  "suspect_ranking_vs_filter": true,
  "suspect_stdout_vs_llm_handoff": true,
  "needs_path_integration": true,
  ...
}
```

Cognitive State 全体を渡さない。射影例:

| Cognitive | Fingerprint / features |
|-----------|------------------------|
| Goal: 品質原因特定 | `task_type: code_diagnosis` |
| Claim: handoff 疑い | `suspect_stdout_vs_llm_handoff: true` |
| H1 ranking | `suspect_ranking_vs_filter: true` |
| コード・ログあり | `code_available` / `has_runtime_logs` |
| Unresolved: どの段階で喪失か | `requires_causal_trace` / `needs_path_integration` |
| 不確実性が高い | `uncertainty: high`（※自己申告ではなく証拠由来を優先） |

### 4.2 形式の推奨

- **Cognitive State と Task Fingerprint は分離 JSON。**  
  - State: 人間可読・会話継続用  
  - Fingerprint: Selector / 実験再利用用（既存 `problems/*.json` スキーマに寄せる）  
- 同一巨大 JSON に混ぜると、Selector ルールと会話ログの版管理が壊れる。

### 4.3 Phase 1 での扱い

Fingerprint は **生成・ログ保存のみ**。`DiagnosticSelector.select` を本番経路から呼ばない。

---

## 5. Selector との境界

### 5.1 責務（指示書を現行に合わせて確定推奨）

| 問い | 担当 |
|------|------|
| ユーザーは何を知りたいか / Goal / 仮説 / 未解決 | Cognitive Layer |
| 何を検証すべきか | Cognitive → Task Model |
| コード調査・ログ・route 分解・モデル選択・再利用・人間確認 | **Selector（＋ Policy）** |
| 「Qwen を使う」を Cognitive が直接決める | **禁止** |

### 5.2 既存 Selector の実態

- 実装: `diagnostic_framework/selector/selector.py`  
- 入力: `problem.features` + catalog + rules + reuse_index  
- 出力: `selected_pipeline`, 理由, 未選択理由, confidence/status, `reusable_artifacts`, `auto_fix: NOT_ALLOWED`  
- 種別: **ルールベース**。ML・LLM 自己選択ではない。  
- 本番 Agent からは **未配線**。

### 5.3 Cognitive が Selector を直接呼ぶべきか

**Phase 1–2: 直接呼ばない。中間層（Task Fingerprint Builder）を置く。**

```text
Cognitive State
  → FingerprintBuilder（純関数・テスト容易）
  → DiagnosticSelector.select（将来）
  → SelectionRecord
  → Cognitive / History へ「調査方針候補」として戻す（実行は別）
```

理由: features キーの安定契約が必要。Cognitive の自由記述を Selector に直接入れるとルールが壊れる。

### 5.4 Selector 結果の戻し方

SelectionRecord を `research_history` または Cognitive の `investigation_plan` 候補に:

- selected methods + reasons + confidence  
- not_selected + reasons  
- reuse artifact paths  
- escalation: none / conditional / required（将来）  
- **実行したかは別フラグ**（Phase 1 では常に not_executed）

---

## 6. Knowledge Base との境界

| 資産 | 役割 | Cognitive | Selector |
|------|------|-----------|----------|
| FINDINGS / HYPOTHESIS_STATUS / METHOD_EFFECTIVENESS | 人間向け知見 | 読まない（Phase 1） | ルール・catalog の根拠 |
| experiment_data.json / method_catalog.json | 機械索引 | 参照しない | **正本の一つ** |
| rules.json / reuse_index.json / problems/*.json | Selector 稼働 | Fingerprint 出力が problems と同型 | 直接使用 |
| SELF_DIAGNOSIS_SELECTOR.md / DIAGNOSTIC_WORKFLOW.md | 方針文書 | 設計参照のみ | ルールの人間説明 |
| runs/... 実験結果 | 証拠 | パス参照のみ | reuse_index |

**二重管理しない:** Cognitive 用に別 method catalog を作らない。experimental 手法は既存どおり `selector/extensions/*.json` と run 内 `GPT_METHOD_CANDIDATE.json` 等に置き、確定反映は別レビュー。

---

## 7. 将来の LLM エスカレーション接続点

実験根拠:

- GPT 比較: `runs/20260825_190500/gpt_external_tool_experiment/`（`GPT_METHOD_CANDIDATE.json` status=experimental）  
- 不確実性ゲート: `runs/20260825_193500/uncertainty_escalation_experiment/`（自己申告 confidence は不十分、本文ヒューリスティックが有望）  
- 拡張案: `selector/extensions/uncertainty_gate_experimental.json`（未配線）

推奨フロー（**未実装・experimental**）:

```text
Fingerprint → Selector（method 候補）
  → Local analysis（method + small model）
  → 出力/証拠の機械ゲート（自信度ではない）
  → 十分 / 不確実
  → 後者のみ GPT_EXTERNAL / large_llm（method 再適用 or 統合 method）
  → 人間承認
```

### Method と Model の分離

現状 catalog は `route_decomposition`（手法）と `small_llm_local` / `gpt_external`（実行主体）が **同列の method_id**。

将来スキーマ案（Phase 1 では実装しない）:

```text
selection:
  method_id: route_decomposition
  model_id: qwen3:8b | gpt_external | composer_large
  materials: code_pack | route_packs | logs
  gate: uncertainty_content_heuristic
```

これにより「分解が効いた」と「GPT が分解をうまく読んだ」を区別できる（指示書 §7）。

外部 GPT 追加時: catalog に `gpt_external` 的エントリと rules の feature 条件を足せば、**Selector コアの大幅改変なし**で候補化可能（既存 `extensions/gpt_external_experimental.json` の方向）。Cognitive は Fingerprint のみ変えればよい。

---

## 8. 現在の設計上の問題

1. **Agent 会話経路と Research State 経路が弱い統合** — Cognitive をどちらに載せるか明示しないと二重実装になる。  
2. **Hypothesis の正本が無い** — 診断実験の H* と会話仮説が別世界。  
3. **Selector が本番未配線** — 接続は設計上可能だが、features の自動抽出が未実装（現状は人手 JSON）。  
4. **Method/Model 混在** — catalog の整理が必要（experimental のまま）。  
5. **Confidence の誤用リスク** — KSS / Qwen 自己評価を Selector 主信号にすると実験 H5 に反する。  
6. **常時深い処理** — Clarity 毎に Selector を回すとコスト増。レベル分けが必要（指示書 §10）。  
7. **Fingerprint 自動生成の品質** — 誤った `suspect_*` は False Escalation を生む（不確実性実験の M9 類例）。

---

## 9. 推奨 Phase 分割

| Phase | 内容 | やらないこと |
|-------|------|----------------|
| **1** ✅ | Cognitive State の最小スキーマ、TaskState/open_questions との対応、更新ログ、人間確認 UI/ファイル、Fingerprint **候補のログのみ**（実装: `tools/ai/state/cognitive_*.py`、メモ: `cognitive_phase1_notes.md`） | Selector 自動起動、GPT/大型自動呼出、Web 自動接続、自動診断・自動修正、KB/Selector 上書き |
| **2** | FingerprintBuilder の純関数化・単体テスト、既存 `problems/search_web_quality.json` との照合 | 本番常時 Selector |
| **3** | 診断セッション限定で Selector 読取専用接続、SelectionRecord を History に記録 | auto_fix、catalog の確定採用昇格 |
| **4** | experimental uncertainty gate + GPT escalation（オプトイン） | 自信度主信号、無条件 GPT |
| **5** | Method/Model スキーマ分離、他 Tool への一般化実験 | 「完成した自己修復」扱い |

---

## 10. 未解決事項

1. Cognitive 拡張フィールドを `TaskState` に直接足すか、`cognitive_state.json` サイドカーにするか。  
2. Agent 会話のみの利用者が Research パイプライン無しで Cognitive をどう永続するか。  
3. Fingerprint の `suspect_*` を誰が立てるか（人間 / 規則 / 将来 LLM）— Phase 1 は人間または固定テンプレ推奨。  
4. SelectionRecord をユーザー向け応答に出す粒度。  
5. `gpt_external` と `large_llm_escalation` の Selector 上の排他・優先。  
6. レベル 0–5 の閾値（仮仕様のまま実験で決める）。  
7. open_questions と Hypotheses のライフサイクル同期規則。

---

## 11. 既存実験への参照

| 参照 | パス | 本レビューでの含意 |
|------|------|-------------------|
| 知識統合 | `knowledge_base/`（FINDINGS, METHOD_EFFECTIVENESS, MODEL_COMPARISON, DIAGNOSTIC_WORKFLOW, SELF_DIAGNOSIS_SELECTOR, experiment_data.json, method_catalog.json） | Selector/KB 正本。Cognitive は置き換えない |
| Selector | `selector/selector.py`, `rules.json`, `reuse_index.json`, `problems/search_web_quality.json` | Fingerprint 契約の実在実装 |
| 大型LLM | `runs/20260825_124200/large_llm_search_web_diagnosis/` | 統合・偽原因棄却は有望だがワークフロー依存 |
| GPT | `runs/20260825_190500/gpt_external_tool_experiment/` | experimental 手段。常用しない |
| 不確実性ゲート | `runs/20260825_193500/uncertainty_escalation_experiment/` | 自己申告 confidence 不支持；機械ゲート有望 |
| 拡張（未配線） | `selector/extensions/gpt_external_experimental.json`, `uncertainty_gate_experimental.json` | 将来接続点 |
| Agent State | `tools/ai/state/task_state.py`, `open_questions.py`, `research_history.py` | Cognitive の載せ先候補 |
| アーキテクチャ | `docs/autonomous_research_architecture.md` | History≠Prompt / State 中心 |

---

## 12. レビュー設問 A–E への回答

### A. Cognitive Layer

1. **配置:** Clarity 後〜ループ前、および Research では Partial Judge 前後が自然。  
2. **重複:** `task` / `open_questions` / `facts` / KSS 観測。Hypothesis は新規。SearchIntent と混同しない。  
3. **保存:** `TaskState`（+ History）。Phase 1 で別本番 DB を増やさない。  
4. **会話 vs Tool 実行:** **分離すべき。**  
5. **既存類似:** TaskState, open_questions, decision_store, context_allocation, KSS 観測群。Cognitive は「会話理解の明示層」として不足分を足す。

### B. Task Model

6. **必要情報:** task_type, 証拠有無, multi_file/path, suspect_*（handoff/ranking 等）, uncertainty（証拠由来）, requires_causal_trace。  
7. **形式:** 既存 `problems/*.json` の `features` 互換。  
8. **同一 JSON?** **分離。**

### C. Selector

9. **接続可能か:** Fingerprint が features 互換なら **可能**（現状は人手 JSON で実証済み）。  
10. **重複:** KB 文書と catalog は役割分担済み。Cognitive 用の第二 catalog は作らない。  
11. **直接呼び出しか:** **中間 FingerprintBuilder を推奨。** Phase 1 は未呼出。  
12. **戻し方:** SelectionRecord → History / investigation_plan 候補（未実行フラグ付き）。

### D. 将来エスカレーション

13. **追加可能か:** Selector の escalation role + uncertainty extension で後付け可能。  
14. **Method/Model 分離:** 設計上可能。現状 catalog は未分離 → 将来スキーマ課題。  
15. **外部 GPT:** extensions + rules 追加でコア大幅変更なしに候補化可能（experimental 維持）。

### E. 実験可能性

16. **判断根拠ログ:** Cognitive 更新前後スナップショットをファイル保存すれば可（Phase 1 推奨）。  
17. **更新前後比較:** `persistence_snapshot` 差分または専用 audit JSON。  
18. **再解釈追跡:** patch 理由コード + 参照 message/tool id。  
19. **Selector 理由:** 既存どおり `reason` / `rule_ids` / `not_selected_reason`。  
20. **過去実験再利用:** `reuse_index.json` + run パス。Fingerprint の `problem_id` で接続。

---

## 13. Phase 1 実装に進む前の人間確認ポイント

- [ ] Cognitive の正本を TaskState 拡張でよいか  
- [ ] open_questions を Unresolved の唯一の正本とするか  
- [ ] Fingerprint キー集合を現行 `rules.json` の when キーに固定するか  
- [ ] Phase 1 で Agent 会話経路のみか、Research 経路も含むか  
- [ ] experimental 手法を UI に出すか（出すなら status を必ず表示）

**設計レビュー本文は変更最小。Phase 1 実装詳細は `cognitive_phase1_notes.md`。**
