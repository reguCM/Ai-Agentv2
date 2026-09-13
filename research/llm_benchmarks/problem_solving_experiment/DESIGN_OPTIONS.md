# DESIGN_OPTIONS — 差分を埋める候補

採用はしない。実装もしない。FA 仕様にもしない。

---

## 5. Tool 提示方式

### A-1. 現状維持（system テキスト + JSON name）

- 変更量: 小さい（説明文・schema テキストを足す程度）
- LLM に見えるもの: 文章。Ollama の tool チャネルではない
- 引数検証: Dispatcher の `**kwargs` のままなら弱い
- 選択の明確性: 低い（自由文と JSON が混ざる）
- 解釈: 「テキストプロトコルを守れたか」と「Tool を選んだか」が混ざる
- 整合: 実験ハーネス現状。本番 Agent の `tools=` とは別
- FA 影響: テキスト FA と混同しやすい。決めない

### A-2. Ollama native tool calling

- 変更量: 中。catalog → Ollama schema、`chat(..., tools=)`、`message.tool_calls` の読取。`probe_tool_calling` が既にある
- LLM に見えるもの: モデルが tools を受け付けるなら function 定義
- 引数: モデル側 JSON schema。実験側でも検証が必要
- 選択の明確性: 高い（tool_calls と content を分けられる）
- 解釈: 本番 Agent に近い
- 整合: `agent.py` / `agent_turn.py` が既に `tools=` を使う。**実験が本番 execute_tool を呼ぶ必要はない**
- リスク: active model が tools 非対応なら成立しない（probe が必要）。対応モデルへの固定は別判断
- FA 影響: 本番 Agent の tool 経路と似る。FA 接続とは別問題

### A-3. 実験用独自 calling の明確化（Dispatcher 維持）

- 変更量: 中。JSON schema を system に出す、parser を schema に合わせる、結果を role=tool 相当で積む、かも
- LLM に見えるもの: より詳しいテキスト schema。依然 native ではない
- 引数検証: Dispatcher 前で schema チェック可能
- 選択の明確性: A-1 より高い。A-2 よりモデル依存が少ない
- 解釈: 「この実験プロトコル上の Tool 選択」として限定できる
- 整合: 現状 Dispatcher を残す
- FA 影響: 実験プロトコルを FA にコピーしない限り中立

**採用しない。** 観測目的が「本番 Agent と同じ tool calling」なら A-2 が近い。「モデル非依存で Dispatcher を測る」なら A-3。「最小変更」なら A-1 + 説明強化。

---

## 6. Failure 情報の分離（単位は未決）

初期候補（第1 user に載せてよいもの）:

- tool_name
- status / result
- error_type / error  
  traceback・source・validation は載せない

追加観測の切り方（候補。必須分割ではない）:

| 単位 | 既存の寄せ先 |
| --- | --- |
| traceback | 生 test_result。今は `get_current_failure` 内 |
| source 全文 | セッション source。同上 |
| 該当行周辺 | `read_file` の offset/limit で既に可能 |
| validation / warnings | `get_current_failure` 内 |
| module / function | 生 test_result |
| return_value | 例外時は無いことが多い |

設計上の選択肢:

- F-1: `get_current_failure` を初期と同型の最小面だけにする  
- F-2: 観測キーを引数で選ばせる（一括禁止）  
- F-3: traceback / source / validation を別 Tool 名にする  
- F-4: 初期は最小、`get_current_failure` は現状維持（実験目的を「一括 Failure 読取後の修正」に変える）

F-4 は「自律調査 Tool 選択」実験には向かない。

---

## 7. Tool 説明 — 現状の可視 vs Dispatcher

