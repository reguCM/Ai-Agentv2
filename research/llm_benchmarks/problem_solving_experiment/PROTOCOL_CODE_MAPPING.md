# PROTOCOL_CODE_MAPPING — プロトコル段階とコード

一次資料。行番号は調査時点のファイル。

---

## A. Failure

| 項目 | 箇所 |
| --- | --- |
| Failure 生成 | `harness.run_case` 108–112。一時的に `cpu_status.py` へ fixture を書き `test_tool("cpu_status")`。finally で原文復元 |
| Validation 計算 | 114–119 `validate_tool_result`。セッションへ。第1 LLM 入力には入れない |
| セッション保持 | `adapters.set_session` 29–33, 120–125 |
| 初期 LLM 投入 | 132–136。`initial_minimal` = tool_name, status, error_type, error |
| 第1 messages | 132 system=`SYSTEM`（Tool一覧含む）, user=英文+minimal JSON |

第1 user に source / traceback / validation / generated code / 過去 Tool 結果は無い。  
SYSTEM に Tool 説明全文がある（Failure 本体ではないが自動付加）。

---

## B. Tool 提示

| 項目 | 箇所 |
| --- | --- |
| 個数・名前 | `catalog.TOOLS` 13 個。`llm_catalog_text` 180–186 |
| LLM に見える | name、引数名列挙、description 1行 |
| 見えない | required、型（JSON schema 本体）、return/error schema、使用例、capability |
| 方式 | harness `SYSTEM` 33–45 + JSON で name。**A-1** |
| `chat(..., tools=)` | 実験: **無し**（`_ask` 82）。`llm.chat` は kwargs 透過 |
| 本番 native | `agent.py`、`ai_tool/chat_interface/agent_turn.py` |
| probe | `tools/system/llm_tool_capability.py` `probe_tool_calling`。実験未使用 |

---

## C. Tool 選択

| 項目 | 箇所 |
| --- | --- |
| 誰が選ぶか | LLM 応答の `action=tool` と `name`（156–158） |
| 固定実行 | なし。ただし LLM が選ぶと `get_current_failure` が一括返す |
| 許可集合 | `catalog.by_name()` |
| 未知 | dispatch 12–13 `unknown_experiment_tool` |
| 引数 | `arguments` をそのまま `**`（dispatch 16） |
| 履歴 | `tools_called` に name のみ append（160）。args/result は turns.parsed に残る場合あり |

---

## D. Tool 実行

```
LLM content → _parse_action 52–77
  → dispatch(name, args) 8–20
  → handler 16
  → dict result
```

引数の JSON Schema 検証は無い。TypeError / Exception は error dict。

---

## E. Tool 結果

| 項目 | 箇所 |
| --- | --- |
| JSON 化 | 163 `json.dumps(..., default=str)` |
| 切詰め | 164–165 3500 + 省略印 |
| 加工 | キー削除はしない。dumps の str 化あり |
| 再投入 | 166 `user = "Tool result:\n" + dumped` |
| 履歴 | messages に残る。結果ファイルには残らない |
| 一括 | `get_current_failure` 36–52: test_result 全体 + validation 一部 + source |

---

## F. 再判断

Tool 後: `continue` で同じ for、`_ask`。messages は system + 全 user/assistant。新しい Tool も final も可。HELP は tool として可。

Test 後: 168–177 `break`。再判断なし。

---

## G. 修正案

| 項目 | 箇所 |
| --- | --- |
| 形式 | SYSTEM 41–42 `action=final`, summary, patch_source, help |
| 適用 | 本番 `apply_repair` なし。`experiment_test_source` に source 文字列 |
| 確定時点 | parsed が final のとき |

---

## H. Sandbox Test

`adapters.experiment_test_source` 133–203。tempfile + subprocess、timeout 15s、関数名 default `cpu_status`。  
return_value は返す。validation / expected / warnings は生成しない。

---

## I. Test 判定

例外なし: `ok: true`, `status: "pass"`（159–161）。  
例外: `ok: false`, `status: "fail"`, error_type, traceback。  
`execution_success` と `solution_correct` の別フィールドは無い。pass が前者を表す。

---

## J. Test → LLM

未実装。`test_of_patch` を record に載せて return。

---

## K. 再調査（Test 後）

未実装（break）。Test **前**は loop 内で別 Tool / 別 final が可能。同一 Tool 繰り返しを禁じるコードは無い。停滞仕様は無い。

---

## L. HELP

`request_human_help` 73–80。dispatch 経由。`help_requested` で `record["help"]=True`（161–162）。final の `help` でも上書き（171）。結果 JSON に `help` bool。

---

## M. ログ

保存: model, turns[].step/at/raw/parsed/timeout, tools_called, patch_source, test_of_patch, notes, initial_minimal, final_summary。

未保存: 送信 messages、SYSTEM 実文字列、Tool definitions 別欄、generation options、parser が拾った断片、Tool result 本文、patch 後 validation、actor 欄。

`at` は応答後の時刻（140–146）。request 時刻は無い。
