# Observation Capability Audit

**Phase:** Capability & Specification Revision — Phase 1  
**Git HEAD:** `32d7d12`  
**Status:** COMPLETE — STOP (Human Review Required for changes)  
**Run:** `runs/ai_tool/20260828_172810_observation_capability_audit/`

---

## 1. 目的

GPU/CPU Observation Tool について、**取得可能範囲（能力境界）** を調査し、Specification 設計の基礎を作る。

本 Phase では production Tool / Registry / Agent / System Prompt **変更なし**。

---

## 2. Git 状態

| 項目 | 値 |
|------|-----|
| HEAD | `32d7d12` |
| branch | `master` |
| agent.py | diff なし |
| get_gpu_processes.py | committed (82c40db), WT diff なし |
| **get_gpu_status.py** | **M** — HEAD: FIXED_STUB / WT: nvidia-smi 実測 |
| **registry/tools.json** | **M** — HEAD: get_gpu_processes only agent-visible / WT: 7 tools |

**Working Tree を正式版と判断しない。**

---

## 3. 実機 Capability Probe 結果（要約）

### GPU (NVIDIA GeForce RTX 3060, driver 591.86)

| Probe | 結果 |
|-------|------|
| nvidia-smi | 利用可能 |
| GPU count | 1 |
| temperature / util / VRAM | 取得可能 |
| process list | 33 processes |
| per-process VRAM (raw) | **全件 `[N/A]`** |
| gpu_uuid (raw, probe only) | 取得可能 — **Tool 未出力** |
| power / clock (probe only) | 取得可能 — **Tool 未出力** |

### CPU (12th Gen i5-12400, Windows)

| Probe | Tool 現状 | CIM で取得可能 |
|-------|----------|---------------|
| LoadPercentage | ✅ `{status}` | ✅ |
| Name / cores / threads | ❌ | ✅ |
| Clock speeds | ❌ | ✅ |
| Temperature | ❌ | ❌ (CIM のみでは不可) |

---

## 4. Tool 別サマリ

### get_gpu_status

| 項目 | 判定 |
|------|------|
| WT 実装 | **REAL** — nvidia-smi 実測、独立観測と整合 |
| HEAD 実装 | **FIXED / STUB** — 固定 RTX 3060 値 |
| 正式採用 | **Human Review 必要** — HEAD vs WT どちらを production とするか |
| 推奨 | **REPAIR** — WT 実測版を HEAD に反映（commit 判断は人間） |

### get_gpu_processes

| 項目 | 判定 |
|------|------|
| PID / name | **REAL** |
| VRAM per process | **PARTIAL** — ソース時点 `[N/A]` → `"unknown"` |
| GPU ID | **NOT_PROVIDED** |
| 0 変換 | **なし** |
| 推奨 | **KEEP** — 能力境界を spec に明文化。VRAM 改善は別 Phase |

### cpu_status

| 項目 | 判定 |
|------|------|
| 現仕様 | LoadPercentage を `status` 文字列で返す **最小 Legacy Tool** |
| model/cores/temp | **NOT_PROVIDED**（仕様違反ではない） |
| CIM 拡張可能性 | Name/cores/threads/clock — **probe REAL** |
| 推奨 | **EXTEND** または **SPLIT** (`get_cpu_status`) — **Human Review 必須**

---

## 5. Observation Status 候補（実装せず文書のみ）

```text
tool_status: available | unavailable | error
observation_status: complete | partial | empty
field_value: <measured> | unknown | not_provided | unsupported
```

例: `tool_status=available`, `observation_status=partial`, `vram_used=unknown`

---

## 6. LLM Tool Selection リスク

| Tool | 使う | 使わない |
|------|------|---------|
| get_gpu_status | GPU 全体（model, temp, util, VRAM 合計） | プロセス一覧 |
| get_gpu_processes | GPU 使用中プロセス（pid, name） | GPU 全体メトリクス |
| cpu_status | CPU LoadPercentage（現仕様） | GPU、詳細 CPU spec |

Registry description を広げすぎると誤選択リスク — **description は能力境界に合わせて限定**（変更は HR）。

---

## 7. Human Review Required

1. **get_gpu_status** HEAD FIXED_STUB → WT 実測の正式化
2. **Registry** HEAD vs WT visibility drift
3. **cpu_status** 拡張 vs 新 Tool `get_cpu_status` 分離
4. **get_gpu_processes** gpu_uuid 追加（output schema 変更）
5. **Cross-tool** ok/status/error 統一（interface 変更）

---

## 関連

- [OBSERVATION_TOOL_DESIGN.md](./OBSERVATION_TOOL_DESIGN.md)
- [../tool_creation/OBSERVATION_CAPABILITY_MATRIX.md](../tool_creation/OBSERVATION_CAPABILITY_MATRIX.md)
