# FILE-TOOLS-CONTEXT-SIZE-FIX-P2-6 作業 REPORT

**TASK_ID:** `FILE-TOOLS-CONTEXT-SIZE-FIX-P2-6`  
**担当:** Cursor  
**状態:** `P2-6_FIX_APPLIED_VERIFY_PARTIAL`  
**日付:** 2026-09-02

---

## 1. 目的

P2-5F で確認された Qwen3:14b の Native Tool Calling 不安定化（`num_ctx=4096` 時に大量 `search_files` 結果後の `read_file` 未生成）に対し、**最小限の本番 LLM 設定変更**として `context_limit`（→ Ollama `num_ctx`）を **8192** に引き上げ、本番経路で改善を検証する。

---

## 2. 変更前

| 項目 | 値 |
|------|-----|
| 対象モデル | `qwen3_14b` → Ollama `qwen3:14b` |
| `context_limit`（= `num_ctx`） | **4096** |
| `num_predict` | 2048 |
| `temperature` | 0 |
| API | `POST /api/chat`（`tools.system.llm.chat`） |
| `think` | 未指定（None） |
| P2-5F 参照結果（同一 payload・post_search） | Native read_file **0/3** |

---

## 3. 変更後

| 項目 | 値 |
|------|-----|
| `context_limit`（= `num_ctx`） | **8192** |
| その他 LLM 設定 | **変更なし** |
| Thinking | **変更なし**（OFF 導入なし） |

---

## 4. 変更箇所

| ファイル | 項目 | 変更 |
|----------|------|------|
| `config/llm_models.yaml` | `qwen3_14b.context_limit` | `4096` → **`8192`** |

**変更しなかったもの:** Tool Registry、Agent Loop、Prompt、`search_files` / `read_file` 実装、Thinking 設定、その他モデルプロファイル。

※ 本リポジトリでは YAML 上の `context_limit` が `tools/system/llm.py` 経由で Ollama `options.num_ctx` にマップされる。

---

## 5. 検証条件

| 項目 | 値 |
|------|-----|
| 経路 | **本番** `tools.system.llm.chat` + `execute_registry_tool`（`run_instrumented_chain`） |
| モデル | `qwen3:14b` |
| user prompt | P2-5E/F 広い search シナリオと同一 |
| 期待動作 | `search_files` → Native `read_file` → 実実行 |
| 実行回数 | **3 回** |
| 検証スクリプト | `ai_tool/agent_integration/file_tools_context_fix_verify_p26.py` |
| 一次資料 | `runs/ai_tool/20260902T070613Z_file_tools_context_fix_verify_p26/verify.json` |

P2-5F との対応:

- P2-5F **Condition C**（`think=True`, `num_ctx=8192`, 固定 50 match payload, post_search）→ **3/3** Native read_file
- 本検証は **instrumented chain**（LLM が round 0 で search 引数を選択）— より本番に近いが、search 結果量が run 依存

---

## 6. 検証結果

### 6.1 サマリー

| 指標 | 結果 |
|------|------|
| Native read_file 生成 | **2/3** |
| read_file 実実行 | **2/3** |
| search → read 連鎖 | **2/3** |
| Type 3 捏造疑い | **1/3**（run1: 空回答・read_file 未生成） |
| 回帰テスト | **179 passed, 3 skipped** |

### 6.2 各試行

| Run | search 結果 | Native read_file | read_file 実行 | Type 3 | 結果 |
|-----|------------|------------------|----------------|--------|------|
| 1 | 50 match / 10337B（広い search） | **No** | **No** | 疑い（空回答で停止） | **FAIL** |
| 2 | 9 match / 2390B | **Yes** | **Yes** | No | **PASS** |
| 3 | 9 match / 2390B | **Yes** | **Yes** | No | **PASS** |

### 6.3 Run 詳細

**Run 1（失敗）**

- Round 0: `search_files(path=".", query="read_file")` → 50 match
- Round 1: `llm_tool_names: []` → 最終回答空
- `tool_sequence: ["search_files"]` のみ

**Run 2 / 3（成功）**

- Round 0: 狭い search（9 match）— LLM が path/query を自主選択
- Round 1: Native `read_file` → `registry/tools.json` 等を実行（payload ~49KB）
- `tool_sequence: ["search_files", "read_file"]`

---

## 7. 回帰テスト

```text
179 passed, 3 skipped
```

対象: `test_search_files_registry`, `test_list_files_registry`, `test_read_file_registry`, `test_tool_calling_rules`, `test_model_registry`, `tests/ai_tool/agent_integration`

**新規失敗なし。**

---

## 8. 判定

### **PARTIAL**

| PASS 条件 | 状態 |
|-----------|------|
| `num_ctx=8192` 適用 | **PASS** |
| 本番経路 3 回検証 | **PASS** |
| Native read_file 安定（3/3） | **FAIL**（2/3） |
| Type 3 捏造なし | **FAIL**（run1 で read_file 未生成・空回答） |
| 回帰テスト問題なし | **PASS** |

**解釈:**

- P2-5F の **固定 payload + post_search** では `num_ctx=8192` で **3/3 成功**済み
- **instrumented chain + 広い search（50 match）** では **1/3 失敗**が残る
- `8192` は改善方向だが、**本番経路での完全安定は未確認**

> `num_ctx=8192` を「完全に検証済みの修正」として確定採用する条件（3/3 安定）は **未達**。

---

## 9. 次の状態

> **P2-6 修正 PARTIAL → 修正後の安定性確認が必要**

推奨（今回は未実施）:

1. 固定 50 match payload + 本番 `ollama_chat` で追加 3 回（P2-5F Condition C 再現）
2. instrumented chain の run1 失敗（空回答）の原因観測（timeout / eval 上限等）
3. 8192 で 3/3 が取れるまで追加検証後、採用確定

**今回実施しなかった追加試行:** `think=False`, `num_ctx=16384`, Tool/Prompt 変更, Tool Call 救済

---

## 10. 成果物

| ファイル | 内容 |
|----------|------|
| `config/llm_models.yaml` | `qwen3_14b.context_limit: 8192` |
| `ai_tool/agent_integration/file_tools_context_fix_verify_p26.py` | 検証スクリプト（新規） |
| `runs/ai_tool/20260902T070613Z_file_tools_context_fix_verify_p26/verify.json` | 検証一次資料 |
| `reports/FILE-TOOLS-CONTEXT-SIZE-FIX-P2-6.md` | 本報告書 |

---

## 11. 再現コマンド

```bash
# 設定確認
python -c "from tools.system.config import get_llm_profile; print(get_llm_profile()['context_limit'])"

# 本番経路検証（3回）
python -m ai_tool.agent_integration.file_tools_context_fix_verify_p26
```
