# Problem Solving 調査連鎖条件探索

**Schema / Tool Mapping 仕様 / FA / 本番接続の採用判断はしない。**  
成功判定（問題が解けた）は作っていない。既存実験結果は変更していない。

目的は、追加調査が始まる条件と、崩れる条件を観察することである。

- 実行: `20260901T005736Z`
- 生ログ: `results/problem_solving_chain_conditions/20260901T005736Z/{deepseek,qwen3_14b}/{F*_S*}.json`
- Prompt は全件同一。途中変更なし。thinking は比較軸にしない。

観測フラグ（`investigation_started` 等）はログ補助。DeepSeek の「To fix this you need to…」も request 語に当たるため、**フラグだけで判断しない。** 以下は `raw_output` を読んだ記録。

---

## 1. 実験条件

| 項目 | 値 |
| --- | --- |
| モデル | `deepseek-coder-v2:16b`, `qwen3:14b` |
| temperature | 0 |
| Prompt | `Analyze the problem below.` / `Do not fix the problem.` / `Do not use tools.` |
| 初期入力 | Failure + traceback。source はケースごとに S1〜S3 |
| LLM への Tool catalog | なし |
| `tools=` | 渡さない |
| Mapping | 別ログ。fixture 内 `.py` の read_file のみ。`search_files` は使わない |
| 修正の実行 | しない |

前回成功事例との差（同時に変わっているので単一原因にしない）:

- Prompt に `Do not use tools.` がある（前回は無し、`Do not fix the problem yet.`）
- Mapping が識別子検索をしない
- fixture パスが `chain_conditions/` 配下

全組合せは回していない。F1〜F6 の差が出やすい 7 条件 × 2 モデル。

---

## 2. fixture 構造

```text
F1 直接参照     main.run → helper.pick_status → rows[2]
                traceback に helper.py が出る

F2 1段階間接    main.rows[2] ← helper.load_rows ← config.FIELD_COUNT
                traceback は main.py のみ（F4 もこの構造）

F3 複数参照     main が helper と validator を import
                例外は rows[2]。validator は list 型チェックのみ

F6 誤誘導       main が data["cpu"] → KeyError
                実キーは config.METRIC_KEY = "cpu_percent"
```

source:

- S1: Failure + traceback
- S2: + main.py
- S3: + main.py + helper.py（config 本文は渡さない。F5 用）

実施したケース: `F1_S1`, `F2_S1`, `F2_S2`, `F2_S3`, `F3_S2`, `F6_S1`, `F6_S2`。

---

## 3. ケース別結果

自然文は正規化せず、要求は原文の意味で書く。全文は JSON。

### F1_S1（traceback に helper.py）

**DeepSeek**

- 既知: IndexError、`pick_status`、`rows` の index 2、traceback 上の main / helper。
- 未知として明示しない。`rows` が未初期化と断定しがち。
- Turn 1 で main.py と helper.py の両方に言及。Mapping は **main.py を read_file**（同一段落に `shows` + 両方のファイル名。先頭が main）。
- Turn 2: main 本文を読んでも `rows` 初期化が無いと言う。helper.py の取得要求は出さない。修正方針（3要素保証）は Turn 1 からある。

**Qwen**

- `helper.py` line 3 の `rows[2]` を事実として述べる。
- 追加情報要求なし。ファイル名は原因の場所として出るが Inspect ではない。
- パッチなし。

### F2_S1 / F4（traceback は main のみ、source なし）

**DeepSeek:** `rows[2]` → `len(rows) > 2` パッチ。helper / config なし。早期修正。

**Qwen:** 短いリスト・データ不足・ガード欠如を列挙。`helper.py` を出さない。パッチコードなし。ファイル要求なし。

### F2_S2（main.py 本文あり）

**DeepSeek:** `load_rows()` が3要素未満と述べ、**main に len チェック**。helper 本文は要求しない。

