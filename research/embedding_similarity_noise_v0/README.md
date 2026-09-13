# Embedding similarity — Japanese input noise v0

独立実験。Production Agent / Conversation Grill には接続しない。

類似度の閾値は正本化しない。この結果だけで候補を SELECTED にする規則は作らない。

人間が実際に行いそうな日本語入力崩れでも、意図した意味の候補が上位になるかを測る。

## 実行

既定は前回実験と同じ `qwen3-embedding:0.6b`。生成LLMの同時常駐は必須ではない（`--with-gen` で観測可）。

```
python research/embedding_similarity_noise_v0/run_v0.py
```

HuggingFace 比較（`cl-nagoya/ruri-small-v2` と `llm-jp/llm-jp-3-150m` の仮 mean-pool）:

```
pip install -r research/embedding_similarity_noise_v0/requirements-hf.txt
python research/embedding_similarity_noise_v0/run_hf_v0.py
```

Grill 後の path + ヒット文照合に、翻訳層を足して測る場合:

```
python research/embedding_similarity_noise_v0/run_grill_translate_v0.py
```

主評価は既存 `match_clarification_to_candidate_paths` が unique gold になるか。cosine は補助。Production には接続しない。

よくある AI-Agent 要求（ファイル読取 / リポジトリ検索 / ネット検索）で同じノイズ種別を試す場合:

```
python research/embedding_similarity_noise_v0/run_v0.py --cases research/embedding_similarity_noise_v0/cases_agent_common.json --run-suffix agent-common
python research/embedding_similarity_noise_v0/run_hf_v0.py --cases research/embedding_similarity_noise_v0/cases_agent_common.json --run-suffix agent-common
```

```
python research/embedding_similarity_noise_v0/run_v0.py --cases research/embedding_similarity_noise_v0/cases_agent_slots.json --run-suffix agent-slots
python research/embedding_similarity_noise_v0/run_hf_v0.py --cases research/embedding_similarity_noise_v0/cases_agent_slots.json --run-suffix agent-slots
```

```
python research/embedding_similarity_noise_v0/run_hf_v0.py --cases research/embedding_similarity_noise_v0/cases_ja_gold.json --run-suffix ja-gold
python research/embedding_similarity_noise_v0/run_v0.py --cases research/embedding_similarity_noise_v0/cases_ja_gold.json --run-suffix ja-gold
```

結果は `research/embedding_similarity_noise_v0/runs/`。
