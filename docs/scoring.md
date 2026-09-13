# LLM Tool ベンチマーク採点仕様

scoring_version: `"1.0"`

この文書は採点の仕様である。実測結果は `research/llm_benchmarks/` に置く。機械採点の実装は `tools/system/tool_builder/score.py`。

## 1. 目的

LLM による Tool 開発能力を、単純な PASS / FAIL だけではなく、

* ユーザー要求を満たせたか
* 正確かつ安全に実装できたか
* 既存システムへ適切に組み込めたか
* 不要な実装をどの程度追加したか

の観点から評価する。

本スコアはモデルそのものの優劣だけでなく、Research / Judge / Implementation / Validation / Repair の各工程における弱点を発見するためにも使用する。

---

## 2. 基本スコア

100点満点とする。

| 評価項目 | 配点 |
|---|---:|
| 要求達成 | 40 |
| 正確性・安全性 | 30 |
| 既存システムへの適合 | 20 |
| 過剰実装・整理 | 10 |
| **合計** | **100** |

100点を上限とし、重大な失敗については別途スコア上限（cap）を適用する。

---

## 3. 要求達成：40点

ユーザーが要求した機能をどの程度実現できたかを評価する。

### 40点：完全達成

要求された機能を正しく実現している。

### 30点前後：ほぼ達成

本質的な要求は満たしているが、軽微な不足や形式上の問題がある。

### 20点前後：部分達成

要求の一部のみを実現している。

例：

* 使用率ではなく総メモリ容量だけを取得
* CPUだけ実装し、メモリを実装していない

### 1～19点：限定的な達成

要求との関連性はあるが、実用上ほぼ要求を満たしていない。

### 0点：未達成

* 未実装
* スタブ
* codeなし
* 全く異なる機能
* 実行不能

など。

---

## 4. 正確性・安全性：30点

実装内容そのものの正確性と安全性を評価する。

### 30点

* 正しいコマンド
* 正しい値
* 正しいデータ解釈
* 適切な戻り値
* 適切なエラー処理
* 実行時に問題がない

### 20～29点

軽微な問題はあるが、基本的に実用可能。

### 10～19点

明確な問題が存在する。

例：

* 特定の出力形式に強く依存
* エラー処理が不十分
* 一部環境で失敗する可能性が高い

### 1～9点

重大な誤りがあるが、要求との関連性は残っている。

### 0点

* 間違ったコマンド
* 存在しないAPI
* 捏造した環境情報
* 全く異なる値を返す
* 実行すると重大な問題を起こす

---

## 5. 既存システムへの適合：20点

既存Tool環境の仕様・構造に正しく適合しているかを評価する。

### 20点

* Registryへの登録が正しい
* Tool APIを守っている
* 所定のJSON形式を守っている
* 既存ファイル構造を維持している
* 他のToolへ影響を与えない
* 既存テストを壊さない

### 15～19点

軽微な構造上の問題。

### 5～14点

修正すれば使用できるが、既存設計を一部無視している。

### 1～4点

既存システムへの適合性が著しく低い。

### 0点

* 既存Toolを破壊
* Registryを破壊
* 既存機能を使用不能にする

---

## 6. 過剰実装・整理：10点

要求されていない機能を勝手に追加した場合に評価する。

この項目は他の項目よりも軽く扱う。

### 10点

要求された機能だけを適切に実装。

### 8～9点

要求を満たしたうえで、軽微な補助処理を追加。

例：

* 関連する補助情報を一緒に返す
* 有用なエラー情報を追加する

### 5～7点

不要な機能を複数追加しているが、害は小さい。

### 1～4点

要求と無関係な実装が多く、整理や修正の手間が大きい。

### 0点

過剰実装によって要求された機能が分かりにくくなったり、既存機能へ悪影響を与えている。

---

## 7. 「増やす」と「減らす」の扱い

本システムでは、不要な追加よりも要求の欠落を重く評価する。

### 許容されやすい

要求：

> メモリ使用率を取得するTool

実装：

> メモリ使用率 + 総メモリ容量

この場合、総メモリ容量が有用で害がなければ大幅な減点はしない。

### 厳しく評価する

要求：

> CPU使用率とメモリ使用率を取得する

実装：

> CPU使用率だけ取得する

これは「過剰実装」の問題ではなく、「要求達成」の問題として大幅に減点する。

---

## 8. 重大失敗によるスコア上限

