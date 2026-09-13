# Production vs Experimental

**監査日:** 2026-08-28

## 核心原則

```text
experimental Tool  ≠  Agent が利用可能な Tool
ai_tool/ の実装     ≠  Production Tool
MCP Provider 存在   ≠  Agent が MCP を使える
```

---

## Production 領域（ACTIVE）

| パス / コンポーネント | 役割 | Agent 接続 |
|----------------------|------|------------|
| `agent.py` | LLM ループ、Tool 実行 | 本体 |
| `registry/tools.json` | 21 Tool 定義 | 直接読込 |
| `tools/` | 本番 Tool 実装 | `execute_tool()` import |
| `tools/system/agent_tool_gate.py` | 実行認可 | 実行前 |
| `registry/agent_tool_trust.json` 等 | Trust 設定（存在） | gate 経由 |

### Agent が「使える」と言える条件（本監査の定義）

1. `registry/tools.json` に登録されている
2. `visibility: "agent"` で Ollama schema に載る
3. `agent_tool_gate` を通過して実行される

→ **該当: 7 Tool のみ**（GPU/CPU/search_web/workspace ファイル操作）

---

## Experimental 領域

| パス | 内容 | Agent |
|------|------|-------|
| `ai_tool/` | AI-TOOL Layer 全体 | **未統合** |
| `ai_tool/experimental/` | scoped_read, read_url, mcp_compare harness | **未統合** |
| `ai_tool/context_builder/` | Context 収集 | **未統合** |
| `ai_tool/providers/mcp/` | MCP client | **未統合** |
| `docs/ai_tool/tool_creation/` | Validator, specs, workflow | **未統合** |
| `registry/ai_tool_catalog.json` | 手動 experimental catalog（1 entry） | **未統合** |
| `runs/ai_tool/` | 14 experiment runs | 記録のみ |

### Experimental Tool の状態

| Tool | コード | Registry | Agent LLM |
|------|--------|----------|-----------|
| `workspace_read_text_scoped` | あり | なし | 不可 |
| `read_url_text` | あり | なし | 不可 |

Catalog draft 状態（既存記録）:

```text
tool_status:         unavailable
experiment_status:   experimental
adoption_status:     not_reviewed
```

---

## Pipeline 領域（Production コード、Agent 非公開）

| 項目 | 値 |
|------|-----|
| Tool 数 | 14 |
| visibility | `pipeline` |
| LLM schema | **含まれない** |
| 利用経路 | `research/llm_benchmarks/`, Tool Builder フロー |

Production **コード**だが、Agent の対話ループからは隔離。

---

## FROZEN 領域（変更禁止・新規実験停止）

| 基盤 | ドキュメント | コード |
|------|-------------|--------|
| Diagnostic Framework | `docs/diagnostic_framework/` | `research/.../diagnostic_framework/` |
| MCP Fetch Comparison Phase 1 | `docs/ai_tool/mcp_comparison/` | Run `20260828_153335_*` |

---

## 境界図（コード準拠）

```text
┌─────────────────────────────────────────────────────────┐
│ PRODUCTION (Agent path)                                  │
│  agent.py → registry/tools.json → tools/ → gate        │
│  LLM sees: visibility=agent (7)                        │
└─────────────────────────────────────────────────────────┘
         ╳ no import ╳
┌─────────────────────────────────────────────────────────┐
│ EXPERIMENTAL (isolated)                                  │
│  ai_tool/* , tool_creation validator, context_builder    │
│  experimental tools NOT in registry/tools.json           │
└─────────────────────────────────────────────────────────┘
         ╳ no import ╳
┌─────────────────────────────────────────────────────────┐
│ FROZEN RESEARCH                                          │
│  Diagnostic Framework (NH1-14)                           │
└─────────────────────────────────────────────────────────┘
```

---

## execute_tool の注意

`execute_tool()` は **visibility を検査しない**。Registry に名前があればプログラムから pipeline Tool も実行可能。通常の LLM 経路では schema 外のため到達しない。

これは Production 境界の**実装事実**であり、experimental Tool が実行可能になる意味ではない（Registry 未登録のため）。
