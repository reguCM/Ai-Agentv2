# FILE-TOOLS-RECOVERY-AGENT-EVALUATION-P2-13 報告書

**TASK_ID:** `FILE-TOOLS-RECOVERY-AGENT-EVALUATION-P2-13`  
**RESULT:** **PASS**  
**Context:** 16384（維持）  
**本番自動 Recovery:** OFF

---

## 実装内容

P2-12 の Evidence-based Ranking を基に、**Agent が Recovery 候補を評価・選択し、その判断を Evidence Ranking と比較観測できる**基盤を追加した。

Agent の判断は **Recovery Engine の最終決定ではない**。観測・将来分析が目的。

### 新規ファイル

| ファイル | 内容 |
|----------|------|
| `tools/system/context_monitor/agent_recovery_evaluation.py` | Agent ブリーフ生成、選択パース、Ranking 比較、Outcome 記録 |
| `tools/system/context_monitor/context_expansion_gate.py` | `increase_context` 最終手段 Gate |
| `tests/test_agent_recovery_evaluation.py` | Synthetic Test A～J |

### 変更ファイル

| ファイル | 内容 |
|----------|------|
| `tools/system/context_monitor/recovery.py` | `increase_context` を通常 Ranking から分離、`context_expansion` フィールド追加 |
| `tools/system/context_monitor/agent_recovery_bridge.py` | `prepare_agent_recovery_evaluation`, `submit_agent_recovery_selection` |
| `tools/system/context_monitor/recovery_helpers.py` | Context Expansion Gate 表示 |
| `tools/system/context_monitor/schema.py` | `RANKING_VS_AGENT`, Gate 定数 |
| `tools/system/context_monitor/paths.py` | `agent_recovery_evaluations.jsonl` |
| `tools/system/context_monitor/recovery_policy.json` | v4, `context_expansion_gate` |
| `tests/test_recovery_ranking.py` | increase_context 分離に合わせ更新 |
| `tests/test_recovery_harness.py` | `AGENT_EVALUATION_REQUIRED` ステータス |

---

## Agent 評価フロー

```text
Failure 検出
  ↓
recommend_recovery_strategies()
  ├─ normal_recommendations (Evidence Ranking, increase_context 除外)
  └─ context_expansion (Gate: BLOCKED/ALLOWED)
  ↓
build_agent_recovery_brief() → Agent へ構造化提示
  ↓
Agent 構造化出力 (selected_strategy, reason, confidence, alternatives_considered)
  ↓
submit_agent_recovery_selection()
  ├─ ranking_vs_agent: MATCH | DIFFERENT | NO_RANKING
  └─ agent_recovery_evaluations.jsonl へ記録
  ↓
resolve_agent_selection_for_execution()
  ├─ 通常 Strategy → Human Approval 後実行可能
  └─ increase_context → Context Expansion Gate 必須
  ↓
record_agent_recovery_outcome()
  ├─ agent_selection
  ├─ recovery_execution
  └─ task_result （分離記録）
```

---

## Ranking と Agent 判断の関係

| 項目 | 扱い |
|------|------|
| Evidence Ranking | Recovery Engine が独立算出（`normal_recommendations`） |
| Agent 選択 | 参照して判断、**最終決定権なし** |
| 一致 | `ranking_vs_agent = MATCH` |
| 不一致 | `ranking_vs_agent = DIFFERENT`（エラーではない） |
| Ranking 覆し | Human Approval 後に実行・Outcome 記録で将来分析 |

保存フィールド:

```text
ranking_top_strategy
agent_selected_strategy
ranking_vs_agent
agent_reason
agent_confidence
alternatives_considered
```

---

## Context 拡張 Gate

`increase_context` は **通常候補 Ranking に含めない**。

### Gate 必須条件（すべて成立時のみ ALLOWED）

1. 通常 Recovery を実施済み (`normal_recovery_attempted`)
2. Task 未解決または Recovery 失敗 (`task_unresolved` / `recovery_failed`)
3. 実行可能な通常候補が残っていない (`viable_normal_candidates_remain` なし)
4. Context 拡張が技術的に可能（Ladder 1 段階、model/pc limit）
5. GPU 観測取得済み
6. Human Approval
7. 当 Cycle で Context 拡張未使用 (`context_expansion_used=false`)

