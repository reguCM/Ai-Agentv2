# capability_route_dataset v0

観測専用データセット（判断傾向発見）。能力スコアや正解ラベルは付けない。

## 構成

```text
v0/
├── cases.json
├── results/          # 収集ランごとに run_<timestamp>/
├── analysis/         # 人間向け要約・基礎スモーク
└── _gen_cases.py     # cases 再生成用（必要時）
```

## 収集

```text
.venv\Scripts\python.exe research/llm_benchmarks/capability_route_cases/run_collection.py ^
  --cases research/llm_benchmarks/capability_route_dataset/v0/cases.json ^
  --out research/llm_benchmarks/capability_route_dataset/v0/results/run_manual
```

- `AI_AGENT_TOOL_GATE=off` は使わない（collection trust）
- Pipeline 非起動
- Stage3 ラベルは null のまま

## 禁止

heuristic 改変、少数例での判断ロジック修正、実行権限への接続。
