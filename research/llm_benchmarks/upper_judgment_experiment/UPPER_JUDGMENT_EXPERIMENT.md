# GPT / Cursor 上位判断層 実問題解決実験

**GPT 採用 / Cursor 採用 / Controller 化 / Schema / Mapping / 下層 LLM / Tool Calling 採否は決めない。**  
既存実験・既存 fixture・本番 Agent には接続していない。

一次資料: `results/20260901T022619Z/`

初期入力は実 pytest / `python main.py` の出力。正解ルートは Solver へ渡していない。

---

## 実験条件の区別（汚染）

| 主体 | 事実 |
| --- | --- |
| 親セッション | fixture `lane_bay_v1` を作成した。二段 Failure の設計を知っている |
| Cursor Solver | [Solve](dd27db87-6495-4d3a-8dc9-2971401b2504)。与えたのは `SOLVER_PROMPT.txt`（実 Failure）と workspace パスだけ |
| GPT | ライブ呼び出し経路は無い。`gpt/PROMPT.txt` に同一入力を保存。**NOT_CONNECTED** |

親が解いた結果を「Cursor の盲検成功」とはしない。Solver は設計文を受け取っていない。ただし workspace 全体を列挙できるため、traceback に無い `config.py` / `bay.py` も一覧に出る。

---

## 初期 Failure（事実）

- pytest exit 1。`pick_lane(lanes, 2)`、`lanes = ['north']`、`helper.py:10 IndexError`
- traceback に `main.py` と `helper.py`。`config.py` / `bay.py` は出ない
- `python main.py` も同じ IndexError
- 単体テストで確認済み: `LANE_TAKE=3` だけでは `bay` で落ちる。両方直すと pass

---

## Cursor（第一候補）観測

操作の一次資料は Solver の報告と、親が確認した最終ファイル・再実行。

### 問題認識

- IndexError。`lanes` が 1 要素、index 2
- テストを読んで `lane == "west"` かつ `bay is True` が必要だと認識した（Solver 報告）

### 調査

一覧: glob で workspace の 5 ファイル。traceback に無い `config.py` と `bay.py` がここに含まれる。

読取順:

1. `tests/test_main.py` — 期待値
2. `main.py` — index 2 の経路
3. `helper.py` — `load_lanes` / `pick_lane`
4. `config.py` — `LANE_TAKE`
5. `bay.py` — テストが `bay is True` を要求するため

### 修正

- `config.py`: `LANE_TAKE` 1 → 3
- `bay.py`: `BAY_OPEN` False → True
- **両方を、修正後の最初の pytest より前に適用**

### Test

親が再実行して確認した。

- pytest exit 0
- `python main.py` → `{"lane": "west", "bay": true}`
- `execution_success: true` / `test_pass: true` / `application_behavior` は上記 JSON

### Test 後の再判断

**NOT_OBSERVED（一段目修正だけの Test 失敗は起きていない）**

二段目の要求は、テストファイルを先に読んだことで修正前に見えている。  
「最初のパッチ → Test 失敗 → 別ファイルへ」というループは、この実行では成立していない。

探索範囲変更は起きている。根拠は Test 失敗ではなく、**テストコードと import 先の読取**。

---

## GPT（第二候補）

- ライブ GPT 呼び出しは **NOT_CONNECTED**
- 同一 Failure を `gpt/PROMPT.txt` に保存した。応答は無い
- 問い1（GPT が不足情報を判断できるか）は **NOT_OBSERVED**
- 表の GPT 列は欠測。欠測を Cursor 成功で埋めない

---

## 比較表

| 項目 | GPT | Cursor Solver |
| --- | --- | --- |
| 初期 Failure 認識 | NOT_OBSERVED | IndexError / lanes 1 要素 / index 2 |
| 必要情報の認識 | NOT_OBSERVED | テスト期待と lanes の生成元 |
| 最初の調査 | NOT_OBSERVED | テスト、main、helper |
| 関連ファイル探索 | NOT_OBSERVED | glob 後に config / bay |
| import 追跡 | NOT_OBSERVED | helper → config / bay |
| 下層への探索 | NOT_OBSERVED | helper → config / bay |
| 上流への探索 | NOT_OBSERVED | テスト（呼び出し側の期待） |
| 最初の修正 | NOT_OBSERVED | LANE_TAKE と BAY_OPEN を同時 |
| Test 実行 | NOT_OBSERVED | あり（修正後） |
| Test 結果の解釈 | NOT_OBSERVED | pass を確認して停止 |
| 仮説更新 | NOT_OBSERVED | 修正後 Test では更新不要 |
| 探索範囲変更 | NOT_OBSERVED | あり（一覧とテスト読取が先） |
| 再修正 | NOT_OBSERVED | 不要（一括修正） |
| 再 Test | NOT_OBSERVED | この実行では 1 回で pass |
| 最終的な解決 | NOT_OBSERVED | pytest pass、main は west/true |

