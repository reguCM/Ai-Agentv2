# 非Tool Calling LLM 判断層・実コード接続実験

**実験日:** 2026-09-01  
**Native Tool Calling:** 未使用（`tools=` 未渡し）  
**既存実験 / 既存 Mapping / 本番 Agent / Registry:** 未変更・未 import  
**一次資料:** `results/20260901T033113Z/`  
**LLM なし回帰:** `tests/research/llm_benchmarks/judgment_layer_llm_connection_experiment` と既存 19 件を合わせて **31 passed**

断定しない: 非TC LLM で十分か、Qwen/Gemma 採用、Controller、正式 Bridge 仕様。

観測事実 / 推測 / 未観測を分ける。

---

## 1. 実験目的

Tool Calling を持たない LLM に「次に何をすべきか」だけ判断させ、専用 Bridge が Action → 検証 → Tool へ落とせるかを測る。LLM に Tool を直接呼ばせない。

---

## 2. fixture

専用 `fixtures/slot_ready/`（既存 fixture を改変していない）

```text
main.py → helper.py → config.py
tests/test_main.py
```

`FIELD_COUNT = 1`, `READY = False`。テストは `item == "gamma"` かつ `ready is True`。  
この構造は Prompt に書いていない。

---

## 3. 初期 Failure（実測）

人工文は渡していない。`python main.py` と `pytest tests/test_main.py -q` の出力をそのまま渡した。

- pytest exit 1。stdout に `IndexError: list index out of range`、`main.py:6`、`items[2]`
- `python main.py` exit 1。stderr に同じ IndexError（helper 経由の traceback を含む）
- pytest の `traceback` 欄は空（pytest 出力に `Traceback (most recent call last):` が無い）。失敗情報は stdout にある

一次資料: `initial_execution/pytest.json`, `python_main.json`, `PROMPT.txt`

---

## 4. Prompt

本文は `Resolve the problem.` のみ。続けて実 pytest / main 出力。  
ファイルを読め、helper を見ろ、Test を回せ、といった探索指示は入れていない。

---

## 5. 使用モデル

インストール済みを使用。追加 pull なし。

| モデル | 用途 |
| --- | --- |
| qwen3:14b | 判断層 |
| gemma3:12b | 同一条件の比較 |

temperature 0、`tools` 非渡し、max_turns 6。fixture / Prompt / Bridge / Test は共通。

---

## 6. LLM raw output

補正せず Bridge へ入力。全文は各 `*/run.json` の `raw_output`。

要約（事実）:

**Qwen Turn 1–2:** IndexError と `load_items()` が短い可能性を述べ、テストを mock する修正案と `assemble` の長さチェック案をコードフェンスで出す。`helper.py` / `config.py` を「読め」とは書いていない。

**Gemma Turn 1:** IndexError と `items[2]`。`assemble` に長さチェックを入れる案。末尾で `main.py` と `load_items()` に言及。

**Gemma Turn 2:** `main.py` 返却後も長さチェック案。`helper.py` を import していることに触れる。

**Gemma Turn 3:** `load_items` が `LABELS[:FIELD_COUNT]` であることと `config.py` の `FIELD_COUNT` を inspect する必要があると書く。

**Gemma Turn 4:** `FIELD_COUNT = 1` を踏まえ `config.py` を `FIELD_COUNT = 3` / `READY = False` にする例を出す。

**Gemma Turn 5:** config.py を開いて `FIELD_COUNT` を 3 にし、tests と main を再実行せよ、と手順を書く。

---

## 7. LLM判断

機械抽出した「判断」欄は無い。`extracted_judgment` は文分割結果。人間が raw から読んだ内容は 6 に同じ。  
「LLM が正しい判断をした」とは評価しない。分離フラグは `split_flags`。

---

## 8. Action候補 / 9. Bridge変換 / 10. 機械検証

### LLM なし（Phase 1–2）

naive 全文正規表現（フェンス無視・1 Tool）で過去失敗を再現し、専用 Bridge で回帰:

