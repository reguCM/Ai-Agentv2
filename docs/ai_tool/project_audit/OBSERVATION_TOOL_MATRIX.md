# Observation Tool Capability Matrix

**Phase:** Agent Observation / Tool Calling Cross Audit — Phase 1  
**Git HEAD:** `32d7d12`  
**監査時刻スナップショット:** 2026-08-28（ローカル WT 実行）

> **NOT_PROVIDED ≠ BUG** — 仕様外項目は欠陥と断定しない。

---

## 凡例

| Observation | 意味 |
|-------------|------|
| REAL | 実測値として確認 |
| PARTIAL | 制限付き（unknown 等） |
| NOT_PROVIDED | 現行仕様スコープ外 |
| UNAVAILABLE | 環境要因で取得不能 |

---

## get_gpu_status

| Field | Source | Observation | Contract (migration spec) | Agent (WT) | E2E |
|-------|--------|-------------|---------------------------|------------|-----|
| gpu | nvidia-smi name | REAL | string / unknown | schema exposed | live_c PASS |
| temperature | nvidia-smi temperature.gpu | REAL | number / unknown | exposed | live_c PASS |
| utilization | nvidia-smi utilization.gpu | REAL | number / unknown | exposed | live_c PASS |
| vram_used | nvidia-smi memory.used | REAL | int MiB / unknown | exposed | live_c PASS |
| vram_total | nvidia-smi memory.total | REAL | int MiB / unknown | exposed | live_c PASS |
| ok | derived | REAL | boolean | in result JSON | det_case4 |
| status | derived | REAL | ok/unavailable/error | in result | det_case4 |
| error | derived | REAL | string/null | in result | det_case4 |
| observation_source | config label | REAL | `"real"` | not in LLM schema | n/a |
| source | nvidia-smi/none | REAL | string | in result | n/a |
| multi_gpu_index | — | NOT_PROVIDED | OUT_OF_SCOPE (GPU 0 only) | n/a | n/a |

### HEAD vs WT 実装

| 層 | 観測 |
|----|------|
| HEAD `gpu_status.py` | **固定値** RTX 3060 / 60°C / 50% / 6000/12288 — REAL ではない |
| WT `gpu_status.py` | `nvidia_smi.query_gpu_status()` — REAL |
| HEAD registry | visibility **なし** — Agent schema **非公開** |
| WT registry | visibility=agent — **公開** |

---

## get_gpu_processes

| Field | Source | Observation | Contract | Agent | E2E |
|-------|--------|-------------|----------|-------|-----|
| processes[].pid | nvidia-smi compute-apps pid | REAL | integer | exposed (HEAD+WT) | pid_match 1.0 |
| processes[].name | nvidia-smi process_name | REAL | string | exposed | PASS |
| processes[].vram_used | nvidia-smi used_gpu_memory | **PARTIAL** | int or `"unknown"` | exposed | 34/34 unknown @ frozen run |
| processes | list | REAL | array (empty=none or error) | exposed | PASS |
| ok / status / error | derived | REAL | per spec | in result | PASS |
| observation_source | label | REAL | `"real"` | n/a | PASS |
| gpu_id | — | NOT_PROVIDED | OUT_OF_SCOPE | n/a | n/a |

### VRAM unknown 扱い（確定）

- `_safe_int` が `[N/A]` 等を `"unknown"` に変換 — **0 にしない**
- E2E Live LLM: 数値捏造 **なし**（「取得不可」報告）
- **テスト失敗扱いにしない**

### 正式採用

- commit `82c40db` — ADOPT_WORKING_TREE
- E2E frozen: `runs/ai_tool/20260828_170349_gpu_process_agent_e2e`

---

## cpu_status

| Field | Source | Observation | Contract | Agent (WT) | E2E |
|-------|--------|-------------|----------|------------|-----|
| status | CIM Win32_Processor LoadPercentage | REAL | string digit | exposed WT | det_case3 PASS |
| model | — | NOT_PROVIDED | OUT_OF_SCOPE | n/a | n/a |
| cores | — | NOT_PROVIDED | OUT_OF_SCOPE | n/a | n/a |
| threads | — | NOT_PROVIDED | OUT_OF_SCOPE | n/a | n/a |
| temperature | — | NOT_PROVIDED | OUT_OF_SCOPE | n/a | n/a |
| observation_source | — | NOT_PROVIDED | registry metadata only | n/a | n/a |
| ok / error | — | NOT_PROVIDED | error 時 `{status:'error'}` のみ | n/a | n/a |

### Registry description

「個別メトリクスの取得可否は**未確認**」— LoadPercentage のみ実装と **hedge 付き整合**

---

## Independent nvidia-smi Comparison（get_gpu_processes）

| 項目 | 凍結 E2E Run |
|------|-------------|
| tool_process_count | 34 |
| independent_pid_count | 34 |
| pid_match_rate | 1.0 |
| tool_vram_unknown_count | 34 |

---

## Safety（観測 Tool）

| Tool | Network | Write | 根拠 |
|------|---------|-------|------|
| get_gpu_status | なし | なし | subprocess nvidia-smi local |
| get_gpu_processes | なし | なし | subprocess nvidia-smi local |
| cpu_status | なし | なし | local PowerShell CIM |

---

## 次 Phase 調査（修正は別 Phase）

Per-process VRAM unknown:

- nvidia-smi query field / driver / permissions
- Windows privilege / Insufficient Permissions entries
- compute vs graphics process distinction

**interface 変更は Human Review → Spec Change → Adoption**
