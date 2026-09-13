# EXP-001 — Local vs MCP get_current_time

**日付:** 2026-08-28  
**種別:** AI-TOOL 実験（Diagnostic Framework NH 番号は使用しない）

## 目的

同一機能（現在時刻 UTC 取得）を Local 参照実装と MCP read-only Tool で比較し、共通 Tool Model と Provider 分離の妥当性を検証する。

## 構成

| 経路 | 実装 |
|------|------|
| A. Local | `local_get_current_time()`（registry 外参照関数） |
| B. MCP | `MCPToolProvider` → `ai_tool.providers.mcp.time_server:get_current_time` |

## 実行

```powershell
.\.venv\Scripts\python.exe ai_tool\run_compare_experiment.py
```

## 結果サマリ

| 観点 | Local | MCP |
|------|-------|-----|
| 入力 | `{}` | `{}` |
| 出力形式 | `{ time_utc, provider, observation_source }` | `{ content: [iso string], structured_content }` |
| 成功 | yes | yes（修正後） |
| duration | ~0.02 ms | ~1058 ms |
| safety verdict | `allow` | `human_required` |
| metadata 取得 | 手動 / N/A | `tools/list` で 1 件 |

## 所見

1. **機能同等性:** 時刻文字列は両方取得可能。構造は異なる（正規化層が将来必要）
2. **性能:** MCP stdio はプロセス起動コストが支配的。本番前に接続プール必須
3. **安全:** 外部 MCP はデフォルトで人間確認要求 — 意図どおり
4. **Tool 選択:** LLM には MCP の方が説明テキストが増えるが、機械 metadata は `ToolDescriptor` で統一可能
5. **監査:** `audit_id` 付き discovery ログを記録

## 成果物

- `runs/ai_tool/20260828_140000_local_vs_mcp_time/results.json`
- `runs/ai_tool/20260828_140000_local_vs_mcp_time/EXPERIMENT_REPORT.md`
- `runs/ai_tool/audit.jsonl`

## ステータス

| 項目 | ラベル |
|------|--------|
| 実験完了 | ADOPT CANDIDATE（手順として再利用可） |
| MCP 経路 | EXPERIMENTAL |
| Agent 統合 | NOT READY |

## 既知の問題（修正済）

- MCP Python SDK 2.x: `inputSchema` → `input_schema`, `isError` → `is_error`（`provider.py` で対応）
