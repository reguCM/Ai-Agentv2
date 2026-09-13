# TC-REGISTRY-FOUNDATION-P0 作業 REPORT

**TASK_ID:** `TC-REGISTRY-FOUNDATION-P0`  
**担当:** Cursor  
**状態:** `P0_COMPLETE`  
**日付:** 2026-09-02

---

## 大目標に対する現在位置

**大目標:** Tool Calling を主経路とし、Tool 規約と Model Registry で運用基盤を整える

**現在位置:** **P0 完了 / P1 未着手**

---

## 実施内容

### P0-1 active_model と Tool Calling 能力の整合

1. `config/pipeline.yaml` の `active_model` を `qwen3_14b`（暫定）へ変更
2. `config/llm_models.yaml` に暫定 active である旨のコメントを追加
3. `agent.py` で `probe_tool_calling()` 結果が `supported: false` のとき、明示メッセージを出して `sys.exit(1)`
   - 研究・互換のみ: `AI_AGENT_ALLOW_NON_TOOL_CALLING_MODEL=1` でバイパス可
   - 既存: `AI_AGENT_SKIP_TOOL_CALLING_PROBE=1` で probe 自体をスキップ

### P0-2 read_url_text drift 解消

- 正本は `registry/tools.json`（`visibility: agent`）を維持
- `production_bridge.py` の overlay は空のまま（no-op）。モジュール docstring とエラーメッセージを Registry 正規経路へ整合
- 失敗していた integration test 4 件を原因分類のうえ修正（下記）

---

## 変更ファイル

| ファイル | 変更理由 |
|----------|----------|
| `config/pipeline.yaml` | 既定 active を TC 対応プロファイルへ |
| `config/llm_models.yaml` | 暫定 active の位置付けを明記 |
| `agent.py` | TC 非対応モデルでの起動停止 |
| `ai_tool/agent_integration/production_bridge.py` | Registry 移行後のドキュメント・エラー文言 |
| `tests/ai_tool/agent_integration/test_human_review.py` | 期待値更新（C） |
| `tests/ai_tool/agent_integration/test_trial.py` | 期待値更新（C） |
| `tests/ai_tool/agent_integration/test_production_integration.py` | Registry 経路へ更新（C） |

**削除していないもの:** `production_bridge.py` 本体、研究資産、Action Bridge 実験

---

## integration test 4 失敗の原因分類

| テスト | 分類 | 対応 |
|--------|------|------|
| `test_human_review::test_approved_still_not_agent_available` | **C** Registry 移行後の期待値不足 | Registry `visibility=agent` で `agent_available=True` に更新 |
| `test_trial::test_production_discovery_still_not_agent_available` | **C** 同上 | 同上 |
| `test_production_integration::test_case4_dangerous_url_blocked` | **C** overlay 経路前提の古いテスト | `execute_registry_tool` 経由に変更（SSRF ブロックは Registry 実装で維持） |
| `test_production_integration::test_regression_production_tool_names_unchanged` | **C** read_url_text 未登録前提 | `read_url_text in names`, `read_file not in names` に更新 |

実装バグ（A）・設計欠落（D）は今回の 4 件では確認されず。

---

## テスト結果

| スイート | 結果 |
|----------|------|
| `tests/ai_tool/agent_integration` | **96 passed**（修正前 94 passed / 4 failed） |
| `tests/test_llm_tool_capability.py` | 2 passed |
| `test_production_bridge.py` | 12 passed |
| `test_observation_agent_e2e_deterministic.py` | passed |

---

## Tool Calling 実測結果（qwen3:14b / active_model 既定）

環境: 本機 Ollama、`active_model_id=qwen3_14b`

| Test | 内容 | 結果 |
|------|------|------|
| probe | `tools` パラメータ受理 | `supported: true` |
| Test 1 | 単一 Tool `get_gpu_status` | tool_calls 1 件 |
| Test 2 | Tool 選択 `get_cpu_status` | tool_calls 1 件 |
| Test 3 | Registry 実行 → LLM へ結果返却 | `execute_ok: true`、follow-up 応答あり |
| Test 4 | 同一ターン複数 Tool | `get_gpu_status` + `get_cpu_status` の 2 件 |
| Test 5 | `read_url_text` SSRF 失敗 → LLM へ error JSON | `ok: false`, `ssrf blocked...`、LLM 後続応答あり |

**deepseek_coder_v2_16b** は引き続き `supported: false`（Ollama 400）。既定 active からは外したため通常経路では起動しない。

---

## read_url_text drift 解消内容

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| LLM schema 正本 | Registry + 空 overlay | Registry のみ（overlay no-op） |
| 実行正本 | `execute_tool()` Registry import | 変更なし（正規経路） |
| Discovery | catalog と Registry が競合しテストが古い | Registry 優先、`agent_available=True` |
| SSRF ブロック | overlay テストのみ | `execute_registry_tool` で同等確認 |

---

## 残課題（P0 では触らない）

1. **SYSTEM_PROMPT と Registry の不整合** — Prompt は `list_files` / `read_file` / `search_files` に言及するが、Registry 未登録（P2 で対応予定）
2. **Model Registry** — role / capability / status / evaluation（P1）
3. **Tool Calling 規約文書・Validator ERROR/WARNING**（P1）
4. **`judgment_action_bridge_regression`** — 別タスク（19/23 passed、報告書未）
5. **工程別 `stage_models`** — 未配線

---

## P1 へ引き継ぐ内容

- P0 実測: qwen3:14b で単一・複数 TC、失敗結果の LLM 返却が成立
- 暫定 active は `qwen3_14b` — P1 Model Registry で `agent` role + `tool_calling` capability として記録する候補
- Registry Validator と命名 WARNING の設計は、現行 Tool 名（`cpu_status` 等）を破壊しない前提で進める
- file tools 公開は P2。P1 では規約と Registry 基盤を先に

---

## 禁止事項の遵守

- 非 TC 研究資産: 未削除
- Model Registry 本格実装: 未実施
- file tools 本番公開: 未実施
- agent.py 大規模再設計: 未実施
