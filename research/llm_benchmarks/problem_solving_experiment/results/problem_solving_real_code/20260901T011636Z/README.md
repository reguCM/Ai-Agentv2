# problem_solving_real_code

一次資料。分析は PROBLEM_SOLVING_REAL_CODE_EXPERIMENT.md。

- fixture: `research\llm_benchmarks\problem_solving_experiment\results\problem_solving_real_code\20260901T011636Z\fixture`
- initial pytest exit_code: 1
- initial main.py exit_code: 1
- models: [
  {
    "model": "deepseek-coder-v2:16b",
    "stop_reason": "idle_no_tool_or_write",
    "turns": 2,
    "tool_calls": 0,
    "modifications": 0,
    "tests": 0,
    "call_ok": true
  },
  {
    "model": "qwen3:14b",
    "stop_reason": "idle_no_tool_or_write",
    "turns": 7,
    "tool_calls": 6,
    "modifications": 1,
    "tests": 1,
    "call_ok": true
  }
]
