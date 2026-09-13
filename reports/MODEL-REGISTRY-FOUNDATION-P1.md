# MODEL-REGISTRY-FOUNDATION-P1 作業 REPORT

**TASK_ID:** `MODEL-REGISTRY-FOUNDATION-P1`  
**担当:** Cursor  
**状態:** `P1-1_COMPLETE`  
**日付:** 2026-09-02

---

## 大目標に対する現在位置

**大目標:** Tool Calling を主経路とし、Tool 規約と Model Registry で運用基盤を整える

**現在位置:**

- P0 完了
- **P1-1 Model Registry 基盤完了**
- P1-2 Tool Calling 規約 未着手

---

## 実装前のモデル管理状況

| 層 | 正本 / 経路 | 役割 |
|----|-------------|------|
| Agent active 参照 | `config/pipeline.yaml` → `active_model`（profile id） | 現在の実行モデル選択（`qwen3_14b` 暫定） |
| 実行プロファイル | `config/llm_models.yaml` | profile id → Ollama モデル名・温度等 |
| 解決 API | `tools/system/config.py` → `active_model_id()`, `get_llm_profile()` | Agent / LLM 呼び出しが参照 |
| Agent 実行時モデル | `agent.py` → `MODEL = get_llm_profile()["model"]` | Ollama へ渡す実モデル名 |
| Tool 正本 | `registry/tools.json` | Tool Registry（並列構造の先例） |
| Model 正本 | **なし**（本タスクで新設） | role / capability / evaluation を分離管理できなかった |

**登録対象モデルの参照状況（調査時）:** 5 モデルはいずれも `config/llm_models.yaml` に profile として定義済み。`pipeline.yaml` の `active_model` は `qwen3_14b` のみ。コード内にモデル名の大量ハードコードはなく、主に yaml 経由。

---

## Model Registry の構造

**正本:** `registry/models.json`（`registry/tools.json` と並列）

```text
registry/models.json
├── version
├── schema_note
├── roles[]          # role 定義（id, description）
└── models[]
    ├── id             # profile id（llm_models.yaml と対応）
    ├── model          # Ollama 実モデル名
    ├── profile_id
    ├── provider
    ├── roles[]
    ├── capabilities{} # supported / verified を分離
    ├── status
    ├── pipeline_active  # pipeline active との対応（別概念）
    ├── installed_observed
    └── evaluation{}   # P0 実測・probe 結果
```

**Access Layer:** `tools/system/model_registry.py`

| API | 用途 |
|-----|------|
| `load_model_registry()` | 正本読込（キャッシュ付き） |
| `get_model(model_id)` | 単一モデル取得 |
| `list_models()` / `list_roles()` | 一覧 |
| `get_models_by_role(role)` | role 別取得 |
| `get_model_capabilities(model_id)` | capability 取得 |
| `get_model_status(model_id)` | status 取得 |
| `get_model_evaluation(model_id)` | evaluation 取得 |
| `tool_calling_capability(model_id)` | TC capability（supported / verified 分離） |
| `is_tool_calling_supported()` / `is_tool_calling_verified()` | TC 判定ヘルパ |
| `get_pipeline_active_model_id()` | pipeline.yaml 参照（既存 config 経由） |
| `get_active_model()` | pipeline active に対応する Registry エントリ |
| `registry_summary()` | 起動時観測用要約 |

**意図的に未実装:** 自動選択、LLM Router、role からの active 解決、pipeline.yaml の Registry 完全移行。

---

## 変更ファイル

| ファイル | 変更理由 |
|----------|----------|
| `registry/models.json` | **新規** Model Registry 正本 |
| `tools/system/model_registry.py` | **新規** Access Layer |
| `tests/test_model_registry.py` | **新規** Registry テスト（指示書 §16 Test 1–7） |
| `agent.py` | `[MODEL_REGISTRY]` 観測ログ追加のみ（選択経路は不変） |

**変更していないもの:** `config/pipeline.yaml`（`active_model` 維持）、`get_llm_profile()` 経路、Tool Calling probe / `create_ollama_tools()` / `execute_tool()`、Tool Registry、Action Bridge、研究資産。

---

## 登録モデル

| id | model | status | pipeline_active | TC supported | TC verified |
|----|-------|--------|-----------------|--------------|-------------|
| `qwen3_14b` | `qwen3:14b` | active | true | true | true |
| `qwen3_8b` | `qwen3:8b` | candidate | false | true | true（probe のみ） |
| `qwen2_5_coder_7b` | `qwen2.5-coder:7b` | candidate | false | true | true（probe のみ） |
| `deepseek_coder_v2_16b` | `deepseek-coder-v2:16b` | experimental | false | false | true |
| `gemma3_12b` | `gemma3:12b` | candidate | false | false | true |

いずれも本環境にインストール済み（`installed_observed: true`）。新規 pull は行っていない。

---

## role

最小構成（将来の専門 LLM 化に向けた仮置き。過剰な role は作らない）:

| id | 説明 |
|----|------|
| `general_agent` | Agent 主経路・Native Tool Calling |
| `coding` | コード生成・修正 |
| `lightweight` | 軽量汎用 |
| `compat_research` | 非 TC 互換・研究経路（Action Bridge 等） |

**未採用（今回）:** `reasoning`, `vision` — 機構未実装のため Registry に空 role だけ作らない。

