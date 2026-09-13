# 判断層実験（Tool Calling 非対応 LLM）

既存の Problem Analysis / Problem Solving / Tool Calling圧縮実験には接続しない。

実行:

```text
python -m research.llm_benchmarks.judgment_layer_experiment.bench
```

単体テスト（実 LLM なし）:

```text
python -m pytest tests/research/llm_benchmarks/judgment_layer_experiment -q
```

- Prompt: `Analyze the problem and indicate the next investigation or action needed.`
- `tools=` は渡さない
- Schema は要求しない
- 仮 Mapping は M1 のみ実行。正式規則ではない