| 失敗例 | naive（再現） | Bridge（修正後） |
| --- | --- | --- |
| 1 `helper.pyを確認したい。` | 認識なし | `read_file(helper.py)` |
| 2 `Testをもう一度実行する。` | 認識なし | `run_test` |
| 3 1+2 | 両方は出ない | `read_file` のあと `run_test` |
| 4 フェンス内 READY/TEST | `apply_patch` 等を誤選択 | `read_file(helper.py)` のみ |
| 5 二ファイル確認 | `読む` があるとき 1 件だけ | `helper.py` 然后 `config.py` |

曖昧文 `もう少し調べる必要がある` は実行なし。

### LLM 接続後（事実）

**Qwen:** 両 Turn `selected_actions: []`。`mapping_status: needs_clarification`。`split_flags.bridge_missed_named_inspect: true`（raw に `main.py` と inspect 語があるが、対象付き inspect Action になっていない）。フェンスのテスト修正は `修正する` が無いため apply_patch にならない。

**Gemma T1:** `read_file(main.py)`（文末の examine / `main.py`）。  
**T2:** `read_file` が `helper.py` → `main.py` → `helper.py`（同一 Turn で 3 件。tests は選ばれていない）。  
**T3:** `read_file(config.py)`。  
**T4–T5:** 候補なし `mapping_gap`。T4 は変更例フェンスがあるが patch 語彙なし。T5 は `Open` / `Modify` / `Run your tests` で、現行語彙（`確認`/`修正する`/`run tests`）に合わない。

これは **LLM が何も言っていないのではなく、Bridge が実行可能な Action に落としていない** ケースを含む。Qwen がソースを読めと言っていない部分は判断側の観測。

---

## 11. Tool実行結果

専用 `workspace.dispatch` のみ。本番 Registry なし。

- Gemma の read_file は ok。`next_input` に実ファイル本文。
- apply_patch / run_test は LLM 経路では選ばれず未実行（この run）。
- LLM なし `test_real_failure_to_tool` では read_file 成功。

---

## 12. LLMへの返却

読取成功時: `You asked to inspect {path}.` + 本文。  
Action なし: `No executable action was derived from the last message.`（やり方は指示していない）

---

## 13. 再判断

Gemma は main.py 返却後に helper 経由の理解へ進み、config.py を inspect した（T3）。探索対象は変わっている。  
Qwen は Action なし通知のあと、テスト mock 手順を繰り返した。Tool 結果を見ていない。

---

## 14. 再Action

Gemma T2–T3 で追加 read。T4–T5 は gap。修正 Tool は出なかった。

---

## 15. 修正

workspace 上の apply_patch は LLM ループでは 0 回。config.py は初期のまま。

---

## 16. Test結果

両モデルとも最終 pytest exit 1（`run.json` の各 turn `pytest_exit_code`）。Test Pass なし。

---

## 17. 成功/失敗（分離）

| フラグ | Qwen | Gemma | LLMなし Bridge |
| --- | --- | --- | --- |
| judgment_success | 未断定。IndexError は述べている。次手はテスト改変が中心 | 未断定。T3 で config を見る判断がある | 固定文では N/A |
| action_extraction_success | 実行 Action 0 | T1–T3 で read_file。T4–T5 なし | 失敗例 1–5 は回帰成功 |
| mechanical_validation_success | 実行対象なし | 読取は通過 | 対象付き read は通過 |
| tool_execution_success | 未実行 | read_file ok | read_file ok |
| test_success | false | false | fixture 初期は fail（想定） |
| behavior_success | false | false | 二段パッチは本 LLM run 外 |
| rejudgment_success | Tool 結果なし | 読取後に config へ進んだ（事実） | 固定文では成立 |

全ループ（修正→Pass）は **今回の LLM 接続では未成立**。

---

## 18. LLM失敗と Bridge失敗の切り分け

混同しない。

**Bridge 失敗（raw に実行要求があるが変換できない）観測:**

