# get_gpu_processes — Legacy → Current Tool Migration Phase 1

**日付:** 2026-08-28  
**Legacy Audit:** REPAIR  
**実装変更:** なし  
**Registry 変更:** なし  
**Agent 変更:** なし

---

## 1. Git 状態（作業開始時）

| 項目 | 値 |
|------|-----|
| branch | `master` |
| HEAD | `88febb3` |
| `gpu_processes.py` | **未コミット diff あり**（HEAD は固定 ollama/python list；working tree は nvidia-smi 実測 dict） |
| `registry/tools.json` | 未コミット diff あり（本 Phase 未変更） |
| `agent.py` | diff なし |

**本 Phase の baseline:** working tree 上の `gpu_processes.py`（実測 dict 返却）。

---

## 2. 現行目的

```text
registry/tools.json (get_gpu_processes, visibility=agent)
  → agent.py execute_tool
  → tools.system.gpu.gpu_processes.get_gpu_processes()
  → tools.system.gpu.nvidia_smi.query_gpu_processes()
  → nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory
```

**Current purpose:** nvidia-smi から GPU 使用中プロセス一覧を実測し、構造化 dict で返す。固定 ollama/python リストは返さない。

---

## 3. 成果物

| パス | 内容 |
|------|------|
| `specs/get_gpu_processes_legacy_migrated.json` | 現行契約（validator **ACCEPT**） |
| `GET_GPU_PROCESSES_MIGRATION.md` | 本ドキュメント |
| `tests/ai_tool/tool_creation/test_get_gpu_processes_migration.py` | 契約テスト 11 + 既存回帰 1 |
| `ai_tool/run_get_gpu_processes_migration.py` | 隔離 Run |
| `runs/ai_tool/20260828_163325_get_gpu_processes_migration/` | comparison / catalog_draft / evaluation |

---

## 4. Input

| 項目 | 値 |
|------|-----|
| 引数 | なし |
| input_schema | `{}` |

---

## 5. Output（現行固定）

### Top-level（6 keys）

| field | type | meaning | source |
|-------|------|---------|--------|
| processes | array | プロセス一覧 | nvidia-smi compute-apps |
| ok | boolean | 観測成否 | derived |
| status | string | ok / unavailable / error | derived |
| error | string\|null | 失敗コード | derived |
| observation_source | `"real"` | 固定ラベル | config |
| source | string | nvidia-smi / none | derived |

### processes[] item（3 keys）

| field | type | meaning | observation |
|-------|------|---------|-------------|
| pid | int \| `"unknown"` | プロセス ID | REAL |
| name | string | process_name | REAL |
| vram_used | int \| `"unknown"` | used_gpu_memory (MiB) | **PARTIAL** — [N/A] 時 unknown |

### NOT PROVIDED

| field | status |
|-------|--------|
| gpu_id | NOT_PROVIDED |
| process_count (独立キー) | NOT_PROVIDED |

---

## 6. UNKNOWN セマンティクス

| 条件 | 動作 |
|------|------|
| used_gpu_memory = `[N/A]` | `vram_used` = `"unknown"`（0 にしない） |
| nvidia-smi 不在 | `processes=[]`, `ok=false`, `status=unavailable` |
| 空 rows + ok | `processes=[]`, `ok=true`（プロセスなし） |
| name = `[Insufficient Permissions]` | その文字列を name として返す（推測置換しない） |

---

## 7. Observation Validity

| 観測対象 | 分類 |
|---------|------|
| process pid | REAL |
| process name | REAL |
| VRAM per-process | **PARTIAL**（unknown 多い） |
| GPU identifier | NOT_PROVIDED |

---

## 8. 独立観測（Run 20260828_163325）

同一 Run 内で Tool と独立 nvidia-smi compute-apps を順次比較。**overall: PASS**

| 指標 | 値 |
|------|-----|
| tool process count | 33 |
| independent process count | 33 |
| pid match rate | 1.0 |
| VRAM unknown (tool / indep) | 33 / 33 |

---

## 9. Contract

`docs/ai_tool/tool_creation/TOOL_CONTRACT.md` を参照。Spec 内 `contract` ブロックに集約（独立 YAML 不要）。

**must_not 要点:** 固定 ollama/python フォールバック禁止、VRAM `[N/A]` を 0/推定値に変換しない。

---

## 10. Test Contract