単純加算によって重大な失敗が高得点になることを防ぐ。

| 失敗 | 最終スコア上限の目安 |
|---|---:|
| 軽微な過剰実装 | 制限なし |
| Repairが必要になった | 制限なし |
| Researchを余分に実行した | 制限なし |
| 要求の一部を満たさない | 69点 |
| 明確な誤情報・wrong command | 49点 |
| 既存Toolを破壊 | 29点 |
| 捏造・危険な実装 | 19点 |

スコア上限は「失敗回数」ではなく、最終的な影響を基準に適用する。複数の cap が該当する場合は、より低い上限を使う。

---

## 9. グレード

100点満点のスコアとは別に、人間が結果を把握しやすいグレードを付与する。

| 点数 | グレード | 意味 |
|---:|:---:|---|
| 95～100 | S | 非常に優秀 |
| 90～94 | A | 優秀 |
| 80～89 | B | 実用的 |
| 70～79 | C | 要改善 |
| 50～69 | D | 大きな問題あり |
| 0～49 | F | 実用困難 |

重大失敗によるスコア上限を適用した後の点数からグレードを決定する。

---

## 10. 工程別スコア

最終スコアだけでなく、可能な限り工程別の評価も保存する。

```text
Research       25/25
Judge          25/25
Implementation 38/40
Validation      8/10
Repair          5/5
--------------------
Final           96/100
```

実際の配点はベンチマークの種類に応じて調整してよいが、最終スコアとは別に工程別の成否を保持する。

目的は「どのモデルが優秀か」だけではなく、

* Researchが弱い
* Judgeが厳しすぎる
* Implementationが弱い
* Validation後のRepairが弱い

といった工程別の特徴を把握することである。

実装層だけのベンチでは、回していない工程は `skipped` とする。

---

## 11. 既存のPASS/FAILとの関係

PASS / FAIL は廃止しない。

両方を保存する。

```text
pass: true
score: 96
grade: S
```

PASS / FAIL は「実用上の合格判定」。

score は「品質の比較」。

この2つは目的が異なるため、分離して扱う。

例えば、

```text
Model A
PASS
98 points

Model B
PASS
87 points
```

であれば、どちらも実用可能だが、Model Aの方が品質が高いと判断できる。

実装層では、要求を満たす finding を使っていれば PASS とする。不要な finding の追加だけでは FAIL にしない。

---

## 12. 現在のA+Cケースの扱い

要求を満たすAに加えて、不要ではあるものの害のないCを追加した場合、

```text
A only       → 100点相当
A + C        → 軽微な減点
```

とする。

現段階では A+C を完全なFAILとはしない。

不要な追加が、

* 有用かもしれない
* 実害がない
* 既存構造を壊していない

場合は、実用上の合格を維持する。

ただし、追加が増えるほど整理コストが上昇するため、過剰実装の点数を下げる。

class としては `unnecessary_finding` を残す。PASS と score は class とは別に付ける。

---

## 13. 自動採点と人間による採点

最終的には可能な限り機械的に採点する。

特に以下は自動判定を優先する。

* codeの有無
* required finding の使用
* wrong command
* unnecessary finding
* Validator結果
* runtime exception
* 既存テスト
* Registry破壊
* Tool実行結果
* 戻り値形式

一方、

* 要求をどの程度満たしているか
* 実装が妥当か
* 追加機能が有益か
* 実装品質がどの程度か

など、機械判定が難しい部分は将来的にJudgeまたは人間による評価対象とする。

---

## 14. 記録形式

ベンチ結果には少なくとも以下を保存する。

```json
{
  "model": "qwen3:8b",
  "scoring_version": "1.0",
  "score": 96,
  "grade": "S",
  "pass": true,
  "score_breakdown": {
    "requirement": 40,
    "correctness": 29,
    "integration": 20,
    "overimplementation": 7
  },
  "caps": [],
  "pipeline": {
    "research": "pass",
    "judge": "pass",
    "implementation": "pass",
    "validation": "skipped",
    "repair": "skipped"
  }
}
```

実際のJSON構造は既存の `repair_results.json` / `environment_results.json` / `implementation_results.json` の設計と整合させる。

所要時間は採点には使わない。記録だけする。`chat()` の合計が `llm_seconds`、残りが `machine_seconds`。工程秒は壁時計で、その工程内の LLM 時間を含む。設計提案など名前のない工程は `total_seconds` にだけ乗る。

