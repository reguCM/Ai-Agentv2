# GPT / Cursor 上位判断層実験

既存 Problem Analysis / Problem Solving / 判断層実験には接続しない。

Failure 取得:

```text
python -m research.llm_benchmarks.upper_judgment_experiment.capture
```

単体テスト:

```text
python -m pytest tests/research/llm_benchmarks/upper_judgment_experiment -q
```

Cursor 解汾は、設計文を渡さず `SOLVER_PROMPT.txt`（実 Failure）だけを与える。
GPT のライブ呼び出し経路はこの環境に無い。入力は `gpt/PROMPT.txt` に保存する。
