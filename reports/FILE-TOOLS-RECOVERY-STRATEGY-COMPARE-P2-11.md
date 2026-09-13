# FILE-TOOLS-RECOVERY-STRATEGY-COMPARE-P2-11 報告書

**TASK_ID:** `FILE-TOOLS-RECOVERY-STRATEGY-COMPARE-P2-11`  
**実装結果:** **PASS**  
**Context:** 16384（維持）  
**本番自動 Recovery:** OFF

---

## ①②③ の区別

| 項目 | 結果 |
|------|------|
| ① Recovery Engine / Strategy 比較ロジック | Synthetic Test **PASS** |
| ② Live LLM で Strategy 比較実行 | **1 cycle 実施** |
| ③ Context 増加のみによる復旧効果 | **今回未確認**（32768 も timeout） |

---

## 実装内容

| ファイル | 内容 |
|----------|------|
| `tools/system/context_monitor/recovery_strategies.py` | Strategy A～E 変換 |
| `tools/system/context_monitor/strategy_compare.py` | 比較 Harness・集計 |
| `tools/system/context_monitor/recovery.py` | `propose_all_recovery_candidates()` 追加 |
| `tools/system/context_monitor/recovery_policy.json` | v2: compare_strategies / strategy_params |
| `ai_tool/context_monitor/strategy_compare_cli.py` | Live 実験 CLI |
| `tests/test_strategy_compare.py` | Synthetic テスト |

---

## 実験シナリオ

```text
search_files(path=".", query="read_file")
  → 50 matches / 10345 bytes / truncated
  → 固定メッセージで post-search read_file を要求
```

モデル: `qwen3:14b`  
configured_context: **16384**（yaml 不変）  
実行: `python -m ai_tool.context_monitor.strategy_compare_cli --runs 1`

---

## Live 実測（1 cycle）

**Evidence source:** `p2-11_live_strategy_compare`  
**出力:** `runs/ai_tool/20260902T084451Z_recovery_strategy_compare_p211/compare.json`

### Baseline（initial 16384）

| 指標 | 値 |
|------|-----|
| failure_reproduced | **true** |
| failure_type | **TIMEOUT** |
| tool_call_recovery | FAILURE |
| latency | ~90238 ms |
| VRAM free (before) | ~471 MiB |
| payload | 50 matches / 10345 bytes |

### 各 Strategy 結果（同一 search payload 起点）

| Strategy | Tool Call | Tool Exec | Timeout | Latency | VRAM free (before) |
|----------|-----------|-----------|---------|---------|-------------------|
| **A retry_same_context** | FAIL | — | **yes** | ~90238 ms | ~392 MiB |
| **B reduce_tool_result** (→10件) | **SUCCESS** | **SUCCESS** | no | ~20627 ms | ~409 MiB |
| **C narrow_search_scope** | FAIL | — | no | ~14910 ms | ~402 MiB |
| **D increase_context** (32768) | FAIL | — | **yes** | ~90325 ms | ~402 MiB |
| **E explicit_tool_instruction** | **SUCCESS** | **SUCCESS** | no | ~77587 ms | ~424 MiB |

---

## 16384 → 32768

**未確認（failure → success ではない）**

- Baseline: 16384 **timeout**
- Strategy D: 32768 も **timeout**
- 今回の Live セッションでは Context 増加による Tool Calling 復旧は観測されなかった

---

## 最も有望な Strategy（今回 1 cycle のみ）

**reduce_tool_result**（tool_call_success_rate 1/1）

- 大量 Tool Result（50件）を 10件に削減
- Native Tool Call + Tool 実行成功
- latency は increase_context / retry_same より大幅に短い
- VRAM 圧力も相対的に低い

**副次:** explicit_tool_instruction も成功（ただし latency ~78s）

---

## 適用条件（Evidence ベース・暫定）

| 失敗条件 | 優先候補（今回） | 根拠 |
|----------|------------------|------|
| 大量 Tool Result + TIMEOUT @ 16384 | **reduce_tool_result** | Live 1/1 成功、他 Strategy timeout |
| 同上 + Context 余裕あり | increase_context | **今回は効果なし**（32768 timeout） |
| 非決定性確認 | retry_same_context | 今回は baseline と同様 timeout |

**注意:** evidence_count=1/cycle のため Policy 固定はしない。

---

## Failure Classification

Baseline: **TIMEOUT**（TOOL_CALL_NOT_GENERATED ではなく 90s 上限）

→ 今回の Live 失敗は「Tool Call 未生成」より「応答時間超過」が主因。

---

## GPU

- Baseline 前: VRAM used ~11817 / 12288 MiB（空き ~471 MiB）
- 32768 試行時も VRAM 逼迫状態が継続
- reduce_tool_result 成功時も VRAM 空きは ~400 MiB 台（固定閾値は設定していない）

---

## 過去 Evidence との関係

| Source | 用途 |
|--------|------|
| `legacy_observation` (P2-6～8) | increase_context 候補の confidence 計算 |
| `p2-11_live_strategy_compare` | **今回の Strategy 比輡** |

混同していない。

---

## Synthetic Test

```text
tests/test_strategy_compare.py     7 passed
tests/test_recovery_harness.py     7 passed
tests/test_context_recovery.py      13 passed
```

Live LLM の偶発的成功を Regression 必須条件にしていない。

---

## Regression Test

```text
211 passed, 3 skipped
```

---

## 本番自動 Recovery

**OFF**（`automatic_recovery_enabled: false`）

---

## 既知の制限

- Live 実験は **1 cycle** のみ（各 Strategy evidence_count=1）
- narrow_search_scope は registry 等で件数削減したが Tool Call 未成功
- task_result（最終回答成功）は未判定
- 自動 Strategy 選択・複数 Recovery ループは未実装

---

## 新たに発見した Recovery 候補

今回 Live で **reduce_tool_result** が increase_context より優位な可能性を確認。  
Policy 化前に追加 cycle が必要。

---

## 外部事例調査

今回は未実施（Local Experiment を優先）。  
外部情報は Verified 扱いにしない方針を維持。

---

## 次 Phase への推奨

1. **reduce_tool_result** を追加 cycle（3～5）で再検証
2. TIMEOUT 失敗時の Strategy 優先順位 Policy 草案（evidence 蓄積後）
3. Agent opt-in から Strategy 比較 Harness への接続（自動発動なし）

---

## 判定

**PASS** — Strategy 比較 Harness 構築・Live 実行・記録・Regression 完了。  
Context 増加以外（**reduce_tool_result**）に Tool Calling 改善可能性を Live で確認。
