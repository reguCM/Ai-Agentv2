# Tool Status

**監査日:** 2026-08-28

**Agent 利用可能** = `registry/tools.json` 登録 **かつ** LLM schema 公開（`visibility: "agent"`）  
実装・テストがあっても Registry / visibility 外なら Agent 利用不可。

---

## 重点 Tool 表（指示書要求）

| Tool | Specification | Implementation | Tests | Safety | Catalog | Registry | Agent |
|------|---------------|----------------|-------|--------|---------|----------|-------|
| **get_gpu_status** | Yes — gold spec + mapping doc | Yes — `tools/system/gpu/gpu_status.py` | Yes — `tests/test_gpu_real_observation.py` + TC gold | Yes — `agent_tool_gate` + risk in registry | Mapping doc only; not in `ai_tool_catalog.json` | **Yes** — `visibility: agent` | **Yes** |
| **cpu_status** | Yes — gold spec + mapping doc | Yes — `tools/system/cpu/cpu_status.py` | Yes — TC gold spec regression | Yes — gate + registry risk | Mapping doc only | **Yes** — `visibility: agent` | **Yes** |
| **read_file** | Mapping doc (existing) | Yes — `tools/file/workspace/read_file.py` | Yes — agent phase verify scripts | Yes — gate | No ai_tool catalog | **Yes** — `visibility: agent` | **Yes** |
| **workspace_read_text_scoped** | Yes — `specs/local_workspace_read_text_scoped.json` (ACCEPT) | Yes — `ai_tool/experimental/scoped_read/` | Yes — 30 passed, 2 skipped | Yes — allowlist policy + tests | Draft — `not_reviewed` | **No** | **No** |
| **read_url_text** | Yes — `specs/local_read_url_text.json` (ACCEPT) | Yes — `ai_tool/experimental/read_url/` | Yes — 28 deterministic + 5 real_web smoke | Yes — SSRF policy + tests | Draft — `not_reviewed` | **No** | **No** |

---

## Agent 公開 Tool（7 件）

| Tool ID (conceptual) | Registry name | Module | visibility |
|----------------------|---------------|--------|------------|
| local:get_gpu_status | `get_gpu_status` | `tools.system.gpu.gpu_status` | agent |
| — | `get_gpu_processes` | `tools.system.gpu.gpu_processes` | agent |
| local:cpu_status | `cpu_status` | `tools.system.cpu.cpu_status` | agent |
| — | `search_web` | `tools.system.network.search_web` | agent |
| — | `list_files` | `tools.file.workspace.list_files` | agent |
| — | `read_file` | `tools.file.workspace.read_file` | agent |
| — | `search_files` | `tools.file.workspace.search_files` | agent |

---

## Pipeline Tool（14 件 — Agent LLM 非公開）

Registry `visibility: pipeline`。Tool Builder / research 経路から利用。Agent Ollama schema には含まれない。

Examples: `create_tool_proposal`, `research_tool`, `register_tool`, `validate_tool_implementation`, …

---

## Experimental Tool（Registry 外）

| Tool ID | Provider | Implementation | Spec validator | Registry | Agent |
|---------|----------|----------------|----------------|----------|-------|
| `local:workspace_read_text_scoped` | local (experimental) | `ai_tool/experimental/scoped_read/` | ACCEPT | No | No |
| `local:read_url_text` | local (experimental) | `ai_tool/experimental/read_url/` | ACCEPT | No | No |

---

## AI-TOOL Catalog（`registry/ai_tool_catalog.json`）

| Tool ID | Provider | Registry | Agent |
|---------|----------|----------|-------|
| `mcp:get_current_time` | mcp | No (`tools.json` 別系統) | No |

Experimental local tools は **未登録**。

---

## MCP Fetch（比較対象 — 本番 Tool ではない）

| Tool ID | 実装 | Agent | 備考 |
|---------|------|-------|------|
| `mcp:fetch` | `mcp-server-fetch`（実験 subprocess） | No | Phase 1 FROZEN 比較のみ |

---

## 凡例

| 列 | 意味 |
|----|------|
| Specification | Tool Creation JSON spec または mapping doc が存在 |
| Safety | 実装側 policy + テスト、または `agent_tool_gate` |
| Catalog | `ai_tool_catalog.json` または catalog draft（三層 status） |
| Agent | LLM が `create_ollama_tools()` 経由で選択可能か |
