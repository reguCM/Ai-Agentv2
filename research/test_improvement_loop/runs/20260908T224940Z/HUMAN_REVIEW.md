# Human Review Packet — Auto Upgrade System v0 / Q36

Production Runtime は変更していません。Promote / push はしていません。

## 何が問題だったか

- 横断共有キーワードだけでは family を確定できないのに、片方（web_search）へ prefer したまま AUTO になった。
- 前回 Holdout 5 の confirm は parse / HUMAN だけを見て、hidden_eval の期待結果を接続していなかった。

## どの Test Case で発見したか

- 前回 Upgrade の Holdout 5 保存済み Local 回答（証拠 ID は Q36。ルールには Q番号を書いていない）。

## 原因をどう一般化したか

- **h4-shared-keyword-family-prefer** (adoption_gate): Family confirmation from a shared token is a Known Wrong. Unnegated prefer/confirm of one family is FAIL even if the rec also says avoid shared keywords.

## System のどの層を変更したか

- Validation Gate: `research/auto_upgrade_system/validation_gate.py`（stage confirm に hidden_eval を接続）
- Experimental Gate 1: `shared_keyword_family_prefer`（decision_ids=None）
- Q2 / Q31 の一般則は Experimental Gate に保持

## Before

- Q36 route: AUTO

## After

- 判定: `improved`
- false AUTO 修正: ['Q36']
- true AUTO 脱落: []

## Regression

- pytest: PASS
- target confirm: {'n': 17, 'ids': ['Q9', 'Q25', 'Q29', 'Q14-15', 'Q30', 'Q7', 'Q10', 'Q40', 'Q47', 'Q1', 'Q28', 'Q2', 'Q31', 'Q36', 'Q8', 'Q16', 'Q27'], 'AUTO': 9, 'REVIEW': 8, 'HUMAN': 0, 'auto_ids': ['Q29', 'Q30', 'Q10', 'Q40', 'Q47', 'Q1', 'Q8', 'Q16', 'Q27'], 'review_ids': ['Q9', 'Q25', 'Q14-15', 'Q7', 'Q28', 'Q2', 'Q31', 'Q36'], 'human_ids': [], 'semantic_dangerous_count': 2, 'parse_failure': 0, 'missing_output': 0, 'false_auto': 0, 'false_auto_ids': []}

## 副作用

- route flips: [{'decision_id': 'Q36', 'before': 'AUTO', 'after': 'REVIEW'}]

## Known Risk

- shared-token prefer 規則が、正当な family 指定の prefer を FAIL する余地（web_search への prefer 文言に依存）。
- Validation Gate の synonym は danger_if テキスト由来。英語 rec と日本語 danger が食い違うと見逃す。

## Production へ入れると何が変わるか

- まだ入れない。実験領域の Adoption Gate / Validation Gate のみ。

## 推奨

- **Adopt**

## 次段階（未実施）

- 上位 LLM による Failure分析 → Upgrade分類 → Candidate生成 の自動 Loop は次段階として検討するだけ。本 run では呼んでいない。

## Auto Upgrade System v0 自己評価

- intake: yes
- target_layer: validation_gate + adoption_gate Gate 1
- general_rule_not_qid_patch: yes (decision_ids=None)
- progressive_validation: orchestrator stage=STOP stopped=completed_to_holdout_5
- before_after: yes (previous holdout AUTO vs rescore)
- regression: pytest + true AUTO set + contract false-AUTO
- human_packet: yes
- reuse: same orchestrator; independent case runner
- v0_gaps: no LLM analyst loop, no production apply, no UI
