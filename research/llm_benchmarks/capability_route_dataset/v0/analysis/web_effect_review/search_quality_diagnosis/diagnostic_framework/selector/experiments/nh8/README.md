# NH8 Uncertainty-Gated Escalation

**目的:** 小型LLM Observation を基本経路とし、機械的不確実性ゲートが HIGH のときだけ大型LLMへ送る。

LLM に「大型へ送るべきか」は聞かない。大型の回答も Observation → Mapping → Selector を通す。

## 実行

```bash
python diagnostic_framework/run_nh8_uncertainty_gated_escalation.py
```

出力: `runs/20260827_145000/nh8_uncertainty_gated_escalation/`

## 条件

- A Gold fingerprint
- B Small only（NH7-D 相当、NH7-C Observation 再利用）
- C Always Large（qwen3:14b 独立 Observation）
- D Gated（small → gate → large 再観測）
