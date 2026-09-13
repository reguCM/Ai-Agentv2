# 実コード型・判断ループ最小実験

**Schema / 正式 Mapping / FA / 本番接続 / モデル採用は決めない。**  
既存実験・既存 fixture・本番 Agent には接続していない。Native `tools=` は使っていない。

一次資料: `results/20260901T024054Z/`  
fixture: `order_live_v1`（1ケース）。Qwen 第一候補、Gemma 比較。

Prompt: `Analyze the current problem and determine what should be done next.`  
初期入力は実 pytest / `python main.py` のみ。探索誘導は無い。

---

## 18項目

### 1. 初期 Failure

実実行。

- pytest exit 1。`pick_item(items, 2)`、`items = ['draft']`、`helper.py:10 IndexError`
- traceback に `main.py` と `helper.py`
- `python main.py` も同じ IndexError
- `config.py` / `store.py` は traceback に出ない
- 単体テスト: `ITEM_SPAN=3` だけでは `store` で落ちる

### 2. 最初の LLM 判断

**Qwen:** IndexError。`items` が 1 要素なのに index 2。仮説は「テストが items を渡していない」または「生成ロジックが足りない」。次はテストを 3 要素にして `assemble_order(items)` する、または `pick_item` に範囲チェック、と書いている。

**Gemma:** 同じ IndexError 認識。`items` がなぜ短いのかを `main.py` とテストで辿れ、と書いている。`main.py` / `helper.py` / `tests/test_main.py` の全文を要求している。暫定案として `pick_item` の範囲チェックも出している。

### 3. 最初に要求した情報

**Qwen:** ファイルを「読んでくれ」とは書いていない。テスト修正と `assemble_order` の生成ロジック確認。

**Gemma:** 明示的に 3 ファイルの全文。加えて「Run Tests Again」（変更後、と本文では条件付き）。

### 4. Mapping 成功/失敗

**Qwen Turn 1–2:** `mapping_gap` / `no_mechanical_target`。実行なし。`not_llm_failure: true`。フェンスは `test_assemble_order` だがパスラベルが無く apply 対象にならなかった。

**Gemma Turn 1:** ファイル名は M2（inspect がファイル名の 64 文字以内に無い）。`Run Tests Again` が M1 `run_test` になり **実行された**。判断の第一件（ファイル全文）と、実行された Tool がずれている。

### 5. 実際に読んだファイル

両モデルとも **0**。`files_read: []`

### 6. 最初の修正

なし。`patch_rounds: 0`

### 7. 最初の Test 結果

ハーネスが LLM 修正後に回す Test は無い。  
Gemma の Mapping が初期とほぼ同じ pytest を再実行した。exit 1、同じ IndexError。これは「修正後 Test」ではない。

### 8. Test 結果を受けた判断

Gemma Turn 2–3: 再実行結果のあと `mapping_gap`。ファイル読取には進まなかった。  
Qwen: Tool 結果を受け取っていない。

### 9. 仮説が変化したか

Qwen: テスト不足 / 生成不足 / 範囲チェック。ファイル調査へは移っていない。  
Gemma: Turn 1 で既に「index の出所を見ろ」。再 pytest 後も読取要求は Mapping されず。Test 失敗による問題モデル更新は **確認できない**（同じ Failure が返っただけ）。

### 10. 探索範囲が変化したか

コード読取としては変化なし。

### 11. 別ファイルへ移ったか

移っていない。

### 12. 再修正したか

していない。

### 13. 最終 Test 結果

初期と同じ失敗のまま。`test_pass` は未達。`application_behavior` は初期 NOT_OBSERVED（main は例外）。

### 14. どの判断能力まで成立したか

| Level | Qwen | Gemma |
| --- | --- | --- |
| 1 Failure 理解 | 本文あり | 本文あり |
| 2 必要情報 | 部分（生成ロジック）。ファイル指定は弱い | あり（3 ファイル全文） |
| 3 Mapping 可能な形 | 不成立（inspect + パスが無い） | 部分。パスは出たが M2。実行されたのは run_test |
| 4 取得情報で更新 | 未到達 | 同じ pytest 結果のあと読取に進まず |
| 5 実コード修正 | 未到達 | 未到達 |
| 6 Test 解釈 | 未到達 | 再実行の IndexError は見ている。探索変更は未観測 |
| 7 Test 失敗後の探索変更 | 未到達 | 未到達 |
| 8 複数段解決 | 未到達 | 未到達 |

### 15. Mapping が原因で失敗した部分

- Qwen のラベル無しフェンス → apply しない（Mapping 不能。判断が「テストを直せ」なので、仮に適用しても仕様どおりではない）
- Gemma がファイル名を出しても inspect 近傍条件を満たさず M2
- Gemma の「Run Tests Again」が、ファイル要求より先に実行された

後者は **判断の第一件と Mapping の第一件の不一致**。LLM がファイルを欲しがったこと自体は判断失敗ではない。

### 16. LLM 判断そのものが原因で失敗した部分

- Qwen は traceback に `helper.py` があるのに、次手を「helper を読む」にしていない。テスト改変と範囲ガードを先に置いている
- どちらも `items` の生成元を **ファイルとして** 指定していない（Qwen は関数名、Gemma は「share the complete code」で人間に要求）

### 17. Cursor との行動構造（参考。Cursor を正解にしない）

上位判断実験の Cursor Solver は、workspace 一覧 → テスト → main → helper → config / bay → 修正 → pytest。  
今回のループは、判断文は出るが **読取 Tool に落ちる前に止まっている**。類似は Failure 認識。相違は、環境一覧が無く、Mapping 可能な「inspect &lt;file&gt;」が出ない／拾われないこと。

### 18. 次に必要な実験

大量ケースは増やさない。1ケースの欠測は次:

- 判断は「ファイルが欲しい」なのに Mapping が `run_test` を選ぶずれを、判断失敗と分けたまま再現するか
- `inspect helper.py` と自然に書く条件（Schema なしのまま）があるか

Schema 固定や本番接続は、まだしない。

---

## 4段階の区別（指示書 20）

| | この実行 |
| --- | --- |
| LLM が判断できなかった | Failure 意味は判断できている。Qwen は調査対象をファイルにしていない |
| 判断したが Mapping できなかった | Gemma の 3 ファイル要求が M2。Qwen の unlabeled 修正案 |
| Mapping できたが Tool が失敗 | 該当なし（run_test は動いた） |
| Tool は成功したが解釈できなかった | Gemma の再 pytest は成功実行。その後読取に進まない。解釈失敗か Mapping 不足かは **NOT_DETERMINED** |

---

## 循環は成立したか

```
実エラー → 判断（本文） → Mapping 可能な次手 → Tool → 再判断 → 修正 → Test
```

**この 1 ケースでは循環は始まっていない。** 判断テキストは存在する。機械的 Mapping して Tool を回すところまで、Qwen では未接続、Gemma では意図と違う Tool が 1 回動いただけ。

「Tool Calling なし LLM で必ず解決できる」とはしない。  
「この構造が利用可能か」に対する今回の答えは、**判断層のテキスト出力までは観測できた。判断と Tool を分離したまま実コード解決まで維持できたとは言えない。**

実行: `python -m research.llm_benchmarks.judgment_loop_min_experiment.bench`
