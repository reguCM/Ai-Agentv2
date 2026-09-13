# Architecture Map — AI-Agent Project

**監査日:** 2026-08-28  
コード・既存文書に基づく構造。推測なし。

**鮮度追記（2026-09-09）:** 下図は 2026-08-28 監査の層構造。現行 Chat Production の入口は `ai_tool/chat_interface/agent_turn.py` の `run_chat_turn`（Chat UI も同じ。この経路は `agent.py` を import しない）。`agent.py` は別入口として残る。廃止ではない。本追記は Chat 経路の入口同期であり、図の全面改訂ではない。search hit 後の pending read は H4 Core の Runtime bridge（意味判断の正本ではない）。

## 全体図

```text
Human
  │
  ├── Cursor（IDE / 開発支援）
  │     └── コード作成・実験ランナー実行・ドキュメント作成
  │         （AI-Agent の自律機能ではない）
  │
  └── AI-Agent（開発対象システム）
        │
        ├── Agent Core ───────────────────────── ACTIVE
        │     agent.py
        │     load_registry() → create_ollama_tools() [visibility=agent only]
        │     execute_tool() → importlib → tools.* 
        │     agent_tool_gate（実行前認可）
        │
        ├── Existing Tool System ───────────────── ACTIVE
        │     registry/tools.json（21 Tool）
        │     tools/（Python 実装）
        │     visibility: agent (7) | pipeline (14)
        │
        ├── AI-TOOL Layer ──────────────────────── EXPERIMENTAL
        │     ai_tool/core/（ToolDescriptor, safety, audit）
        │     ai_tool/providers/（Local, MCP）
        │     ai_tool/registry/catalog.py
        │     ai_tool/experimental/（scoped_read, read_url, mcp_compare）
        │     ※ agent.py から import なし
        │
        ├── Tool Creation Layer ────────────────── EXPERIMENTAL
        │     docs/ai_tool/tool_creation/（validator, specs, workflow）
        │     docs/ai_tool/tool_creation/tests/（pytest + CI）
        │     ※ registry 自動登録なし
        │
        ├── Context Builder ────────────────────── EXPERIMENTAL
        │     ai_tool/context_builder/
        │     scoped_read 経由で本文取得
        │     ※ LLM / Agent 自動投入なし
        │
        ├── External Help Package ──────────────── EXPERIMENTAL
        │     package_generator.py（Phase 2）
        │     ※ Cursor 自動送信なし
        │
        └── Experimental Tools ─────────────────── EXPERIMENTAL
              local:workspace_read_text_scoped
              local:read_url_text
              ※ registry/tools.json 未登録

Diagnostic Framework ─────────────────────────── FROZEN（別系統）
        research/llm_benchmarks/.../diagnostic_framework/
        docs/diagnostic_framework/
        NH1–NH14 研究・Shadow 実験
        ※ agent.py 統合なし
```

## 依存関係（実コード）

```text
agent.py
  ├── registry/tools.json          （読み取り）
  ├── tools.<module>.<function>    （動的 import 実行）
  ├── tools.system.agent_tool_gate （実行認可）
  └── tools.system.tool_builder.search （Tool 検索）

ai_tool/                           （独立 — agent.py 非依存）
  ├── LocalToolProvider → registry/tools.json（読み取りビュー）
  ├── MCPToolProvider → stdio MCP subprocess
  ├── experimental/* → 直接 Python import（実験・pytest のみ）
  └── context_builder → experimental/scoped_read

Tool Creation validator            （独立 — docs/ai_tool/tool_creation/）
  └── JSON spec 検証（registry 書き込みなし）

Diagnostic Framework               （独立 — research/ 配下）
  └── NH 実験ランナー、Shadow ログ
```

## Production vs Experimental 境界

```text
                    AI-Agent Project
                          │
             ┌────────────┴────────────┐
             │                         │
       Production                 Experimental
             │                         │
        agent.py                 ai_tool/
        tools/                   ai_tool/experimental/
        registry/tools.json      docs/ai_tool/tool_creation/
             │                   context_builder/
             │                   mcp_comparison/ (FROZEN)
             │
             └──────────┐
                        │
                     Agent (LLM loop)
                        │
              7 public tools + gate
```

## LLM 公開 vs 実行可能

| 経路 | visibility フィルタ | 備考 |
|------|---------------------|------|
| `create_ollama_tools()` | **agent のみ** | LLM が選択可能 |
| `execute_tool()` | **なし**（名前が Registry にあれば実行可） | 通常 LLM は schema 外 Tool に到達しない |
| `ai_tool/*` | N/A | Agent 未接続 |

## Diagnostic Framework の位置

Agent Core・AI-TOOL Layer と**並列の研究基盤**。2026-08-28 FROZEN（[../../diagnostic_framework/PROJECT_FREEZE.md](../../diagnostic_framework/PROJECT_FREEZE.md)）。

NH14 の External Help **パターン**は Context Builder Phase 2 が参照するが、DF コードは Agent / ai_tool 実行時に呼ばれない。
