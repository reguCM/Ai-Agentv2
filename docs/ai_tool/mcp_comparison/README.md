# MCP Fetch Comparison — Phase 1

**状態:** FROZEN（2026-08-28）  
**対象 Run:** [`runs/ai_tool/20260828_153335_mcp_fetch_comparison/`](../../../runs/ai_tool/20260828_153335_mcp_fetch_comparison/)

## 目的

Local experimental Tool `local:read_url_text` と公開 MCP Fetch Tool（`mcp-server-fetch` / `fetch`）を、同一 harness 上の **14 ケース**で比較し、AI-TOOL Layer の Tool Model / Safety / Provider 設計ギャップを**観測記録**する。

**これは MCP 本番導入を意味しない。** Agent 統合・Registry 登録・MCP 自動選択は Phase 1 の範囲外。

## 比較対象

| 側 | Tool ID | 備考 |
|----|---------|------|
| Local | `local:read_url_text` | `ai_tool/experimental/read_url/`（experimental） |
| MCP | `mcp:fetch` | `mcp-server-fetch` 2026.8.18、stdio subprocess |

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [CURRENT_STATUS.md](./CURRENT_STATUS.md) | 現在地（1 枚） |
| [COMPARISON.md](./COMPARISON.md) | 14 ケース比較表（Run 数値） |
| [SAFETY_COMPARISON.md](./SAFETY_COMPARISON.md) | Safety 観点の整理 |
| [BEHAVIOR_COMPARISON.md](./BEHAVIOR_COMPARISON.md) | 安全性以外の挙動差 |
| [EXPERIMENT_REPORT.md](./EXPERIMENT_REPORT.md) | 実験条件・結果・判定 |
| [FAILURE_ANALYSIS.md](./FAILURE_ANALYSIS.md) | 失敗・例外の分類 |
| [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) | 今回評価していない範囲 |
| [PHASE1_FREEZE.md](./PHASE1_FREEZE.md) | Phase 1 固定宣言 |

## 関連（Phase 1 外）

- Local Tool 作成: [tool_creation/READ_URL_COMPLETION_REPORT.md](../tool_creation/READ_URL_COMPLETION_REPORT.md)
- 簡易比較メモ（接続前）: [tool_creation/LOCAL_VS_MCP_FETCH.md](../tool_creation/LOCAL_VS_MCP_FETCH.md)
- MCP 候補調査: [tool_creation/candidate_research/fetch.md](../tool_creation/candidate_research/fetch.md)
- AI-TOOL Layer 入口: [README.md](../README.md)

## 注意

- 数値・成否は **対象 Run の JSON のみ**を根拠とする（推測値なし）。
- 「MCP が優秀」「Local が完全に安全」等の採用判断は Phase 1 では行わない。
