# CURRENT_STATE — 問題解決実験基盤の現状

この文書は実装仕様ではない。コード一次資料に基づく現状記録である。

対象:

- `research/llm_benchmarks/problem_solving_experiment/harness.py`
- `catalog.py` / `dispatch.py` / `adapters.py`
- `tools/system/llm.py`
- 結果 `results/20260831T183219Z/index_error.json`

本番 `agent.py` / Registry / Repair は実験基盤ではない。

---

## 1. LLM 呼び出し

| 項目 | 現状 |
| --- | --- |
| 入口 | `harness._ask` → `chat(model=MODEL, messages=messages)` |
| 接続 | `tools.system.llm.get_client()` = `ollama.Client` |
| model | `get_llm_profile()` の active model |
| options | `num_predict`, `temperature`, `num_ctx`（profile）, `keep_alive` |
| `tools=` | **渡していない** |
| 応答 | `response.message.content` の文字列のみ使用 |
| 生リクエスト保存 | **無い**。`record_llm` は秒数のみ |

本番 Agent（`agent.py`, `ai_tool/chat_interface/agent_turn.py`）は `tools=` を渡す経路がある。実験ハーネスはその経路を使っていない。

---

## 2. 1ターンの流れ

```
初期: messages = [system SYSTEM, まだ user なし]
loop:
  user を append
  chat()
  assistant を append
  parse
  tool なら dispatch → 次 user = "Tool result:\n" + json
  final なら experiment_test_source（会話には戻さない）して break
```

固定 Tool 1本のパイプラインではない。許可集合は catalog の 13 名。

---

## 3. 初期 Failure

第1 user（`harness.py` 133–136）:

```
Solve this test failure. Get any information you need yourself.
{"tool_name","status","error_type","error"}
```

traceback / source / validation は第1 user に無い。

セッションには `set_session` で生 `test_result` + `validate_tool_result` + source が入っている。LLM は `get_current_failure` を呼ぶまでそれを見ない。

---

## 4. Tool 提示（LLM に見えるもの）

方式: system テキスト + JSON で `name` を書かせる。

`llm_catalog_text()` が LLM に出す情報:

- name
- 引数名の列挙（型・必須・意味は出さない。description 文に一部ある場合のみ）
- description 1行（英語）

出していない: purpose 欄、return schema、errors、使用条件、具体例、`capability`、`origin`。

Ollama function schema（`type: function`）としては渡していない。

---

## 5. Dispatcher

`dispatch(name, arguments)` → `TOOLS[name].handler(**arguments)`。

名前変換なし。未知名は `unknown_experiment_tool`。結果は JSON 文字列化して次 user。3500 文字超は切断。

---

## 6. `get_current_failure`

返す: `test_result` 全体、validation の一部、`source` 全文。

1回の成功呼び出しで source + traceback + validation が揃う。

---

## 7. Test

`experiment_test_source`: 一時ファイルで関数を実行。例外なし → `ok: true`, `status: "pass"`。return_value の意味は見ない。`validate_tool_result` はパッチには使わない（初期セッション構築時のみ）。

`final` 後にハーネスが1回呼ぶ。**結果は LLM の messages に戻らない。**

ケース全体の成功フラグは無い。ログは `patch={bool}`。

---

## 8. 結果 JSON に残るもの / 残らないもの

残る: model、turns[].raw / parsed / timeout、tools_called、patch_source、test_of_patch、initial_minimal、notes、final_summary。

残らない: 送信 messages、SYSTEM 全文、Tool 結果本文、generation options、parser 失敗時の抽出断片、Validation のパッチ後結果。

---

## 9. Parser

要求: markdown 無しの JSON only（system 文）。

実装: 全文 `json.loads`。失敗時 greedy `\{.*\}`（DOTALL）。混在（説明 + python dict + markdown JSON）は失敗 → `unparsed_llm_output` → 短い再指示。

再指示は当初の形式説明より短い。壊れた assistant 文は履歴に残る。

---

## 10. HELP / 停滞 / タイムアウト

HELP: `request_human_help` の戻り `help_requested`、または final の `help`。仕様化された状態機械ではない。

停滞・タイムアウト値: 未実装。`MAX_TURNS = 12` と LLM `timeout_seconds` のみ。
