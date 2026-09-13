# NH12-2 Observation Compression Shadow Experiment

本番非接続。Mechanical Log Compression → Fixed Slots → Observation 比較。

- Runner: `diagnostic_framework/run_nh12_2_observation_compression.py`
- Code: `selector/experiments/nh12_2/`
- Baseline A: NH12-1 `runs/20260828_110500/nh12_real_shadow_expansion/`（再実行しない）

Conditions:
- **A**: NH12-1 baseline（再利用）
- **B**: Compression → mechanical slot mapping（LLMなし）
- **C**: Compression → Observation LLM → Gate（Largeなし）
- **D**: C + Large LLM（Gate条件時のみ）
