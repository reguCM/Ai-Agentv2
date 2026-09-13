# NH10 Mechanical Prefill + Explicit high_slots Gate

本番 Agent / Tool / Manager / Selector / search_web は変更しない。NH1–NH9 run は再利用のみ。

```bash
python diagnostic_framework/run_nh10_mechanical_prefill_gate.py
```

出力: `runs/20260827_163000/nh10_mechanical_prefill_gate/`

## Conditions

| Cond | 内容 |
|------|------|
| A | NH9-C baseline（保存結果再利用、LLMなし） |
| B | 明示 high_slots（reason+evidence）。Largeなし |
| C | Mechanical Prefill + high_slots。Largeなし |
| D | Prefill + HIGH slot のみ Large 訂正 + Validation |

`auto_fix = NOT_ALLOWED`
