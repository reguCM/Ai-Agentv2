# Tool Calling 非対応 LLM による判断層の成立性実験

**採用 LLM / Schema / Mapping 規則 / Controller / Native Tool Calling 採否 / FA / 本番接続は決めない。**  
既存 Problem Analysis / Problem Solving / Tool Calling圧縮実験・fixture・結果は変更していない。接続していない。

`tools=` は渡していない。Schema は要求していない。Mapping は **仮** で、**M1 のみ自動実行**。正式規則ではない。

Prompt: `Analyze the problem and indicate the next investigation or action needed.`

一次資料:

- `results/20260901T020948Z/`（Gemma のみ。DeepSeek が文脈長で中断した実行）
- `results/20260901T021334Z/`（Gemma / DeepSeek / Qwen。調査結果の返し方を短くしたあと）

2回を混ぜて「1つの成功」にしない。温度 0 でも Gemma の Mapping 結果は一致していない。

---

## 初期 Failure（事実）

実 pytest / `python main.py`。人工エラーではない。

- `pick_bin(bins, 2)`、`bins = ['empty']`、`helper.py:10 IndexError`
- traceback に `main.py` と `helper.py`
- `config.py` / `gate.py` は traceback に出ない
- `BIN_SPAN=3` だけでは `dock` で落ちることは単体テストで確認済み

---

## 事実 / 推測 / 未観測

混ぜない。

### Phase 1: LLM 単体の判断（3モデル、本文）

**事実（Gemma, 両 run の Turn 1）**

- IndexError、`bins` が 1 要素、index 2、を本文で述べている
- `assemble_pack` / `pick_bin` / `helper.py` / `main.py` / テストを名指ししている
- 次に `bins` の生成を見る必要がある、と書いている

**事実（DeepSeek Turn 1, 021334Z）**

- 同じ IndexError 認識
- `helper.py` の `pick_bin` を review、`assemble_pack` を check、テストを debug 実行、と書いている

**事実（Qwen Turn 1, 021334Z）**

- IndexError と `bins=['empty']` を述べている
- `assemble_pack` の中で `bins` がどう作られるかを調べよ、テストが `bins` を渡していない可能性、と書いている
- ファイル名 `helper.py` は、この Turn の Mapping 対象としては取れていない（M4）

**推測にしないこと**

- 「判断できたから採用できる」とはしない
- unknown_information は Schema で取っていない（`NOT_EXTRACTED`）。本文から人間が読む

### Phase 2: 仮 Mapping

**事実**

| 出力 | 仮分類 | 自動実行 |
| --- | --- | --- |
| Gemma 020948Z Turn 1「コード断片 + ファイル名」 | M1 `read_file` | した |
| Gemma 021334Z Turn 1 同趣旨だが「Inspect assemble_pack」「Specific Code to Focus On: helper.py」 | M2（ファイル名はあるが read 意図が機械的に取れない） | していない |
| Qwen「Inspect assemble_pack Logic」 | M4 | していない |
| DeepSeek「Review pick_bin」かつ「Run the Test with Debugging」 | M1 として **先に `run_test`** | した |
| 「`bins` の生成元」に相当する Qwen 文 | ファイル名なし → M4 | していない |

**これは LLM 失敗ではない場合がある（指示書 10）**

- Gemma 2回目: 判断本文はファイルを名指ししている。M1 にならなかったのは **仮 Mapping の不足**
- Qwen: `assemble_pack` を調べよは判断として具体。ファイルへ変換できなかったのは Mapping 不足の候補
- DeepSeek: helper を読めという判断と、テストを走れが併記。実行されたのは `run_test`。**判断の第一候補と Mapping の第一件がずれている**

### Phase 3: 実 Tool（Gemma 020948Z のみ連鎖）

**事実**

```
read tests/test_main.py
 → テストは bin==ready かつ dock is True を期待している、と本文で更新
read main.py
 → load_bins() が短いリストを返している、と更新
read helper.py
 → BIN_LABELS[:BIN_SPAN]、BIN_SPAN は config にある、と更新
```

