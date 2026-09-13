# LLM判断・機械的判定協調基盤 検証

**検証日:** 2026-09-01  
**LLM:** 未使用。モデル比較・Prompt 最適化・正式 Schema・本番 Mapping は決定していない。  
**既存:** Problem Solving / Analysis / `judgment_loop_min` / 本番 Agent / 既存 Mapping / 既存 fixture / 既存結果は未変更・未接続。  
**一次資料:** `results/20260901T032211Z/run.json`  
**pytest:** `tests/research/llm_benchmarks/judgment_action_bridge_experiment` **19 passed**

観測事実と推測を混ぜない。

---

## 1. 専用 fixture の構造

`fixtures/chain_count/`（既存 fixture の流用ではない）

```text
main.py → helper.py → config.py
tests/test_main.py
```

- 初期: `FIELD_COUNT = 1` → `items[2]` で IndexError
- 一段修正 `FIELD_COUNT = 3`, `READY = False` → pytest は `ready is True` で失敗
- 二段修正 `READY = True` → pytest / `python main.py` 成功

LLM へ依存関係は説明していない（本検証は固定判断文のみ）。

---

## 2. 実装した各層

専用パッケージ内のみ。既存 `classify_mapping` は import していない。

```text
入力文
  → parse.parse_actions     文単位で intent / target。フェンスはマスク
  → validate.validate_actions 既知パス・空パッチを落とす。希望の差替えなし
  → select.select_actions     execute=True のみ実行。代替候補は残す
  → execute.run_scripted      dispatch を順実行し next_input を返す
  → workspace.*               隔離 Tool
```

正式 Parser / Schema ではない。仮仕様として文分割と語彙を使っている。

---

## 3. Tool 接続状況

本実験専用 `workspace.dispatch`:

| Tool | 接続 |
| --- | --- |
| read_file | コード上成立。実測済み |
| search_files | 候補として保持。inspect では自動実行しない |
| list_files | 語彙があれば実行可能。本 pytest の主経路ではない |
| apply_patch | 全文上書き。修正 intent + フェンスのときだけ |
| run_test / run_program | subprocess。TimeoutExpired は捕捉する |

本番 Registry には接続していない。

---

## 4. Action 分解状況

**観測:** 1 入力から複数 Action を出せる。

- `helper.pyを確認したい。その後Testを実行したい。` → `read_file` のあと `run_test`（`flags.multiple_actions: true`）
- `main.pyを見てからhelper.pyを確認したい` → 出現順で 2 読取

1 Tool 制限は設けていない。

---

## 5. Mapping 状況

既存 Mapping は使っていない。本層の選択は:

- inspect + 既知ファイル → `read_file` を実行候補。`search_files` は候補のみ
- 対象不明の inspect → `needs_clarification`。ファイルを捏造しない
- 希望を別ファイルへ書き換えない（`config.pyを調べたい` → config.py）

---

## 6. 成功した Test ケース

T1 単一読取、T2 単一 Test、T3 単一 Patch、T4 複数 Action、T5 順序、T6 ファイル名、T7 曖昧停止、T8 類似語、T9 フェンス内 TOKEN、T10 離れた判断、T11 結果後の追加調査、T12/T13 修正→失敗→再修正→Pass、T14 mapping_gap、T15 複数候補保持、`helper.pyを読む`、対象差替えなし、`このファイル` でパス捏造なし、フルループ。

---

## 7. 失敗した Test ケース

現時点の pytest は 19 件すべて成功。  
実装前は `bridge` モジュール不存在で収集エラー（想定どおり）。

実装中に見つけた欠落（テスト追加後に修正）:

- 当初 INSPECT に `読む` が無く `読み|読ん` のみだった。`helper.pyを読む` 用テストを足して `読む` を追加した。

---

## 8. 発見した基盤バグ

本新層の初期実装:

1. `読む` が inspect 語彙に無いと読取 Action にならない（旧 Mapping と同型の語彙穴）。
2. フェンスをマスクしないと `READY` / `# TEST` が Action になり得る（旧 Mapping の問題。本層ではマスクと `\bread\b` で回避）。

既存 `judgment_loop_min.mapping` は変更していない。再現防止は新層側。

---

## 9. 修正した基盤バグ

- `parse.py` の INSPECT に `読む` を追加。
- フェンス本文を Action 走査から除外。
- 英語 `read` は単語境界。`READY` にはマッチしない。
- `まだ実行しない` でその文の `run_test` を落とす。

---

## 10. 修正後の Test 結果

19 passed。`run_bridge` flags:

```text
judgment_received true
action_extracted true
tool_selected true
multiple_actions true
false_run_test false
ambiguous_stopped true
loop_mid_fail true
loop_test_pass true
```

