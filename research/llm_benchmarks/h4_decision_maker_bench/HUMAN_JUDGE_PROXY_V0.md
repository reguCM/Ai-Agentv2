# Local LLM Human-Judge代替 仮仕様 v0

**内部ID:** `local_llm_human_judge_proxy`  
**状態:** 仮仕様 v0 / H4 で実験済み / Production 未統合  
**根拠範囲:** H4 Decision Maker Bench の今回の実験結果のみ。汎用保証ではない。  
**記録日:** 2026-09-09

コード正本:

- `research/llm_benchmarks/h4_decision_maker_bench/adoption_gate.py`
- `research/llm_benchmarks/h4_decision_maker_bench/run_bench.py`

評価専用（Local に送らない）:

- `research/llm_benchmarks/h4_decision_maker_bench/packets/hidden_eval.json`

関連実験 run（参照。本文は書き換えない）:

- Gate replay: `research/llm_benchmarks/h4_decision_maker_bench/results/20260908T213718Z/`
- Routing rescore: `research/llm_benchmarks/h4_decision_maker_bench/results/20260908T220502Z/`

---

## 目的

Local LLM を、人間の Decision / Judge 選択の **一部代替** として使う。

人間の最終承認を省略するものではない。Local の `first_recommendation` をそのまま採用仕様にもしない。

## 核心前提

**Local recommendation ≠ Final / Locked Decision。**

Local 出力は候補である。Gate を通っても、人間 Review の対象になり得る。hidden_eval の adopted 本文は Local へ送らない。Strong / Cursor の adopted 回答も retry に載せない。

Q番号 allowlist で Routing しない。

---

## Gate 1（採用前の意味検査）

対象:

- Known Wrong
- Locked Prior
- semantic invariant
- 構造不備（必須欄欠落、空の `first_recommendation` など）

FAIL 時:

- 正解（hidden adopted）を教えない
- Contract / Known Wrong の禁止内容 / Locked Prior だけを再提示する
- retry は原則 1 回

## heuristic dangerous と semantic dangerous

分離する。

- **semantic dangerous:** Gate 1 の FAIL 原因になり得る（Known Wrong の unnegated adopt など）
- **heuristic dangerous:** 記録する。これだけを原因にして FAIL しない

## Gate 2（Routing）

| 経路 | 意味（H4 実験での使い方） |
|---|---|
| AUTO | 既存 Contract / コードで一意に閉じた。semantic PASS。価値判断ではない |
| REVIEW | 契約の再確認が要る。禁止採用のやり直し、未閉じの Decision fork、未検証の safety 変更、未解決 artifact など。人間の趣味判断そのものではない |
| HUMAN | 残る選択が利用者の目的・選好である。または破壊的操作に既存の禁止/承認が無い |

`need_human` / `uncertainty` / `needs_deep_review` は **補助信号** である。単独の Routing 条件にしない。H4 の 38 件 batch では `needs_deep_review=true` が全件についており、これで HUMAN にすると Routing が潰れる。

---

## Experimental 一般則（Q番号に紐づけない）

H4 の false AUTO から一般化した。Experimental Gate に保持。Production 未統合。

| ID | 層 | 概要 | 発見の証拠 ID（ルールには書かない） |
|---|---|---|---|
| `cardinality_index_or_head_select` | Gate 1 | 2+ 候補で first / `[0]` / head の unnegated adopt は FAIL。禁止例としての言及は FAIL しない | Q31 |
| `polarity_fork_unclosed` | Gate 2 | 質問が両極を出し、rec が両方を主張したままなら AUTO しない | Q2 |
| `shared_keyword_family_prefer` | Gate 1 | 横断共有トークンから片方 family を prefer / confirm する unnegated adopt は FAIL。Avoid したうえで Prefer する混合文も FAIL | Q36 |

文をまたいだ Avoid は、後続文の unnegated adopt を打ち消さない。

---

## 規模の進め方

標準 Chunk 候補: **10 Decision 前後**（H4 の chunk 実装は 8–12 を想定し、実グループは先頭 10 件単位）。

**新しい経路 / 形式**では、一気に 10 へ行かない。

1. 1 件 → 確認
2. 5 件 → 確認
3. 10 件

既存形式の再現は保存済み replay を優先し、不要な LLM 再実行をしない。

## 長時間処理

H4 bench runner が持つ観測:

- overflow preflight（ctx 超過見込みなら本実行前に止める）
- heartbeat
- timeout を明示する
- parse / retry を記録する

---

## 境界

これは H4 ケースからの **仮仕様** である。

- 他 Goal / 他モデル / 他 Decision 集合への汎用保証ではない
- Production Runtime には入れていない
- 人間 Review を省略しない

---

## 次回改善時に見るべき点

- false AUTO が実運用（または次の実験集合）で出たか
- AUTO / REVIEW / HUMAN の Routing 精度（true AUTO 脱落、false AUTO 残存、HUMAN 過発火）
- 別モデルでも同じ Gate が有効か
- 10 件 Chunk が妥当か（overflow / 欠落 / 文脈切れ）
- 1 → 5 → 10 を新しい経路で守れたか
- heuristic と semantic の混同が再発していないか
- Production 統合の必要性（まだ必要とは限らない）
- hidden_eval の英語 rec / 日本語 danger 食い違いで Validation が見逃していないか