```json
{
  "timing": {
    "total_seconds": 184.2,
    "llm_seconds": 162.8,
    "machine_seconds": 21.4,
    "research_seconds": 71.4,
    "judge_seconds": 18.2,
    "implementation_seconds": 42.7,
    "repair_seconds": 30.5,
    "validation_seconds": 0.8
  }
}
```

比較用の短い履歴は `research/llm_benchmarks/history.json`。モデル別・ケース別の集計は `summary.json`。

```text
python -m research.llm_benchmarks.history
python -m research.llm_benchmarks.history --case implement_choose_usage_among_memory_findings
python -m research.llm_benchmarks.history --model qwen3_8b
python -m research.llm_benchmarks.history --rebuild
```

実装層ベンチは結果を追記したあと、この履歴を自動更新する。generated_code は results にだけ残す。

---

## 15. 今後の拡張

現段階ではこの採点仕様を固定しすぎない。

今後のベンチ結果から、

* 配点が実態に合っていない
* 重大失敗の扱いが厳しすぎる
* 過剰実装をもっと許容すべき
* ResearchとImplementationを分離した方がよい
* Repair成功を別評価した方がよい
* 所要時間を配点に入れる
* STATE の維持を配点に入れる

などが判明した場合は、仕様のバージョンを上げて変更する。

採点仕様自体もベンチマークの対象となるため、過去の結果を比較できるよう、各runには使用した scoring version を保存する。

例：

```text
scoring_version: "1.0"
```

---

## 16. 基本思想

このベンチマークでは、

> **「人間が欲しいものを正しく作ったか」**

を最優先する。

そのため、

**要求を減らすこと > 不要なものを増やすこと**

の順で厳しく評価する。

また、

**Research → Judge → Implementation → Validation → Repair**

のどこで失敗したかを記録し、単純なモデルランキングだけではなく、工程ごとのモデル特性を把握できるようにする。

---

## 17. 機械採点 v1.0（実装層）

実装層ベンチが、`implementation_class` から付ける初期値。Validator / 実行結果 / Registry はまだ見ない。

| class | requirement | correctness | integration | overimplementation | cap | pass |
|---|---:|---:|---:|---:|---:|---|
| `ok` | 40 | 30 | 20 | 10 | なし | true |
| `unnecessary_finding`（余分1件） | 40 | 30 | 20 | 8 | なし | true |
| `unnecessary_finding`（余分2～3件） | 40 | 30 | 20 | 6 | なし | true |
| `unnecessary_finding`（余分4件以上） | 40 | 30 | 20 | 3 | なし | true |
| `finding_not_used`（関連 finding のみ） | 20 | 0 | 20 | 10 | 69 | false |
| `finding_not_used`（スタブ） | 0 | 0 | 20 | 10 | なし | false |
| `wrong_command` | 0 | 0 | 15 | 10 | 49 | false |
| `empty_code` | 0 | 0 | 0 | 10 | なし | false |

JSON が取れない `empty_code` は適合 0。実装ベンチはファイルを書かないので、破壊系 cap（29 / 19）はまだ付けない。

正解 finding は1つでも複数でもよい。`correct_fragments` がすべて code にあれば要求達成、欠けていれば `finding_not_used`。余分があれば `unnecessary_finding`。

Repair は R1〜R5 を分けて測る。仕様は `docs/repair_types.md`。`AI_AGENT_REPAIR_FAMILY=R2` のように家族単位でベンチする。

これにより、

* 単一選択で余計な finding まで使う
* 複数選択で必要な finding を揃える

を分けて測る。

## 15. Clarity

Clarity ベンチは 100 点採点の対象外である。次の5項目を機械で見る。

1. 要求が明確か判断できた
2. 必要な場合だけ質問した
3. 質問内容がユーザーの決定事項だった
4. 実装方法をユーザーに丸投げしなかった
5. Research に正しく引き渡した（材料隔離と PROJECT_CONTEXT）

Clarity 問答由来の STATE を Research へ渡す確認は `python -m research.llm_benchmarks.clarity_state_research`。最初から STATE がある持続性ベンチとは別である。

```text
python -m research.llm_benchmarks.clarity_benchmark
```

## 18. Research → Implementation

④は 100 点採点の対象外である。Clarity で「使用率です」まで得た STATE を持ったまま、Research で確定した方法を Implementation が Tool にできるかを6項目で見る。Repair は `skipped`。