Turn 4 本文は `` `config. `` で切れ、`config.py` の読取は M2 で **実行されなかった**。

**推測**

- 内部では config を読む判断をしていた可能性がある
- 出力切断が Mapping 不能の直接原因だった可能性もある。どちらが主因かは **NOT_DETERMINED**

### Phase 4: Test 後再判断（Gemma 020948Z）

**事実**

- Mapping が code fence の **先頭** を `apply_patch(config.py)` した。中身は例示の `BIN_SPAN = 2`（本文では 3 以上が必要と書いてある）
- pytest は再び IndexError。`bins = ['bin1', 'bin2']`
- 次 Turn で「2 では足りない。3 以上が必要」と本文が更新された
- その修正 fence は M2 で **未適用**
- `gate.py` / `DOCK_OPEN` には到達していない
- 最終 `test_pass: false`

**分離**

- LLM 判断: Test 後に「2 では不足」へ更新した（事実）
- Mapping: 例示 fence を先に適用した（Mapping 側の問題候補）
- これを一つの「Gemma 失敗」にまとめない

---

## 021334Z の 3 モデル（同一 Prompt・同一 Failure）

### Gemma

- 判断本文あり。ファイル名あり。M2 → 次 Turn M4。Tool 0
- 020948Z と判断内容は近い。**実行連鎖は起きなかった**

### DeepSeek

- 判断本文あり
- 4 回連続 `run_test`（同じ Failure が返る）
- helper は読んでいない
- その後 context_length_exceeded
- 同一仮説の繰り返し（範囲ガードとテスト改変の提案）が本文に残る

### Qwen（tools= なし）

- 判断本文あり（IndexError、bins 不足、assemble_pack を調べよ）
- M4。ファイル読取なし
- Native Tool Call は無い（渡していない）
- 本文に判断が出ている。Tool Call 圧縮はこの経路では起きていない

優劣は付けない。

---

## Level（観測分類。採用閾値ではない）

| | Gemma 020948Z | Gemma 021334Z | DeepSeek | Qwen |
| --- | --- | --- | --- | --- |
| 1 エラー意味 | 本文あり | 本文あり | 本文あり | 本文あり |
| 2 不足情報 | bins の生成が不明、と読める | 同 | 実装を見よ、と読める | bins の生成、と読める |
| 3 具体指定 | load_bins / BIN_SPAN | assemble_pack の bins | pick_bin の範囲 | assemble_pack / テスト setup |
| 4 調査対象 | ファイル名あり、かつ読んだ | ファイル名あり、未読 | helper を名指し、未読 | 関数名。ファイルは Mapping 不能 |
| 5 調査方法 | read が M1 になった | inspect が M2 | run_test が M1 | inspect が M4 |
| 6 結果で更新 | テスト期待・load_bins・BIN_SPAN へ更新 | 未到達 | run_test 後もほぼ同文 | 未到達 |
| 7 Test で探索変更 | config の値を 2→3 へ。gate へは行っていない | 未到達 | 未到達 | 未到達 |
| 8 根本まで継続 | gate 未到達。未完 | 未到達 | 未到達 | 未到達 |

---

## 分析 A–G（一つの成功/失敗にしない）

### A. LLM が判断したか

3 モデルとも Phase 1 で IndexError の意味と「bins が短い」ことは本文に出た。  
「正しい根本原因まで述べた」とはしない。

### B. 機械的 Mapping できたか

できた場合とできない場合が両方ある。Gemma 同一趣旨の 2 出力で M1 と M2 に割れた。仮 Mapping は脆い。正式規則にはしない。

### C. Mapping された Tool が正しかったか

- Gemma の read 連鎖: 調査としては妥当なファイルだった（事実。正解ルートを事前に教えてはいない）
- Gemma の apply_patch: 本文の意図（SPAN=3）と、適用された fence（SPAN=2）が不一致
- DeepSeek の run_test: 併記された review helper より先にテスト再実行が選ばれた

### D. Tool 結果の解釈

Gemma 020948Z は読んだ内容に応じて原因記述を更新した。DeepSeek は run_test の同じ Failure を繰り返し受け取っている。

### E. Test 結果で判断更新

Gemma 020948Z: あり（2 では不足）。  
他: Test 後ループに入っていない、または同じテストを繰り返した。

### F. 探索範囲変更

Gemma 020948Z: tests → main → helper →（本文上）config。config 読取は未実行。gate なし。  
他: 変更なし、または Mapping が実行していない。

### G. 根本原因へ近づいたか

Gemma 020948Z は `BIN_SPAN` まで本文で到達した。`DOCK_OPEN` には到達していない。他は未到達。

---

## 成功事例として価値があるもの（誘導していない）

Gemma 020948Z の読取連鎖は、指示書 21 の形に **部分的に** 近い。

```
Failure
 → helper/main/tests が必要という判断
 → Mapping が read
 → load_bins と BIN_SPAN
 → config を直す判断
```

ただし:

- config 読取は切断で落ちた
- 適用された patch は例示の SPAN=2
- dock の第二 Failure には未到達
- 同じ Gemma の再実行では Mapping が M2 で連鎖が起きなかった

「再現する成功ルート」としては未確立。

## 失敗事例として残すもの

DeepSeek: 判断では helper を見る必要があるとしつつ、Mapping が `run_test` を繰り返し、文脈長で停止。

```
問題認識更新なし（本文がほぼ固定）
探索範囲変更なし
同一アクションの繰り返し
```

Qwen: 判断は出るが Mapping 不能（M4）。LLM 失敗と Mapping 不能を同一視しない。

---

## 仮説 A / B について

仮説 A（非 Tool Calling でも判断を文章で出せる）: **この実行では Phase 1 として成立の証拠がある。** 3 モデルとも本文に判断が出た。

仮説 B（判断と Mapping+実行を分離できる）: **部分的。** 分離したログは取れた（`llm_decision` と `mapping_result` は別キー）。一方、仮 Mapping が判断の第一件を落とす・取り違える例があり、分離したあと自動 Tool まで安定してはいない。

Native Tool Calling 必須とはしない。Schema もこの結果だけでは採用しない（指示書 26 の Phase 6）。

---

## 最終的な問い

> Tool Calling が無い LLM でも、判断層を担当できるか。

**観測:** 担当の入力（Failure の理解、不足、次に見たいもの）は本文として取り出せた。  
**未観測 / 不足:** その判断を毎回機械的に Tool へ落とすこと、Test 後に第二原因まで辿ること、同一モデルでの Mapping 再現。

> 判断を機械的 Mapping で Tool にできるか。

**M1 のときだけ** できた。M2/M4 は判断があっても実行していない。これは LLM 失敗と分けて **Mapping 能力の不足** として記録する。

> 人間が情報を足していくようなループを再現できるか。

Gemma 020948Z では読取のたびに判断が更新された。再現条件は未確立。DeepSeek / Qwen 021334Z ではそのループに入っていない。

---

## 次（仕様ではない）

Phase 6 の Schema を急がない。先に必要なのは、仮 Mapping が M2 を落とす例と、fence 先頭を誤適用する例を、判断失敗と混ぜずに残すこと。

実行: `python -m research.llm_benchmarks.judgment_layer_experiment.bench`
