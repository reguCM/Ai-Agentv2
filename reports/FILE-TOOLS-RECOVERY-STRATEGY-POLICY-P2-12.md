# FILE-TOOLS-RECOVERY-STRATEGY-POLICY-P2-12 報告書

**TASK_ID:** `FILE-TOOLS-RECOVERY-STRATEGY-POLICY-P2-12`  
**実装結果:** **PASS**  
**Context:** 16384（維持）  
**本番自動 Recovery:** OFF

---

## 実装結果

Evidence ベースの Recovery Strategy **候補順位付け基盤**を構築した。

```text
Failure
  ↓ Failure Classification
  ↓ Situation Analysis
  ↓ Recovery Candidates (propose_all_recovery_candidates)
  ↓ Evidence-based Ranking (rank_recovery_candidates)
  ↓ Recommendation (recommend_recovery_strategies)
  ↓ Human / Agent Approval（自動実行なし）
```

専用 Live 再実験は **実施していない**（P2-11 Evidence を初期 Evidence として利用）。

---

## 追加/変更ファイル

| ファイル | 内容 |
|----------|------|
| `tools/system/context_monitor/recovery_evidence.py` | Evidence 蓄積・P2-11 import・Positive/Negative 分類 |
| `tools/system/context_monitor/recovery_ranking.py` | Situation Analysis・スコアリング・順位付け |
| `tools/system/context_monitor/recovery.py` | `recommend_recovery_strategies()` |
| `tools/system/context_monitor/recovery_policy.json` | v3: ranking_signals / situation_thresholds |
| `tools/system/context_monitor/recovery_helpers.py` | `format_recommendation_list()` |
| `tools/system/context_monitor/agent_recovery_bridge.py` | 順位付き候補提示 |
| `tools/system/context_monitor/strategy_compare.py` | recommendation 連携・実行後 Evidence 記録 |
| `tools/system/context_monitor/__init__.py` | 公開 API 更新 |
| `ai_tool/context_monitor/cli.py` | `import-p11-evidence` サブコマンド |
| `tests/test_recovery_ranking.py` | Synthetic Test A～I |
| `runs/ai_tool/context_monitor/strategy_evidence.jsonl` | P2-11 Evidence 取り込み済み |

---

## Recovery Strategy（すべて維持）

| Strategy | 役割 |
|----------|------|
| `retry_same_context` | 非決定性・偶発失敗の確認（TIMEOUT 時は deprioritize） |
| `reduce_tool_result` | 大量 Tool Result 削減 |
| `narrow_search_scope` | 検索範囲縮小（reduce とは別 Strategy） |
| `increase_context` | Context Ladder 1 段階増加（**削除しない**） |
| `retry_with_explicit_tool_instruction` | Tool Call 生成明示指示 |

---

## P2-11 Evidence の取り込み

**Source:** `p2-11_live_strategy_compare`  
**参照:** `runs/ai_tool/20260902T084451Z_recovery_strategy_compare_p211/compare.json`  
**取り込み:** `python -m ai_tool.context_monitor.cli import-p11-evidence` → **6 行 imported**

### Positive Evidence

| Strategy | 結果 | Latency |
|----------|------|---------|
| `reduce_tool_result` | Tool Call / Execution SUCCESS | ~20627 ms |
| `retry_with_explicit_tool_instruction` | Tool Call / Execution SUCCESS | ~77587 ms |

### Negative Evidence

| Strategy | 結果 | Latency |
|----------|------|---------|
| `baseline` / `retry_same_context` | TIMEOUT | ~90238 ms |
| `narrow_search_scope` | Tool Call 未成功 | ~14910 ms |
| `increase_context` (16384→32768) | TIMEOUT | ~90325 ms |

---

## Candidate Priority（現時点・固定順位ではない）

**条件:** 大量 Tool Result (50) + TIMEOUT + truncated + Context 16384

| Rank | Strategy | Score (例) | Confidence |
|------|----------|------------|------------|
| 1 | `reduce_tool_result` | 110.0 | LOW |
| 2 | `retry_with_explicit_tool_instruction` | 28.0 | LOW |
| 3 | `narrow_search_scope` | 15.0 | LOW |
| 4 | `retry_same_context` | -35.0 | LOW |
| 5 | `increase_context` | -60.0 | LOW |

