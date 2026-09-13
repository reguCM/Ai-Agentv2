# 実験基盤・判断ループ単体実用性検証

**検証日:** 2026-09-01  
**LLM:** 未使用。Qwen / Gemma / DeepSeek / GPT / Cursor の性能評価はしていない。  
**一次資料:** `results/20260901T030944Z/run.json`  
**SUT（既存実験は未変更、import のみ）:** `judgment_loop_min_experiment` の `classify_mapping` / `dispatch` / `sent_for_tool` / `run_test` / `format_test_failure`  
**本番:** `agent.py` / Registry / Dispatcher には接続していない。既存 Problem Solving 実験・既存 fixture・過去結果には接続していない。

判定の区別:

| 表現 | 意味 |
| --- | --- |
| 判断は固定で正しいと仮定 | 入力文は人間が用意した。LLM の正しさは評価しない |
| Mapping 失敗 | その固定判断に対して SUT が期待 Tool を選ばなかった |
| Tool 成功 | `dispatch` が期待どおり動き、workspace に反映された |
| コード上成立 / 実測済み | 本検証で実行して記録した |

---

## 結論（先に）

成功条件 16 の区別:

| 条件 | 結果 |
| --- | --- |
| 成功1 固定判断 → 正しい Tool → Tool結果 | **成立**（Case 1 `helper.py を確認する` → `read_file(helper.py)` → 本文が次入力へ戻る） |
| 成功2 次の判断 → 別 Tool | **部分成立**（短い `config.py を確認する` なら読取先を変えられる。長い文だと別ファイル名があっても先のファイルを再読する） |
| 成功3 Failure → 調査 → 修正 → Test失敗 → 再調査 → 再修正 → Test Pass | **不成立（Mapping）** |

Tool を `dispatch` で直接呼べば、一段目パッチ失敗 → 二段目パッチ成功 → pytest pass は **実測で成立**する。  
同じパッチを「固定判断 → Mapping」経由で流すと、`apply_patch` 候補があっても `_prefer` が `read_file` を選び、修正に到達しない。

**評価: C（修正が必要）。Mapping 層は D に近い。**  
LLM 判断能力比較には進まない。

---

## 1. 検証対象

変更前にコードから確認した経路（結果は後段で実測）:

```text
固定判断文字列
  → classify_mapping(text, known_files)     # mapping.py
  → execute = mapping["execute"]            # 実行可能候補 1 件
  → workspace.dispatch(name, arguments)     # HANDLERS
  → sent_for_tool / format_test_failure     # bench.py / execute.py
  → session.messages に次入力として追加      # 本検証ハーネス
```

| 段階 | 入力 | 出力 | 関数 | エラー |
| --- | --- | --- | --- | --- |
| 判断 | 文字列 | 同じ文字列 | なし（抽出層なし） | なし |
| Mapping | 全文 + known_files | candidates / execute | `classify_mapping` | mapping_gap |
| Tool選択 | execute 1 件 | tool_name, arguments | `_prefer` | 未選択 |
| Tool実行 | name, args, workspace | dict | `dispatch` | unknown_tool / TypeError / ファイル不存在 |
| 返却 | Tool dict | 次の user 文 | `sent_for_tool`。パッチ後は `format_test_failure` | 切り詰め 3500 字 |
| 状態 | session | files_read 等を append | 本検証 `harness.py`。SUT に ProblemState は無い | |
| Turn | 固定シナリオ | turn_id | 本検証。SUT `MAX_TURNS` は未使用 | |

`copy_fixture`（order_live）は呼んでいない。

---

## 2. 使用した専用 fixture

`fixtures/chain_ready/`（既存 fixture のコピーではない）

```text
main.py → helper.py → config.py
```

- `config.py`: `FIELD_COUNT = 1`, `READY = False`
- `helper.py`: `LABELS[:FIELD_COUNT]`, `is_ready()`
- `main.py`: `items[2]` と `ready`
- テスト: `item == "gamma"` かつ `ready is True`

初期: IndexError（FIELD_COUNT=1）。  
FIELD_COUNT だけ 3 にすると assertion（READY=False）。  
両方直すと pass。

