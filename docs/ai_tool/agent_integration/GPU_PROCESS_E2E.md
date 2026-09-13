# GPU Process Agent E2E Validation

**状態:** Phase 4 COMPLETE — 回帰検証固定済み  
**正式採用:** `get_gpu_processes` — Human Review `ADOPT_WORKING_TREE`（commit `82c40db`）  
**凍結 Run（参照）:** `runs/ai_tool/20260828_170349_gpu_process_agent_e2e/`

---

## 1. 目的

正式採用済み `get_gpu_processes` について、Agent 実運用経路が以下を満たすことを記録・固定する。

```text
User Request
  → Agent Tool Schema
  → Ollama (tool-capable model)
  → get_gpu_processes
  → nvidia-smi
  → 実測結果
  → Ollama
  → 最終回答
```

本 Phase は **Tool の性能向上や interface 変更ではない**。E2E 検証の固定と回帰基準の確立が目的。

---

## 2. Agent → LLM → Tool → 実測 → LLM の経路

| 段階 | 実装 |
|------|------|
| Tool Schema 公開 | `registry/tools.json` (`visibility=agent`) + `build_production_agent_tools()` |
| LLM への schema 渡し | `ollama_tools_for_llm()` |
| Tool 選択・実行 | `run_e2e_scenario()` → `execute_registry_tool()` |
| 実測 | `tools.system.gpu.gpu_processes.get_gpu_processes()` → `nvidia_smi.query_gpu_processes()` |
| 結果返却 | `role=tool` message として LLM に JSON 返却 |
| 最終回答 | LLM が Tool 結果を解釈して自然言語応答 |

**コード（E2E harness）:**

- `ai_tool/agent_integration/gpu_process_e2e.py`
- `ai_tool/agent_integration/gpu_process_e2e_scenarios.py`
- `ai_tool/run_gpu_process_agent_e2e.py`

---

## 3. Deterministic Test

Mock LLM による Agent bridge 検証（実 LLM 不使用）。

| Case | ユーザー意図 | Expected Tool |
|------|-------------|---------------|
| 1 | GPUプロセス確認 | `get_gpu_processes` |
| 2 | プロセスVRAM | `get_gpu_processes` |
| 3 | CPU状態 | `cpu_status`（`get_gpu_processes` 不可） |
| 4 | GPU全体状態 | `get_gpu_status` |
| 5 | Web検索 | `search_web` |

各ケースで **selected → executed → result returned** を確認。

```bash
python -m pytest tests/ai_tool/agent_integration/test_gpu_process_agent_e2e_deterministic.py -q
```

**Phase 3/4 結果:** 9/9 PASS（5 routing + schema/state/regression/observation tests）

---

## 4. Live LLM Test

Ollama 実 LLM による Tool 選択・実行・結果利用検証。

| Scenario | Prompt 要約 | Expected Tool |
|----------|------------|---------------|
| A | GPUプロセス確認 | `get_gpu_processes` |
| B | プロセス+VRAM | `get_gpu_processes` |
| C | GPU全体（温度・使用率） | `get_gpu_status` |
| D | VRAM多いプロセス説明 | `get_gpu_processes` |

### 使用モデル

| 用途 | Model | 結果 |
|------|-------|------|
| Pipeline active (`config/pipeline.yaml`) | `deepseek-coder-v2:16b` | **Tool calling 非対応**（400） |
| Live E2E 検証 | `qwen3:8b` (`qwen3_8b` profile) | **4/4 PASS** |

tool calling 非対応モデルを無理に Live E2E に使用しない。Run 記録に両モデルの結果を残す。

---

## 5. Independent nvidia-smi comparison

同一 Run 内で Tool 結果と独立 `nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory` を比較。

**凍結 Run（20260828_170349）記録:**

| 項目 | 値 |
|------|-----|
| tool_process_count | 34 |
| independent_pid_count | 34 |
| common_pid_count | 34 |
| pid_match_rate | **1.0** |
| tool_vram_unknown_count | 34 |

PID / process name は一致。process count は環境依存（瞬間変化あり）。

---

## 6. REAL / PARTIAL の意味

### REAL（確認済み）

- `processes[]` プロセス一覧
- 各エントリの `pid`（整数）
- 各エントリの `name`（文字列）
- `observation_source: "real"`
- `source: "nvidia-smi"`

### PARTIAL（制限付き）

- 各プロセスの `vram_used`
  - 整数: 実測値（MiB 等、query 結果に依存）
  - `"unknown"`: 取得不能（**0 ではない**）

「完全に正しい GPU 情報取得」とは表現しない。現在確認できた範囲のみ REAL とする。

---

## 7. VRAM unknown の扱い

`vram_used == "unknown"` の場合:

- **0 と解釈しない**
- **数値を推測しない**
- **LLM に数値を生成させない**（system prompt + Live 結果で確認）
- 回答では「取得不可 / unknown」として扱う

VRAM unknown は **テスト失敗扱いにしない**。独立観測でも unknown count を記録するのみ。

---

## 8. Safety

**凍結 Run 記録:**

| 項目 | 値 |
|------|-----|
| unsafe_accept | 0 |
| unexpected_network | 0 |
| unexpected_write | 0 |
| schema_regression | false |
| tool_execution_count | 9 |

`get_gpu_processes` はローカル GPU 観測 Tool。E2E 実行で不要なネットワークアクセスは発生しない。

---

## 9. Regression

以下 production Tool の schema / Tool ID が E2E 前後で変化しないことを確認:

- `get_gpu_status`
- `cpu_status`
- `read_file`
- `search_web`
- `get_gpu_processes`

`production_schema_snapshot()` による pytest 回帰テストあり。

---

## 10. Known Limitations

### Pipeline model と Tool Calling（UNKNOWN / POLICY QUESTION）

`config/pipeline.yaml` の `active_model: deepseek_coder_v2_16b` は Ollama tool calling API 非対応。

> Pipeline の active model と Agent Tool Calling capability の整合性をどこで保証するか。

候補（今回は決定しない）:

- startup validation
- configuration validation
- Tool Calling capability metadata
- human review

### Per-process VRAM（次 Phase 調査対象）

現環境では全プロセス `vram_used == "unknown"` が観測される。

調査候補:

- `nvidia-smi --query-compute-apps`
- NVIDIA driver / permissions
- process visibility / Windows privilege
- compute process vs graphics process
- PID と VRAM usage の対応方法

**interface 変更は別 Phase:** Human Review → Specification Change → Test → Adoption

---

## 11. 再実行方法

### 全 E2E（deterministic pytest + live + observation + safety）

```bash
python ai_tool/run_gpu_process_agent_e2e.py
```

成果物: `runs/ai_tool/<timestamp>_gpu_process_agent_e2e/`

### Deterministic のみ

```bash
python -m pytest tests/ai_tool/agent_integration/test_gpu_process_agent_e2e_deterministic.py -q
```

### 前提

- Ollama 起動済み
- `nvidia-smi` 利用可能（observation テスト用）
- Live LLM には tool-capable model（例: `qwen3:8b`）— run script が active model 非対応時に `qwen3_8b` で補完

---

## 関連

- [GET_GPU_PROCESSES_MIGRATION.md](../tool_creation/GET_GPU_PROCESSES_MIGRATION.md)
- [README.md](./README.md)
