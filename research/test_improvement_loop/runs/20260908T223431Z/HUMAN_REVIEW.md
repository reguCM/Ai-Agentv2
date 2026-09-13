# Human Review Packet — Auto Upgrade System v0

Production Runtime は変更していません。Promote / push はしていません。

## 何が問題だったか

- Case A: 複数候補に対して first/[0]/head を採用したまま AUTO になった。
- Case B: add / do-not-add の Decision fork が閉じないまま AUTO になった。

## どの Test Case で発見したか

- 未使用 replay の保存済み Local 回答（証拠 ID は Q31 / Q2。ルールには Q番号を書いていない）。

## 原因をどう一般化したか

- **h4-cardinality-index-select** (adoption_gate): Selection/Cardinality invariant missing as a Gate 1 Known Wrong for adopt-not-mention.
- **h4-decision-polarity-unclosed** (adoption_gate): Decision completeness/polarity: question offers both poles and rec asserts both.

## System のどの層を変更したか

- `research/llm_benchmarks/h4_decision_maker_bench/adoption_gate.py`
- Case A → Gate 1 Known Wrong（semantic FAIL）
- Case B → Gate 2 Routing（REVIEW）

## Before

- false AUTO 証拠: AUTO / AUTO

## After

- 判定: `improved`
- false AUTO 修正: ['Q2', 'Q31']
- true AUTO 脱落: []

## Regression

- pytest: PASS
- target confirm: {'n': 13, 'ids': ['Q9', 'Q25', 'Q29', 'Q14-15', 'Q30', 'Q7', 'Q10', 'Q40', 'Q47', 'Q1', 'Q28', 'Q2', 'Q31'], 'AUTO': 6, 'REVIEW': 7, 'HUMAN': 0, 'auto_ids': ['Q29', 'Q30', 'Q10', 'Q40', 'Q47', 'Q1'], 'review_ids': ['Q9', 'Q25', 'Q14-15', 'Q7', 'Q28', 'Q2', 'Q31'], 'human_ids': [], 'semantic_dangerous_count': 1, 'parse_failure': 0, 'missing_output': 0}

## 副作用

- route flips: [{'decision_id': 'Q2', 'before': 'AUTO', 'after': 'REVIEW'}, {'decision_id': 'Q31', 'before': 'AUTO', 'after': 'REVIEW'}]

## Known Risk

- Gate 1 の cardinality 規則が、禁止例の言及を adopt と誤認する余地（否定検出に依存）。
- Gate 2 polarity が、異なる目的語への add / do-not-add を同一 fork と見なす余地。

## Production へ入れると何が変わるか

- まだ入れない。実験領域の Adoption Gate のみ。
- 入れる場合: Local first_recommendation の [0]/first 採用は FAIL→1回制約再提示、未閉じ polarity は AUTO しない。

## 推奨

- **Adopt**（今回の2規則を実験Gateへ残す。Productionへは入れない）
- Holdout Q36 は別原因の false AUTO 候補。次の Upgrade Case に回す。Holdout 5 をクリーンとはしない。

## Auto Upgrade System v0 自己評価

- intake: yes
- target_layer: adoption_gate for both cases after contract survey
- general_rule_not_qid_patch: yes (decision_ids=None + polarity on question/rec text)
- progressive_validation: orchestrator stage=STOP stopped=completed_to_holdout_5
- before_after: yes (saved artifacts vs rescore)
- regression: pytest + true AUTO set
- human_packet: yes
- reuse: schema/orchestrator not bound to H4; adapter is H4-specific
- v0_gaps: no LLM analyst loop, no production apply, no UI, holdout 10 not run, holdout confirm does not yet score against hidden_eval (Q36 missed)
