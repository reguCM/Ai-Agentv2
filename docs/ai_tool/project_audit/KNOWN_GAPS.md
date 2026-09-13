# Known Gaps

**監査日:** 2026-08-28

調査に基づく**未完成・未接続**の記録。推測で埋めない。

---

## Agent ↔ AI-TOOL 統合

| ギャップ | 状態 | 根拠 |
|----------|------|------|
| Agent が AI-TOOL Layer を認識 | **No** | `agent.py` に `ai_tool` import なし |
| Agent が experimental Tool を認識 | **No** | registry 未登録 |
| `ToolCatalog.summarize_for_agent_view()` → Agent | **No** | 実装あるが未接続（AI-TOOL CURRENT_STATUS） |
| MCP Tool を Agent が選択 | **No** | MCPToolProvider 未統合 |

---

## Registry / Catalog

| ギャップ | 状態 |
|----------|------|
| experimental Tool の Registry 登録 | **No** |
| `ai_tool_catalog.json` → `tools.json` 自動マージ | **No**（note フィールドで明示） |
| Tool Creation Validator → Registry 自動書込 | **No** |
| 三層 catalog status の本番運用 | **DESIGN_ONLY**（draft のみ） |

---

## MCP

| ギャップ | 状態 |
|----------|------|
| MCP trust model 実装 | **NOT_READY**（H-MCP-5: 設計仮説のみ） |
| MCP Provider SDK 1.x / 2.x 分離 | **PARTIAL** — Fetch 比較で list_descriptors 失敗記録 |
| MCP Fetch 本番接続 | **NOT_READY** — Phase 1 FROZEN |
| Agent MCP allowlist | **NOT_STARTED** |

---

## Tool Creation / Automation

| ギャップ | 状態 |
|----------|------|
| Human approval ワークフロー統合 | **NOT_READY** |
| Cursor への External Help 自動引き渡し | **No** |
| LLM 自動 Tool 生成 | **NOT_STARTED**（指示書でも禁止） |
| LLM 自動 Implementation | **NOT_STARTED** |
| Compatibility validation（registry 変更時） | **Partial** — 政策 doc のみ |
| Tool versioning 本番運用 | **NOT_READY** |

---

## Safety / Trust

| ギャップ | 状態 |
|----------|------|
| MCP 呼び出し前 Client-side URL policy | **NOT_READY** |
| experimental Tool の agent_tool_gate 統合 | **No** |
| DNS rebinding 完全防御（read_url） | **UNKNOWN**（政策明記） |
| `trust_external` の Catalog 表現 | **NOT_READY** |

---

## Context / Help

| ギャップ | 状態 |
|----------|------|
| Context Builder → LLM 自動投入 | **No** |
| read_url を Context Builder に追加 | **No**（selection_rules 未登録 — 既存記録） |
| NH14 パターンの Agent 統合 | **No**（DF FROZEN） |

---

## Diagnostic Framework

| ギャップ | 状態 |
|----------|------|
| DF → Agent / search_web 統合 | **意図的に未実施**（FROZEN） |
| NH15+ | **保留**（需要まで停止） |

---

## ドキュメント / 運用

| ギャップ | 状態 |
|----------|------|
| PROJECT_SPEC.md §14 開発状態 | **Stale**（Registry 未実装等と記載 — 実装は先行） |
| APIToolProvider | **UNKNOWN / 未実装** |
| audit JSONL ローテーション | **NOT_READY** |

---

## 最大の構造ギャップ（要約）

```text
[ 実装・実験・Validator まで到達 ]
              │
              ▼  ← ここが未接続
[ Human Review → Registry → Agent LLM schema ]
```

experimental 層は **意図的に隔離** されている。ギャップの多くは「未実装」ではなく **「統合 STOP 条件により未着手」**。
