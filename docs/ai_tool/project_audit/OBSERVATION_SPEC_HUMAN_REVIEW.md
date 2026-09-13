# Observation Tool Specification — Human Review Package

**Phase:** Specification Phase 2  
**Git HEAD:** `32d7d12`  
**Status:** STOP — HUMAN REVIEW REQUIRED  
**Date:** 2026-08-28

---

## 1. 目的

Phase 1 Capability Audit の結果を基に、GPU/CPU Observation Tool の **v2 正式仕様ドラフト** を提示する。本書は **推奨仕様** であり、承認前は本番反映しない。

---

## 2. 推奨仕様（監査結果に基づく）

### get_gpu_status → **REPAIR + formalize v2**

| 項目 | 推奨 |
|------|------|
| 正式 output | v2 draft = v1 keys 維持（後方互換） |
| 実装 | **WT 実測版** を HEAD に反映（FIXED_STUB 廃止） |
| Provider | Strategy **A** — 単一 Tool + internal NVIDIA provider |
| 必須フィールド | gpu, temperature, utilization, vram_used, vram_total, ok, status, error |
| 将来 optional | gpu_count, power, clock — **NOT_IMPLEMENTED** until HR |
| 非 NVIDIA | status=unavailable — AMD/Intel provider は将来 |

**根拠:** OBSERVATION_CAPABILITY_AUDIT — WT VERIFIED REAL; HEAD FIXED_STUB drift

---

### get_gpu_processes → **KEEP v2 contract**

| 項目 | 推奨 |
|------|------|
| 正式 output | 82c40db 採用 dict 形状を v2 spec で明文化 |
| PID/name | REQUIRED — VERIFIED |
| vram_used | ENVIRONMENT_DEPENDENT — unknown 許容（PARTIAL success） |
| gpu_uuid | PROBED — **NOT_IMPLEMENTED** v2 baseline; v2.1+ additive HR |
| Agent | E2E frozen PASS — 維持 |

**根拠:** Adoption 82c40db, E2E `20260828_170349`

---

### cpu_status → **KEEP Legacy + SPLIT extension**

| 項目 | 推奨 |
|------|------|
| cpu_status | **LoadPercentage Legacy 互換維持** — output `{status}` only |
| 拡張 | **get_cpu_status** 新 Tool（別 ID）— NOT_IMPLEMENTED draft |
| temperature | **UNSUPPORTED** in get_cpu_status — cpu_temperature 分離候補 |
| ok/error 追加 | cpu_status への追加は **HR**（cross-tool gap 解消） |

**根拠:** CPU_STATUS_MIGRATION — model/cores NOT_PROVIDED ≠ defect

---

### 横断ポリシー

| 項目 | 推奨 |
|------|------|
| unknown | 文字列 `"unknown"` — 0 や推測値にしない |
| unsupported | provider 非適用（非 NVIDIA GPU 等） |
| unavailable | nvidia-smi / CIM 不在 |
| partial success | get_gpu_processes: ok=true + all vram unknown **valid** |
| Provider 戦略 | **A 優先**（単一 Tool + internal provider）; B（別 Tool per vendor）は過度複雑時のみ |

---

## 3. v2 Specification Drafts

| File | Tool | output change |
|------|------|---------------|
| `specs/get_gpu_status_v2_draft.json` | get_gpu_status | **None** (keys) — impl REPAIR |
| `specs/get_gpu_processes_v2_draft.json` | get_gpu_processes | **None** |
| `specs/cpu_status_v2_draft.json` | cpu_status | **None** |
| `specs/get_cpu_status_v2_draft.json` | get_cpu_status (new) | New tool — HR |

---

## 4. Human Review 対象（承認が必要な変更）

| # | 変更 | Breaking | 優先度 |
|---|------|----------|--------|
| HR-1 | get_gpu_status WT 実測 impl commit（STUB 除去） | Semantic fix | **HIGH** |
| HR-2 | registry visibility HEAD→WT 整合 | Agent schema | **HIGH** |
| HR-3 | get_gpu_processes gpu_uuid 追加（optional field） | Additive | MEDIUM |
| HR-4 | 新 Tool get_cpu_status Registry 登録 | New ID | MEDIUM |
| HR-5 | cpu_status ok/error 追加 | Schema change | LOW |
| HR-6 | System Prompt unknown/partial ルール | Prompt spec | MEDIUM |
| HR-7 | Pipeline active_model tool-capability policy | Config | HIGH |

---

## 5. Human Review 不要（情報のみ）

- Capability matrix 更新
- v2 draft JSON 作成
- OBSERVATION_SPEC_HUMAN_REVIEW.md（本書）
- Validator tests PASS
- Phase 1 audit 再利用

---

## 6. Agent / LLM 設計指針（spec に反映済み）

| ユーザー意図 | Tool |
|-------------|------|
| GPU温度/使用率/VRAM合計 | get_gpu_status |
| GPU使用中プロセス | get_gpu_processes |
| CPU使用率% (Legacy) | cpu_status |
| CPU model/cores | get_cpu_status（実装後） |

**Ollama native tool calling 前提 — Qwen3 固有形式なし**

---

## 7. Implementation Phase へ進む条件

Human Review で以下を **明示承認** 後:

1. ✅ get_gpu_status REPAIR（WT→HEAD）承認
2. ✅ Registry visibility 正式化方針
3. ✅ get_gpu_processes v2 KEEP（変更なし or gpu_uuid additive）
4. ✅ cpu_status KEEP + get_cpu_status 新 Tool 方針（または EXTEND 却下）
5. ⬜ System Prompt 変更範囲（任意）
6. ⬜ Pipeline model policy（任意だが推奨）

承認後の Implementation Phase:

- Spec v2 draft → approved spec
- Implementation + tests + selective commit
- Agent description 更新（HR 範囲内）
- **再 E2E**

---

## 8. STOP

```text
OBSERVED FACT: HEAD gpu_status STUB; WT measured; get_gpu_processes adopted; cpu_status minimal
PROBLEM: Registry/impl drift; partial VRAM; CPU metrics split needed
PROPOSED CHANGE: v2 specs + REPAIR + optional new get_cpu_status
COMPATIBILITY IMPACT: gpu_status REPAIR fixes false constants; additive fields low risk
HUMAN REVIEW REQUIRED: YES
```

**STOP — HUMAN REVIEW REQUIRED**

---

## 関連

- [OBSERVATION_CAPABILITY_AUDIT.md](./OBSERVATION_CAPABILITY_AUDIT.md)
- [OBSERVATION_TOOL_DESIGN.md](./OBSERVATION_TOOL_DESIGN.md)
- [../tool_creation/OBSERVATION_CAPABILITY_MATRIX.md](../tool_creation/OBSERVATION_CAPABILITY_MATRIX.md)