| カテゴリ | 状態 |
|---------|------|
| Normal | COVERED |
| Boundary (empty list) | COVERED |
| Invalid | NOT_APPLICABLE |
| Failure | COVERED |
| Safety | COVERED |
| UNKNOWN (VRAM NA) | COVERED |

---

## 11. Safety

| 項目 | 値 |
|------|-----|
| read-only subprocess | nvidia-smi query |
| network | false |
| filesystem write | false |
| side_effect | read_only（spec 記録） |
| gate | risk=low, visibility=agent |

`SAFETY_BOUNDARY.md` 参照。境界変更なし。

---

## 12. Registry / Compatibility

**Registry: PARTIAL_MATCH** — name/module/function/visibility/observation_source/input 一致。output schema は Spec が補完。

**Compatibility: COMPATIBLE_DOCUMENTATION_ONLY**

| 項目 | 結果 |
|------|------|
| Tool ID / Input | UNCHANGED |
| Output keys (working tree) | UNCHANGED |
| Output meaning | UNCHANGED（文書化） |
| Error semantics | UNCHANGED |
| Agent | UNCHANGED |

**注意:** HEAD コミット版は **list 返却 + 固定値** — working tree との差は Git 状態として記録。本 Phase では実装変更なし。

---

## 13. REPAIR 分解

| 分類 | 必要 | 本 Phase |
|------|------|---------|
| Documentation | ✅ | ✅ |
| Specification | ✅ | ✅ |
| Test | ✅ | ✅ |
| Implementation | ❌ | 変更なし |
| Safety | ❌ | 記録のみ |
| Interface | ❌ | output 追加なし |

---

## 14. 最終報告

```text
Tool: get_gpu_processes
Legacy status: REPAIR

Observation validity: REAL (process list); PARTIAL (VRAM per-process)

Independent observation: PASS / PARTIAL (pid set; VRAM often unknown)

Specification: PASS

Contract: PASS (spec contract block + TOOL_CONTRACT.md ref)

Tests:
  Normal: COVERED
  Boundary: COVERED
  Invalid: NOT_APPLICABLE
  Failure: COVERED
  Safety: COVERED

Registry: PARTIAL_MATCH
Agent: UNCHANGED
Compatibility: COMPATIBLE_DOCUMENTATION_ONLY

UNKNOWN:
  - VRAM per-process when nvidia-smi returns [N/A]
  - GPU id per process (not queried)
  - HEAD vs working tree return shape (list vs dict)

Recommended action: REPAIR → toward KEEP after Catalog + live regression

Human Review: NOT_REQUIRED (this phase)

Production code changed: NO
Registry changed: NO
Agent changed: NO
STOP: NO
```

---

## 15. Formal Adoption（Phase 1 — ADOPT_WORKING_TREE）

**Human Decision:** `ADOPT_WORKING_TREE`（Review Run: `runs/ai_tool/20260828_164546_get_gpu_processes_human_review/`）

| 項目 | 値 |
|------|-----|
| Previous HEAD | `88febb3` |
| Adopted implementation | Working Tree measured nvidia-smi（dict 返却） |
| Interface | **list → dict**（Human Review 承認済み Breaking Change — 完全互換ではない） |
| Observation | REAL process list / PARTIAL per-process VRAM |
| Safety | PASS |
| Tests | PASS（migration + gpu_real_observation） |
| Registry | HEAD 基準 + `get_gpu_processes` entry のみ patch（unrelated Tool 変更は同 commit に含めない） |
| Agent | 意図しない変更なし |
| Commit | `82c40db` — `ai-agent: formally adopt measured gpu process tool` |

---

## 16. Commit 候補（selective、Phase 1-10）

```text
ai-agent: formally adopt measured gpu process tool
```

**Production:** `gpu_processes.py`, `nvidia_smi.py`, `registry/tools.json`（get_gpu_processes entry のみ）

**含めない:** unrelated registry changes, `gpu_status.py`, research/, agent.py

---

## 17. 旧 Migration 最終報告（採用前）

```text
ai-agent: formalize legacy get_gpu_processes contract
```

対象: `docs/ai_tool/tool_creation/specs/get_gpu_processes_legacy_migrated.json`, `GET_GPU_PROCESSES_MIGRATION.md`, `tests/ai_tool/tool_creation/test_get_gpu_processes_migration.py`, `ai_tool/run_get_gpu_processes_migration.py`, `runs/ai_tool/20260828_163325_get_gpu_processes_migration/`

**含めない:** `tools/`, `registry/`, `agent.py`, unrelated changes
