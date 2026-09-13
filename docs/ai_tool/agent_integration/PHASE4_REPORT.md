# Agent Integration Phase 4 — 完了報告

**日付:** 2026-08-28  
**Run:** `runs/ai_tool/20260828_160259_agent_experimental_trial/`

---

## 成功条件

> `local:read_url_text` を隔離 trial で Agent/LLM に公開し、Tool 選択・引数・実行・結果利用を検証。Registry・本番 Tool・Production path は変更しない。

**達成:** ✅（mock LLM + mock network、隔離 runner）

---

## 変更ファイル

| ファイル | 内容 |
|---------|------|
| `ai_tool/agent_integration/experimental_exposure.py` | trial Ollama schema overlay |
| `ai_tool/agent_integration/trial_scenarios.py` | search_web vs read_url_text シナリオ |
| `ai_tool/agent_integration/trial.py` | trial loop + execute_trial_tool |
| `ai_tool/run_agent_experimental_trial.py` | isolated run |
| `tests/ai_tool/agent_integration/test_trial.py` | Phase 4 テスト |
| `docs/ai_tool/agent_integration/EXPERIMENTAL_TRIAL.md` | 設計 |

**未変更:** `registry/tools.json`, `tools/`, `agent.py`, production catalog entries

---

## Trial 結果（2 シナリオ）

| scenario_id | expected | selected | exec ok |
|-------------|----------|----------|---------|
| url_fetch_known_page | read_url_text | read_url_text | ✅ |
| web_search_open_question | search_web | search_web | ✅ |

結果は LLM messages の `role=tool` に返却され、最終回答生成まで到達（mock）。

---

## テスト

```text
tests/ai_tool/agent_integration/test_trial.py  — 10 passed
tests/ai_tool/agent_integration/ (全体)       — 47 passed
```

---

## Safety

| 項目 | 結果 |
|------|------|
| registry/tools.json | SHA256 不変 |
| production Ollama schema | 不変 |
| Discovery agent_available | false 維持 |
| agent.py 実行 path | 未変更 |
| trial 実行回数 | ≥2（mock） |

---

## search_web 使い分け評価

- **URL 明示** → `read_url_text`（SSRF 保護付き GET）
- **探索質問** → `search_web`（hits 一覧）
- 詳細: `routing_comparison.json` in run dir

---

## 未解決 UNKNOWN

| 項目 | 状態 |
|------|------|
| 本番 agent.py への trial overlay 接続 | 未実施（隔離 runner のみ） |
| live LLM + real network trial | オプション未実装（mock 既定） |
| agent_tool_gate 本番統合 | trial は `authorize_trial_execution` 記録のみ |
| Human Review approved → trial 自動昇格 | なし（独立 trial） |

---

## 次 Phase 候補

1. Live LLM trial（`--live-llm`、限定 URL）
2. agent_tool_gate への experimental network Tool ポリシー接続
3. Human Review approved + Registry 統合 GO 後の本番公開 path
