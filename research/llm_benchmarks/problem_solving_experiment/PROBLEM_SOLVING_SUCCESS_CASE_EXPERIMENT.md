# Problem Solving 成功事例探索実験

**Problem Analysis の正式採用・Schema・Tool Mapping 仕様・FA・本番接続はしない。**

目的は成功事例そのものと、そこに入らなかった経路の観察である。型に事例を合わせない。

- 実行: `20260901T004252Z`
- ハーネス: `problem_solving_success_case_bench.py`
- fixture: `fixtures/cross_file_index_error/`
- 生ログ: `results/problem_solving_success_case/20260901T004252Z/{deepseek,qwen3_14b}/cross_file_index_error.json`
- Prompt は全ターン同一ヘッダ。途中変更なし。Repair は実行していない。

---

## 実験条件

| 項目 | 値 |
| --- | --- |
| モデル | `deepseek-coder-v2:16b`, `qwen3:14b` |
| temperature | 0 |
| Tool catalog を LLM に提示 | しない |
| `tools=` | 渡さない |
| 初期 Prompt | `Analyze the problem below.` / `Do not fix the problem yet.` |
| 初期入力 | Failure JSON + 実 traceback のみ |
| helper.py / config.py | 初期入力に含めない（漏洩なし） |
| 実験側 Mapping | NL から既存 `read_file` / `search_files` / `list_files` へ。正式 Schema ではない |
| 1ターンあたりの Tool | 最大 1 |
| 上限 | 6 ターン |
| 修正の適用 / 再実行 | しない |

Mapping は実験記録用の機械変換である。採用仕様ではない。

---

## fixture 構成

```text
main.py
  from helper import load_rows
  rows = load_rows()
  value = rows[2]          ← IndexError はここで発生

helper.py
  from config import FIELD_COUNT, STATUS_LABELS
  return list(STATUS_LABELS[:FIELD_COUNT])

config.py
  STATUS_LABELS = ["LoadPercentage", "Idle", "Busy"]   # 3 要素
  FIELD_COUNT = 2                                      # 先頭 2 要素だけ返す
```

Ground truth（LLM には未提示）:

- traceback に出るのは `main.py` の `rows[2]` だけ。helper / config はスタックに乗らない。
- `rows` の長さは helper と config を見ないと確定できない。
- 意図した調査連鎖の一例は `main.py` → `helper.py` → `config.py`。強制はしていない。

実 traceback（改変なし）:

```text
File "...\fixtures\cross_file_index_error\main.py", line 11, in <module>
    print(run())
File "...\fixtures\cross_file_index_error\main.py", line 6, in run
    value = rows[2]
IndexError: list index out of range
```

---

## 初期入力

Failure:

```json
{
  "tool_name": "cross_file_index_error",
  "status": "fail",
  "error_type": "IndexError",
  "error": "list index out of range"
}
```

加えて上記 traceback。source 全文は付けていない。会話も付けていない。

---

## DeepSeek — 失敗（早期修正）

1 ターン。Tool 0。`stop_reason: no_mappable_request`。

### Turn 1

**事実認識:** IndexError、`rows[2]`、リストに index 2 が無い。

**未知:** `rows` の生成元・長さ・呼び出し関係は特定していない。`helper.py` は出てこない。

**追加情報要求:** なし。Mapping も空。曖昧な「コードが必要」すら無い。

**修正への飛躍:** `len(rows) > 2` のガードと、`rows` を関数内で埋め直す例。

これは指示書の失敗例1に該当する。

```text
Failure + traceback
    ↓
rows が短いと推測
    ↓
len() チェックを提案
    ↓
調査連鎖は始まらない
```

最終: 原因特定なし（生成元未確認）。修正方針は提案。修正実行なし。Test なし。解決とはしない。

---

## Qwen — 部分的成功（調査は進み、config 未取得で停止）

5 ターン。Tool 4。読んだファイルは `helper.py` のみ。

**重要:** Tool 呼び出しの一部は LLM の要求ではなく、実験側 Mapping の取り違えである。混同しない。

### Turn 1

事実: `rows[2]` が範囲外。仮説: 未初期化 / 入力不足 / off-by-one。

要求の自然言語: `inspect how rows is constructed in the run function`。

Mapping が実行したのは `search_files(query="run")`。同時に抽出候補へ `and` も乗っていた（英語の接続詞）。実行は先頭の `run` のみ。

これは「helper.py を読め」ではない。関数名 `run` への検索として機械変換された。

### Turn 2（search `run` の後）

変化: `run()` の定義行は分かったが、`rows` の中身は分からない、と明示。

要求: `inspect the code inside the run() function` / `how rows is populated`。

Mapping: `search_files(query="rows")`。候補には `is` / `call` も混入。実行は `rows`。

**この結果が調査の転換点になった。** 一致行に次が含まれる。

- `helper.py`: `def load_rows():`
- `main.py`: `from helper import load_rows`
- `main.py`: `rows = load_rows()`
- `main.py`: `value = rows[2]`

### Turn 3（search `rows` の後）

