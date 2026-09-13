# 観測ログ実装（Phase 2D）

`OBSERVABILITY_DESIGN.md` に基づく最小保存。問題解決プロトコルは変更していない。  
FA / native tools / IndexError 再実験は対象外。

---

## 変更したファイル

| ファイル | 内容 |
| --- | --- |
| `observability.py` | 新規。messages コピー、chat kwargs 記録、Tool dumps、parse 記録、Test 分解 |
| `harness.py` | `_ask` / `_run_turns` で上記を保存。`chat(model=, messages=)` は維持 |
| `tests/research/llm_benchmarks/problem_solving_experiment/test_observability.py` | ダミー `chat` による単体確認 |
| `README.md` | 本ファイルへの参照 |

未変更: `catalog.py`, `dispatch.py`, `adapters.py`, `_parse_action`, `SYSTEM`, Tool 一覧、Dispatcher、`get_current_failure`。

---

## 変更した関数

| 関数 | 役割 |
| --- | --- |
| `observability.copy_messages` | `chat()` 直前 `messages` の deepcopy |
| `observability.chat_kwargs_snapshot` | harness が渡す引数と `llm.chat` の profile 注入の記録。`tools` は渡さない |
| `observability.dump_tool_result_for_llm` | 既存と同一の `json.dumps` + 3500 + `"...(truncated)"`。raw / sent を分ける |
| `observability.parse_log` | `_parse_action` の戻りを成否として記録。Parser 本体は触らない |
| `observability.split_test_of_patch` | 既存 `test_of_patch` を分解。`solution_correct` は作らない |
| `harness._ask` | コピーと kwargs 記録を追加。`chat(model=MODEL, messages=messages)` は同じ |
| `harness._new_record` / `_run_turns` | ループ本体の切り出し。分岐・retry 文・break 条件は従来どおり |
| `harness.run_case` | 既存の Failure 生成 → `_run_turns`。`initial_minimal` は再利用 |

---

## 保存した情報

既存フィールドは削除していない。追加は `turns[].observability` とトップレベル `observability` / `test_observability`。

### LLM Turn（`turns[].observability`）

- `turn_id`（既存 `step` と同じ整数）
- 時刻: 既存 `turns[].at`
- `messages`: `chat()` 直前の deepcopy（system / user / assistant / Tool result user / retry user を含む）
- `chat_kwargs`: `model`, `options`（profile 由来）, `tools: "not_used"`, `tool_presentation: "system_text"`, `kwargs_source`
- raw: 既存 `turns[].raw`
- parse: `parse_success`, `parse_error`（失敗時 `"unparsed"`）。parsed は既存 `turns[].parsed`
- `retry_user`: Parser 失敗または unknown action のとき、次に送る user 文

Tool 提示は A-1 のまま system text。別 Schema は作っていない。`messages[0]`（system）で後から確認できる。

### Tool（`turns[].observability.tool` および `observability.tool_calls`）

- `tool_call_id`（`"{step}:1"`）
- `turn_id`, `tool_name`, `arguments`
- `raw_result`: Dispatcher 戻りを JSON 化した全量
- `sent_tool_result`: LLM へ渡した JSON 文字列（切断後）
- `truncated`, `sent_equals_raw_json`
- `execution_error`: `ok is False` のときの `error`。それ以外は `null`

LLM へ送る user 文は従来どおり `"Tool result:\n" + sent`。

### Failure

既存 `initial_minimal` を再利用。第1 user 全文は Turn 1 の `messages` に含まれる。重複生成しない。

### Repair Proposal

既存 `patch_source` / `final_summary` / `help` を維持。  
`observability.repair_proposal.turn_id` でどの Turn の final かを指す。

### Test

既存 `test_of_patch` を維持。追加 `test_observability`:

- `execution_success`: `ok is True` かつ `status == "pass"`
- `execution_success_means`: `"no_exception"`（解決判定ではない）
- `exception`: `error_type` / `error` / あれば `traceback`
- `return_value`

`solution_correct` は作らない。`status=pass` の意味は変更していない。

`observability.test_returned_to_llm` は常に `false`（現行経路に Test→LLM が無いことの記録。経路は追加していない）。

### Experiment

- `observability.experiment_start` / `experiment_end`
- `observability.stop_reason`: 現行分岐から取れる文字列のみ（`final` / `llm_timeout` / `max_turns`）。正式 enum ではない

---

## 保存場所

実験実行時は従来どおり:

```
research/llm_benchmarks/problem_solving_experiment/results/<stamp>/<case_id>.json
```

単体確認は実ファイルへ書かない。

---

## JSON 構造（追加分）

```text
record
  id, model, turns, tools_called, help, patch_source, final_summary,
  test_of_patch, notes, initial_minimal     # 既存
  test_observability                         # 追加（patch がある final のみ）
  observability
    experiment_start, experiment_end, stop_reason
    tool_calls[]
    test_returned_to_llm
    repair_proposal { turn_id, existing_fields }
  turns[]
    step, at, raw, timeout, parsed           # 既存
    observability
      turn_id, messages, chat_kwargs
      parse_success, parse_error, retry_user
      tool { tool_call_id, turn_id, tool_name, arguments,
             raw_result, sent_tool_result, truncated,
             sent_equals_raw_json, execution_error }
```

---

## 単体確認結果

IndexError の実 LLM 再実験はしていない。

| 確認 | 結果 |
| --- | --- |
| Test 1 ログ保存の単体 | `pytest tests/research/llm_benchmarks/problem_solving_experiment/test_observability.py` → **10 passed** |
| Test 2 messages / raw / parsed / Tool / sent / truncated | ダミー `chat` + `_run_turns` で保存を確認。`tools=` が `chat()` に無いことも確認 |
| Test 3 parse 失敗時 raw / parse_error / retry_user | 非 JSON の次 Turn の user が retry 文と一致 |
| Test 4 Test 結果の分離 | `test_of_patch` は既存意味。`test_observability` は例外なし / exception / return_value。`solution_correct` なし |

---

## 既存実験動作への影響確認

コード上、次は変えていない。

- `chat(model=MODEL, messages=messages)` のみ。`tools=` なし
- `SYSTEM` / catalog / dispatch / adapters / `_parse_action`
- retry user の文言
- Tool result の dumps・3500・`"...(truncated)"`・`"Tool result:\n"` 接頭辞
- final 後に `experiment_test_source` して break（Test を LLM に戻さない）
- `initial_minimal` の生成と第1 user の組み立て

検証手段はコード照合とダミー `chat` の単体テスト。同一ケースの実 LLM 再実行によるビット一致は **NOT OBSERVED**（今回禁止）。

---

## 未解決事項

- Ollama 生 HTTP ボディは保存しない（クライアント未接続）
- Parser 内部の `JSONDecodeError` 文面・greedy マッチ断片は、Parser を触らないため取れない。失敗は `parse_error: "unparsed"`
- 情報源ラベル（`initial_failure` / `tool:name` / `harness_retry`）は専用フィールドにしていない。messages と `retry_user` から再構成する
- `stop_reason` は正式 enum ではない
- messages / Tool raw にログ用 truncation は足していない。巨大結果の JSON 肥大は未計測
- `chat_kwargs.options` は profile の記録であり、Ollama に乗った最終リクエストの証明ではない
- パッチ後 `validate_tool_result` は現行どおり呼ばない
