# FILE-TOOLS-CONTEXT-RECOVERY-P2-10 報告書

**TASK_ID:** `FILE-TOOLS-CONTEXT-RECOVERY-P2-10`  
**判定:** PASS  
**本番自動 Recovery:** OFF  
**Context 16384:** 維持（変更なし）

---

## 実装結果

P2-9 Context Monitor を基盤に、Tool Calling 失敗時の段階的 Recovery Strategy 基盤を実装した。本番 Agent Loop への自動接続は行っていない。

---

## 変更ファイル

| ファイル | 内容 |
|----------|------|
| `tools/system/context_monitor/failure_classifier.py` | 失敗分類（新規） |
| `tools/system/context_monitor/recovery.py` | Recovery Engine（新規） |
| `tools/system/context_monitor/recovery_policy.json` | ポリシー（新規） |
| `tools/system/context_monitor/schema.py` | FAILURE_TYPES 等追加 |
| `tools/system/context_monitor/paths.py` | recovery JSONL パス追加 |
| `tools/system/context_monitor/__init__.py` | export 追加 |
| `tools/system/llm.py` | `runtime_context` 分離（yaml 不変） |
| `tests/test_context_recovery.py` | Synthetic テスト（新規） |

P2-9 既存モジュール（record, aggregate, recalibration 等）は変更最小（schema/paths/__init__ のみ）。

---

## 追加した Recovery Strategy

| Strategy | 今回 |
|----------|------|
| `increase_context` | 実装（Context ladder 一段階） |
| `retry_same_context` | 構造のみ（将来） |
| `decrease_context` / その他 | スキーマ定義のみ |

---

## 失敗分類

`failure_classifier.py`:

- `TOOL_CALL_NOT_GENERATED` — thinking で tool 言及あり、native tool_calls なし
- `TOOL_CALL_PARSE_FAILED`
- `TOOL_EXECUTION_FAILED`
- `TIMEOUT`
- `CONTEXT_LIMIT`
- `GPU_RESOURCE_INSUFFICIENT`
- `UNKNOWN` / `NONE`

`execution_result` / `task_result` / `recovery_result` を分離。主対象は execution / recovery。

---

## Context 候補決定方法

1. `recovery_policy.json` の `context_ladder`: `[4096, 8192, 16384, 32768]`
2. `next_context_step(current)` で一段階上げ（16384 → 32768）
3. 制約チェック:
   - `candidate <= model_context_limit`（qwen3:14b → 40960）
   - `candidate <= pc_context_limit`（32768）
4. P2-9 `observations.jsonl` から task_type / context 別 evidence を収集
5. confidence: HIGH / MEDIUM / LOW / UNKNOWN（観測数不足で HIGH 禁止）

---

## GPU 状態の扱い

- `get_gpu_status` / snapshot を Recovery 判断入力として記録
- VRAM 固定閾値は設けない（指示遵守）
- 観測不能（capture_error / vram_total 不明）時のみ execution_allowed=false
- GPU 情報は安全性判断の観測材料として保存

---

## Recovery データ構造

**RecoveryDecision** (`recovery_decisions.jsonl`):

- recovery_id, parent_execution_id
- configured_context, current_context
- failure_type, candidate_strategy, candidate_context
- confidence, reason, evidence, gpu_state
- automatic_execution_allowed, execution_allowed

**RecoveryResult** (`recovery_results.jsonl`):

- parent_execution_id, recovery_id
- previous_context, current_context, configured_context
- recovery_result, retry_execution_id, gpu_before, gpu_after

**configured vs runtime:**

- configured_context = yaml の 16384（不変）
- runtime_context = llm.chat(runtime_context=32768) で一時上書き

---

## テスト結果

Synthetic テスト 13 passed (`tests/test_context_recovery.py`):

1. 成功時 recovery なし
2. TOOL_CALL_NOT_GENERATED 検出
3. 16384 → 32768 候補生成
4. model 上限超過で候補不可
5. PC 上限超過で候補不可
6. GPU 観測不能で execution ブロック
7. Retry ループ防止
8. 16384 失敗 → 32768 成功の chain 記録
9. 承認なしでは not_executed
10. 自動 Recovery OFF
11. evidence 収集

---

## 実測結果

Recovery Engine の仕組みを Synthetic Test で検証した。

本番 GPU 環境での 16384 failure → 32768 retry の live 再現は今回未実施（P2-8 既存実測データを evidence として利用可能）。

---

## 既存 Regression 結果

P2-9 基準セット + 新規:

```text
197 passed, 3 skipped
（179 + test_context_monitor 5 + test_context_recovery 13）
```

---

## 本番自動 Recovery

OFF（recovery_policy.json: automatic_recovery_enabled: false）

---

## Context 16384

維持 — config/llm_models.yaml 未変更

---

## 既知の制限

- Agent Loop 未接続（明示承認ハーネスのみ execute_recovery_retry）
- VRAM ベースの実行可否 Policy は未導入（データ不足）
- task_result（最終目的達成）は未判定
- 自動比較テスト・恒久 Context 変更は未実装

---

## 今後必要な作業

1. Agent Loop から build_execution_record + propose_recovery を opt-in 接続
2. 人間承認 UI / harness 整備
3. 実測データ蓄積後の GPU Policy 導入
4. 他 Strategy（reduce_tool_result 等）の実装

---

## 推奨する次 Phase

P2-11: Recovery Harness 実測 + Agent opt-in 接続（自動発動は依然 OFF）