1. Research が方法を選んだ
2. Judge が採用した
3. コードが生成された
4. コードが採用した finding と一致する
5. Registry / `tools.system.*` に入った
6. 実行できた

失敗時の `fail_stage` は `research` / `judge` / `implementation`。値の整形不足はここでは落とさず、⑤ Repair に残す。

④本体は Judge 孤立テストで A を確認したあと再開する。工程別採点は `pipeline_stages` に残す。

探索再起動 v3 後の④本体記録: `research_implement_snapshot_exploration_v3.json`（上書きしない）。`research_implement_results.json` に全履歴。

| 実行 | fail_stage | error | 要点 |
|---|---|---|---|
| 1回目（探索 retry 前） | research | stagnation | usable finding `--`、3ラウンドで同一 PowerShell 失敗 |
| 2回目（探索 retry 後） | judge | max_research_rounds | usable finding ok、wmic 等へ切替するが Judge 未採用 |

| 工程 | キー |
|---|---|
| STATE維持 | state_held |
| Research候補生成 | candidates_generated |
| Verifier実行 | verifier_ran |
| Verifier失敗検出 | verifier_failure_detected |
| Judge A品質 | judge_a_quality |
| Research再調査 | research_retried |
| usable finding | usable_finding |
| Judge採用 | judge_adopted |
| Implementation code | implementation_code |
| Tool実行 | tool_runs |

Verifier 失敗後の Judge は **missing の質** を A/B/C/FAIL で見る（`judge_verify_failed_retry`）。C baseline は `judge_verify_retry_baseline_c.json`。

usable finding 採用は **ACCEPT/MISREJECT/FAIL**（`judge_usable_usage_percent`）。

### Judge 固定回帰基準（上書きしない）

契約フェーズ `verify_gap_adopt_v5` で次を baseline JSON に凍結済み。

| baseline | 合格基準 | 内容 |
|---|---|---|
| `judge_verify_retry_baseline_a.json` | A 3/3 | Verifier 失敗後 missing |
| `judge_adopt_usable_baseline_accept.json` | ACCEPT 3/3 | sample=48 採用 |

C baseline（`judge_verify_retry_baseline_c.json`）は履歴として残す。④本体の results とは別。

### Research 再調査（follow-up）

Judge missing + 失敗候補を固定し、Web 候補生成だけを測る。④本体は回さない。

固定ケース `judge_usable_usage_percent`（hand-crafted Round 3 相当）: **ACCEPT 3/3** baseline `judge_adopt_usable_baseline_accept.json`。

④本体から抽出したケース `judge_usable_from_research_implement_round7`（探索再起動 v3 後 Round 7、sample=`68719476736`）: ④と同様の誤拒否が孤立 Judge で再現するかを見る。④本体は回さない。**実測 MISREJECT 3/3**（④本体 Round 7 と整合）。

```text
python -m unittest tests.test_judge_adopt_usable
python -m research.llm_benchmarks.judge_adopt_usable
$env:AI_AGENT_JUDGE_ADOPT_CASE='judge_usable_from_research_implement_round7'
python -m research.llm_benchmarks.judge_adopt_usable
```

### Implementation 孤立（Judge ACCEPT 固定）

Clarity STATE・Verifier 成功 sample=48・Judge ACCEPT を固定し、Implementation だけを測る。ケース: `implement_from_judge_accept_usage_percent`。④本体は回さない。

見るもの: 採用済み finding を既存 Tool 構造へ実装できるか、Registry 登録できるか、実行できるか。

**実測（deepseek_coder_v2_16b）**: `ok` 3/3、score 100 S、`registry=True` `runs=True`（④の Judge 採用まで固定した Implementation 単体）。

```text
python -m unittest tests.test_implementation_classify
$env:AI_AGENT_IMPLEMENT_CASE='implement_from_judge_accept_usage_percent'
$env:AI_AGENT_MODEL='deepseek_coder_v2_16b'
$env:AI_AGENT_IMPLEMENT_REPEAT='3'
python -m research.llm_benchmarks.implementation_benchmark
```

| 判定 | 意味 |
|---|---|
| A | missing を理解し、前回とは異なる有効な候補 |
| B | 再調査するが候補が曖昧 |
| C | 前回と同じ候補を繰り返す |
| FAIL | JSON なし等 |

正解コマンドは採点に入れない。探索空間が変わるかを見る。ケース: `research_followup_after_verify_fail`。