単体テスト `test_fixture_two_stage_failure` で確認済み。

---

## 3. 既存コードとの隔離

- 専用ディレクトリ `experiment_infrastructure_validation/`
- 既存実験ファイルは未編集
- SUT は import のみ。`workspace.copy_fixture` は不使用
- 本番 Agent / Registry 不使用
- LLM / Ollama 不使用
- pytest: `tests/research/llm_benchmarks/experiment_infrastructure_validation` のみ（4 passed）

---

## 4. 判断入力

すべて固定文字列。`judgment_status` は常に `fixed_assumed_correct`。  
LLM が正しいかは評価していない。

---

## 5. Mapping結果

指示書 Case 1–5（実測）:

| Case | 判断 | 期待 | 実際 | 分類 |
| --- | --- | --- | --- | --- |
| 1 | helper.py を確認する | read_file(helper.py) | 一致 | judgment_ok_mapping_ok |
| 2 | helper.py の内容を読みたい | read_file(helper.py) | 実行なし（M2） | 判断OK / Mapping失敗 |
| 3 | helper.py を調査した後、config.py も確認する | 両方 read | helper.py のみ実行。候補には両方 | 複数判断 → 1 件だけ実行 |
| 4 | Testをもう一度実行する | run_test | mapping_gap | 判断OK / Mapping失敗 |
| 5 | helper.py を読んでからTestを実行する | read → run_test | read のみ。run_test は候補 | 順序が崩れる（1 件選択） |

誤 Mapping:

| 入力 | 実際 | 意味 |
| --- | --- | --- |
| helper.pyを確認する必要があります。 / Run Tests Again. | **read_file**（run_test も候補） | inspect が近傍なら `_prefer` が read を優先。Gemma 実ログのずれは再現しない |
| I need to inspect helper.py before making a change. | read_file | 一致 |
| ファイル名要求と inspect 語を離し、Run Tests Again | **run_test**。helper.py は M2 | **Failure A 再現。判断失敗ではない** |

Case 2 の根拠: INSPECT が `読む|読ん` であり `読みたい` に一致しない。  
Case 4 の根拠: TEST_HINT が `テストを(再)?実行` / `run tests?` であり、`Testをもう一度実行する` に一致しない。

---

## 6. Tool実行結果

`dispatch` 直接および Mapping 経由の読取:

- `read_file(helper.py)`: ok。本文に `from config import FIELD_COUNT, READY`
- 存在しないファイル: `{ok: false, error: "ファイルが存在しません"}`。未知 Tool 名とは区別できる
- 未知 Tool: `{ok: false, error: "unknown_tool:not_a_real_tool"}`
- `apply_patch(config.py, 全文)`: 対象のみ変更。helper.py / main.py のハッシュ不変
- 断片 `"FIELD_COUNT = 3\n"` を書くと **READY 行が消える**（全文上書き）
- ロールバック API: **未実装**

---

## 7. Tool結果の返却

成功1 の次入力（実測）:

```text
You asked to inspect helper.py.

Here is the file:

from config import FIELD_COUNT, READY
...
```

Failure C（Tool成功なのに返らない）: **観測されず**（読取経路）。

欠落: 元ファイル末尾改行が `read_file` の `splitlines` + join で落ちる。内容の識別には足りる。

---

## 8. 複数Turn結果

固定 3 Turn:

| Turn | 判断の意図 | Mapping | 実行 |
| --- | --- | --- | --- |
| 1 | helper.py を読む | 一致 | read_file(helper.py) |
| 2 | config.py を読む（文中に helper.py あり） | **helper.py を再実行** | 探索変更が文面どおりにならない |
| 3 | patch config.py + フェンス | apply_patch は候補だが **read_file を実行** | 修正に進まない |

Turn 2 で `files_read` は `helper.py` を残したまま増える。Turn 1 の記録は消えない。  
短い判断 `config.py を確認する`（solve loop Turn 2）では config.py に移れる。

---

## 9. Test実行結果

初期 Failure（実測）: pytest exit 1、IndexError、command / stdout / stderr あり。