---

## 11. LLM なしで成立した範囲

- 固定判断 → Action → Tool → 次入力
- 複数 Action の順実行
- 曖昧入力で Tool を選ばない
- コード例の READ/TEST/READY で run_test / patch しない
- 実 fixture の Failure → 読取 → 部分修正 → Test 失敗 → 再修正 → Test Pass

---

## 12. LLM を入れると残ると考えられる問題（推測。未実測）

- 語彙に無い言い回しは gap になる（`確認したい` 以外の表現）。
- 長文・箇条書き・英語混在の分解品質は未検証。
- パッチはフェンス付き全文が必要。LLM が断片だけ出すと apply できないか、全文上書きで壊す。
- 複数候補（read vs search）の最終選択を LLM に返す確認ループは未接続。
- Native Tool Calling は使っていない。接続時の二重実行は未観測。

---

## 13. 判断と Mapping を分離できたか

**できた（本ディレクトリ内）。**  
`input_text` / `action_candidates` / `selected_actions` / `selection_reason` を分けて保存する。既存 Mapping 関数は呼ばない。

---

## 14. 複数 Action を扱えるか

**扱える。** 1 出力 1 Tool 制限は無い。

---

## 15. 曖昧な判断を安全に停止できるか

**できる。** `ちょっと確認したい` 等は `selected_actions == []`、`needs_clarification`。勝手な `read_file` はしない。

---

## 16. 実コード→Test→結果→再 Action の循環

**固定判断では成立。** pytest の `test_full_solve_loop_scripted` と `run_bridge` の loop で、中間 Test 失敗と最終 Pass を実測。

---

## 17. Cursor 型手順との構造上の共通点

Cursor 再実験はしていない。概念との対応:

| Cursor 側の行動（既存資料の参考） | 本基盤 |
| --- | --- |
| workspace を見る | list_files（語彙があれば） |
| ファイルを読む | inspect → read_file |
| 修正 | apply_patch（フェンス必須） |
| Test | run_test |
| 結果を見る | next_input |
| 別ファイルを読む | 次の固定判断で別 target |
| 再修正 | 2 回目の apply_patch |

Cursor と同一実装ではない。同じ手順を Action として表現できるかが対象。

---

## 18. 現時点で未成立の部分

- LLM 接続（意図的に未実施）
- 抽出結果を LLM に問い返す候補確認
- 部分 diff パッチ
- ロールバック
- 正式 Schema / 語彙の網羅
- 探索順の固定ルール

---

## 19. 次に LLM を戻す場合に必要な条件

1. 本層を既存 Mapping に置き換えない。全文正規表現へ戻さない。
2. ログで judgment / candidates / selected / tool を分離したままにする。
3. まず 1 モデル・少数 Turn。比較実験にしない。
4. LLM がフェンス無しで修正を述べたら mapping_gap とし、勝手にファイルを書き換えない。
5. 出力に `Run Tests Again` や `READY` があっても、否定・フェンス規則を維持する回帰を残す。

---

## 成功判定の分離（指示書 22）

| フラグ | 本検証（LLM なし固定判断） |
| --- | --- |
| judgment_received | true |
| action_extracted | true |
| action_validated | true（既知パス） |
| tool_selected | true |
| tool_executed | true |
| result_returned | true |
| next_action_extracted | true（次の固定文） |

「LLM が正しい判断をした」とは評価していない。

---

## A–H（指示書 23）

| 項目 | 評価 | 根拠 |
| --- | --- | --- |
| A 判断を受け取れたか | 成立 | `judgment_received` |
| B 複数 Action へ分解 | 成立 | T4/T5、phase2 |
| C 希望を勝手に変えない | 成立 | T8/T9、対象差替えテスト、phase4 `false_run_test: false` |
| D 正しい Tool へ接続 | 成立（固定文の範囲） | T1–T6 |
| E 実コードで Tool 実行 | 成立 | workspace 実測 |
| F 結果を次入力へ | 成立 | T11 next_input にソース |
| G Test 後の次 Action | 成立（固定文） | フルループ |
| H 曖昧・誤単語で停止 | 成立 | T7/T8/T14 |

---

## 最重要問いへの答え

LLM なしの固定判断では、

```text
考える（固定文）→ Action 化 → 機械検証 → Tool → 結果 → 次の固定判断
```

は専用ディレクトリ上で動く。  
既存 Mapping の「全文ヒットで run_test / READY→read」は、この層では再現させず止められた。

非 Tool Calling LLM を判断層にする実験は、上記回帰を残したまま別フェーズで行う。今回は行っていない。