`search_results` は実検索キャプチャを凍結する（手書きの良質ヒットではない）。④本体は各ラウンドの `web_hits` を `research_rounds_detail` に残す。

C 3/3 baseline: `research_followup_baseline_c.json`（上書きしない）。クエリ現状: `research_followup_query_snapshot.json`。

`research_followup_v3`（空ヒット + `exploration_hints` + 未試行 command 誘導）: 同一固定ケースで **A 3/3**（wmic へ切替）。

改善手順（④本体は回さない）:

1. missing → `structure_search_keywords`
2. 無関係ヒット → `filter_relevant_hits`
3. 空ヒット + prior_failures → `exploration_hints` / `empty_search_restart`（`available_commands` から別経路）
4. 拒否候補の繰り返し → `exploration_retry_extra`（`run_research` にも配線済み）
5. **同一固定ケース**で `research_followup` を再測
6. A に近づいたら④へ戻す

### 7. Judge 候補選択ベンチ — `judge_select_method`

同じ目的（メモリ使用率）に対して **5 つの取得方法** を並べ、Judge が正しく選別できるかを見る。

| 候補 | 内容 | 正解 |
|------|------|------|
| A | 使用率を直接返す | ○ |
| B | 総メモリ＋空きメモリから計算 | ○ |
| C | 総メモリ容量だけ | ✕ |
| D | 使用量 bytes | ✕ |
| E | CPU 使用率 | ✕ |

| グレード | 意味 |
|----------|------|
| CORRECT | `satisfies_request=true` かつ不正候補を採用していない |
| OVER_ACCEPT | 不正候補（C/D/E）に言及しつつ採用 |
| WRONG_REJECT | 正しい候補があるのに `satisfies_request=false` |
| FAIL | JSON なし等 |

ケース: `judge_select_method_memory_usage`。正解コマンドは契約に入れない。

**結果: CORRECT 3/3** (`deepseek-coder-v2:16b`, 2026-08-19)

### 8. Judge 候補選択ベンチ② — 電力 W（直接/計算/単位変換）

② 直接取得と計算取得の両方を許す。③ 単位変換（kW→W）も許すが Wh は不可。

| 候補 | 内容 | 正解 |
|------|------|------|
| A | 電力センサー → 123 W 直接 | ○ |
| B | 電圧×電流 = 200 W 計算 | ○ |
| C | 0.048 kW（×1000 = 48 W 変換可能）| ○ |
| D | 電流 2.0 A だけ（電力にならない）| ✕ |
| E | 電力量 200 Wh（W ではない）| ✕ |
| F | CPU 使用率（無関係）| ✕ |

ケース: `judge_select_method_power_watt`。

**結果: CORRECT 3/3** (`deepseek-coder-v2:16b`, 2026-08-19)

### 9. ④本体 `research_implement` 再実行（複数経路探索前）

**結果: fail_stage=judge  10 ラウンド消費**

- Research が `TotalPhysicalMemory`（存在しない）を使い 0除算エラーが続く
- Round 7 で `TotalVisibleMemorySize` の sample が取れたが Judge が「total physical memory であり usage rate ではない」と誤読
- ボトルネックは **Research のコマンド品質** と **Judge の sample 誤読**

### 10. Research 複数経路探索の導入

契約に `route` / `multi_route` / `route_diversity` を追加。`build_route_hints` で STATE から経路ヒントを生成。

### 11. ④本体 `research_implement` 再実行（複数経路探索後）

**結果: fail_stage=implementation  2 ラウンドで Research/Judge 完了**

- **Round 1**: candidates=4（複数経路生成に成功）、verify_fail あり、Judge satisfies=false
- **Round 2**: candidates=3、verify_fail=false、Judge satisfies=true — **Judge 採用成功**
- **64 秒で Research→Judge 完了**（以前は 107 秒で 10 ラウンド消費して失敗）
- Implementation が empty_code で失敗（次のボトルネック）

```text
python -m unittest tests.test_judge_regression_baseline
python -m research.llm_benchmarks.judge_regression
python -m research.llm_benchmarks.judge_regression --live
python -m research.llm_benchmarks.research_followup
python -m research.llm_benchmarks.judge_adopt_usable
python -m research.llm_benchmarks.judge_verify_retry
python -m research.llm_benchmarks.judge_select_method
python -m research.llm_benchmarks.research_implement
```

