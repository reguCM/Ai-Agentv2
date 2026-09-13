# 実験観測設計 v1

実装仕様ではない。ログ Schema・状態名は未確定。  
目的は、実験後に「LLM が何を見て、何を要求し、何を受け取り、何を判断し、何を Test し、結果をどう扱ったか」を検証できること。完璧なログ基盤を作ることではない。

一次資料: `harness.py`, `catalog.py`, `dispatch.py`, `adapters.py`, IndexError 結果 JSON, `PROTOCOL_V1.md` / `PROTOCOL_GAP.md` / `PROTOCOL_CODE_MAPPING.md`。

未確定のまま残す: Tool 提示方式、Failure 分離、Test 起動主体、HELP、停滞判定、Timeout、FA。

---

## 1. 観測目的

1 件の実験について、時系列で少なくとも次を追えること。

```
Failure → LLM Input → LLM Output
  → (Tool Call → Tool Result → LLM Input → LLM Output)*
  → Repair Proposal → Test → Test Result
  → LLM Input → LLM Output → Final Decision
```

「結果だけ」ではなく **その時点の LLM Input** を残す。  
ハーネスが組み立てた `messages` と、Ollama に乗った最終リクエストは別物として扱えるようにする（現状、後者の生ログは Repository に無い）。

---

## 2. 観測単位（定義は設計用。ID 形式は未決）

| 単位 | 意味 | 最低限つなぐもの |
| --- | --- | --- |
| Experiment | Failure 1 件の解決試行 | case_id, model, start/end, 終了理由（名称未決） |
| Turn | `chat()` 1 回 | その回の input / output / parsed / parser_status |
| Tool Call | LLM が要求した実行 | turn に紐づく name, arguments |
| Tool Result | Dispatcher が返したもの、および LLM へ送った文 | call に紐づく raw / sent |
| Test | 修正案の検証 1 回 | patch, execution, return_value, validation 等（軸は分離） |
| Decision | その瞬間の分岐の記録 | 名称は候補のみ（continue / tool / repair / test / solved / help / timeout / parse_error 等）。ハーネスが「停滞した」と先に決めない |

Proposal ≠ Successful Repair。Test の execution_success ≠ solution_correct。

---

## 3. 必須観測項目

実験評価に不可欠。欠けているとプロトコル v1 の評価ができない。

### LLM Input（各 Turn）

- その `chat()` 直前の `messages` 全体（system / 過去 assistant / 今回 user を含むコピー）
- model
- `tools=` を付けた場合はその定義。付けない場合は「未送信」と分かる印、および system に埋め込んだ Tool テキスト
- generation に効いている profile 値（model, temperature, num_predict, num_ctx, timeout）

必須な理由: 結果 JSON の output だけでは「何を見たか」が分からない（現状その状態）。

Ollama 生 HTTP ボディは、クライアントが残さない限り必須にしない（下記候補）。ハーネス `messages` と options があれば、実験コード上の入力は再構成できる。

### LLM Output（各 Turn）

- raw content
- timeout の有無

### Parser

- parse 成否
- parsed オブジェクト（成功時）
- 失敗時は失敗したこと。抽出に使った断片があればそれ（greedy の結果など）
- retry したか、その user 文（条件変化）

### Tool Call / Result

- 要求 name, arguments（LLM が出したもの）
- handler の生 result
- LLM へ実際に渡した文字列（JSON 化・3500 切断後）
- 切断したか
- 未知 Tool / TypeError 等の execution_error

### Failure の出所

- 第1 user に載せた初期 Failure（今の `initial_minimal` 相当）
- それ以外で LLM が見た Failure 関連が、どの Turn のどの Tool Result 経由か

必須な理由: 初期投入と Tool 取得を混ぜると「自分で調べた」と評価できない。

### Repair Proposal

- 提案テキスト / source（今の `patch_source`）
- 提案が出た Turn
- 適用したか（今はサンドボックス実行のみ。本番 apply は無い）

`proposal_generated` と `test_execution_success` と `solution_correct` は別。後者は自動必須にしない（未決の判定）。

### Test