Mapping 経由の修正ループでは `apply_patch` が選ばれないため、ハーネスのパッチ後 Test は **未到達**。

`dispatch(apply_patch)` 直接:

- 部分修正後: pytest exit 1、`assert False is True`（ready）
- 再修正後: pytest exit 0

`format_test_failure` の次入力には Exit code、stdout、stderr、python main.py ブロックが含まれる。ラベル「The test still fails.」だけではない。  
部分修正後は traceback 欄が空（AssertionError で `Traceback (most recent call last):` が stdout に無い）。stdout 本文には失敗情報がある。

---

## 10. Test Failure後の再判断

- Mapping ループ: パッチ未実行のため、パッチ後 Failure を次判断へ返す経路は **未到達**
- 直接パッチ: 返却文面は実測で欠落していない（Failure D の Tool/返却側は成立）
- 再判断そのものは固定文を次 Turn に流すことで確認。基盤は messages を保持する

---

## 11. apply_patch の挙動

| 項目 | 実測 |
| --- | --- |
| 対象以外を変えない | 成立 |
| 全文を渡したとき内容を消さない | 成立 |
| 断片を渡すと残りが消える | **成立（危険）** |
| import 消失 | 断片上書きで READY 消失 |
| encoding | utf-8。本 fixture では破壊なし |
| ロールバック | 未実装 |
| Test失敗後の再修正 | **dispatch 直接なら成立** |
| Mapping 経由 | `_prefer(read > write)` と、フェンス内 `READY` が INSPECT の `read` にヒットし read が M1 になる |

後者: `I need to patch config.py` + フェンス本文 `READY = False` の窓で `READ` が `read` にマッチする。コード上確認済みかつ本検証で実行済み。

---

## 12. 状態保持

本検証 session（SUT には無い）:

- `files_read` は append。Turn 2 で Turn 1 の helper.py は残る
- `tool_calls` 累積
- `files_changed` は Mapping がパッチしない限り空
- workspace ファイルは残る
- `new_session` が初期 pytest を回すため `.pytest_cache` が known_files に混入する（本検証の副作用。SUT の本番ループでも copy 後に test すると同様）

---

## 13. 成功した経路

- 短い「確認する」+ ファイル名 → read_file → 本文返却
- 短い「config.py を確認する」で読取対象を切り替え
- dispatch による apply_patch（全文）と二段 Test
- 未知 Tool と欠ファイルのエラー区別
- 読取結果の次入力化（Failure C なし）

成功1、成功2（短い判断に限る）は基盤の Tool/返却として使える。

---

## 14. 失敗した経路

すべて **判断失敗ではない。**

- 成功3 の Mapping 経路全体
- Case 2 / 4 の無実行
- Case 3 / 5 の複数行動を 1 Tool に圧縮
- 離れたファイル要求 + `Run Tests Again` → run_test
- パッチ判断が read_file になる
- 断片パッチによるファイル破壊
- ロールバックなし

---

## 15. Mappingの問題

問題:  
明確な読取判断が実行されない。

根拠:  
`mapping.py` INSPECT。Case 2 `読みたい` は M2。`classify_mapping` が execute=None。

影響:  
LLM が自然な日本語で読取を述べても Tool が動かない。

確実性: 実測済み。

---

問題:  
1 判断文から実行は常に 1 Tool。順序は `_prefer`（read が write / run_test より前）。

根拠:  
`_prefer` の order。Case 5 で run_test は候補だが未実行。パッチ判断で apply_patch は候補だが read が実行。

影響:  
調査のあとに Test、読んだあとに修正、が機械的に落ちる。

確実性: 実測済み。

---

問題:  
inspect 窓 64 文字の外のファイル要求は M2。同じ文の TEST_HINT だけが M1 なら run_test。

根拠:  
`_near_inspect` と `failure_a_distant_file_then_run_tests_again` の mapping_output.reason=`run_test`。

影響:  
Gemma 既存ログと同型。LLM 失敗と混同してはいけない。

確実性: 実測済み。

---

問題:  
識別子 `READY` が INSPECT `read` にマッチする。

