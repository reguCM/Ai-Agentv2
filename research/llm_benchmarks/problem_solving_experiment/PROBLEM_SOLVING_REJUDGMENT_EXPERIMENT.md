# Test後再判断実験

**Schema / FA / 本番接続 / 「失敗N回で別ファイル」ルールは採用しない。**  
既存の実コード実験・成功事例・fixture は変更していない。混ぜない。

一次資料: `results/problem_solving_rejudgment/20260901T012916Z/`

Prompt は全件 `Analyze the problem and resolve it.` のみ。Tool 一覧・import 調査・別ファイル指示は入れてない。

---

## 観測事実

### 1. 初期 Failure

実実行。人工エラー文は無い。

- pytest exit 1。stdout に `pick_status(rows, 2)`、`rows = ['LoadPercentage', 'Idle']`、`helper.py:10 IndexError`。
- `python main.py` exit 1。stderr に同じ IndexError。`main.py` と `helper.py` が traceback に出る。

fixture（LLM には構造を知らせていない）:

- `config.FIELD_COUNT = 2` のため rows が 2 要素
- `runtime.READY = False`
- テストは `status == "Busy"` かつ `ready is True`

`FIELD_COUNT` だけ直しても ready で落ちることは、実験側の単体テストで確認済み。

### 2. 最初の LLM 判断

**DeepSeek**（`tools` 未使用。Ollama が tools パラメータを拒否）  
IndexError。`pick_status` に範囲チェック、`rows` を `['LoadPercentage', 'Idle']` にハードコード、テスト期待を `default_status` に合わせる、と文章で提案。

**Qwen**（native `apply_patch`）  
thinking 上、index 2 が長さ 2 に対して範囲外。`main.py` の index を 1 にすればよい、と判断。コードは読んでいない（`files_read` 空）。

### 3. 最初に調査した対象

DeepSeek: 調査 Tool なし。  
Qwen: `read_file` / `list_files` / `search_files` なし。最初の行動は `apply_patch(main.py)`。

### 4. 最初の修正

DeepSeek: 未適用。workspace 無差分。

Qwen Turn 1 `main.py` を置き換え:

- `load_report_rows` / `report_ready` / `json` / `__main__` を削除
- `rows = ['LoadPercentage', 'Idle']`
- `pick_status(rows, 1)`
- `ready` キーなし

### 5. Test 結果（最初の修正後）

Qwen: pytest exit 1。`NameError: pick_status is not defined`。  
`python main.py` exit 0 だが `__main__` が無いため stdout 空。  
`test_pass: false`。`first_patch_test_pass: false`。

この結果は `sent_to_llm` に原文のまま返している。別ファイル指示は無い。

### 6. Test 結果を見た LLM の判断

Qwen Turn 2: 同じ `main.py` に `from helper import pick_status` を足す。index 1 とハードコード rows は維持。

DeepSeek Turn 2: 一次方程式の別問題。Test フィードバック自体が無い（修正未適用のため）。

### 7. Test 後に新しい調査をしたか

Qwen: `read_file` は一度も無い。新しいファイルを開いていない。  
Turn 5 の本文で `helper.py` の `report_ready` を `return True` にせよと書くが、`apply_patch` していない。

### 8. 探索範囲が変化したか

適用された変更は **すべて `main.py`**。`helper.py` / `config.py` / `runtime.py` は最終 workspace でも初期のまま。

```text
Turn1 main.py（index 1、import 削除）
Turn2 同ファイル（import 復帰）
Turn3 同ファイル（Idle → Busy をハードコード）
Turn4 同ファイル（ready: report_ready() を追加）
Turn5 helper を文章で指名、未適用
```

依存先ファイルへの移動は、適用ログ上は起きていない。

### 9. 修正方針が変化したか

Qwen は Test のたびに **main.py 内の方針を変えている**。

| 後 | pytest | 次の修正 |
| --- | --- | --- |
| Turn1 | NameError pick_status | import を戻す |
| Turn2 | `Idle` != `Busy` | リストに Busy を埋め込む |
| Turn3 | KeyError `ready` | `ready` キーを足す |
| Turn4 | `False is True` | helper.report_ready を True にせよ（未適用） |

同じガードを繰り返してはいない。同じファイルへの再パッチではある。

### 10. 再 Test 結果

4 回とも pytest exit 1。最終:

- `assert report["ready"] is True` → `False is True`
- main.py: ハードコード `['LoadPercentage', 'Busy']` + `report_ready()`
- `runtime.READY` は False のまま
- `test_pass: false`

### 11. DeepSeek / Qwen の差（優劣にしない）

- DeepSeek: 修正未適用。Test 後再判断のループに入れない。
- Qwen: 修正→実 Test→結果返却→再修正が 4 周した。最初の修正では Test 成功していない（偶然の成功ではない）。
- Qwen の再判断は **同一ファイル内の対症療法** が中心。config / runtime には到達していない。

### 12. Controller なしで成立した部分

- 実エラーを渡す
- Qwen が自発的に `apply_patch` する
- ハーネスが修正後に実 Test し、誘導文なしで結果を返す
- Qwen が失敗内容（NameError / Idle / ready 欠落 / False）に応じて次のパッチ内容を変える

「失敗したら別ファイルを見ろ」は書いていない。それでも **失敗の種類に合わせて修正内容は変わった。**

### 13. 現時点で成立していない部分

- DeepSeek 側の実ファイル修正と Test ループ
- Test 失敗後に **依存ファイルを読む** こと（Qwen の `files_read` は常に空）
- `runtime.READY` / `FIELD_COUNT` への到達
- Turn 5 で書いた helper 修正の適用
- pytest 通過と `{"status":"Busy","ready":true}` の実測

ケース分類（失敗回数とは独立）:

- Qwen Turn2–4: **ケース1**（失敗 → 同じファイルを再修正）
- ケース2/3（依存先・import 元ファイルの確認）: **未観測**
- Turn5: helper を原因として名指ししたが未適用。ケース4の途中まで、とは言えるが完了していない

### 14. 次に必要な実験

確定仕様ではない。観測ギャップから:

- 同一ファイル再パッチが続くとき、読取が後から起きるか（今回は起きなかった）
- helper を文章で指名したあと、適用まで行くか
- DeepSeek が tools 無しでも named fence を適用できる別経路が要るか（今回の fence 検出は `# helper.py` 形式で、提案は検出されず）

---

## 分析区分（指示書 14）

| 区分 | この実行 |
| --- | --- |
| ① 認識更新 | Qwen: IndexError → NameError → 値の不一致 → ready 欠落 → ready False。更新あり |
| ② 探索範囲変更 | 適用先は main.py のまま。ファイル間移動なし |
| ③ 修正方針変更 | あり（index、import、ハードコード値、ready キー） |
| ④ Test 無視 | 同じパッチのコピペ繰り返しは無い。失敗を見てはいる |
| ⑤ 偶然の成功 | 該当しない。初回修正では Test 失敗 |

「Qwen は常に深掘りできる」「失敗回数で上層へ移る」「PA が必須」とはしない。

確認できた一点:

> 実 Test 失敗を返すと、Qwen はこの条件で **問題認識と main.py 上の修正方針を更新した。**  
> **依存先へ探索を広げて再修正する** ところまでは、この実行では成立していない。

実行: `python -m research.llm_benchmarks.problem_solving_experiment.rejudgment_bench`