| name | LLM に見えている | Dispatcher / handler が実際に使う |
| --- | --- | --- |
| get_current_failure | 名前、`(none)`、1行（error, traceback, return_value, warnings, source に言及） | 引数なし。セッション全返し |
| read_file | path, offset, limit。offset は 1-based と description | path 必須。offset/limit 任意 |
| search_files | query, path, glob | query 必須 |
| list_files | path, recursive, glob | すべて任意（default path=.） |
| search_web | query, limit | query 必須 |
| read_url_text | url, max_bytes, timeout_seconds | url 必須 |
| read_pdf | path, page, max_chars | path 必須。ライブラリ無ければ error |
| get_execution_environment | `(none)` + 何を返すか1行 | 引数なし |
| get_gpu_status | `(none)` + GPU 項目 | 引数なし |
| get_gpu_processes | `(none)` | 引数なし |
| experiment_test_source | source, function_name。一時ファイルと書く | source 必須。例外なしで pass |
| read_git_diff | `(none)` | 引数なし |
| request_human_help | reason, questions | reason 必須 |

差分の典型: required が LLM 向け一覧に出ていない。return の形が無い。`get_current_failure` の description は「全部入る」と読める。

説明に足しうる候補（採用しない）: name, description, purpose, arguments, required, types, return schema, errors, 使用条件, 例。最低限の実験用は name + purpose + required args + 返す情報の種類、が候補。

---

## 8. Test 設計

現状の `status=pass` は execution_without_exception。

保持する軸の候補（同一視しない）:

- execution_ok（例外なし）
- exception / error_type / traceback
- return_value
- expected（proposal.output 等。実験が何を期待するかは別判断）
- validation（既存 `validate_tool_result`。本番 Schema は変えない。実験が呼ぶだけ）
- warnings / missing_outputs

実験ハーネスは「解決した」フラグを自動で立てない、が候補。LLM 再判断に結果を返す。

---

## 9. Test 結果を LLM へ戻す

### T-1. final 後にハーネスが Test し、結果を user として再投入して続行

現状に近い Dispatcher ループ。`break` をやめ、Test 後もう一周する。

### T-2. LLM に `experiment_test_source` を自分で選ばせる

修正案提出と Test 実行を別 Tool 選択として観測できる。

### T-3. native tool の tool ロールで Test 結果を返す

A-2 と組む。

比較: T-1 は「Test を LLM が選んだ」とは言えない。T-2 は Tool 利用と Test を分けて観測しやすい。T-3 は本番 Agent に近い。

---

## 10. ログ

保存候補（形式未決）:

- request: model, messages（送信時点のコピー）, tool definitions（使った場合）, options, timestamp
- response: raw, parsed, parser_error
- tool: name, arguments, result, error, truncated?
- test: patch, result, return_value, validation（呼んだ場合）
- turn: 上記を時系列で id 付け

現状 `turns[].raw` だけでは不足。messages 全文を turn ごとに残すのが候補。

---

## 11. Parser

現状: JSON only 要求 + greedy 抽出 + 短い再指示。

候補（実装しない）:

- P-1: 全文 JSON のみ。失敗は再指示。greedy をやめる  
- P-2: markdown code fence 内 JSON だけ拾う  
- P-3: native tool_calls を正本にし、content JSON は使わない（A-2）  
- P-4: 失敗内容を parser_error として保存し、再指示文を固定テンプレで変えない

「壊れた JSON」を修復して実行するかは未決。修復すると「モデルが出した Tool」と「parser が推測した Tool」が混ざる。

---

## 12. 停滞・タイムアウト・HELP

停止条件は決めない。ログが turn ごとに tool / test / parsed action を持てば、後から同一 Tool・同一 patch・時間を数えられる。

HELP: `request_human_help` の呼び出しと final.help を turn に残す。状態機械は作らない。

---

## 13. 観測の分離（設計上の置き方）

| 観測 | ログ上の置き場の候補 |
| --- | --- |
| Tool 利用 | requested name ≠ 一括 Failure Tool だけか |
| 情報理解 | Tool 結果後の次 action が変わるか |
| 修正 | patch_source の有無 |
| Test | execution / return_value / validation を別フィールド |
| 再評価 | Test 結果を見たあとの action |
| 脱出 | help / 別 patch / 別 tool |
