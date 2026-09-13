# KSS-1.1 Measurement Report

- experiment_id: `kss11_20260820_151041`
- measurement_ok: **True**
- formalize_phase5_1: False
- auto_routing: False

## Aggregate

- decision_count: 87
- decision_source_distribution: `{'verifier': 29, 'llm_judgment': 13, 'deterministic_rule': 45}`
- evidence levels: `{'high': 2, 'medium': 26, 'low': 1}`
- provenance rate: `1.0`
- threshold rate: `0.667`
- high_evidence_failure_count: 0
- low_evidence_success_count: 0
- failure_by_evidence_level: `{'medium': 3}`
- success_by_evidence_level: `{'high': 1}`

## Missing fields (not invented)

- `llm_judge_confidence_numeric`
- `progress_decision_confidence`
- `proposal_decision_confidence`
- `verify_confidence_numeric`
- `help_escalation_decision`
- `partial_llm_judgment`
- `judge_accept_weights`
- `official_source_reliability_numeric_table`
- `composite_web_confidence`
- `composite_decision_confidence`

## Recommendation

**Primary: A**

既存の verifier high/low・progress reason・live_skip・escalation・no_gain だけで failure/success の根拠分解は可能。KSS-1 の LLM 自己申告は coverage=0 で信頼できないため B は後回し。HELP/上位LLM routing (D/E) はまだ根拠不足。F は『単一 confidence 数値化』に限れば妥当。

### Options

- **A**: verifier/rule 校正を優先（推奨）
- **B**: LLM structured self-assessment（取得率が低い限り後回し）
- **C**: Web evidence 強化（hit_score の decision 紐付けが次）
- **D**: 上位 LLM 相談判定（データ不足）
- **E**: HELP escalation（経路未実装）
- **F**: 単一 confidence 定量化は難しい（自己申告失敗を踏まえ正当）

## Disclaimer

Observation-only. Do not invent missing scores. Do not implement routing/HELP/Web priority from this run alone.
