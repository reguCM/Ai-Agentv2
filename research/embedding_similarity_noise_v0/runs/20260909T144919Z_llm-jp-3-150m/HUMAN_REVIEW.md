# Embedding similarity Japanese input noise v0

- run_id: `20260909T144919Z_llm-jp-3-150m`
- embed_model: `llm-jp/llm-jp-3-150m`
- backend: `llm-jp-3-150m`
- device: `cpu`
- embedding_method: `mean_pool_last_hidden_state`
- gen_model: `None`
- with_gen: `False`
- Production / Grill 接続: なし
- 閾値正本化: なし
- SELECTED規則: なし

`gold_is_top` はこの候補集合で意図候補が1位だった観測。SELECTED規則ではない。

## 資源

- baseline: VRAM 3752 / 12288 MiB, RAM used 38865 / 65277 MB
- after_model_load: VRAM 3752 / 12288 MiB, RAM used 39685 / 65277 MB
- after_embed: VRAM 3752 / 12288 MiB, RAM used 39678 / 65277 MB

## ノイズ種別まとめ


失敗したノイズ種別: None

## 失敗ケース

なし

## 各クエリ
