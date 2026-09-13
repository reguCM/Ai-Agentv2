# gemma3:12b

自己修復の仕様は `docs/architecture.md` と `docs/repair_types.md` を正とする。  
Validator と CONTRACT はモデルで変えない。包装は基準の Qwen3 8B と同じ。

プロファイル: `config/llm_models.yaml` の `gemma3_12b`

## 設定

- model: `gemma3:12b`
- context_limit: 4096
- prompt_style: `japanese_verbose`
- 材料: 短縮しない

## 実測

`research/llm_benchmarks/repair_results.json` の `runs` を参照。temperature=0 では 4/6, 3/6, 4/6。①は `'Loa'`、④は生表が残る。2回目の⑥は見出し `LoadPercentage` で落ちた。