**Qwen:** `load_rows()` が短い、またはデータ源が想定外、と断定調。helper.py 要求なし。パッチなし。

### F2_S3 / F5（main + helper、config なし）

**DeepSeek:** `STATUS_LABELS[:FIELD_COUNT]` が短いと理解したうえで、**main の len チェック**。config.py を読めとは言わない。

**Qwen:** `config.py` の `FIELD_COUNT` が 3 未満（例: 2 or 0）と述べる。これは helper 本文からの推論。`Inspect config.py` は無い。実値は未取得のまま断定。

### F3_S2（main に helper と validator）

**DeepSeek:** validator には触れず（コード引用には `validate_rows` が残る）、len チェック。参照先の区別なし。全部読め、とも言わない。

**Qwen:** `load_rows()` の不足 **または** `validate_rows()` が行数を減らした、の二候補。validator は実際には長さを変えない。どちらも読めとは言わない。

### F6_S1（KeyError `'cpu'`、source なし）

**DeepSeek:** キー欠落 → `.get("cpu")` / `in` チェック。helper/config なし。

**Qwen:** 構造の不一致と書く。パッチなし。ファイル要求なし。

### F6_S2（main 本文あり）

**DeepSeek:** `load_metrics` が `'cpu'` を返せ、かつ `.get`。実装は見ない。

**Qwen:** 原因は `helper` の `load_metrics`。別キー名（`"CPU"` / `"cpu_usage"`）の可能性に触れる。config.py も METRIC_KEY も要求しない。パッチなし。

---

## 4. DeepSeek / Qwen 比較

モデル優劣は付けない。差の位置だけ。

| 段階 | DeepSeek | Qwen |
| --- | --- | --- |
| 問題理解 | traceback の例外と行を使う | 同様 |
| 情報不足認識 | 弱い。長さ/キー欠落で足りるとする | 関数名までは出すことが多い。ファイル取得にはしない |
| 調査要求 | F1 でファイル名が出る。他は修正文の need | Inspect/read がほぼ無い |
| Mapping→Tool | F1 のみ main.py を読んだ | 0 回 |
| 結果理解 | main を読んでも helper へ進まない | Tool なし |
| 追加調査 | 連鎖なし | 連鎖なし |
| 修正 | ほぼ全ケースでパッチ例 | この回はコードブロックが少ない |

前回成功事例（Qwen が `rows` 検索相当まで行った）と、今回 Qwen がファイル要求しないことは両立する。Prompt・Mapping・fixture が同時に違う。

---

## 5. 調査連鎖が発生した条件

今回、**2 ファイル以上を辿る連鎖は観測されていない。**

起きたことに限定する:

- **traceback に helper.py がある（F1）** と、DeepSeek は helper を場所として述べ、実験側 Mapping がファイル読取を 1 回走らせた。読んだのは main.py。
- **helper 本文を最初から与える（F2_S3）** と、両モデルとも `FIELD_COUNT` / `config.py` に言及できる（Qwen はファイル名、DeepSeek はスライス式）。これは「読んだ結果から次ファイルを要求した」ではなく、**入力に helper があったので次シンボルが見えた**。

---

## 6. 調査連鎖が発生しなかった条件

- F2_S1: traceback に参照先が出ない。DeepSeek は len 修正。Qwen は一般原因列挙で停止。
- F2_S2: import が見えても helper 本文を要求しない。
- F3_S2: 二つの import があっても、どちらを読むかの具体要求にならない。
- F6: KeyError が main のキー欠落に見え、参照先 B（config のキー名）へ戻らない。
- F1 の DeepSeek Turn 2: 別ファイルを 1 つ読んでも、次の helper.py 要求が出ない。
- F2_S3: config の必要性は文章になるが、取得要求（Inspect）にならない。Qwen は値を推測で埋める。

---

## 7. Mapping 上の問題

LLM 出力は書き換えていない。変換は別ログ。

