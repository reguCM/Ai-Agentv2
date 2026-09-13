# qwen3:14b

自己修復の仕様は `docs/architecture.md` と `docs/repair_types.md` を正とする。  
このファイルは **このモデルへの最適化メモ** だけを書く。Validator と CONTRACT はモデルで変えない。

プロファイル: `config/llm_models.yaml` の `qwen3_14b`

## 設定

8B と同じ包装。14B 専用の分岐・プロンプト追加はしない。

- model: `qwen3:14b`
- context_limit: 4096
- prompt_style: `japanese_verbose`
- 材料: 短縮しない（`drop_keys: []`、ソース切り詰めなし）

## 実測

`research/llm_benchmarks/repair_results.json` の `runs` を参照。temperature=0 では 6/6 が3回続いた。8B と同じ包装・同じベンチで、成功率では差が出なかった。
