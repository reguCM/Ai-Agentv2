# Grill observation v0

Goal を仕様 Tree へ段階的に具体化する観察実験。Production Chat UI / Runtime には接続しない。

既存 Chat UI（`python ai_tool/run_chat_ui.py`）は Agent Turn・Tool・Production Session に結びつくため、今回は再利用していない。

## 続行

同じ Run で人間回答を入れる（次の質問はまだ出さない）:

```
python research/grill_observation_v0/run_turn.py --run-id <RUN_ID> --answer A
```

回答後に次の1問を出す:

```
python research/grill_observation_v0/run_turn.py --run-id <RUN_ID> --ask-next
```

任意の地点で止められる。raw は `turn_N_raw.txt`、状態は `run.json`。

## Q2 中間層（独立 Run）

既存 Q1 Run は読み取り専用。新しい Run を作り `parent_run_id` で参照する。

```
python research/grill_observation_v0/run_q2_layer.py --parent 20260909T003636Z
```

Q2 を1問生成したところで停止する。Human 回答は入れない。
