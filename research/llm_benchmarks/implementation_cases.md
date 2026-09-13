# 実装層の評価

unittest ではない。Research / Judge は固定し、実装 LLM だけを測る。

```text
Research / Judge  （固定した usable_findings = コマンドA）
  ↓
Implementation
  ├─ A だけ → ok
  ├─ A + 不要な finding → unnecessary_finding
  ├─ 不要な finding だけ → finding_not_used
  ├─ code が空 → empty_code
  └─ usable_findings にないコマンド → wrong_command
```

質問は「必要な finding だけを選べるか」。単一選択と複数選択を分けて測る。

PASS と score は分ける（`docs/scoring.md`）。

- 単一選択で A だけ → `ok`、PASS、100点
- 単一選択で A + 不要 → `unnecessary_finding`、PASS、軽微減点
- 複数選択で A+B → `ok`、PASS、100点
- 複数選択で A だけ → `finding_not_used`、FAIL（要求を減らした）

- `implement_single_select_memory_usage` … 使用率だけ。正解は A
- `implement_multi_select_usage_and_available` … 使用率と空き容量。正解は A+B
- `implement_combine_total_and_used_to_usage` … 総メモリと使用済みから計算。正解は TotalVisibleMemorySize + CommittedBytes。PercentCommittedBytesInUse は近道であり不正解

```text
AI_AGENT_IMPLEMENT_CASES=implement_single_select_memory_usage,implement_multi_select_usage_and_available,implement_combine_total_and_used_to_usage
python -m research.llm_benchmarks.implementation_benchmark
python -m research.llm_benchmarks.history
```

```text
python -m research.llm_benchmarks.implementation_benchmark
python -m research.llm_benchmarks.history
```

履歴は `history.json` / `summary.json`。ベンチが1件保存するたびに score / class / PASS を抜き出して更新する。

モデル比較（Research/Judge は回さない）:

```text
AI_AGENT_IMPLEMENT_MODELS=qwen3_8b,qwen3_14b,qwen2_5_coder_7b,gemma3_12b
```
