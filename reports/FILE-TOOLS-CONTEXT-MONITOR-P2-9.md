# FILE-TOOLS-CONTEXT-MONITOR-P2-9 報告書

**TASK_ID:** `FILE-TOOLS-CONTEXT-MONITOR-P2-9`  
**判定:** PASS（基盤構築完了）  
**暫定 Context:** 16384（変更なし）

---

## ① 現在構成

| 項目 | 場所 | 内容 |
|------|------|------|
| Context 上限（設定） | `config/llm_models.yaml` → `qwen3_14b.context_limit` | **16384**（今回変更なし） |
| Model Registry | `registry/models.json` | モデルメタ。context_limit は保持せず profile 参照 |
| LLM 実行 | `tools/system/llm.py` → `chat()` | `context_limit` → `num_ctx` にマップ。**Context Monitor フック追加** |
| GPU 状態 | `tools/system/gpu/gpu_status.py`, `gpu_processes.py` | 実行前後スナップショットに利用 |

**分離方針（実装反映）**

- **上限:** `limits.configured_context_limit` / yaml の `context_limit`
- **現在状態:** `gpu_before` / `gpu_after`（VRAM・利用率・プロセス）
- **実測結果:** `outcome` / `performance`（成功率・timeout・tool call・実行時間）
- **評価:** `aggregate.py` / `recalibration.py` で**後計算**（観測 JSONL には含めない）

---

## ② 実測データ設計

1 観測 = 1 回の LLM 実行（`llm.chat` 呼び出し、または legacy インポート 1 round/run）。

```json
{
  "schema_version": 1,
  "observation_id": "uuid",
  "timestamp": "ISO8601",
  "source": "llm.chat | import:p2-8",
  "execution": {
    "model", "profile_id", "context_size", "tools_enabled",
    "task_type", "scenario_id", "execution_id"
  },
  "gpu_before": { "vram_total_mib", "vram_used_mib", "vram_free_mib", ... },
  "gpu_after": { ... },
  "outcome": {
    "success", "timeout", "error",
    "native_tool_call", "native_tool_names",
    "type3", "type4", "tool_execution_success"
  },
  "performance": { "elapsed_ms", "round_index", ... },
  "limits": { "configured_context_limit", ... },
  "legacy_ref": "元 verify.json パス（インポート時のみ）"
}
```

**task_type:** `simple` / `search_read` / `list_read` / `multi_read` / `large_result` / `unknown`

---

## ③ 保存場所

| ファイル | 用途 |
|----------|------|
| `runs/ai_tool/context_monitor/observations.jsonl` | 観測事実（append-only） |
| `runs/ai_tool/context_monitor/summary.json` | 集計・評価（再生成可能） |
| `runs/ai_tool/context_monitor/recalibration_status.json` | 再調整要求状態 |
| `runs/ai_tool/context_monitor/dashboard.html` | 簡易見える化 |
| `runs/ai_tool/context_monitor/legacy_import_manifest.json` | P2-6～8 インポート記録 |
| `tools/system/context_monitor/recalibration_policy.json` | 再調整判定ルール（閾値は後から変更可） |

**無効化:** 環境変数 `AI_AGENT_CONTEXT_MONITOR=0`

---

## ④ 見える化

```bash
python -m ai_tool.context_monitor.cli import-legacy
python -m ai_tool.context_monitor.cli dashboard
```

- `summary.json`: Context 別（8192/16384/32768…）の成功率・timeout率・平均実行時間・VRAM 空き
- `dashboard.html`: Context 別比較表 + 再調整要求ステータス
- `cross_analysis.context_x_vram_free_before`: Context × 実行前 VRAM 空き × 実行時間の生データ

**データ不足時:** `evaluation_state` = `insufficient_data` / `accumulating`（断定しない）

---

## ⑤ 再調整要求

`recalibration.py` + `recalibration_policy.json`:

- 条件例（enabled/disabled・閾値は JSON で変更可能）:
  - 観測数が一定以上
  - timeout 率上昇
  - 成功率低下
  - 平均実行時間の baseline 比悪化
  - 実行前 VRAM 空きが少ない
- 出力: `recalibration_required`, `status`, `reasons[]`
- **自動 Context 変更は行わない**（人間承認後に比較テストへ）

---

## ⑥ P2-6～P2-8 との関係

- `import_legacy.py` が verify.json を**読み取りのみ**で observations.jsonl に変換
- 元ファイル（`runs/ai_tool/20260902T.../verify.json`）は**不変**
- manifest に `legacy_ref` と `observation_ids` を記録

---

## ⑦ 今後の拡張

```
実測 (llm.chat フック)
  ↓ observations.jsonl 蓄積
  ↓ aggregate → summary
  ↓ recalibration → RECALIBRATION_RECOMMENDED + reasons
  ↓ 人間承認
  ↓ 比較テスト (P2-6～8 型)
  ↓ 新評価
```

将来: Agent Loop から `context_monitor_meta`（task_type 等）を渡す、自動実験は別フェーズ。

---

## 実装ファイル

- `tools/system/context_monitor/` — schema, record, gpu_snapshot, aggregate, recalibration, import_legacy, visualize
- `tools/system/llm.py` — 最小フック
- `ai_tool/context_monitor/cli.py` — CLI
- `tests/test_context_monitor.py` — ユニットテスト

---

## 回帰テスト

```text
tests/test_search_files_registry.py              18 passed, 1 skipped
tests/test_list_files_registry.py                17 passed, 1 skipped
tests/test_read_file_registry.py                 15 passed, 1 skipped
tests/test_tool_calling_rules.py                 14 passed
tests/test_model_registry.py                     14 passed
tests/ai_tool/agent_integration                  99 passed, 3 skipped
tests/test_context_monitor.py                     5 passed  (新規)
────────────────────────────────────────────────────────────────
合計                                             184 passed, 3 skipped
```

基準（179 passed, 3 skipped）を満たし、新規 5 件を追加。

## 初期データ（legacy import）

- インポート件数: **47 observations**
- Context 別: 8192=3, 16384=23, 32768=21
- 16384 暫定値に対する再調整候補: `recalibration_recommended`（timeout率・成功率。自動変更なし）
