# deepseek-coder-v2:16b

自己修復の仕様は `docs/architecture.md` と `docs/repair_types.md` を正とする。  
このファイルは **このモデルへの最適化メモ** だけを書く。

プロファイル: `config/llm_models.yaml` の `deepseek_coder_v2_16b`

## 設定

- model: `deepseek-coder-v2:16b`
- context_limit: 4096（材料が長いと overflow / HTTP 400）
- prompt_style: `english_compact`
- 材料: 契約は残す。`current_source` は 2500 文字まで。compact JSON

## プロンプト処理

`prompt_style: english_compact`

- CONTRACT は同じ条項の英語。項目は消さない
- MATERIALS は compact JSON。ソースだけ切り詰める
- 再試行は `Output ONLY the JSON object.`

Validator の分岐は変えない。プロンプト包装だけの対策である。

## 実測（temperature=0、3回）

`research/llm_benchmarks/repair_results.json` の `runs` と `failure_analysis.md` を参照。毎回 **3/6**。

向いている: ② キー修正、③ dict 化、⑥ コマンド置換  
弱い（3回とも同一。プロンプト強化は打ち止め）:

- ① `unparsed_output` / ④ `subprocess_result_handling` → 固定インデックスパースで IndexError。機械側で `parsed_table` を渡す
- ⑤ `stub_value` → findings を使わず `'未実装'` のまま。LLM 領域。履歴は `repair_failures.json` と `llm_failure_memory`
