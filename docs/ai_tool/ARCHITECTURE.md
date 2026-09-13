# AI-TOOL Architecture (Phase 1)

## レイヤ概要

```text
┌─────────────────────────────────────────────────────────┐
│  agent.py (既存・未変更)                                  │
│  load_registry → create_ollama_tools → execute_tool      │
└───────────────────────────┬─────────────────────────────┘
                            │ 将来: 非破壊アダプタ
┌───────────────────────────▼─────────────────────────────┐
│  AI-TOOL Layer (ai_tool/) — Phase 1 実験パッケージ        │
│                                                          │
│  ToolCatalog ──► LocalToolProvider ──► registry/tools.json│
│       │                                                  │
│       ├──► registry/ai_tool_catalog.json (手動)         │
│       └──► MCPToolProvider ──► stdio ──► time_server     │
│                                                          │
│  evaluate_tool_safety (Validator)                        │
│  append_audit (監査)                                      │
└─────────────────────────────────────────────────────────┘
```

## 責務分離

| 層 | 責務 | Phase 1 実装 |
|----|------|--------------|
| **Tool** | 何ができるか（metadata） | `ToolDescriptor` |
| **Discovery** | 一覧・仕様取得 | `LocalToolProvider`, `MCPToolProvider`, `ToolCatalog` |
| **Selector** | どれを使うか | 未実装（既存 Agent LLM + registry に委譲） |
| **Validator** | 使ってよいか | `evaluate_tool_safety()` |
| **Execution** | 実行する | Provider の `execute` / `call_tool` |
| **Result** | 何が返ったか | `ToolExecutionResult` |
| **Audit** | 証跡 | `append_audit()` → JSONL |

Diagnostic Framework の Observation → Mapping → Fingerprint → Gate → Selector → Validator 思想に対応する機械的フィールドを Descriptor に集約し、LLM 推測を避ける。

## 既存システムとの境界

### 触っていない境界（安全）

1. **`registry/tools.json`** — Local Provider は読み取りのみ
2. **`agent.py`** — 実行パスは従来どおり
3. **`tools/*.py`** — 本番 Tool 実装は不変

### 追加した境界（拡張点）

1. **`registry/ai_tool_catalog.json`** — 外部 Tool の手動記述。`tools.json` と独立
2. **`ai_tool/` パッケージ** — 新規。import しない限り既存動作に影響なし
3. **`runs/ai_tool/`** — AI-TOOL 専用ログ・実験（NH 番号不使用）

### 将来の統合パス（設計のみ）

```text
Registry (論理ビュー)
 ├── local tools      ← tools.json（既存）
 ├── mcp tools        ← ai_tool_catalog.json + live discovery
 └── future external  ← APIToolProvider 等

Agent
 └── execute_tool() は維持
 └── オプション: ai_tool 経由で descriptor 解決・安全チェック・監査
```

## データフロー（EXP-001）

```text
run_compare_experiment.py
  │
  ├─► ToolCatalog.audit_discovery()
  ├─► local_get_current_time()          [Local 参照実装]
  ├─► MCPToolProvider.call_tool()       [MCP get_current_time]
  ├─► evaluate_tool_safety() × 2
  └─► runs/ai_tool/.../results.json
```

## Tool Builder との関係

既存 Tool Builder は維持。将来:

```text
Tool Builder → Local Tool 実装 → LocalToolProvider → ToolCatalog
Tool Proposal → Specification → registry/tools.json（人間承認後）

MCP Server → MCPToolProvider.discovery → ai_tool_catalog.json（手動承認後）
```

Phase 1 では Builder / Proposal へのコード変更は行っていない。
