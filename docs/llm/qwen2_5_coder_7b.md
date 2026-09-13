# qwen2.5-coder:7b

自己修復の仕様は `docs/architecture.md` と `docs/repair_types.md` を正とする。  
Validator と CONTRACT はモデルで変えない。包装は基準の Qwen3 8B と同じ。

プロファイル: `config/llm_models.yaml` の `qwen2_5_coder_7b`

## 設定

- model: `qwen2.5-coder:7b`
- context_limit: 4096
- prompt_style: `japanese_verbose`
- 材料: 短縮しない

## 実測

`research/llm_benchmarks/repair_results.json` の `runs` を参照。temperature=0 では 4/6 が3回続いた。NG は毎回①④で、区切り線 `--------------` を返す。
