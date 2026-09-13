# IMPLEMENTATION_OPTIONS — 不一致を埋める候補

実装しない。採用しない。本番 Registry / execute_tool / Repair / FA は対象外。

実験ディレクトリ中心。`validate_tool_result` は **呼ぶだけ**なら Schema 変更不要。

---

## O1. 送信 messages を結果 JSON に保存

- ファイル: `harness.py`（`_ask` 前後）
- 内容: chat 直前の messages コピー、options、model
- 利点: 「何を見たか」が結果だけで追える
- 欠点: JSON が大きくなる。秘密は現状ほぼ無いが冗長
- 実験: Logging × が解消に近づく。他の採用より独立
- 本番: なし
- FA: なし（実験ログ）
- 規模: 小

---

## O2. `get_current_failure` の返す範囲を狭める / 分割

- ファイル: `adapters.py`（必要なら catalog description）
- 内容: 最小面のみ、またはキー選択、または traceback/source/validation を別口
- 利点: Tool 選択実験が成立しうる
- 欠点: 分割単位は人間判断。切りすぎると LLM が詰まる
- 実験: Failure △ の主因
- 本番: なし
- FA: 観測単位の議論に似るが、実験ラッパに留める
- 規模: 小〜中

---

## O3. Test 多軸 + LLM へ再投入

- ファイル: `adapters.experiment_test_source`、`harness.py` final 分岐
- 内容: exception と return_value と（任意で）`validate_tool_result` を別フィールド。break せず Test 結果を user にして `_ask`
- 利点: Test判定 × と Test再投入 × と Test 後再調査を同時に改善しうる
- 欠点: LLM が Test を「解決」と誤読するラベルを残すと再発。pass という語の使い方を変える必要
- 実験: プロトコル後半が初めて測れる
- 本番: Repair Loop は触らない
- FA: なし
- 規模: 中

---

## O4. Test を LLM 選択の Tool にする（ハーネス自動 Test をやめる）

- ファイル: `harness.py` final 処理
- 内容: final は案の提出のみ。実行は LLM が `experiment_test_source` を選ぶ
- 利点: Tool 利用と Test 起動を分離して観測
- 欠点: LLM が Test を呼ばないランの扱いが要る
- 実験: 「修正した」と「検証した」が分かれる
- 本番: なし
- FA: なし
- 規模: 小〜中（O3 と排他ではない）

---

## O5. Tool 提示 A-1 の説明強化（native にしない）

- ファイル: `catalog.llm_catalog_text`、場合により SYSTEM
- 内容: purpose、required、返す情報の種類
- 利点: モデル非依存。Dispatcher 維持
- 欠点: 依然テキストプロトコル。JSON 混在は残る
- 実験: 「用途が分からず選ばない」ノイズを減らせる可能性
- 本番: なし
- FA: プロンプト設計と似て見える。実験専用と明記が要る
- 規模: 小

---

## O6. Ollama native `tools=`（A-2）

- ファイル: `harness._ask`、catalog → Ollama schema、tool_calls 読取
- 内容: `probe_tool_calling` で事前確認。dispatch は維持可
- 利点: 本番 Agent に近い選択観測。parser 混在を減らせる
- 欠点: モデル非対応なら実験不成立。active model 依存
- 実験: 「JSON を書けるか」と「Tool を選ぶか」が分かれやすい
- 本番: execute_tool を呼ぶ必要はない
- FA: Agent 経路と似る。接続はしない
- 規模: 中

---

## O7. Parser を全文 JSON のみにし、失敗を保存（greedy 廃止）

- ファイル: `harness._parse_action` と unparsed 分岐
- 内容: 失敗時 parser_error を turn に残す。再指示文を固定するか、失敗でも Tool 結果 user を消さないか
- 利点: 条件変化の追跡がしやすい
- 欠点: 厳格だとターン消費が増える
- 実験: Parser が能力評価を汚染しにくくなる
- 本番: なし
- FA: なし
- 規模: 小

---

## 組み合わせの注意

O1 は他と独立して先にできる。  
O2 なしで Tool 選択実験を読むのは、現状どおり危険。  
O3 なしではプロトコル末尾（解決/再調査/HELP）が測れない。  
O5 と O6 は提示方式の別候補。同時全面採用はしない方が解釈が単純。
