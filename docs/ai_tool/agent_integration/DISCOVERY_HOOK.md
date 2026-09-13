# Agent Discovery Hook — Phase 2

**状態:** IMPLEMENTED（read-only hook + optional Agent startup）

Phase 1 の Discovery Adapter 上に、Agent Core 向け **fail-safe hook** を追加。

## Hook API

```python
from ai_tool.agent_integration.hook import safe_run_agent_discovery_hook

result = safe_run_agent_discovery_hook()
# result.execution_count == 0 always
# result.tools[] — flattened records with三層 status
```

## Agent Core 接続

`agent.py` 起動時（デフォルト ON、`AI_AGENT_SKIP_TOOL_DISCOVERY=1` で skip）:

```text
[AGENT_TOOL_DISCOVERY]  — observation_only JSON
```

- **変更しない:** `create_ollama_tools()`, `execute_tool()`
- Discovery 失敗時も Agent 継続（`safe_run_agent_discovery_hook`）

## Discovery vs Execution

| | Discovery Hook | Agent execute_tool |
|---|----------------|-------------------|
| 目的 | Tool 存在の認識 | Tool 実行 |
| experimental | 認識可、`agent_available=false` | Registry 未登録 → 通常到達不可 |
| LLM schema | **非接続** | visibility=agent のみ |
| 副作用 | なし | Tool 依存 |

## Experimental が実行できない理由

1. `registry/tools.json` 未登録 → LLM schema に含まれない  
2. Discovery は metadata のみ — execute path 非接続  
3. `agent_available=false` + `experimental_not_integrated` を明示保持  

## Run

`runs/ai_tool/<timestamp>_agent_discovery_hook/`

## Phase 2 成果物

- [PHASE2_REPORT.md](./PHASE2_REPORT.md)
- [DISCOVERY_HOOK.md](./DISCOVERY_HOOK.md)

## Phase 1

- [PHASE1_REPORT.md](./PHASE1_REPORT.md)
- [AGENT_DISCOVERY_SPEC.md](./AGENT_DISCOVERY_SPEC.md)