根拠:  
パッチ用フェンスに `READY` があると config.py が M1 read になる。本検証 Turn 3/5。

影響:  
修正判断が読取に化ける。

確実性: 実測済み。

---

正規表現 Mapping が「十分」とは言えない。動く範囲は短い「確認する」+ 単一ファイル名程度。

---

## 16. Tool側の問題

- 全文上書き。断片で破壊される（実測）
- ロールバックなし
- `read_file` が末尾改行を落とす
- 未知 Tool と欠ファイルは区別できる（これは欠陥ではない）

読取・隔離パス・対象外ファイルを変えない点は実用に足る。

---

## 17. Test側の問題

- pytest / command / exit_code / stdout / stderr は取得できる
- traceback 欄はマーカー依存。AssertionError では空になり得る。stdout には失敗がある
- Mapping が run_test やパッチ後 Test に届かないと、ループ上の Test 返却は評価できない（返却関数自体は直接呼び出しで確認済み）

---

## 18. 状態管理上の問題

- SUT に名前付き ProblemState は無い。会話 list と run.json
- 本検証ハーネスは累積リストを持つ。Turn 1 の読取を Turn 2 が消すことはない
- pytest_cache が workspace 列挙に入る
- Mapping がパッチしないため `files_changed` が空のまま成功3 を語れない

---

## 19. 実用性評価

**総合 C：修正が必要**

| 層 | 評価 | 理由 |
| --- | --- | --- |
| Tool 実行（隔離 workspace） | B | 読取・限定パッチ・Test は実測で動く |
| 結果返却 | B | 読取と format_test_failure は実測 |
| Mapping | D | 複数行動・語彙・READY/read・1件選択 |
| 判断ループ全体 | C | 成功3 が Mapping で止まる |

LLM を繋いでも、悪い結果がモデル由来か基盤由来か区別できない状態が、本検証で再確認された。

---

## 20. 次に修正すべき基盤

正式 Mapping 仕様の決定はこの結果だけではしない。次の候補（採用必須ではない）:

1. 判断と Mapping と実行をログで分離したまま（本検証は実施済み）、**実行件数と優先**を変えるかは人間判断
2. INSPECT の単語境界（`READY` 誤ヒット）は、正規表現を触るなら既存実験を複製した専用 Mapping で試す。既存 `mapping.py` は今回変更していない
3. 抽出層の導入は未決定。全文 Mapping が Failure A の原因の一つ
4. apply_patch を diff にするかは未決定。現状は全文前提で判断文を書く必要がある
5. ロールバックは未実装のまま記録

**次の LLM 実験へ進む条件（指示書 22）は未充足。**

---

## Failure A–G（指示書 19）

| ID | 内容 | 本検証 |
| --- | --- | --- |
| A | 判断正しく Mapping 誤り | **確認**。Case 2/4、distant Run Tests Again、パッチ判断→read |
| B | Mapping 正しく Tool 失敗 | 未知 Tool / 欠ファイルはエラーを返す。正常 read/patch は成功。Mapping 成功後の Tool 事故は本セットでは主因ではない |
| C | Tool 成功、返却なし | **読取では未観測** |
| D | Test が次判断へ戻らない | Mapping ループではパッチ未到達。直接パッチでは **戻る** |
| E | 修正が workspace に無い | 全文 dispatch では **無い**。断片では内容が壊れる |
| F | Test失敗後に再修正できない | Mapping では未到達。dispatch では **できる** |
| G | 別ファイルへ探索できない | 短い判断では **できる**。複数ファイルを一文に書くと先のファイルを優先 |

---

## 指示書 22 の循環

```text
固定判断 → Mapping → 正しい Tool → 結果 → 次判断 → 別Tool
```
短い読取判断に限れば部分的に成立。

```text
修正 → Test → Failure → 再判断 → 追加調査 → 再修正 → 再Test
```
**Mapping 経由では不成立。** Tool 直接なら成立。

したがって、基盤は「Tool と Test の部品」としては使えるが、「LLM の判断を正しく受け取り修正ループまで進める」状態ではない。