- `search_files("may")` は今回発生していない（識別子検索を止めたため）。
- F1 DeepSeek: 同一チャンクに `shows` と `main.py` / `helper.py`。先頭の main.py が選ばれた。traceback 上の本当の発生ファイルは helper。
- `shows` / `need to`（修正文）が request 語として効く。
- すでに prompt にある source は `source_already_in_prompt` で読まない。F2_S3 の helper.py 言及は変換されない（意図どおり）。
- Qwen F2_S3 の `config.py` は事実の断定であり、同一チャンクに Inspect が無いので未変換。これは Mapping が要求を消したのではなく、**要求形式になっていない**。

---

## 8. 修正への飛躍

隠さない。

- DeepSeek: F2 / F3 / F6 で len チェックまたは `.get`。F2_S3 では helper を見ても main を直す。
- Qwen: この回はパッチ例が少ない。代わりに原因断定（FIELD_COUNT が 2 未満、load_metrics のキー名）で埋める。
- `Do not fix the problem.` は DeepSeek のパッチを止めていない。

---

## 9. 確認できた事実

問いへの答え（この実験範囲）。

**問い1 何が分からないか:** Failure+traceback だけでも例外の意味は両モデルが述べる。参照先の中身が未知だ、とファイル要求まで落とすことは、今回ほとんど無い。

**問い2 helper.py を確認する、の具体化:** traceback に helper がある F1 ではファイル名が出る。traceback に無い F2_S1 では出ない。main の import（F2_S2）でも「helper.py を確認」にはならない。

**問い3 helper のあと config:** S3 で helper を最初から渡すと config / FIELD_COUNT に言及する。S1 から helper を自分で取って、その結果で config を要求する経路は今回無い。

**問い4 仮説が外れたとき調査に戻るか:** F6 では戻らない。DeepSeek は `.get`。Qwen は mismatch と書くが config は取らない。F3 で validator を疑っても読まない。

**問い5 調査対象の誤り方:** 対象を誤って別ファイルを指定する、より、**調査せず発生行を直す** / **次ファイルを推測で埋める**。DeepSeek F1 では Mapping が helper ではなく main を読んだ。

**問い6 差の位置:** DeepSeek は修正例へ早い。Qwen はこの Prompt では分析文で止まり、前回のような多段 Tool 連鎖は再現しなかった。

---

## 10. 仮説（未採用）

確定しない。

- `Do not use tools.` が、Inspect / read という調査要求を抑えている可能性がある。
- traceback にファイル名があることは、場所の言及を増やす。取得要求や正しい Mapping とは別。
- source を足すと参照シンボルは見えるが、DeepSeek はそれでも発生行パッチに戻りやすい。
- 最初の仮説（長さ、キー欠落）が例外型から強いとき、参照先 B へは自然には戻らない。
- 前回 Qwen の連鎖は、この条件セットでは再現条件になっていない。

独立段階にするか、は結果を見たあとの検討材料に留める。今回は **採用しない。**

観察された流れは、指示書の長い鎖より短いことが多い。

```text
Failure + traceback
    ↓
例外の言い直し
    ↓
（DeepSeek）発生行のガード
  または
（Qwen）関数/設定の断定
```

ファイル取得と再分析が挟まるのは F1 DeepSeek の 1 回だけで、しかも次ファイルへ繋がっていない。

---

## 11. 未確定事項

- 同じ fixture で `Do not use tools.` を外したときの差（今回は Prompt を変えて再実行していない）
- Mapping が helper.py を先に読んだ場合、DeepSeek が config へ進むか
- S4（複数ファイルを最初から渡す）の効果
- F3 で validator と helper の本文を片方だけ渡した場合
- 1 温度・1 ケース繰り返しでの安定性
- Problem Analysis を独立段階にするか
- Tool Mapping をどこに置くか

実行: `python -m research.llm_benchmarks.problem_solving_experiment.chain_conditions_bench`
