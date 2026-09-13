# Tool Calling圧縮仮説・比較実験

**Schema / FA / Controller / Tool Mapping / 本番接続 / モデル採用は決めない。**  
既存 Problem Analysis / Problem Solving 実験・fixture・結果は変更していない。接続していない。

一次資料: `results/20260901T014622Z/`

Prompt は全件 `Resolve the problem.` のみ。探索手順・Tool 利用・思考過程の出力は要求していない。

経路:

- **native**: Ollama `tools=`。実行するのは structured tool call のみ。テキストからの Tool 抽出は使っていない（`application_side_tool_parsing: not_used`）
- **text**: `tools=` なし。Tool は実行しない。1 Turn

モデル: `qwen3:14b` / `gemma3:12b`。temperature 0。fixture `ticket_stage_v1`（既存 fixture ではない）。

---

## 観測事実 / 推測 / 未観測

この3つを混ぜない。

### 初期 Failure（事実）

実 pytest / `python main.py`。人工エラー文は無い。

- pytest exit 1。`select_stage(rows, 2)`、`rows = ['queued']`、`helper.py:10 IndexError`
- traceback に `main.py` と `helper.py` が出る。`config.py` / `flags.py` は出ない
- `python main.py` exit 1。同じ IndexError

fixture（LLM には構造を知らせていない）:

- `config.STAGE_LIMIT = 1` のため rows が 1 要素
- `flags.WINDOW_OPEN = False`
- テストは `stage == "closed"` かつ `window is True`
- `STAGE_LIMIT=3` だけでは window で落ちることは単体テストで確認済み

---

## 経路 B（Tool なし）

### Qwen3:14b text（事実）

- `analysis_observable: true`
- `tool_selection_observable: false`
- assistant 本文: IndexError、`rows` が 1 要素、`select_stage(rows, 2)` が範囲外、と書いている
- 提案: テスト側で `rows` を 3 要素にする。本文はコードフェンス開始で切れている
- `read_file` 等は呼ばれていない（経路上実行しない）
- `thinking_observed: true`。思考過程は Prompt で要求していない。分析の外部観測には使わない

### Gemma3:12b text（事実）

- `analysis_observable: true`
- IndexError、`rows[2]`、`['queued']` を分解している
- 「`main.py` と `helper.py` の全文が無いと正確な修正は難しい」と書いている
- 範囲チェック、`rows` の充足、index 2 が必要か、の選択肢を文章で出している
- Tool は実行していない
- `thinking_observed: false`

### 経路 B について断定しないこと（推測と未観測）

- 推測: 両モデルとも Failure テキストから IndexError の場所は復元できている
- 未観測: その文章が「十分に問題を分解した」かどうか。今回は外部に文章が出た、という事実だけを取る
- 「Tool が無いから分析能力が高い」とはしない

---

## 経路 A（Native Tool Calling）

### Gemma3:12b native（事実）

- Ollama 400: `gemma3:12b does not support tools`
- `stop_reason: native_tools_unsupported`
- Native 経路の Tool 選択・Test 後再判断は **NOT_OBSERVED**
- Gemma が Tool を使えない能力不足、とはこの実験では言わない。API が tools を拒否した

Qwen と Gemma の Native 比較は成立していない。

### Qwen3:14b native（事実）

`stop_reason: idle_no_native_tool`。6 Turn。`read_file` / `list_files` / `search_files` は 0 回。変更ファイルは `helper.py` のみ。

| Turn | 可視 content | native tool | Test |
| --- | --- | --- | --- |
| 1 | 空 | `apply_patch(helper.py)` 範囲チェック付き IndexError。import / `load_stages` / `window_open` を削除 | pytest ImportError `load_stages` |
| 2 | 空 | 同ファイルに import と関数を戻し、IndexError は維持 | 明示 IndexError `Index 2 out of range for rows ['queued']` |
| 3 | 空 | なし | なし |
| 4 | 空 | 範囲外なら `rows[-1]` | pytest `assert 'queued' == 'closed'`。`python main.py` は `{"stage": "queued", "window": false}` |
| 5 | `To resolve the test` | なし | なし |
| 6 | STAGE_LIMIT / config / `main.py` の index 変更を文章で提案 | なし（未適用） | なし |

機械フラグ（run 全体）:

- `analysis_observable: true`（Turn 5–6 に本文があるため。Turn 1–4 の Tool 呼び出し時は false）
- `tool_selection_observable: true`
- `tool_call_without_visible_content_any: true`
- `visible_content_with_tool_call_any: false`（Tool と同時に本文は出ていない）
- `search_scope_changed: false`（新規 `files_read` なし）
- `same_file_repatch_events`: Turn 2, 4（いずれも `helper.py`、Test 失敗後）
- `final_test_pass: false`
- `hypothesis_updated` / `tool_result_used` / `test_feedback_used`: 機械側は `NOT_DETERMINED`

最終 workspace: `config.py` / `flags.py` / `main.py` は初期のまま。`helper.py` だけ範囲外で最後の要素を返す。

---

## Pattern（事実としての当てはめ）

誘導していない。ログから後付けで見る。

