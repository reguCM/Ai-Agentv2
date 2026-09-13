# capability_route ログ収集メモ

## 普段使い（推奨の本命）

`python agent.py` を普通に使うだけで、既定で次に追記される。

- `logs/capability_route.jsonl` … Stage1/2
- `logs/execution_identity.jsonl` … 主体ログ

意図的に難問だけを作る必要はない。日常利用の分布の方が有用。

## 意図的な多様ケース（バッチ）

ケース定義: `research/llm_benchmarks/capability_route_cases/cases.json`

```text
.venv\Scripts\python.exe research/llm_benchmarks/capability_route_cases/run_collection.py
.venv\Scripts\python.exe research/llm_benchmarks/capability_route_cases/run_collection.py --only web_unneeded_cpu
```

出力先: `research/llm_benchmarks/capability_route_obs/collect_<timestamp>/`

各ケースに `capability_route.jsonl` / `execution_identity.jsonl` / `stdout.txt` / `meta.json`。

### バッチ時の環境（設計）

| 変数 | 値 | 意味 |
|------|-----|------|
| `AI_AGENT_USER_REQUEST` | ケース文 | 要求差し替え |
| `AI_AGENT_SKIP_CLARITY` | `1` | 収集時のみ Clarity 対話スキップ |
| `AI_AGENT_TOOL_TRUST` | `registry/agent_tool_trust.collection.json` | 公開Toolを収集用に昇格 |
| `AI_AGENT_TOOL_GATE` | **設定しない（offにしない）** | Gate自体は維持 |
| `AI_AGENT_COLLECTION_CASE_ID` / `_CATEGORY` | ケース情報 | ログの `extra` に付与 |
| `AI_AGENT_SKIP_PRE_WEB` | **設定しない** | Webなし回答候補を同一 `observation_id` で記録 |

各ケースの `capability_route.jsonl` には通常 3 行が入る:

1. `pre_web_answer_candidate`
2. `capability_route_observation`（judgment / execution）
3. `capability_outcome_compare`（final_answer + web_search_results）

Pipeline は起動しない。`needs_new_tool` は観測のみ。Web有益性の自動判定もしない。
