# Audit Report — AI-Agent Project Phase 1

**監査日:** 2026-08-28  
**監査種別:** 読み取り専用棚卸し（新規実装・実験なし）

---

## 1. 調査対象

| 領域 | 主要パス |
|------|----------|
| Agent Core | `agent.py`, `registry/tools.json`, `tools/` |
| AI-TOOL Layer | `ai_tool/`, `docs/ai_tool/`, `runs/ai_tool/`（14 runs） |
| Tool Creation | `docs/ai_tool/tool_creation/`, validator, pytest/CI |
| Context Builder | `ai_tool/context_builder/`, Phase 1–2 runs |
| Experimental Tools | `ai_tool/experimental/scoped_read`, `read_url` |
| MCP | Provider, `docs/ai_tool/mcp_comparison/`, frozen run |
| Diagnostic Framework | `docs/diagnostic_framework/`, NH1–NH14 research code |

---

## 2. 現在の Agent 構造

- **本体:** `agent.py` — Ollama LLM ループ
- **Tool 定義:** `registry/tools.json`（21 Tool）
- **実行:** `execute_tool()` → `importlib` → `tools.*`
- **LLM 公開:** `create_ollama_tools()` — **`visibility: "agent"` の 7 Tool のみ**
- **認可:** `agent_tool_gate`
- **ai_tool 統合:** **なし**（grep ゼロ）

---

## 3. 実際に Agent（LLM）が利用可能な Tool

**7 件:** `get_gpu_status`, `get_gpu_processes`, `cpu_status`, `search_web`, `list_files`, `read_file`, `search_files`

Pipeline 14 件は Registry にあるが **LLM schema 非公開**。

---

## 4. Experimental Tool（Agent 不可）

| Tool | 実装 | Registry | Agent |
|------|------|----------|-------|
| `local:workspace_read_text_scoped` | Yes | No | No |
| `local:read_url_text` | Yes | No | No |

Tool Creation 工程（Spec → Validator → Impl → Test → Safety → Catalog draft）は **一周済み**。

---

## 5. Tool Creation Layer の状態

| 項目 | 状態 |
|------|------|
| Validator + pytest + CI | **EXPERIMENTAL** / ADOPT CANDIDATE |
| Gold specs | 4 件 |
| Registry 自動登録 | **No** |
| Agent 統合 | **No** |

---

## 6. Context Builder の状態

| Phase | 状態 |
|-------|------|
| Phase 1 — Context manifest | **EXPERIMENTAL** 完了（13 pytest） |
| Phase 2 — External Help Package | **EXPERIMENTAL** 完了（27 pytest） |
| Agent / LLM 投入 | **NOT_READY** |

---

## 7. MCP の状態

| 項目 | 状態 |
|------|------|
| MCPToolProvider | コードあり — **EXPERIMENTAL** |
| EXP-001 time | 成功 |
| Fetch 比較 Phase 1 | **FROZEN**（14 cases） |
| Agent 統合 | **NOT_READY** |
| ai_tool_catalog | `mcp:get_current_time` のみ |

---

## 8. Diagnostic Framework の状態

- **FROZEN**（2026-08-28）、NH1–NH14 仮完成
- コード: `research/llm_benchmarks/.../diagnostic_framework/`
- **Agent 統合なし**（import なし）
- 新規 NH 実験: 需要まで **停止**（凍結ポリシー）

位置付け `Diagnostic Framework = 研究・診断基盤 / FROZEN` は既存 `PROJECT_FREEZE.md` と **一致**。

---

## 9. Cursor と Agent の役割分離

- **Cursor:** 開発支援 — experimental コード・実験・文書の作成
- **AI-Agent:** 実行対象 — Registry 経由の 7 Tool のみ LLM 公開

「AI-Agent が自律的に Tool を作った」とは **現状記載不可**（[CURSOR_VS_AGENT.md](./CURSOR_VS_AGENT.md)）。

---

## 10. 最大の未完成部分

```text
Human Review → registry/tools.json → agent.py (LLM schema)
```

experimental 層（ai_tool, Tool Creation 成果, Context Builder, MCP 実験）は **隔離済み**だが **本番 Agent パス未接続**。

---

## 11. 今後人間判断が必要な項目

1. experimental Tool の Registry 登録要否（scoped read / read_url）
2. AI-TOOL Layer の Agent 統合タイミング（NOT READY 継続か）
3. MCP trust model / SDK 分離方針
4. Tool Creation Validator の pipeline 正式採用
5. Diagnostic Framework 再開条件（NH15+）
6. Context Builder / External Help の配信先設計

詳細候補: [NEXT_DECISIONS.md](./NEXT_DECISIONS.md)

---

## 12. 本監査で変更していない本番領域

| 対象 | 変更 |
|------|------|
| `agent.py` | **なし** |
| `tools/` | **なし** |
| `registry/tools.json` | **なし** |
| Local Tool 本体（`ai_tool/experimental/read_url/` 等） | **なし** |
| MCP Provider 本体 | **なし** |
| Diagnostic Framework コード / runs | **なし** |
| 既存 experiment runs | **なし** |
| 新規実験実行 | **なし** |

**変更:** `docs/ai_tool/project_audit/` 新規 11 ファイル + `docs/ai_tool/README.md` リンク 1 行

---

## 13. 作成ファイル一覧

```text
docs/ai_tool/project_audit/
├── README.md
├── CURRENT_STATE.md
├── ARCHITECTURE_MAP.md
├── COMPONENT_STATUS.md
├── TOOL_STATUS.md
├── PRODUCTION_VS_EXPERIMENTAL.md
├── CURSOR_VS_AGENT.md
├── COMPLETED_CAPABILITIES.md
├── KNOWN_GAPS.md
├── NEXT_DECISIONS.md
└── AUDIT_REPORT.md
```

---

## 14. 検証チェックリスト

| 項目 | 結果 |
|------|------|
| 推測で UNKNOWN を埋めていない | OK |
| Agent 利用可能 = 7 Tool のみと明示 | OK |
| experimental ≠ Agent Tool と明示 | OK |
| DF FROZEN 状態を既存 doc と照合 | OK（一致） |
| MCP Phase 1 FROZEN を参照 | OK |
| 本番コード未変更 | OK |

---

## STOP

本監査 Phase 1 完了。Agent 統合・新規実験・Registry 変更には **進んでいない**。