- Gemma T4: config.py を `FIELD_COUNT = 3` にする例。`修正する` が無く apply_patch なし。
- Gemma T5: Open / Modify / Run your tests。現行語彙外で mapping_gap。
- Qwen: テストファイルをフェンスで書き換えよ。patch 語彙なし。`main.py` 言及と inspect 語が同一節に無いため named inspect も落ちる（`bridge_missed_named_inspect`）。

**LLM 側の観測（Bridge が拾う形の「ファイルを確認せよ」が薄い）:**

- Qwen は helper.py / config.py を読む次手を書いていない。mock テストを主解にしている。
- Gemma T1 の第一関心は assemble の防御的修正。config に至るのは読取後。

**Tool 失敗:** 本 run の read_file 成功分では未観測。

**Validation が正しい Action を拒否:** 本 run では未観測。

Qwen を「判断できないモデル」とはしない。Gemma を「採用」ともしない。

---

## 19. Qwen / Gemma 比較

同一 fixture / Prompt / Bridge / 温度。モデルだけ違う。

| | Qwen3:14b | Gemma3:12b |
| --- | --- | --- |
| stop | idle_no_action（2 Turn） | idle_no_action（5 Turn） |
| Tool | なし | read_file 複数 Turn |
| config への言及 | なし（raw 要約の範囲） | T3 で inspect し読取 |
| 修正の適用 | なし | なし（Bridge が patch 未選択） |
| Test Pass | なし | なし |

優劣の採用判断はしない。接続が Gemma の読取連鎖では部分的に動いた、という事実のみ。

---

## 20. Cursor 既存観測との比較

Cursor 再実験なし。既存観測の参考:

Cursor: 一覧 → 複数ファイル読取 → 依存を見て修正 → pytest。  
本 run: Gemma は読取で config に到達した。一覧 Tool は使っていない。複数ファイル修正と pytest 適用は未到達。Prompt で Cursor 手順は示していない。

---

## 21. 未観測事項

- DeepSeek はこの実験に未接続
- apply_patch が LLM 経由で成功する経路
- Test Pass 後の終了
- Native Tool Calling との対比
- `Run your tests` や `Open the file` を語彙に足した場合の副作用
- READY=False のまま FIELD_COUNT だけ直したときの二段 Failure（LLM がそこまで進んでいない）

---

## 22. 次の実験候補

採用ではない。候補のみ。

1. Gemma T4/T5 の raw を固定入力にして、patch / run_test 抽出の回帰を足す（過剰辞書化はしない）。
2. Action なしの返却文が LLM を「手順説明」へ固定していないか確認する。
3. 1 モデルで Turn を増やし、patch 語が自然に出るか見る。
4. 既存 19 件は維持したまま、本ディレクトリの失敗例テストだけを育てる。

---

## Phase 実施状況

| Phase | 内容 | 結果 |
| --- | --- | --- |
| 0 | 隔離 | 専用 dir。既存パッケージ未 import |
| 1 | naive で失敗再現 | pytest で 5 件の naive 失敗を固定 |
| 2 | Bridge 修正と回帰 | 失敗例 1–5 を Bridge が通す。既存 19 件も通過 |
| 3 | 実 Failure→read_file | LLM なしで成立 |
| 4–5 | 非 TC LLM 接続 | 実施。Gemma は読取まで。Qwen は Action 0 |
| 6 | 結果→再判断 | Gemma で部分観測。Qwen は未到達 |
| 7 | 修正→Test | LLM 経路では未成立 |
| 8 | 別ファイル探索 | Gemma が config.py 読取まで。修正は未 |

---

## 最終問い

非 Tool Calling LLM を判断層にし、Bridge 経由でループを組めるか。

**部分的に組める。** LLM なし Bridge は過去の誤変換を止め、複数 Action を順実行できる。LLM 接続後は、Gemma の自然文から read_file を複数回実行し、結果を返して再判断できた。修正と Test 成功までは、今回の一次ログでは届いていない。届かない理由は「LLM が何も判断していない」だけではなく、**変更・再実行の英語表現を Bridge が Action にしていない**ことも一次 raw から確認できる。

既存 Mapping 全文正規表現には戻していない。