- 実行した patch
- exception の有無と error_type / traceback
- return_value
- 呼んだなら validation / warnings / errors（現状パッチ後は未呼び出し）
- `status=pass` を残すなら、**例外なし**なのか他なのかを別フィールドまたは注記で残す。solution_correct と同じキーにしない

### Test → LLM（将来接続するとき）

- Test 結果をどの Turn の input に入れたか
- 情報源が test であること

現状この矢印はコードに無い。接続したら必須。未接続の間は「Test 後 LLM なし」を Experiment に残すのが必須。

### 終了

- ループがなぜ止まったか（final / timeout / MAX_TURNS / その他）。名称は未決
- HELP を要求したか（tool または final.help）

### 時系列

- Turn 順、各 Turn の timestamp
- Tool / Test がどの Turn に属するか

停滞判定はしない。上記があれば後から同じ Tool・同じ patch の繰り返しを数えることができる。

---

## 4. 候補観測項目（必須ではない）

| 項目 | 理由 |
| --- | --- |
| Ollama 生リクエスト / レスポンス全体 | ハーネス messages とクライアント内部差分の証明。無いと「コード上の messages」までしか保証できない |
| `message.tool_calls` 生フィールド | A-2 採用時。今は content のみ使用 |
| catalog の capability / origin | LLM に出していない内部メタ |
| GPU / git / web の生の巨大 payload の無制限保存 | 評価に必要なのは **送った側**（sent）。raw は差分確認用に任意 |
| pytest・本番 test_tool の全 Registry | 実験の sandbox とは別 |
| トークン数・logits | 問題解決過程の再構成に不要 |
| 停滞フラグ・Timeout 秒の仕様値 | 判定未決。時刻列があれば足りる |
| Decision の正式 enum | 候補名のみ |
| 全ファイルの git blob | `read_git_diff` の sent で足りる |
| FA 関連 | 対象外 |

保存すると大きく、評価に直結しないものはここに置く。

---

## 5. 情報源の分類

情報そのものに加え、**どこから LLM の視野に入ったか**。

| 源 | 意味 |
| --- | --- |
| initial_failure | 第1 user の Failure JSON |
| system | SYSTEM（Tool 一覧を含む） |
| previous_turn | 過去の assistant / user |
| tool:\<name\> | その Tool の **sent** 結果 |
| harness_retry | parser 失敗後の再指示 user |
| test_result | Test を LLM に戻した場合 |
| session_not_sent | ハーネス SESSION にあるが、その Turn の messages に無い（今の生 test_result 全体がこれに当たりうる） |

これにより「LLM が Tool で source を取った」と「ハーネスが一括投入した」を分ける。方式（A-1/A-2 や Failure 分割）は決めない。分類だけ用意する。

---

## 6. 現在コードとの対応

