# qwen3:8b

自己修復の仕様は `docs/architecture.md` と `docs/repair_types.md` を正とする。  
このファイルは **このモデルへの最適化メモ** だけを書く。

プロファイル: `config/llm_models.yaml` の `qwen3_8b`

## 設定

- model: `qwen3:8b`
- context_limit: 4096
- prompt_style: `japanese_verbose`
- 材料: 短縮しない（`drop_keys: []`、ソース切り詰めなし）

## プロンプト処理

`prompt_style: japanese_verbose`

- CONTRACT は日本語の固定条項をすべて付ける
- MATERIALS は indent 付き JSON。ソースは切らない
- 契約項目は落とさない。包装だけ変える

## 実測

`research/llm_benchmarks/repair_results.json` の `runs` を参照。temperature=0 では 6/6 が3回続いた。
