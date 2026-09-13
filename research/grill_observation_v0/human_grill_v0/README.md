# Human Grill 自然出口・人間仕様抽出

既存 Grill Run は変更しない。LLM は人間回答を代行しない。

最初の1問:

```
python research/grill_observation_v0/human_grill_v0/run.py --new
```

人間回答のあと、同じ Run で次の1問:

```
python research/grill_observation_v0/human_grill_v0/run.py --run-id <RUN_ID> --answer "Bがいい" --ask-next
```
