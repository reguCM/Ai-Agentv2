# Completed Capabilities

**監査日:** 2026-08-28

**収録基準:** コード・テスト・Run 記録で**動作確認済み**と文書化されているもののみ。  
Agent 統合不要の能力も含む（ラベル付き）。

---

## Agent Core（Production — ACTIVE）

| 能力 | 根拠 |
|------|------|
| Registry から Tool 定義を読み込む | `agent.py` → `load_registry()` |
| `visibility: agent` Tool を Ollama schema 化 | `create_ollama_tools()` — 7 Tool |
| Registry Tool を動的 import 実行 | `execute_tool()` |
| Tool 実行前の認可ゲート | `agent_tool_gate.authorize_tool_execution()` |
| GPU 状態取得（Agent 経由） | `get_gpu_status` — registry + tests |
| CPU 状態取得（Agent 経由） | `cpu_status` |
| Web 検索（Agent 経由） | `search_web` |
| Workspace ファイル一覧 / 読取 / 検索 | `list_files`, `read_file`, `search_files` |

---

## Existing Tool System

| 能力 | 根拠 |
|------|------|
| 21 Tool を registry で管理 | `registry/tools.json` |
| Pipeline Tool（14）を research 経路で実行 | visibility pipeline + research scripts |
| Tool 結果の要約分離 | `test_f001_summarize_separation.py` |

---

## AI-TOOL Layer（Experimental — Agent 未統合）

| 能力 | 根拠 |
|------|------|
| Registry → ToolDescriptor 変換 | `LocalToolProvider` — ADOPT CANDIDATE 記録 |
| MCP stdio で `get_current_time` 呼び出し | EXP-001 Run `20260828_140000_local_vs_mcp_time` |
| 手動カタログ + 統合ビュー | `ToolCatalog` |
| 機械 Safety 判定（external → human_required） | `evaluate_tool_safety()` |
| 監査 JSONL 追記 | `append_audit()` |

---

## Tool Creation Layer（Experimental）

| 能力 | 根拠 |
|------|------|
| JSON Tool Specification の機械検証 | Validator — 36 pytest（doc） |
| Gold spec 4 件 regression | cpu, gpu, scoped_read, read_url |
| CI 実行 | `.github/workflows/tool_creation_tests.yml` |
| Specification → Implementation → Test → Safety → Catalog draft **一周** | scoped_read, read_url completion reports |

**未到達:** Human Review → Registry → Agent

---

## Experimental Tools（実装・テスト済み — Agent 未統合）

| 能力 | 根拠 |
|------|------|
| Allowlist 付き scoped filesystem read | `workspace_read_text_scoped` — 30 passed |
| SSRF 付き URL read (GET) | `read_url_text` — 28 deterministic |
| 実在公開 URL smoke fetch | 5 passed — Run `20260828_153616_read_url_real_web_smoke` |

---

## Context Builder（Experimental）

| 能力 | 根拠 |
|------|------|
| Fixed slots + manifest + scoped read で Context 構築 | Phase 1 — 13 pytest |
| External Help Package 生成 | Phase 2 — 27 pytest |

**未到達:** LLM / Agent / Cursor への自動投入

---

## MCP（Experimental / FROZEN）

| 能力 | 根拠 |
|------|------|
| MCP Fetch vs Local 14-case 比較記録 | Run `20260828_153335_mcp_fetch_comparison` + `mcp_comparison/` docs |
| 参照 MCP time server | `ai_tool/providers/mcp/time_server.py` |

**未到達:** Agent MCP 統合、本番 Fetch 接続

---

## Diagnostic Framework（FROZEN — 別系統）

| 能力 | 根拠 |
|------|------|
| NH1–NH14 実験記録 | `docs/diagnostic_framework/` |
| Shadow / External Help パターン研究 | NH14 |

**未到達:** Agent / search_web 本番統合（凍結ポリシーで禁止）

---

## 明示的に「できない」こと（混同防止）

| 誤解しやすい点 | 実際 |
|---------------|------|
| read_url_text がある | Agent Registry にない → **Agent は使えない** |
| MCP Provider がある | agent.py 未 import → **Agent は使えない** |
| Context Builder がある | 自動 LLM 投入なし |
| External Help がある | Cursor 自動送信なし |
| Validator ACCEPT | Registry 自動登録なし |
