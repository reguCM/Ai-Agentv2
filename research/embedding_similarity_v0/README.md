# Embedding similarity v0

独立した小規模実験。Production Agent / Conversation Grill には接続しない。

類似度の閾値は正本化しない。この結果だけで候補を SELECTED にする規則は作らない。

## 実行

生成LLM（既定 `qwen3:14b`）を keep_alive したまま、小型 Embedding で日本語・英語・コード寄りの言い換えを比較する。

```
python research/embedding_similarity_v0/run_v0.py
```

結果は `research/embedding_similarity_v0/runs/<UTC>/`。
