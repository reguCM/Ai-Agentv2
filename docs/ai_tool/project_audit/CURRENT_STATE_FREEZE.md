# Current State Freeze — Development Re-entry Baseline

**Freeze date:** 2026-08-28  
**HEAD:** `9612259` — `ai-agent: implement current-environment observation tools`  
**Branch:** `master`  
**Purpose:** Observation / Agent Integration 調査の区切り。以降は通常開発へ戻る。

> Source of truth = **HEAD のコード・Registry・実行経路**。過去 Phase 報告は参考のみ。

---

## 正式採用 Tool（Registry `visibility=agent`）

| Tool | Module | 役割 |
|------|--------|------|
| `get_gpu_status` | `tools.system.gpu.gpu_status` | NVIDIA + nvidia-smi GPU デバイス状態 |
| `get_gpu_processes` | `tools.system.gpu.gpu_processes` | GPU 使用中プロセス（82c40db 契約） |
| `cpu_status` | `tools.system.cpu.cpu_status` | Legacy LoadPercentage → `{status}` |
| `get_cpu_status` | `tools.system.cpu.get_cpu_status` | Windows CIM 構造化 CPU メトリクス |

すべて `observation_source: real`（Registry 記載）。

---

## Experimental Tool（Registry 未登録）

| Tool | 経路 | 無効化 |
|------|------|--------|
| `read_url_text` | `ai_tool/agent_integration/production_bridge.py` overlay | `AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL=1` |

commit `88febb3` で Agent overlay 統合済み。Catalog ID: `local:read_url_text`。

---

## Agent ↔ Ollama Tool Calling 経路

```text
User → agent.py → create_ollama_tools(registry)
  → append_experimental_agent_tools (read_url_text)
  → chat(tools=...) → tool_calls
  → execute_tool() → registry import / experimental bridge
  → {role:tool, content: json} → LLM final answer
```

- Qwen / DeepSeek 専用 parser **なし**（Ollama native `tool_calls`）
- 起動時 `[AGENT_TOOL_CALLING_CAPABILITY]` 診断（`tools/system/llm_tool_capability.py`）
- Tool Calling は **LLM model 依存**（例: deepseek-coder-v2:16b → 400 unsupported; qwen3_8b → OK）

---

## Observation 契約（HEAD 実装）

### get_gpu_status
- 実測: gpu, temperature, utilization, vram_used, vram_total
- 失敗: unknown / unavailable — **固定値 Stub なし**

### get_gpu_processes
- 実測: pid, name, processes[]
- per-process VRAM: 環境依存 → **`unknown` 許容**（0 変換禁止）

### cpu_status
- Legacy: `{status: LoadPercentage string}` のみ — **変更禁止**

### get_cpu_status
- 実測: model, physical_cores, logical_processors, load_percentage, max/current_clock_mhz, architecture
- **temperature: UNSUPPORTED**（フィールドなし）

### セマンティクス（System Prompt + 実装）
- observed / unknown / unsupported / unavailable — unknown を推測で埋めない

---

## Environment（監査ホストで確認済みのみ）

| 項目 | 状態 |
|------|------|
| Windows + PowerShell/CIM | VERIFIED |
| NVIDIA GPU + nvidia-smi | VERIFIED |
| Ollama + tool-capable LLM | VERIFIED (model-dependent) |
| Linux / AMD / Intel GPU / 複数 GPU | **UNKNOWN**（未検証・未対応） |
| CPU temperature | **UNSUPPORTED** |

---

## Safety Boundary（現状維持）

| 境界 | 状態 |
|------|------|
| `agent_tool_gate` | デフォルト人間確認（`registry/agent_tool_trust.json`） |
| Observation Tools | ローカル subprocess のみ、network write なし |
| `read_url_text` | experimental — SSRF 境界は catalog + bridge 側 |
| `capability_route_obs` | 観測のみ — 実行許可には接続しない |

---

## Known Limitations

1. **System Prompt vs Ollama schema:** Prompt は `search_web` / `list_files` 等に言及するが、Registry `visibility=agent` には Observation 4 Tool のみ。Web/Workspace Tool は **未公開**（read_url_text のみ experimental overlay）。
2. **per-process VRAM:** 監査ホストで全件 `unknown`（nvidia-smi raw `[N/A]`）。
3. **Active pipeline model:** tool calling 非対応モデルでは Agent E2E live が失敗（supplementary model で検証済み）。
4. **WT unrelated changes:** research / cognitive state / 監査ドラフト等が unstaged/untracked に残存。

---

## UNKNOWN（意図的に未断定）

- Linux / 非 NVIDIA GPU での Observation Tool 動作
- gpu_uuid 追加（HR-3 deferred）
- cpu_status と get_cpu_status の cross-tool ok/error 形状統一
- Registry への search_web / workspace tools 正式登録タイミング

---

## 検証（Freeze Run）

**Run:** `runs/ai_tool/<timestamp>_current_state_freeze/`  
**Script:** `scripts/run_current_state_freeze.py`

Freeze 時点テスト（67 passed）:
- Observation E2E deterministic
- GPU process E2E deterministic
- production_bridge
- get_cpu_status / gpu_real_observation / llm_tool_capability
- observation spec v2 draft validator

---

## 次の開発 Phase

監査 Phase を自動継続**しない**。

新機能・拡張は要求発生時に:

`Specification → Validation → Implementation → Test → Safety → Agent integration → E2E → HR（仕様変更時のみ） → selective commit`

**HR が必要:** 仕様変更 / Interface 変更 / Safety 境界変更 / 正式採用判断  
**HR 不要:** 既存契約内のバグ修正・テスト追加・実装改善

---

## 関連コミット（ai-agent 系列）

| Commit | 内容 |
|--------|------|
| `9612259` | Observation Tool Implementation Phase 1 |
| `32d7d12` | GPU process Agent E2E freeze |
| `82c40db` | get_gpu_processes 正式採用 |
| `88febb3` | read_url_text experimental overlay |

**FREEZE COMPLETE — 通常開発へ re-entry 可能**