変化: 対象が `helper.load_rows` に絞られた。ファイル読み仮説（空ファイル、splitlines）をまだ置く。`data.txt` の架空修正例を出す。

自然言語では `Inspect load_rows() in helper.py` がある。

Mapping は **先頭出現の `helper.py` が事実の言い直しだったため `filename_mentioned_without_request` とし、後段の Inspect を落とす。** 代わりに `search_files(query="may")`（`may fail` の助動詞）を実行。一致 0 件。

これは LLM が `may` を調べたいと言ったのではない。Mapping の誤変換である。

### Turn 4（search `may` の後）

Qwen は空検索を「無関係」と切り、再び `Inspect load_rows() in helper.py` を最重要とする。

今回は `read_file(helper.py)` に接続できた。

同時に `main.py` も Mapping 候補になったが、1 Tool/ターンのため未実行。

### Turn 5（helper.py 取得後）

変化（入力に基づく）:

- `load_rows` は `STATUS_LABELS[:FIELD_COUNT]` を返す。
- 値は `config.py` 由来。

ここまでは helper 本文から確認できる。

確認していないのに書いていること:

- 例として `FIELD_COUNT = 2` と `STATUS_LABELS = ["A", "B"]` を置く（後者は実 fixture と異なる。実 `STATUS_LABELS` は 3 要素）。
- guard clause と config 値の変更案。

自然言語の次手: `Inspect config.py`。

Mapping: 先頭の `config.py` が「from config.py」の説明だったため未接続。調査停止。

config.py は読んでいない。原因の値は未確定。修正は実行していない。

---

## 成功 / 失敗判定

指示書の最重要成功条件:

> 現在の情報では足りないことを認識し、具体的な追加情報を要求し、その要求で Tool 取得が行われ、結果で分析を更新できること。

| ケース | 判定 | 根拠 |
| --- | --- | --- |
| DeepSeek | **失敗**（早期修正） | 不足の認識がファイル要求にならず、len チェックへ飛んだ |
| Qwen | **部分的成功** | `rows` の生成が不明 → 検索結果で helper を知る → helper 本文で `FIELD_COUNT` / `STATUS_LABELS` に更新。config 未読のまま推測修正へ入った |

Qwen を「完全な原因特定」や「問題解決」にはしない。例外は消していない。config の実値は未確認。

---

## 成功経路の図式化（Qwen、実測。理想図ではない）

```text
Failure + traceback (main.py / rows[2])
    ↓
不足: rows の作り方が不明
    ↓
実験側 Mapping: search_files("run")     ← LLM は「run を検索」とは書いていない
    ↓
分析ほぼ維持（定義行だけでは不足）
    ↓
Mapping: search_files("rows")           ← 「rows の初期化を見よ」から変換
    ↓
helper.load_rows と import 関係が表に出る
    ↓
分析更新: 対象は helper.py の load_rows
    ↓
Mapping 誤変換: search_files("may")     ← LLM 要求ではない
    ↓
空結果を無関係と切り、再び helper.py を要求
    ↓
read_file(helper.py)
    ↓
分析更新: STATUS_LABELS[:FIELD_COUNT]、値は config
    ↓
config.py を Inspect と書くが Mapping されず停止
    ↓
未確認の config 例とガード修正を提案
```

理想として書いた `main.py を読め → helper → config` とは異なる。Qwen は **変数名 `rows` の検索** で別ファイルに到達した。指示どおり、合理的な別経路として記録する。

---

## 失敗経路

```text
DeepSeek:
  traceback の rows[2]
      ↓
  長さ不足と推測
      ↓
  len チェック（ファイルを読まない）
```

```text
Qwen 後半:
  helper 本文取得
      ↓
  config が必要と書く
      ↓
  Mapping が接続しない / 値を例示で埋める
      ↓
  未確認のまま修正案
```

```text
Mapping 失敗（実験側）:
  helper.py / config.py の後段 Inspect を取りこぼす
  英語単語 (and, is, may, call) を識別子として検索する
```

誤ファイル要求（存在しない `utils.py` を指定）は、今回の生出力には無い。

無限探索は 6 ターン上限まで達していない。停止は「Mapping できる要求が無い」判定。

---

## LLM が自然に行った行動

- 両モデル: traceback から `rows[2]` / IndexError を事実として使う。
- DeepSeek: 仮説をすぐ修正コードにする。
- Qwen: 「中身が見えない」と繰り返し、生成関数へ対象を移す。
- Qwen: Tool の JSON（path / line / text）を読んで次の仮説を更新できる。
- Qwen: 空の検索結果を原因にしない。
- どちらも Tool 名 `read_file` は自ら書いていない。

---

## 人間 / 実験側が誘導しないとできなかったこと

- Tool catalog を見せていないので、LLM は Tool 名を選んでいない。接続はすべて実験側。
- DeepSeek に「ファイルを読め」とは言っていない。言わなければ読まなかった。
- Qwen の `search_files("run"|"may")` は、人間が「この文は検索クエリだ」と解釈した産物。LLM の明示クエリではない。
- `config.py` の Inspect は文面にあるが、現行 Mapping では Tool にならなかった。
- 修正の実行・再テストはしていない（禁止どおり）。