- **Pattern 1**: Turn 1。Failure → `apply_patch(helper.py)`。なぜ helper かは可視本文に無い
- **Pattern 2**: Tool Result → 次 Tool は成立（Turn 1→2、2 のあと Turn 4）。間の Turn 3 は空
- **Pattern 3**: Test 失敗後に **別ファイル調査** は無い
- **Pattern 4**: 失敗を重ねても適用先は `helper.py`。Turn 6 で config / main に言及するが Tool なし
- **Pattern 5**: Test 前に config まで読む、は無い

失敗回数と switch は別値。今回 switch（別ファイルへ探索）は Tool ログ上 0。失敗は 3 回ある。

---

## 分類 A–H

モデル優劣ではない。この実行のラベル。

### Qwen native

- **A**: Tool 呼び出し Turn では不成立。Tool が止まった Turn 5–6 では文章が出た
- **B/C**: 初手 `helper.py` は traceback に helper があるので「全く無関係なファイル」ではない。ただし **選んだ根拠の本文は無い → C**
- **D**: 初手で helper を丸ごと短く書き、`load_stages` を消した。直後 ImportError。選択が失敗に直結した事実はある
- **E**: ImportError を受けて関数を戻しているので、少なくともその Test 結果は次パッチに使われている（推測ではなくパッチ内容の差）
- **F**: 不成立ではない。失敗種別が IndexError 明示 → `queued != closed` と変わったあと、範囲外を raise から `rows[-1]` に変えている
- **G**: 不成立。config / flags を読んでいない
- **H**: 成立。Test 後も `helper.py` に留まった

### Qwen text / Gemma text

- **A**: IndexError の分解が本文にある
- Tool 選択関連の B–H は経路上対象外
- Gemma text は不足情報として `main.py` / `helper.py` を名指ししている。Qwen text はテスト修正を先に書いている

### Gemma native

- 全項目 **NOT_OBSERVED**（tools 非対応）

---

## 独立評価（指示書 24）

| フラグ | Qwen text | Qwen native | Gemma text | Gemma native |
| --- | --- | --- | --- | --- |
| analysis_observable | true（本文） | Tool 中は false。終盤 true | true | NOT_OBSERVED |
| tool_selection_observable | false | true | false | NOT_OBSERVED |
| tool_result_used | 対象外 | パッチ内容が Test 後に変化（事実）。内部利用は NOT_DETERMINED | 対象外 | NOT_OBSERVED |
| hypothesis_updated | NOT_DETERMINED | NOT_DETERMINED | NOT_DETERMINED | NOT_OBSERVED |
| search_scope_changed | 対象外 | false（読取なし） | 対象外 | NOT_OBSERVED |
| test_feedback_used | 対象外 | 次パッチが失敗内容に応じて変化（事実） | 対象外 | NOT_OBSERVED |
| final_test_pass | 未実行 | false | 未実行 | NOT_OBSERVED |

---

## Native と text の比較（同一 Failure）

事実:

- Qwen text: Failure → 原因と修正案が **assistant content** に出る
- Qwen native: Failure → **content 空** + `apply_patch`
- 同じモデルでも、Tool Calling 中は問題分析に相当する **外部観測可能な出力が減少した**

断定しない:

- 「Tool Calling によって問題分析が消えた」
- 「内部では分析している」（解釈 A）
- 「分析せず Tool に飛んだ」（解釈 B）

Turn 1–4 は `thinking_observed: true` の Turn がある。保存はした。Prompt で出させていない。これを読んで A の証拠にはしない。外部ログとしての分析は **空の content + Tool Call** である。

解釈 A/B は **判別不能**。

---

## 最終的な問いへの答え

問: Tool Calling 時に「問題分析 → 調査対象決定 → Tool 選択」は内部にあり圧縮されているだけか、分析せず Tool に飛んでいるのか。

この実行から言えること:

1. **外部ログ** では、Qwen native の Tool 使用 Turn は Tool Call に圧縮されて見える。なぜその Tool / ファイルかは本文に無い。
2. 同じ Qwen の text 経路では、Failure 認識と修正案が本文に出る。
3. 内部で同じ判断をしていたかは、この実験では **判別不能**。
4. Gemma では Native 経路自体が観測できないので、圧縮仮説のモデル間比較は未成立。
5. Test 結果を返すと、Qwen native は **同じファイルの修正内容** を変えた。依存先ファイルへ探索を広げた記録は無い。

---

## 人間 Controller なしで成立した部分

- 実 Failure を渡す
- Qwen が native `apply_patch` を出す
- ハーネスが修正後に実 Test し、誘導文なしで結果を返す
- Qwen が失敗種別の変化に応じて helper の中身を変える

## 成立していない部分

- Gemma native
- Native 中の問題分析の外部復元
- `read_file` による調査
- config / flags への探索範囲 switch
- pytest 通過
- 解釈 A と B の区別

## 次に必要な実験（仕様ではない）

- Native tools を両方サポートするモデル対での同一比較（今回 Gemma は経路 A が欠測）
- Tool 呼び出し Turn に本文が乗るか、乗らないかが再現するか
- text 経路で「ファイルが必要」と書いたあと、Native では即 `apply_patch` するかの対

実行: `python -m research.llm_benchmarks.tool_calling_compression_experiment.bench`