未成立時: `gate_status = BLOCKED`

Agent が `increase_context` を選んでも Gate 未成立なら **実行 BLOCKED**。判断自体は Evidence として記録。

---

## テスト結果

### Synthetic / Integration (P2-13)

```text
tests/test_agent_recovery_evaluation.py   10 passed (A～J)
tests/test_recovery_ranking.py            10 passed
tests/test_recovery_harness.py             7 passed
tests/test_strategy_compare.py             7 passed
tests/test_context_recovery.py            13 passed
tests/test_context_monitor.py              5 passed
────────────────────────────────────────────────────
合計                                      52 passed
```

| Test | 内容 | 結果 |
|------|------|------|
| A | Ranking = Agent → MATCH | PASS |
| B | Ranking ≠ Agent → DIFFERENT | PASS |
| C | reason + confidence 取得 | PASS |
| D | Agent選択 / Recovery実行 分離 | PASS |
| E | Recovery成功 + Task失敗 | PASS |
| F | increase_context Gate 未成立 → BLOCKED | PASS |
| G | 条件成立 + Approval → ALLOWED | PASS |
| H | 同一 Cycle 2 回 Context 拡張不可 | PASS |
| I | Ranking 覆し記録 | PASS |
| J | P2-10～12 Regression | PASS |

---

## Regression

P2-10～P2-12 関連: **52 passed**

Live LLM 結果を Regression 必須条件にしていない。

---

## Live Recovery Case

```text
Live Recovery Case: なし

理由: 専用 Failure を人工的に作成していないため
```

**FAIL ではない**（仕様通り）。

---

## 今回得られた Evidence

| 種別 | 件数 |
|------|------|
| 新規 Live Agent 評価 | 0 |
| P2-11 初期 Evidence | 既存（変更なし） |
| Synthetic 評価記録 | テスト内のみ |

---

## increase_context の扱い（P2-13 変更点）

- 通常 Ranking から **除外**
- `context_expansion` として Gate 管理
- 削除しない・禁止しない（条件成立時のみ最後の手段）
- 16384 → 32768 の 1 段階のみ（連続拡張なし）

---

## 未解決事項

- Agent 判断の Live 観測データは未蓄積（自然発生 Failure 待ち）
- Agent 選択後の全 Strategy 実行パイプラインは Harness 経由が主（Bridge は計画生成まで）
- 「Agent が Ranking を覆した方が成功率が高い」等の結論は **今回付けない**

---

## 次フェーズ提案

- 自然発生 Failure 時の Agent 評価ループ接続（`agent.py` opt-in 拡張）
- Agent 判断 vs Ranking の一致率・成功率分析（Evidence 蓄積後）
- Human Approval UI / CLI フロー整備
- Recovery 実行後の `record_agent_recovery_outcome` 自動呼び出し

---

## 最終報告

```text
TASK_ID: FILE-TOOLS-RECOVERY-AGENT-EVALUATION-P2-13
RESULT: PASS
変更ファイル: recovery.py, agent_recovery_bridge.py, recovery_helpers.py, schema.py, paths.py, recovery_policy.json, __init__.py, tests/*
新規ファイル: agent_recovery_evaluation.py, context_expansion_gate.py, test_agent_recovery_evaluation.py
テスト結果: 52 passed (P2-13 + P2-10～12 関連)
Regression: PASS
Agent Ranking一致/不一致: MATCH/DIFFERENT 比較・記録可能
Context Gate: 実装済み (BLOCKED/ALLOWED)
Context拡張実績: なし（Live 未実施）
Live Recovery: なし（人工 Failure 禁止のため）
Evidence追加件数: 0（Live）
未解決事項: Live Agent 評価データ未蓄積
次フェーズ提案: 自然 Failure 時の Agent 評価ループ接続、一致率分析
```

**P2-13 の成果:** Agent 判断を観測可能にした。Agent 判断が Recovery 性能を改善したとは結論付けていない。
