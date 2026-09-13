# Legacy Registered Tool Audit — Phase 1

**日付:** 2026-08-28  
**スコープ:** 監査のみ（修正・削除・Registry 変更なし）  
**Git HEAD（監査時）:** `88febb3` — `ai-agent: integrate experimental read_url_text`

---

## 0. Git / 作業前状態

| 項目 | 状態 |
|------|------|
| branch | `master` |
| HEAD | `88febb3` |
| ai-tool 監査 Run | 新規作成（本 Phase） |
| 未コミット変更 | `registry/tools.json`, `tools/system/gpu/*.py`, research/* 等 — **本監査では触らない** |
| 対象 Tool 実装の working tree | `gpu_status.py`, `gpu_processes.py` に未コミット diff あり（`cpu_status.py` は diff なし） |

**注意:** 監査観測は **working tree 上の現行コード** に基づく。GPU Tool の HEAD コミット版との差分は `RECONSTRUCTION CANDIDATE` 判断材料として記録するが、今回は変更しない。

---

## 1. 対象 Tool 一覧

| Registry name | tool_id (Catalog 映射) | 存在 |
|---------------|------------------------|------|
| `get_gpu_status` | `local:get_gpu_status` | ✅ |
| `get_gpu_processes` | （spec ファイルなし） | ✅ |
| `cpu_status` | `local:cpu_status` | ✅ |
| `get_cpu_status` | — | **NOT FOUND**（Registry に無し） |

---

## 2. 実装経路（共通パターン）

```text
registry/tools.json
  visibility=agent, module, function, observation_source
        ↓
agent.py: create_ollama_tools() → LLM schema
agent.py: execute_tool() → find_tool() → importlib → function(**args)
        ↓
tools/system/{gpu,cpu}/*.py
        ↓
OS observation (nvidia-smi / PowerShell CIM)
        ↓
structured dict return
```

**Agent 接続:** 3 Tool すべて `visibility: agent` — LLM 公開・実行可能。

---

## 3. Tool 別監査

### 3.1 `get_gpu_status`

#### 実装経路

```text
registry/tools.json → tools.system.gpu.gpu_status.get_gpu_status()
  → tools.system.gpu.nvidia_smi.query_gpu_status()
  → subprocess nvidia-smi --query-gpu=...
```

#### フィールド分類（実測性）

| フィールド | 分類 | 根拠 |
|-----------|------|------|
| gpu (model name) | **REAL_OBSERVATION** | nvidia-smi `name` |
| temperature | **REAL_OBSERVATION** | nvidia-smi `temperature.gpu` |
| utilization | **REAL_OBSERVATION** | nvidia-smi `utilization.gpu` |
| vram_used | **REAL_OBSERVATION** | nvidia-smi `memory.used` (MiB) |
| vram_total | **REAL_OBSERVATION** | nvidia-smi `memory.total` (MiB) |
| ok / status / error | **DERIVED_VALUE** | 観測成否のメタ |
| observation_source | **CONFIG_VALUE** | 常に `"real"`（観測成功/失敗に関わらずラベル） |

**HARDCODED / MOCK:** コード内に RTX 3060 等の固定成功値なし（`tests/test_gpu_real_observation.py` で否定テストあり）。

#### 独立観測比較（2026-08-28 Run）

| フィールド | Tool | Independent | comparison |
|-----------|------|-------------|------------|
| gpu | NVIDIA GeForce RTX 3060 | NVIDIA GeForce RTX 3060 | **PASS** |
| temperature | 58 | 58 | **PASS** |
| utilization | 37 | 29 | **MISMATCH**（スナップショット時差） |
| vram_used | 1773 | 1790 | **MISMATCH**（スナップショット時差） |
| vram_total | 12288 | 12288 | **PASS** |

**結論:** GPU 基本メトリクスは **nvidia-smi 実測**。固定値フォールバックは観測されず。utilization/vram_used の差は時系列変動と判断（再現テスト要）。

#### 工程カバレッジ表

| 項目 | 状態 |
|------|------|
| Registry descriptor | **FOUND** |
| Specification | **FOUND** — `specs/local_get_gpu_status.json` (ACCEPT) |
| Contract | **FOUND** — spec + mapping doc |
| Implementation | **FOUND** |
| Test | **PARTIAL** — `tests/test_gpu_real_observation.py`（mock 中心、live 比較は今回 Run） |
| Safety | **PASS** — subprocess read-only, no network, gate low risk |
| Catalog | **PARTIAL** — mapping doc / draft のみ、`ai_tool/catalog/entries/` なし |
| Current observation | **REAL** |
| Output meaning | **CLEAR** |
| Error behavior | **CLEAR** — unknown/unavailable、固定値フォールバック禁止 |
| Version | **FOUND** — spec `1.0.0` / Registry 明示なし |

#### Gap 分類

| Gap | 種別 |
|-----|------|
| Catalog entry 未整備 | **Legacy Documentation Gap** |
| Registry に version なし | **Legacy Documentation Gap** |
| working tree に未コミット GPU  refactor | **UNKNOWN**（意図・採否は人間判断） |

#### Recommended action: **KEEP**

**Reason:** 実測経路明確、固定値なし、Specification/Contract/Test が最も整っている Legacy Tool。不足は主に Catalog 整備と live 回帰テスト。

---

### 3.2 `get_gpu_processes`

#### 実装経路

```text
registry/tools.json → tools.system.gpu.gpu_processes.get_gpu_processes()
  → nvidia_smi.query_gpu_processes()
  → nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory
```

#### フィールド分類

| フィールド | 分類 |
|-----------|------|
| processes[].pid | **REAL_OBSERVATION** |
| processes[].name | **REAL_OBSERVATION** |
| processes[].vram_used | **REAL_OBSERVATION** または **UNKNOWN**（`[N/A]` → `_safe_int` → `"unknown"`） |
| ok / status / error | **DERIVED_VALUE** |

**HARDCODED / MOCK:** ollama/python 固定リストなし（テストで否定）。

#### 独立観測

同一 nvidia-smi ソース。プロセス名は一致。VRAM per-process は権限/`[N/A]` により **UNKNOWN** が多い — 推測値ではなく unknown 返却。

#### 工程カバレッジ表

| 項目 | 状態 |
|------|------|
| Registry descriptor | **FOUND** |
| Specification | **MISSING** — 専用 spec JSON なし |
| Contract | **MISSING** |
| Implementation | **FOUND** |
| Test | **PARTIAL** — GPU テストファイル内のみ |
| Safety | **PASS** — read-only subprocess |
| Catalog | **MISSING** |
| Current observation | **REAL**（リストは実測、VRAM  per-process は部分 UNKNOWN） |
| Output meaning | **PARTIAL** — 構造化 dict 化は working tree 変更（後方互換コメントあり） |
| Error behavior | **CLEAR** |
| Version | **UNKNOWN** |

#### Gap 分類

| Gap | 種別 |
|-----|------|
| Specification / Contract 不在 | **Legacy Documentation Gap** |
| `[N/A]` VRAM → unknown | **OBSERVED GAP**（推測で埋めていない — 設計判断要） |
| 戻り値 list → dict 変更（未コミット） | **Legacy Implementation Gap** 候補 — Agent 互換要確認 |

#### Recommended action: **REPAIR**

**Reason:** 観測経路は妥当。Specification・Contract・Catalog・専用テスト不足。VRAM unknown 処理と出力形状の Agent 契約を明文化・テスト化すれば KEEP へ移行可能。

---

### 3.3 `cpu_status`

#### 実装経路

```text
registry/tools.json → tools.system.cpu.cpu_status.cpu_status()
  → powershell Get-CimInstance Win32_Processor | Select LoadPercentage
  → {'status': '<LoadPercentage>'}  or {'status': 'error'}
```

#### フィールド分類

| メトリクス | Tool が返すか | 分類 |
|-----------|--------------|------|
| LoadPercentage (utilization) | ✅ `status` 文字列 | **REAL_OBSERVATION** |
| CPU model | ❌ | **NOT_RETURNED** |
| physical cores | ❌ | **NOT_RETURNED** |
| logical processors | ❌ | **NOT_RETURNED** |
| temperature | ❌ | **NOT_RETURNED** |
| current time | ❌ | **NOT_RETURNED** |
| load average (Linux) | ❌ | N/A（Windows 実装） |

**Registry vs 実装:** Registry `observation_source: real` だが **実装は observation_source フィールドを返さない** — **OBSERVED GAP**。

**エラー時:** `{'status': 'error'}` のみ — 詳細 error なし。推測値で成功を装わない。

#### 独立観測比較

| 項目 | Tool | Independent (CIM) | comparison |
|------|------|-------------------|------------|
| LoadPercentage | 56 → 50（Run 内時差） | 50 | **PASS**（許容差内） |
| CPU model | NOT_RETURNED | 12th Gen Intel i5-12400 | **OBSERVED GAP** |
| Cores / threads | NOT_RETURNED | 6 / 12 | **OBSERVED GAP** |
| Temperature | NOT_RETURNED | NOT_QUERIED | **UNKNOWN** |

#### 工程カバレッジ表

| 項目 | 状態 |
|------|------|
| Registry descriptor | **FOUND** |
| Specification | **FOUND** — `specs/local_cpu_status.json` (ACCEPT) |
| Contract | **FOUND** — legacy 最小契約として文書化 |
| Implementation | **FOUND** |
| Test | **MISSING** — 専用ユニットテストなし |
| Safety | **PARTIAL** — PowerShell subprocess (`side_effect: execute`)、gate low risk |
| Catalog | **PARTIAL** — mapping / draft のみ |
| Current observation | **PARTIAL** — LoadPercentage のみ REAL |
| Output meaning | **AMBIGUOUS** — `status` が load なのか general status なのか名前が曖昧 |
| Error behavior | **UNKNOWN** — `error` 詳細なし |
| Version | **FOUND** — spec `1.0.0` |

#### Gap 分類

| Gap | 種別 |
|-----|------|
| observation_source 未返却 | **Legacy Implementation Gap** |
| 最小出力（status のみ） | **Legacy Documentation Gap** + **Implementation Gap** |
| 専用テストなし | **Legacy Documentation Gap** |
| Registry description「個別メトリクス未確認」と実装一致 | 整合（問題ではない） |

#### Recommended action: **REPAIR**

**Reason:** LoadPercentage は実測だが、契約が Legacy 最小パターン。`get_gpu_status` 型の ok/error/observation_source 統一、テスト追加、出力フィールド拡張は **REPAIR** で足りる。全面 REBUILD 必須の証拠なし。

---

## 4. Tool Creation Layer との比較（3 Tool まとめ）

| 工程 | get_gpu_status | get_gpu_processes | cpu_status |
|------|----------------|-------------------|------------|
| Specification | ✅ ACCEPT | ❌ MISSING | ✅ ACCEPT |
| Validator | ✅ 適用可 | ❌ | ✅ 適用可 |
| Implementation | ✅ EXISTING | ✅ EXISTING | ✅ EXISTING |
| Test Contract | ⚠️ PARTIAL | ⚠️ PARTIAL | ❌ MISSING |
| Safety | ✅ PASS | ✅ PASS | ⚠️ PARTIAL |
| Catalog | ⚠️ PARTIAL | ❌ | ⚠️ PARTIAL |
| Human Review | UNKNOWN | UNKNOWN | UNKNOWN |
| Registry | ✅ EXISTING | ✅ EXISTING | ✅ EXISTING |
| Agent | ✅ EXISTING | ✅ EXISTING | ✅ EXISTING |

---

## 5. Legacy Gap 分類（A/B/C）

### A. Legacy Documentation Gap（作り直し必須ではない）

- Catalog entry 未整備（GPU/CPU）
- `get_gpu_processes` Specification 不在
- Registry version フィールド不足
- cpu_status 専用テスト不足

### B. Legacy Implementation Gap（REPAIR/REBUILD 候補）

- cpu_status: `observation_source` 未返却 vs Registry 宣言
- cpu_status: エラー詳細不足（`status: error` のみ）
- get_gpu_processes: 戻り値形状変更（working tree、Agent 互換 UNKNOWN）
- get_gpu_processes: VRAM per-process が `[N/A]` 時 unknown（推測はしていない）

### C. Safety Gap

- 3 Tool とも network なし、filesystem write なし
- cpu_status の PowerShell 実行は `side_effect: execute` — gate 確認済み low risk
- **Safety 重大 GAP なし**（Interface Compatibility とは別軸）

---

## 6. 「本当に PC 状態を取得しているか」

### GPU（get_gpu_status / get_gpu_processes）

**実測値として確認できた**（nvidia-smi 経由）。

- 固定値フォールバック: **観測されず**
- 独立観測との一致: モデル名・VRAM total・温度は **PASS**；utilization/vram_used は **スナップショット時差**

### CPU（cpu_status）

**一部は実測値、大部分は未提供**

- LoadPercentage: **REAL**（CIM と一致）
- model / cores / threads / temperature: **Tool は返さない**（Registry description とも整合）
- temperature on Windows: **UNKNOWN**（別 API 要否は人間判断）

---

## 7. 最終報告（指示書フォーマット）

### get_gpu_status

```text
Tool: get_gpu_status
Current status: Production / Agent visible
Registry: FOUND (observation_source=real)
Agent: EXISTING (visibility=agent)

Observation validity: REAL

Specification: PASS
Contract: PASS
Tests: PARTIAL
Safety: PASS

Recommended action: KEEP
Reason: nvidia-smi 実測、固定値なし、Spec/Contract 整備済み。Catalog/ live test 不足のみ。
```

### get_gpu_processes

```text
Tool: get_gpu_processes
Current status: Production / Agent visible
Registry: FOUND
Agent: EXISTING

Observation validity: REAL (VRAM per-process often UNKNOWN)

Specification: MISSING
Contract: MISSING
Tests: PARTIAL
Safety: PASS

Recommended action: REPAIR
Reason: 観測経路は妥当。Spec/Contract/Catalog/出力契約の文書化とテスト追加が必要。
```

### cpu_status

```text
Tool: cpu_status
Current status: Production / Agent visible
Registry: FOUND (observation_source=real — 実装未反映)
Agent: EXISTING

Observation validity: PARTIAL (LoadPercentage only)

Specification: PASS (legacy minimal)
Contract: PARTIAL
Tests: MISSING
Safety: PARTIAL (execute side_effect)

Recommended action: REPAIR
Reason: 実測は load のみ。observation_source/ error 契約を gpu 型に揃える REPAIR が妥当。
```

---

## 8. Run 記録

最新 Run: `runs/ai_tool/20260828_161848_legacy_tool_audit/`

含む: `inputs.json`, `outputs.json`, `comparison.json`, `evaluation.json`, `audit.jsonl`, `REPORT.md`

---

## 9. STOP — 次 Phase（人間判断）

今回 **修正なし**。次に人間が選択:

1. **KEEP** — get_gpu_status Catalog 整備 + live 回帰テスト追加
2. **REPAIR** — cpu_status / get_gpu_processes 契約・テスト・observation_source 統一
3. **REBUILD** — 証拠不足のため今回は **候補に挙げず**
4. **RETIRE** — 該当なし（重複 Tool なし）

関連: [LEGACY_TOOL_AUDIT_POLICY_CANDIDATE.md](../tool_creation/LEGACY_TOOL_AUDIT_POLICY_CANDIDATE.md)