---

## capability

各モデルに `capabilities` オブジェクト。最低限:

- `tool_calling` — `supported` / `verified` / `verification_method` / `verification_date`
- `text` — `supported` / `verified`
- `coding` — `supported` / `verified`

**原則:** Registry に `supported: true` と書いてあるだけでは「実環境で動作保証」とは扱わない。`verified` と `evaluation` で実測・probe 結果を分離記録。

---

## status

採用した状態:

| status | 使用例 |
|--------|--------|
| `active` | 現在 Agent 主経路で使用中（`qwen3_14b`） |
| `candidate` | 利用候補・代替検討中 |
| `experimental` | 研究・非 TC 互換経路向け |

**別概念として維持:**

- **Tool Calling 対応** → `capabilities.tool_calling.supported` + `verified`
- **pipeline active model** → `config/pipeline.yaml` + Registry の `pipeline_active` フラグ（参照用）

---

## evaluation

P0（`TC-REGISTRY-FOUNDATION-P0`）実測を反映:

**qwen3_14b（Agent E2E 実測）**

| 項目 | 結果 |
|------|------|
| single_tool | PASS |
| multiple_tools | PASS |
| tool_result_return | PASS |
| tool_failure_handling | PASS |

**qwen3_8b / qwen2_5_coder_7b:** probe_accepted PASS（Agent E2E フル実測は未記録）

**deepseek_coder_v2_16b / gemma3_12b:** probe_accepted FAIL（`does not support tools`）

**gemma3_12b:** 判断層実験（`judgment_layer_llm_connection_experiment`）への参照を notes に記録。

---

## 既存 Agent への影響

| 項目 | 影響 |
|------|------|
| モデル選択 | **なし** — `get_llm_profile()` / `pipeline.yaml` 経路を維持 |
| Native Tool Calling | **なし** — probe 強制・`sys.exit(1)` ロジックは P0 のまま |
| 起動時観測 | `[MODEL_REGISTRY]` JSON ログを追加（`AI_AGENT_SKIP_MODEL_REGISTRY=1` でスキップ可） |
| 新規ハードコード | モデル名の各所への追加なし |

---

## テスト結果

### Model Registry（指示書 §16）

| Test | 内容 | 結果 |
|------|------|------|
| Test 1 | Registry からモデル取得 | **PASS** |
| Test 2 | 存在しないモデルの扱い | **PASS** (`ModelNotFoundError`) |
| Test 3 | role 取得 | **PASS** |
| Test 4 | capability 取得 | **PASS** |
| Test 5 | Tool Calling capability 判定 | **PASS** |
| Test 6 | status 取得 | **PASS** |
| Test 7 | evaluation 取得 | **PASS** |
| Test 8 | 既存 Agent TC 経路 | **PASS**（agent_integration 96 passed） |

```text
tests/test_model_registry.py     14 passed
tests/ai_tool/agent_integration  96 passed
```

---

## P0 回帰結果

`tests/ai_tool/agent_integration`: **96 passed**（P0 完了時と同数）。Tool Registry 経路・production_bridge・human_review 期待値に退行なし。

---

## 残課題

1. **pipeline active の Registry 解決** — 現状は `pipeline.yaml` が正、`pipeline_active` は参照用フラグのみ。完全移行は P1-2 以降で設計。
2. **role → モデル自動選択** — 今回スコープ外。Access Layer に API の土台のみ。
3. **qwen3_8b / qwen2_5_coder_7b** — probe PASS だが Agent E2E 実測 evaluation 未記録。
4. **vision / embedding / reasoning role** — 機構未実装のため Registry 未登録。
5. **Registry と llm_models.yaml の二重管理** — profile パラメータは yaml 正本、意味論（role/capability/evaluation）は `models.json` 正本。同期は手動（自動同期機構は今回作らない）。

---

## P1-2 への引き継ぎ

1. Tool Calling 規約（ツール名・引数・返却形式の文書化と Registry 整合）
2. `list_files` / `read_file` / `search_files` と SYSTEM_PROMPT の不整合（P2 想定だが規約設計時に言及）
3. Model Registry を参照した active model 解決（`pipeline.yaml` → role/model reference → Registry）の段階的移行設計
4. 各モデルの Agent E2E evaluation 追記（候補モデルの実測）

---

## 禁止事項の遵守

- LLM 自動選択・Specialist LLM・Vision・Embedding 機構: **未実装**
- Agent 再設計・Tool Registry 再設計: **未実施**
- Action Bridge / 非 TC 研究資産の削除: **なし**
- qwen3:14b の永久固定: **なし**（暫定 active として明記）
- モデル名の大量ハードコード: **なし**
- 不要モデルのダウンロード: **なし**
- 本格ベンチマーク機構: **なし**

---

## 完了条件チェックリスト

- [x] Model Registry の正本が決定されている（`registry/models.json`）
- [x] role を管理できる
- [x] capability を管理できる（supported / verified 分離）
- [x] model を管理できる
- [x] status を管理できる
- [x] evaluation を管理できる
- [x] P0 実測 Tool Calling 結果を可能な範囲で記録
- [x] Registry を参照する最小 Access Layer がある
- [x] 既存 Agent の Native Tool Calling が継続動作
- [x] テストを追加・実行
- [x] REPORT を作成

**判定:** `PASS`
