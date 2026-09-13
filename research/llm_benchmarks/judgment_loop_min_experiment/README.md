# 実コード型・判断ループ最小実験

既存実験・本番 Agent には接続しない。

```text
python -m pytest tests/research/llm_benchmarks/judgment_loop_min_experiment -q
python -m research.llm_benchmarks.judgment_loop_min_experiment.bench
```

- Native `tools=` なし
- Schema なし
- 暫定 Mapping は `inspect helper.py` を `read_file` にする程度
- 判断失敗と Mapping 不能は別記録