| 観測項目 | 生成箇所 | 保存 | 未保存なら取得可能か |
| --- | --- | --- | --- |
| model | harness `MODEL` / profile | 結果 JSON `model` | — |
| start/end | `_now` は turn 後のみ | turn.`at` のみ。experiment 開始終了なし | `run_case` 前後で取れる |
| 初期 Failure | `initial_minimal` 126–136 | **保存される** | — |
| 第1 user 全文 | 133–136 | キーとしては無い。`initial_minimal` から再構成は可能（英文プレフィックスはコード固定） | `_ask` 直前 |
| SYSTEM / Tool テキスト | 33–45 + `llm_catalog_text` | **未保存** | `chat` 直前 `messages[0]` |
| 送信 messages | `_ask` 80–82 | **未保存** | `chat()` 直前の `messages` |
| tools= | 渡していない | 未保存（無いこと自体未記録） | `_ask` の chat kwargs |
| generation options | `llm.chat` が profile を注入 | **未保存** | `get_llm_profile()` または chat 内 `kwargs["options"]` |
| Ollama 生ボディ | Client.chat | **無い** | クライアント改造なしでは不可。必須にしない |
| raw output | `_ask` の content | turns[].`raw` | — |
| parsed | `_parse_action` | turns[].`parsed`（失敗時 null） | 失敗時の regex マッチ断片は未保存。parser 内 |
| parser 失敗 | 151–153 | `notes` に `unparsed_llm_output` のみ | turn に parser_status / retry_prompt を足せる |
| retry user | 153, 179 | **未保存** | その代入直後 |
| tool name | 157–160 | `tools_called` と、成功 parse なら turns.parsed | — |
| tool arguments | 158 | parse 成功 turn の `parsed.arguments` には残る。独立レコードなし | 同 |
| raw tool result | `dispatch` 159 | **未保存** | dispatch 直後、dumps 前 |
| sent tool result | 163–166 | **未保存** | dumps / truncate 直後 |
| truncate | 164–165 | **未保存** | 条件分岐内 |
| get_current_failure 中身 | adapters 36–52 | LLM には送るが JSON に残らない | dispatch 戻り |
| SESSION 生 test_result | set_session 120–125 | **LLM 第1入力にも結果 JSON にも全体は無い** | adapters.SESSION（実行中のみ） |
| patch | 169 | `patch_source` | — |
| Test 実行 | 172–176 | `test_of_patch`（ok/status/return_value/error） | — |
| Test の pass 意味 | adapters 159–161 例外なし | `status=pass` として保存。軸名は混同 | コード注記のみ |
| validation（パッチ後） | 呼ばれない | 無い | 呼べば `validate_tool_result` |
| Test → LLM | なし（break） | 「戻していない」も未明示 | — |
| help | 161–162, 171 | `help` bool | — |
| 終了理由 | break / timeout / ループ満了 | timeout は notes。final は patch 有無。MAX_TURNS 切れは非区別 | loop 条件 |

---

## 7. 現在保存されているもの

IndexError JSON および `run_case` の record:

- case `id`, `model`
- `initial_minimal`
- `turns[].step, at, raw, timeout, parsed`
- `tools_called`（name 列）
- `patch_source`, `final_summary`, `help`
- `test_of_patch`（ok, status, return_value, error, error_type）
- `notes`（unparsed / timeout 等の文字列）

---

## 8. 保存されていないもの（必須に近い欠落）

- 各 `chat()` の messages
- SYSTEM / その時点の Tool 提示文
- `tools=` の有無
- generation options
- Tool 生 result と sent 文字列、truncate フラグ
- retry の user 文
- parser 失敗の詳細
- 情報源ラベル
- Test 後 LLM（経路自体が無い）
- execution_success と solution_correct の分離
- experiment の start/end、明示的終了理由

---

## 9. 保存する場合の候補位置（実装しない）

| 何 | 候補位置 |
| --- | --- |
| messages コピー、options、tools 有無 | `harness._ask` の `chat()` 直前直後 |
| parser 詳細・retry user | `_parse_action` 戻りを広げ、151–153 の代入と一緒に turn へ |
| raw / sent / truncated | `dispatch` 直後〜166 の `user=` まで |
| 初期 Failure と第1 user | 既に `initial_minimal`。user 全文も 136 直後 |
| Test 多軸 | `experiment_test_source` の戻りを分けて record。LLM に戻すなら break をやめた直後の user |
| 終了理由 | `run_case` の各 break 地点 |
| 情報源 | sent を書くときに tool 名を添える。自動投入なら `initial_failure` / `harness_retry` |

本番 `llm.py` を変えなくても、ハーネスが chat に渡す引数を保存すれば実験入力は足りる。Ollama 生ログが要る場合だけクライアント側が候補。

---

## 10. 未確定事項

- A-1 / A-2 / A-3
- Failure をどの単位で Tool 分割するか
- Test を誰が起動するか
- HELP / 停滞 / Timeout の定義と名称
- solution_correct を誰が付けるか（自動にしないのが観測設計上の推奨候補であり、決定ではない）
- FA
- 必須ログの JSON 形・ファイル分割
- Ollama 生ボディを取るか（必須からは外す）

---

## 削ってはいけないもの / 大きくてよいもの

削ると評価不能: LLM input（messages）、その時点の Tool 提示、Tool call、sent Tool result、LLM output、Test 結果、終了の仕方、初期 Failure。

大きくてよい（必須にしない）: Ollama 生トレース、未送信の SESSION 全体の毎回ダンプ、logits。
