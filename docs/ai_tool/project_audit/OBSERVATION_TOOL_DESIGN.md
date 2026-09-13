# Observation Tool Design — Capability Boundaries & Revision Proposals

**Phase:** Capability & Specification Revision — Phase 1  
**Status:** Design document only — **no implementation**

---

## 1. 設計原則

1. **取得できない ≠ 壊れている** — `unknown` / `not_provided` / `unsupported` を区別
2. **固定値で埋めない** — HEAD `get_gpu_status` FIXED_STUB は REPAIR 対象
3. **Tool を巨大化しない** — 責務ごとに分離を検討
4. **Description は能力境界に一致** — LLM 誤選択を防ぐ
5. **Interface 変更は Human Review** — 本 Phase では実装しない

---

## 2. Tool 責務（推奨境界）

### get_gpu_status — GPU 全体状態

**Supported Environment:** Windows/Linux + NVIDIA GPU + nvidia-smi in PATH

**Required Capability:** `--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total`

**Returns (current + candidate):**

| Field | Status | Notes |
|-------|--------|-------|
| gpu, temperature, utilization, vram_used, vram_total | CURRENT | REAL on WT |
| ok, status, error, observation_source, source | CURRENT | |
| gpu_count | CANDIDATE | probe 取得可能 — HR |
| power.draw, clocks | CANDIDATE | optional — HR |
| per-process info | **OUT_OF_SCOPE** | use get_gpu_processes |

**Degraded:** nvidia-smi なし → `status=unavailable`, fields `unknown`

**Unsupported:** AMD/Intel-only GPU without nvidia-smi

---

### get_gpu_processes — GPU 使用中プロセス

**Supported Environment:** NVIDIA + nvidia-smi compute-apps query

**Required Capability:** process pid + process_name

**Optional Capability:** per-process VRAM, gpu index/uuid

**Returns:**

| Field | Status | Notes |
|-------|--------|-------|
| processes[].pid, name | CURRENT | REAL |
| processes[].vram_used | CURRENT | PARTIAL — often unknown |
| gpu_id / gpu_uuid | CANDIDATE | nvidia-smi raw に存在 — HR for schema |
| empty processes | CURRENT | valid (no compute apps) |

**Degraded (this host):** process list REAL, VRAM all unknown — **Tool は partial success として返す（現行どおり）**

**VRAM unknown 調査メモ (UNKNOWN root cause):**

- OBSERVED: nvidia-smi `used_gpu_memory=[N/A]` for WDDM graphics processes
- OBSERVED: `[Insufficient Permissions]` process names coexist
- UNKNOWN: driver policy / elevation / compute vs graphics context

---

### cpu_status — CPU LoadPercentage（現行）

**Supported Environment:** Windows + PowerShell + CIM Win32_Processor

**Current scope:** `{status: "<LoadPercentage>"}` or `{status: "error"}`

**NOT in scope (NOT_PROVIDED, not defects):** model, cores, threads, temperature

---

### get_cpu_status — 分離候補（新 Tool、未実装）

**Purpose:** CPU 一般メトリクス（model, cores, threads, utilization, clock）

**Rationale:** `cpu_status` の `status` キー意味（LoadPercentage）を変更せず拡張するより、新 Tool で明確化

**Probe evidence:** CIM で Name/cores/threads/clock **取得可能** on audit host

**Human Review:** 新 Tool ID、Registry、Agent schema

---

### cpu_temperature — 分離候補（ハードウェア依存、未実装）

**Purpose:** CPU 温度（ベンダー/センサー API 依存）

**Probe:** CIM Win32_Processor だけでは **UNSUPPORTED**

**Rationale:** 一般 CPU metrics Tool に温度を混ぜない

---

## 3. Tool ごと最終提案

| Tool | Proposal | Rationale |
|------|----------|-----------|
| get_gpu_status | **REPAIR** | HEAD=STUB, WT/spec=real — commit WT |
| get_gpu_processes | **KEEP** | REAL pid/name; PARTIAL vram documented |
| cpu_status | **KEEP** (minimal) + **EXTEND** or **SPLIT** | LoadPercentage valid; richer metrics via new tool |

---

## 4. STOP — Interface 変更候補

### A. get_gpu_status REPAIR (commit WT)

- **Change:** HEAD fixed → nvidia-smi measured
- **Breaking:** HEAD consumers got fake constants — **semantic breaking fix**
- **HR:** REQUIRED

### B. get_gpu_processes — add gpu_uuid

- **Change:** new optional field per process
- **Breaking:** additive — lower risk
- **HR:** REQUIRED

### C. cpu_status → get_cpu_status split

- **Change:** new tool, cpu_status unchanged
- **Breaking:** none if split
- **HR:** REQUIRED for new tool

### D. Unified ok/status/error on cpu_status

- **Change:** output schema
- **Breaking:** yes
- **HR:** REQUIRED

---

## 5. System Prompt 変更候補（実装せず）

- unknown を数値推測しない
- Tool が返さないフィールドを捏造しない
- partial observation（vram unknown）を失敗と混同しない
- get_gpu_status vs get_gpu_processes 使い分け

---

## 6. 次 Phase 候補

1. **Human Review** — HEAD/Wt gpu_status + registry visibility
2. **Specification Phase 2** — approved fields only
3. **Implementation Phase** — post-HR
4. **Agent description tuning** — post-spec
