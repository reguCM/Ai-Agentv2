# Agent Integration — Phase 1–5

**状態:** Phase 5 COMPLETE（Production Agent experimental overlay）

## 目的

AI-Agent が AI-TOOL Layer の Tool **存在を認識**する第二経路を追加する。experimental Tool は **実行・公開しない**。

```text
registry/tools.json ──→ Discovery Adapter ──→ production (agent_available=true)
ai_tool/catalog/entries ──→                  ──→ experimental (agent_available=false)
registry/ai_tool_catalog.json ──→            ──→ MCP experimental
```

**接続していない:** `agent.py` 実行 path、Ollama schema、Tool execution

## コード

| パス | 役割 |
|------|------|
| `ai_tool/agent_integration/discovery.py` | `discover_tools()`, `get_tool_descriptor()` |
| `ai_tool/agent_integration/models.py` | `AgentDiscoveredTool`, 三層 status |
| `ai_tool/catalog/review.py` | Human Review → adoption_status（Phase 3） |
| `ai_tool/catalog/entries/` | experimental local Tool metadata（Registry 外） |
| `ai_tool/run_agent_tool_discovery.py` | Phase 1 run 記録 |
| `ai_tool/agent_integration/trial.py` | Experimental execution trial（Phase 4） |
| `ai_tool/run_human_review.py` | Phase 3 run 記録 |
| `ai_tool/run_agent_experimental_trial.py` | Phase 4 run 記録 |

## API（読み取り専用）

```python
from ai_tool.agent_integration import discover_tools, get_tool_descriptor, apply_human_review
from ai_tool.agent_integration.hook import safe_run_agent_discovery_hook

result = discover_tools()
hook = safe_run_agent_discovery_hook()  # Phase 2 — Agent startup 用

review = apply_human_review("local:read_url_text", "approved", reason="...")  # Phase 3 — Catalog only

trial = run_experimental_trial(catalog_entries_dir=sandbox)  # Phase 4 — isolated trial
```

## Agent Core 接続（Phase 2）

起動時 `[AGENT_TOOL_DISCOVERY]` ログ（read-only）。Skip: `AI_AGENT_SKIP_TOOL_DISCOVERY=1`。

詳細: [DISCOVERY_HOOK.md](./DISCOVERY_HOOK.md) / [PHASE2_REPORT.md](./PHASE2_REPORT.md)

## Human Review（Phase 3）

Catalog `adoption_status` の人間判断記録。Registry / Agent 実行 / LLM 公開には接続しない。

詳細: [HUMAN_REVIEW.md](./HUMAN_REVIEW.md) / [PHASE3_REPORT.md](./PHASE3_REPORT.md)

## Experimental Trial（Phase 4）

`local:read_url_text` を隔離 trial で LLM 公開し、`search_web` との使い分けを検証。Registry / agent.py 本番 path は不変。

詳細: [EXPERIMENTAL_TRIAL.md](./EXPERIMENTAL_TRIAL.md) / [PHASE4_REPORT.md](./PHASE4_REPORT.md)

## Production Integration（Phase 5）

`local:read_url_text` を本番 Agent overlay で LLM 公開・実行（Registry 未登録）。無効化: `AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL=1`。

詳細: [PRODUCTION_INTEGRATION.md](./PRODUCTION_INTEGRATION.md) / [PHASE5_REPORT.md](./PHASE5_REPORT.md)

## GPU Process E2E（get_gpu_processes 正式採用後）

正式採用済み `get_gpu_processes` の Agent → Ollama → Tool → nvidia-smi → 回答経路を E2E 固定。

詳細: [GPU_PROCESS_E2E.md](./GPU_PROCESS_E2E.md)  
凍結 Run: `runs/ai_tool/20260828_170349_gpu_process_agent_e2e/`


## Run

`runs/ai_tool/20260828_155152_agent_tool_discovery/`（最新 Phase 1 run）

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [AGENT_DISCOVERY_SPEC.md](./AGENT_DISCOVERY_SPEC.md) | API・データモデル |
| [STATUS_MODEL.md](./STATUS_MODEL.md) | 三層 status + discovery_category |
| [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) | read-only 境界 |
| [TEST_MATRIX.md](./TEST_MATRIX.md) | テスト一覧 |
| [PHASE1_REPORT.md](./PHASE1_REPORT.md) | Phase 1 完了報告 |
| [DISCOVERY_HOOK.md](./DISCOVERY_HOOK.md) | Phase 2 Hook 設計 |
| [PHASE2_REPORT.md](./PHASE2_REPORT.md) | Phase 2 完了報告 |
| [HUMAN_REVIEW.md](./HUMAN_REVIEW.md) | Phase 3 Human Review 設計 |
| [PHASE3_REPORT.md](./PHASE3_REPORT.md) | Phase 3 完了報告 |
| [EXPERIMENTAL_TRIAL.md](./EXPERIMENTAL_TRIAL.md) | Phase 4 trial 設計 |
| [PHASE4_REPORT.md](./PHASE4_REPORT.md) | Phase 4 完了報告 |
| [GPU_PROCESS_E2E.md](./GPU_PROCESS_E2E.md) | get_gpu_processes Agent E2E 固定 |

## 関連

- [../project_audit/README.md](../project_audit/README.md) — 監査時点の全体像
- [../tool_creation/CATALOG.md](../tool_creation/CATALOG.md) — Catalog 三層設計
- [../tool_creation/SAFETY_BOUNDARY.md](../tool_creation/SAFETY_BOUNDARY.md) — Tool Creation 安全境界

## 禁止（Phase 1）

- LLM への experimental Tool 公開
- Tool 実行
- Registry 変更
- `agent.py` 既存 execution path 変更