---

## Tool へ機械的に接続できた要求 / できなかった要求

接続できた（結果として Tool が走った）:

| 自然言語の核 | 変換 | 妥当性 |
| --- | --- | --- |
| inspect … `run` function | `search_files(query="run")` | 弱い。関数名ではあるが検索指示ではない |
| how `rows` is populated | `search_files(query="rows")` | 変数名は具体。結果は有用 |
| Inspect `load_rows()` in `helper.py`（Turn 4） | `read_file(helper.py)` | 具体。接続として妥当 |

接続できなかった / 誤接続:

| 自然言語 | 結果 |
| --- | --- |
| DeepSeek の len 修正のみ | 要求なし |
| Qwen Turn 3 の Inspect helper.py | 同一メッセージ先頭の言及が事実扱いで落ちた |
| Qwen Turn 5 の Inspect config.py | 同上 |
| `may fail` / `and validate` | 誤って search 候補化。`may` は実行された |

「ログを確認してください」型の粗い要求は、DeepSeek には出なかった（要求自体が無い）。Qwen は関数・ファイルまで下りることが多かった。

---

## Tool 結果による分析変更

| 後 | 変化 |
| --- | --- |
| search `run` | ほぼ維持。不足の明示が強まる |
| search `rows` | **更新。** helper.load_rows が候補の中心になる |
| search `may` | 原因仮説は変わらない。ノイズと判定 |
| read helper.py | **更新。** スライスと config 由来シンボルへ |

最初の判断（`rows` が短い）は維持しつつ、短さの所在が「main の index」から「load_rows のスライス」へ移った。

---

## 調査停止の判断

- DeepSeek: 調査せず修正へ。停止は Mapping 空。
- Qwen: config を Inspect と書いた直後に、値の例示とガード修正へ。Mapping が config を取らなかったことも停止理由。LLM が「これ以上調査不要」と明示したわけではない。

十分な情報で止まった、とは言えない。config の実値は未読。

---

## 修正へ飛躍したケース

- DeepSeek Turn 1: 典型。
- Qwen: 調査中も概念修正（len、data.txt、ガード）を混ぜる。helper 取得後は config 未読のまま値の書き換え例を出す。
- `Do not fix the problem yet.` は修正文の抑制にはなっていない。

---

## モデル間の違い

主目的は経路が成立するかであり、優劣ではない。

| | DeepSeek | Qwen |
| --- | --- | --- |
| 調査連鎖 | 始まらない | search → helper 読取まで |
| 追加情報の具体性 | なし | 関数・変数・ファイル名 |
| Tool 後の更新 | なし | あり |
| 修正飛躍 | 直後 | 調査と並行、終盤で強い |
| Mapping ノイズの影響 | 受けていない（要求なし） | `may` で 1 ターン消費 |

---

## 発見された共通構造（1 本の部分成功から。一般化しない）

この回で観測できた流れは次に近い。

```text
Failure 上の記号（rows[2], run）
    ↓
その記号の生成箇所が未知
    ↓
（Qwen）生成に関する名前でリポジトリ内を探す / ファイルを読む
    ↓
別ファイルが表に出る
    ↓
分析対象が移る
    ↓
さらに import 先が未知として残る
```

DeepSeek ではこの流れは起きなかった。**成功事例に入らない問題がある**、という前提は今回も成り立つ。

複数成功事例の共通型、とはまだ言えない。事例は実質 Qwen 1 本の部分成功である。

---

## この成功事例から今後の設計に利用できそうな考え方

仕様ではない。材料である。

- traceback の発生行だけでは別ファイル原因に届かないことがある。足りなさの認識が次の取得を駆動する。
- 「`rows` はどこで作られるか」は `search_files` に落ち得て、その結果が `read_file` より先に別ファイル名を渡すことがある。
- Tool 結果を要約せず JSON のまま返すと、Qwen は path/line/text を使えた。
- 要求がファイル名を含んでも、事実の言い直しと Inspect が同一出力に混在すると、単純な機械変換は落とすか誤る。
- 英語の一般語を識別子として検索すると、LLM が頼んでいない調査が挟まる。
- 会話（前回実験）ではなく Failure+traceback でも、モデルによっては実装修正へ飛ぶ。

---

## この成功事例だけでは決められないこと

- Problem Analysis を独立段階にするか
- 不足情報を必ず出力させるか
- Tool Mapping の正式規則
- search を先に置くか read を先に置くか
- DeepSeek 側を「できない」と断定すること（1 ケース）
- config まで読ませれば原因確定・正しい修正になること
- 今回の Mapping 実装を採用すること

---

## まだ分からないこと

- Mapping の「後段の Inspect を拾う」変更で config まで連鎖するか（今回は結果を見て Prompt / Mapping を変えて再実行していない）
- LLM に Tool 名を出させず、人間変換だけにしたことが連鎖の本態なのか
- `Do not fix yet` 以外の止め方が調査を伸ばすか（今回は追加していない）
- 同じ fixture を別モデル・別温度で再現できるか

実行: `python -m research.llm_benchmarks.problem_solving_experiment.problem_solving_success_case_bench`
