# Tool Calling圧縮仮説・比較実験

既存の Problem Analysis / Problem Solving 実験・fixture・結果・本番 Agent には接続しない。

実行:

```text
python -m research.llm_benchmarks.tool_calling_compression_experiment.bench
```

単体テスト（実 LLM なし）:

```text
python -m pytest tests/research/llm_benchmarks/tool_calling_compression_experiment -q
```

- Prompt: `Resolve the problem.`
- 経路 A: Ollama `tools=` Native Tool Calling（テキストからの Tool 抽出は実行しない）
- 経路 B: `tools=` なし。文章のみ。Tool は実行しない
- モデル: `qwen3:14b` / `gemma3:12b`