優劣判定はしない。GPT 列は欠測。

---

## 分解評価（Cursor）

| フラグ | この実行 |
| --- | --- |
| problem_recognition | あり |
| information_need_recognition | あり（テスト期待、LANE_TAKE、BAY_OPEN） |
| investigation_selection | あり |
| hypothesis_update | 読取に応じて原因を設定値へ更新。Test 失敗後の更新は NOT_OBSERVED |
| exploration_switch | あり。きっかけは glob とテスト読取 |
| repair_selection | あり |
| test_interpretation | pass を見て停止 |
| iterative_repair | NOT_OBSERVED（一括修正） |
| execution_success | true |
| test_pass | true |
| application_behavior | `{"lane":"west","bay":true}` |

---

## 下層 LLM（参考。今回は再実行していない）

判断層実験では、Gemma / Qwen / DeepSeek は Failure の意味を本文に出せた。Mapping が M2/M4 だと Tool に落ちない例、Gemma が読取連鎖に入る例があった。  
「下層は常に劣る」とはしない。今回 Cursor が解いたことと、下層が判断文を出せたことを一つの順位にしない。

---

## 問いへの回答

事実と未観測を分ける。採用はしない。

### 問い1 GPT

**NOT_OBSERVED。** この環境に GPT 呼び出しが無い。

### 問い2 Cursor

**この fixture では、必要なファイルを自分で探し、読んで修正し、Test が通るところまで確認した。**  
ただし「最初の修正後の Test 失敗を見て探索範囲を変えた」ではない。テストを先に読んだため、二条件を同時に直している。

### 問い3 同じ判断が起きるか

GPT 応答が無いので **比較不能**。

### 問い4 成功の内訳

**LLM 判断（Solver 報告上）**

- traceback の IndexError を `lanes` 長と index 2 の不一致と認識
- テスト期待が `west` と `bay is True`
- `LANE_TAKE=1` が短いリストの原因、`BAY_OPEN=False` が bay の原因

**環境統合（Cursor / ハーネス）**

- workspace のファイル一覧（traceback に無いファイルが列挙される）
- ファイル読取・編集
- pytest / `python main.py` の実行

一覧が無ければ `bay.py` に辿るコストは上がる。判断と環境をこれ以上機械的に分離する方式は、今回決めない。

### 問い5 上位判断 + 機械的 Mapping + 非 Tool Calling LLM

**成立しそう、とはまだ言えない。**  
Cursor 側は一覧・読取・実行が一体で動いた。下層実験では、判断文があっても Mapping が M2/M4 で止まると Tool に落ちない。上位の判断を Mapping 可能な形で出す設計は未実験。

### 問い6 人間を判断層に入れる前に十分か

**この 1 fixture の Cursor 成功だけでは、判断層を構築できるとは言えない。**  
GPT 欠測。Test 後再判断ループもこの実行では欠測。人間判断層の要否は決めない。

---

## 3系統について（今回測れた範囲）

```
GPT          → ライブ未接続
Cursor       → 環境操作込みでこの fixture は解決
非 Tool LLM  → 参考実験では判断文は出る。自動 Tool は不安定
```

「判断は LLM 単体でどこまで、環境統合はどこから必要か」について、今回確認できたのは次だけである。

- 実 Failure だけでも、ファイル一覧とテスト読取があれば Cursor Solver はこの規模の二条件を一括で直せた
- その成功は、Test 失敗をきっかけにした再判断の証拠にはならない
- GPT 単体の判断は未観測

実行:

```text
python -m research.llm_benchmarks.upper_judgment_experiment.capture
```

Cursor Solver: [Solve](dd27db87-6495-4d3a-8dc9-2971401b2504)
