# Agent Discovery Spec — Phase 1

**状態:** IMPLEMENTED（read-only）

## 責務

`AgentToolDiscoveryAdapter` は **metadata 読み取りのみ**。Tool 実行・Registry 更新・ネットワーク・ファイル書込を行わない。

```text
Agent (future / optional)
  ↓
AgentToolDiscoveryAdapter   ← Phase 1 ここまで
  ↓
registry/tools.json | ai_tool/catalog/entries | ai_tool_catalog.json
```

`agent.py` の `execute_tool()` / `create_ollama_tools()` には **接続しない**。

---

## Public API

### `discover_tools(*, audit: bool = True) -> DiscoveryResult`

全 Tool を discovery。`tool_id` 昇順で deterministic。

### `get_tool_descriptor(tool_id: str) -> AgentDiscoveredTool | None`

単一 Tool。存在しない場合 **`None`**（情報を捏造しない）。

### `AgentToolDiscoveryAdapter.comparison_table() -> list[dict]`

代表 5 Tool の観測表（Phase 1 比較用）。

---

## `AgentDiscoveredTool` フィールド

| フィールド | 説明 |
|-----------|------|
| `tool_id` | 例: `local:get_gpu_status`, `local:read_url_text` |
| `name` | Tool 名 |
| `provider` | `local` \| `mcp` |
| `description` | 説明 |
| `source` | データ由来パス（`registry/tools.json` 等） |
| `discovery_category` | `production` \| `experimental` \| `unavailable` \| `not_ready` |
| `agent_available` | Agent LLM 経路で利用可能か（Phase 1: registry visibility=agent のみ true） |
| `availability` | `available` \| `not_available` |
| `catalog_status` | **三層** — 下記 |
| `unavailability_reason` | 例: `experimental_not_integrated` |
| `input_schema` / `output_schema` | JSON Schema |
| `side_effect` | 例: `read_only` |
| `risk_level` | low / medium / high |
| `permissions` | 例: `visibility:agent` |
| `status_derivation` | 派生規則ラベル（監査用） |

### `catalog_status`（三層 — 潰さない）

| 層 | フィールド |
|----|-----------|
| Tool 本体 | `tool_status` |
| 実験 | `experiment_status` |
| 採用 | `adoption_status` |

`discovery_category` は **別軸**。`experiment_status=experimental` を単一 `experimental` ラベルに置換しない。

---

## データソース

| ソース | 内容 | discovery_category |
|--------|------|-------------------|
| `registry/tools.json` | 全 21 Tool | visibility=agent → production; pipeline → not_ready |
| `ai_tool/catalog/entries/*.json` | experimental local | experimental |
| `registry/ai_tool_catalog.json` | MCP manual | experimental |

**MCP live discovery（stdio）は Phase 1 で呼ばない**（非決定論・実行境界回避）。

---

## 代表 Tool  mapping（Phase 1 確認済み）

| tool_id | agent_available | discovery_category | source |
|---------|-----------------|-------------------|--------|
| local:get_gpu_status | true | production | Registry |
| local:cpu_status | true | production | Registry |
| local:read_file | true | production | Registry |
| local:workspace_read_text_scoped | false | experimental | AI-TOOL Catalog |
| local:read_url_text | false | experimental | AI-TOOL Catalog |

---

## Registry production の status 派生

Registry エントリには三層フィールドが無いため、**明示的派生**（`status_derivation` 記録）:

| visibility | tool_status | experiment_status | adoption_status |
|------------|-------------|-------------------|-----------------|
| agent | available | tested | approved |

experimental catalog エントリは JSON の三層を **そのまま**保持。

---

## UNKNOWN / NOT_FOUND

- 未知 `tool_id` → `get_tool_descriptor()` returns `None`
- comparison_table で missing → `NOT_FOUND` / `UNKNOWN` 行（捏造なし）

---

## 責務境界

| 文書 | 責務 |
|------|------|
| [TOOL_CONTRACT](../tool_creation/TOOL_CONTRACT.md) | Tool 入出力契約 |
| [CATALOG](../tool_creation/CATALOG.md) | Catalog スキーマ・三層定義 |
| 本 spec | Agent 向け **discovery ビュー** |
| [SAFETY_BOUNDARY](./SAFETY_BOUNDARY.md) | discovery read-only 境界 |
