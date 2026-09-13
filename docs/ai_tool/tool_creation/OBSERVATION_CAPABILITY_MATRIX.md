# Observation Capability Matrix (Updated — Spec Phase 2)

**Evidence tiers:** VERIFIED | PROBED | IMPLEMENTED | NOT_IMPLEMENTED | ENVIRONMENT_DEPENDENT | UNKNOWN

> **VERIFIED** = audit host independent observation matched Tool output  
> **PROBED** = isolated probe retrieved value; Tool does not output it  
> **IMPLEMENTED** = in committed or WT production code path  
> **NOT_IMPLEMENTED** = spec candidate only  
> **ENVIRONMENT_DEPENDENT** = varies by OS/driver/permissions  
> **UNKNOWN** = root cause or general availability undetermined

**Audit host:** Windows 10, NVIDIA RTX 3060, driver 591.86, Intel i5-12400  
**Run:** `runs/ai_tool/20260828_172810_observation_capability_audit/`

---

## get_gpu_status

| Field | Tier | Tool output | Independent | Notes |
|-------|------|-------------|-------------|-------|
| gpu (model) | VERIFIED / IMPLEMENTED (WT) | REAL | nvidia-smi name match | HEAD=FIXED_STUB |
| temperature | VERIFIED / IMPLEMENTED (WT) | REAL | nvidia-smi | snapshot drift |
| utilization | VERIFIED / IMPLEMENTED (WT) | REAL | nvidia-smi | ±15% between sequential queries |
| vram_used | VERIFIED / IMPLEMENTED (WT) | REAL | nvidia-smi | |
| vram_total | VERIFIED / IMPLEMENTED (WT) | REAL | nvidia-smi | |
| ok/status/error | IMPLEMENTED (WT) | REAL | derived | |
| gpu_count | PROBED | NOT_IMPLEMENTED | nvidia-smi count=1 | v2.1+ candidate |
| power / clock | PROBED | NOT_IMPLEMENTED | nvidia-smi | optional future |
| gpu_uuid | PROBED | NOT_IMPLEMENTED | nvidia-smi | optional future |

---

## get_gpu_processes

| Field | Tier | Tool output | Independent | Notes |
|-------|------|-------------|-------------|-------|
| pid | VERIFIED / IMPLEMENTED | REAL | pid set match 1.0 | adopted 82c40db |
| name | VERIFIED / IMPLEMENTED | REAL | nvidia-smi | incl. [Insufficient Permissions] |
| vram_used | ENVIRONMENT_DEPENDENT | PARTIAL | all [N/A] raw | → unknown, not 0 |
| gpu_uuid | PROBED | NOT_IMPLEMENTED | in raw nvidia-smi | HR for schema add |
| gpu_index | UNKNOWN | NOT_IMPLEMENTED | — | |

---

## cpu_status (Legacy)

| Field | Tier | Tool output | Independent | Notes |
|-------|------|-------------|-------------|-------|
| status (LoadPercentage) | VERIFIED / IMPLEMENTED | REAL | CIM LoadPercentage | key name legacy |
| model | PROBED | NOT_IMPLEMENTED | CIM Name available | use get_cpu_status draft |
| physical_cores | PROBED | NOT_IMPLEMENTED | CIM 6 | |
| logical_processors | PROBED | NOT_IMPLEMENTED | CIM 12 | |
| clock | PROBED | NOT_IMPLEMENTED | CIM 2500 MHz | |
| temperature | UNSUPPORTED | NOT_IMPLEMENTED | CIM path N/A | separate tool candidate |
| ok/error keys | NOT_IMPLEMENTED | NOT_PROVIDED | — | cross-tool gap |

---

## get_cpu_status (draft — NOT_IMPLEMENTED)

| Field | Tier | Evidence | Status |
|-------|------|----------|--------|
| All structured fields | PROBED | CIM probe on audit host | Spec only — HR before impl |

---

## Cross-tool OBSERVED GAPs (document only)

| Gap | Tools affected |
|-----|----------------|
| ok/status/error pattern | cpu_status lacks ok/error |
| observation_source in output | cpu_status registry only |
| unknown string semantics | cpu_status uses status=error instead |

**統一は Human Review 後の Implementation Phase**
