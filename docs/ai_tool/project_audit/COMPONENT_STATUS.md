# Component Status

**監査日:** 2026-08-28

**監査分類:** ACTIVE | EXPERIMENTAL | DESIGN_ONLY | NOT_READY | FROZEN  
**既存ラベル:** ADOPT CANDIDATE 等は別列（Tool Creation / AI-TOOL 文書由来）

| Component | Code | Tests | Agent integrated | Production use | Audit status | Existing label |
|-----------|------|-------|------------------|----------------|--------------|----------------|
| **A. Agent Core** (`agent.py`) | Yes | Partial (`test_agent_tool_gate`, `test_f001_*`, etc.) | N/A (本体) | **Yes** — LLM loop | **ACTIVE** | — |
| **B. Local Tool System** (`tools/` + `registry/tools.json`) | Yes (21 tools) | Yes (multiple `tests/`) | **Yes** (7 agent tools) | **Yes** | **ACTIVE** | — |
| **B. agent_tool_gate** | Yes | Yes | **Yes** | **Yes** | **ACTIVE** | — |
| **C. AI-TOOL core** (`ai_tool/core/`) | Yes | Via providers/experiments | **No** | **No** | **EXPERIMENTAL** | ToolDescriptor: EXPERIMENTAL |
| **C. LocalToolProvider** | Yes | EXP-001 | **No** | **No** | **EXPERIMENTAL** | ADOPT CANDIDATE |
| **C. MCPToolProvider** | Yes | EXP-001, MCP compare | **No** | **No** | **NOT_READY** (Agent) / **EXPERIMENTAL** (code) | EXPERIMENTAL |
| **C. ToolCatalog** | Yes | Manual / experiments | **No** | **No** | **EXPERIMENTAL** | EXPERIMENTAL |
| **D. Tool Creation Validator** | Yes (`docs/.../validator/`) | 36 pytest (doc) | **No** | **No** | **EXPERIMENTAL** | ADOPT CANDIDATE |
| **D. Tool Creation Workflow docs** | Docs | — | **No** | **No** | **DESIGN_ONLY** (自動化) / **EXPERIMENTAL** (validator) | ADOPT CANDIDATE |
| **D. Tool Creation CI** | Yes (`.github/workflows/tool_creation_tests.yml`) | CI | **No** | **No** | **EXPERIMENTAL** | — |
| **E. Context Builder Phase 1** | Yes | 13 passed (doc) | **No** | **No** | **EXPERIMENTAL** | — |
| **E. Context Builder Phase 2** | Yes | 27 passed (doc) | **No** | **No** | **EXPERIMENTAL** | — |
| **F. External Help Package** | Yes (`package_generator.py`) | In Phase 2 tests | **No** | **No** | **EXPERIMENTAL** | — |
| **G. workspace_read_text_scoped** | Yes | 30 passed, 2 skipped | **No** | **No** | **EXPERIMENTAL** | not_reviewed |
| **G. read_url_text** | Yes | 28 + 5 smoke | **No** | **No** | **EXPERIMENTAL** | not_reviewed |
| **H. MCP time_server (ref)** | Yes | EXP-001 | **No** | **No** | **EXPERIMENTAL** | — |
| **H. MCP Fetch comparison** | Harness only | 14-case run | **No** | **No** | **FROZEN** | Phase 1 complete |
| **I. Diagnostic Framework** | Yes (`research/.../diagnostic_framework/`) | NH runs | **No** | **No** | **FROZEN** | PARTIALLY_READY |
| **Pipeline Tools** (14) | Yes | Research/benchmark tests | **No** (not in Ollama schema) | Pipeline only | **ACTIVE** (code) / not Agent-public | visibility: pipeline |
| **registry/ai_tool_catalog.json** | Yes (1 entry) | — | **No** | **No** | **EXPERIMENTAL** | manual catalog |
| **APIToolProvider** | No | No | **No** | **No** | **NOT_READY** | UNKNOWN |
| **Cognitive Phase 1 sidecar** | Yes (`agent.py`) | Yes | Partial (obs only) | Env-flag only | **EXPERIMENTAL** | Not connected to tools |

## Layer 別サマリ

| Layer | 実装 | 実験 | Agent 統合 | 本番利用 |
|-------|------|------|------------|----------|
| L0 Agent Core | Yes | Sidecar obs | Yes | Yes |
| L1 Existing Tools | Yes | — | Yes (7) | Yes |
| L2 AI-TOOL | Yes | Yes | No | No |
| L3 Tool Creation | Validator yes | Yes | No | No |
| L4 Context Builder | Yes | Phase 1–2 | No | No |
| L5 External Help | Yes | Phase 2 | No | No |
| L6 Diagnostic FW | Yes | NH1–14 | No | No (FROZEN) |
