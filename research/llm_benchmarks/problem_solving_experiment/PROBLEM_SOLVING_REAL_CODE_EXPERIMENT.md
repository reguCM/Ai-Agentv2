# 実コード・実エラー Problem Solving 実験

**Schema / Tool Mapping / FA / 本番接続 / 上層 switch 規則は採用しない。**  
既存の Problem Analysis 実験結果は、今回の成功証拠に混ぜない。

一次資料: `results/problem_solving_real_code/20260901T011636Z/`

途中で Qwen の native tool メッセージ形式が壊れて aborted した実行 `20260901T011427Z` は不完全。比較対象は **011636Z** のみ。

---

## 事実

### 実験条件

| 項目 | 値 |
| --- | --- |
| モデル | `deepseek-coder-v2:16b`, `qwen3:14b` |
| temperature | 0 |
| 作業ディレクトリ | モデルごとに fixture をコピーした独立 workspace |
| Prompt | 「この問題を解決してください」+ 実実行結果。import 先・traceback・PA・読むファイルは指定していない |
| Tool | `list_files` / `read_file` / `search_files` / `write_file` / `run_tests`（workspace 内のみ） |
| 修正後 | 実験側が pytest と `python main.py` を再実行し、生出力を返した |

DeepSeek は Ollama が `tools` パラメータを拒否し、テキストのみ。Qwen は native tool_calls を使用した。

### fixture と初期実行

コードは実際に import し、Python で実行した。エラー文は実験者が作っていない。

```text
main.py  → helper.pick_status(rows, 2)
helper.py → STATUS_LABELS[:FIELD_COUNT]
config.py → FIELD_COUNT = 2, STATUS_LABELS は 3 要素
tests/test_main.py → status == "Busy"
```

初期実行（`initial_execution/`）:

- `python main.py`: exit_code 1。stderr に実 traceback。`main.py` と `helper.py:9` の `IndexError: list index out of range`。
- pytest: exit_code 1。失敗内容は **stdout**（stderr は空）。`rows = ['LoadPercentage', 'Idle']`, `index = 2`。

pytest の traceback フィールドは stderr だけ見ているためログ上は空。LLM への入力には stdout 全文が入っている。

### DeepSeek がしたこと

一次資料: `deepseek/run.json`

- Turn 1: Tool なし。pytest 出力上の `rows` 長さ 2 と `index` 2 を述べる。
- 提案: `pick_status` に範囲チェック、テストを `index 0` に合わせる。コードを `main.py` に置く例（実ファイルでは `pick_status` は helper.py）。
- `write_file` も named fence も無く、**ファイルは変化していない**（`final_git_diff` 空、modifications 0、tests 0）。
- Turn 2: 連分数の別問題。Tool なし。idle 停止。

探索経路: コードを読んでいない。修正は未適用。Test 再実行なし。

### Qwen がしたこと

一次資料: `qwen3_14b/run.json` および `qwen3_14b/workspace/`

Tool 順:

1. `list_files` — 引数に `tool` が入れ子 → TypeError
2. `list_files(glob="*.py")` — トップの `config.py` / `helper.py` / `main.py`（`tests/` は出ない）
3. `read_file(helper.py)` と `read_file(main.py)`
4. `read_file(config.py)`
5. `write_file(config.py)` — `FIELD_COUNT = 3`

探索経路（ログから）:

```text
list_files（失敗）
 ↓
list_files
 ↓
helper.py + main.py
 ↓
config.py
 ↓
config.py を書き込み
```

修正は 1 回。適用済み git diff:

```text
-FIELD_COUNT = 2
+FIELD_COUNT = 3
```

`main.py` と `helper.py` は最終 workspace でも初期と同じ。

修正後の実実行（実験側）:

- pytest: exit_code 0, `1 passed`
- `python main.py`: exit_code 0, stdout `{"status": "Busy"}`

Turn 6–7: Tool なしの説明文。idle 停止。

`run_tests` Tool は LLM が呼んでいない。再実行は実験側の「修正後は必ず実行」による。

### 修正回数と探索範囲

Qwen は Test 失敗を複数回受けてから別ファイルへ行った、という経路ではない。コードを読んでから **最初の書き込みで config を変え、その Test は通っている。**

DeepSeek は修正 0 回。

### 成功事例条件（判定を混同しない）

| 条件 | DeepSeek | Qwen |
| --- | --- | --- |
| 実際の Failure があった | はい（初期実行） | はい |
| 実際のコードを調査した | いいえ（Tool 0） | はい（list / read） |
| 実際に修正した | いいえ（未適用） | はい（config.py） |
| 実 Test 通過 | 未実行 | pytest exit 0 |
| 期待動作の確認 | 未確認 | pytest の `Busy` と main の `{"status": "Busy"}` が一致 |

`solution_correct` はハーネスで自動判定していない。Qwen について `execution_fixed` と、テストが定義した `status == "Busy"` に対する `behavior_verified` は、上記の実出力から確認できる。それ以外の仕様上の正しさは未判定。

---

## 考察（一次資料の後。実験前の仮説を結果として書かない）

### A. エラー理解

両モデルとも初期出力の IndexError と index 2 を使っている。Qwen はファイル読後に `FIELD_COUNT = 2` とスライスを結び付けた。DeepSeek はテストを index 0 に合わせる案を出しており、`Busy` という期待は使っていない。

### B. 初期探索

Qwen はまず一覧、続けて traceback に出ている helper / main。DeepSeek は Tool を使わず、実行ログ上の断片だけで提案した。

### C. 局所修正

DeepSeek の提案は helper ではなく main に関数を置く例と、テスト側の期待変更。未適用。  
Qwen の適用修正は **config.py のみ**。発生行のガードではない。

### D. Test 後の変化

Qwen は修正後の成功出力を受けて、追加調査せず説明で止まった。失敗が続いて探索が広がった事例は無い。

### E. 探索範囲

Qwen: 一覧 → helper/main → import 元の config。無関係なリポジトリ外ファイルは読んでいない。`tests/test_main.py` は Tool では読んでいない。

### F. 仮説更新

Qwen の thinking では、範囲チェックやテスト不正の案が出たあと、config を読んで `FIELD_COUNT` に寄っている。最終の適用は後者。DeepSeek は仮説をコードで検証していない。

### G. 根本原因

config の `FIELD_COUNT = 2` と main の index 2 の不一致が、初期の `rows` 長さ 2 を説明する。Qwen はそこに書き込んだ。DeepSeek は未到達。

### H. 不要な探索

Qwen Turn 1 の壊れた `list_files` 引数は無駄な 1 回。DeepSeek Turn 2 は課題と無関係。

### DeepSeek と Qwen の違い（優劣にはしない）

- Tool: Qwen は native。DeepSeek はこの環境で `tools` 未対応、JSON Tool も出さなかった。
- 調査: Qwen はファイルを読んだ。DeepSeek は読まずにパッチ文を出した。
- 修正適用: Qwen 1 ファイル。DeepSeek 0。
- 実 Test: Qwen のみ通過を観測。

同じ Prompt・同じ初期 Failure でも、経路は一致していない。

### 今回決めないこと

Problem Analysis の独立、Schema、Mapping、FA、失敗 N 回で別ファイル、traceback 必読、依存必追、モデル優劣。いずれも正式仕様にしない。

観測できたのは、**実コードと実エラーに対して、あるモデルは参照先まで読んで設定を変え、別のモデルはログ上の提案で止まった** ことである。

実行: `python -m research.llm_benchmarks.problem_solving_experiment.real_code_bench`