スコアは `ranking_signals` + 状況フラグ + P2-11 Evidence から算出。**B > E > D の固定順位はコードに埋め込んでいない。**

---

## Evidence不足時の扱い

| evidence_count | confidence |
|----------------|------------|
| 0 | UNKNOWN |
| 1～4 | LOW |
| 5～9 | MEDIUM |
| 10+ | HIGH（ただし ev_count < 3 では HIGH に昇格しない） |

P2-11 は各 Strategy **1 cycle** のため、すべて **LOW / UNKNOWN** 扱い。Evidence 1 件だけで Policy 確定しない。

---

## 今後の Evidence 追加方法

```python
from tools.system.context_monitor import record_strategy_outcome

record_strategy_outcome(
    strategy="reduce_tool_result",
    failure_type="TIMEOUT",
    configured_context=16384,
    runtime_context=16384,
    tool_result_count=50,
    payload_bytes=10345,
    truncated=True,
    tool_call_success=True,
    tool_execution_success=True,
    timeout=False,
    latency_ms=21000,
    gpu_before={"vram_free_mib": 450},
    recovery_result="success",
    scenario_id="dev_case_001",
    evidence_source="normal_dev_test",
)
```

- `strategy_compare` 実行時も Strategy 試行後に自動記録
- CLI: `python -m ai_tool.context_monitor.cli import-p11-evidence`

**Positive / Negative** は `evidence_polarity` として自動分類（`recovery_result` / `tool_call_success` / `timeout` から導出）。

---

## Synthetic Test

```text
tests/test_recovery_ranking.py   10 passed (A～I)
tests/test_strategy_compare.py    7 passed
tests/test_recovery_harness.py    7 passed
tests/test_context_recovery.py   13 passed
tests/test_context_monitor.py     5 passed
file tools / model registry 等   80 passed
────────────────────────────────────────────
合計                            122 passed, 3 skipped
```

| Test | 内容 | 結果 |
|------|------|------|
| A | 大量 Result + TIMEOUT → reduce 候補 | PASS |
| B | Context 関連 Failure → increase 候補 | PASS |
| C | P2-11 increase 失敗 → increase 評価低下 | PASS |
| D | P2-11 reduce 成功 → reduce 評価上昇 | PASS |
| E | 複数 Strategy → 順位付き候補 | PASS |
| F | Positive / Negative 区別 | PASS |
| G | Evidence 1 件 → HIGH にしない | PASS |
| H | 候補生成のみ・Recovery 未実行 | PASS |
| I | automatic_recovery_enabled=false | PASS |

Live LLM 結果を Regression 必須条件にしていない。

---

## Regression Test

P2-11 関連 + file tools + recovery 系:

```text
122 passed, 3 skipped
```

（全リポジトリ `tests/` 実行時の既存 7 failures は本 Phase 変更と無関係の別領域）

---

## increase_context の扱い

- Recovery 候補として **維持**（Context Ladder: 4096→8192→16384→32768、1 段階ずつ）
- P2-11 では 32768 でも TIMEOUT → **Negative Evidence** として記録
- 同条件では Priority を下げるが、**Strategy 削除・禁止はしない**
- GPU VRAM 固定閾値による禁止ルールは **未導入**（観測フラグ `gpu_vram_tight_observation` のみ）

---

## 自動 Recovery

| 項目 | 値 |
|------|-----|
| `automatic_recovery_enabled` | **false** |
| `config/llm_models.yaml` context_limit | **16384**（不変） |
| Agent 自動実行 | **OFF**（`AI_AGENT_RECOVERY_OPT_IN` 時も APPROVAL_REQUIRED） |

---

## 既知の制限

- P2-11 Evidence は **1 cycle / Strategy** — 統計的優劣は未確定
- Strategy 自動選択・複数連続 Recovery・恒久 Context 変更は未実装
- 「価値なし」判定の Evidence 数閾値は未固定
- `Recovery Success` ≠ `Task Success` ≠ `Final Problem Resolution`（評価分離は維持）

---

## 次 Phase 候補

- 通常開発・テスト失敗時の Recovery 試行フロー整備（Harness / Agent opt-in 拡張）
- Evidence 蓄積後の Failure 条件別成功率分析
- 十分な Evidence 蓄積後の Strategy 有効性分類（有効 / 条件付き / 効果不明 / 効果低 / 価値なし）
- 人間承認後の単一 Strategy 実行と結果フィードバックループ
