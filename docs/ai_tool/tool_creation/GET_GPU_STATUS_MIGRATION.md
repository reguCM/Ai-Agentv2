# get_gpu_status — Legacy → Current Tool Migration Phase 1

**日付:** 2026-08-28  
**Legacy Audit:** KEEP  
**実装変更:** なし  
**Registry 変更:** なし  
**Agent 変更:** なし

---

## 1. Git 状態（作業開始時）

| 項目 | 値 |
|------|-----|
| branch | `master` |
| HEAD | `88febb3` |
| `gpu_status.py` | 未コミット diff あり（本 Phase では変更なし） |
| `registry/tools.json` | 未コミット diff あり（本 Phase では変更なし） |

---

## 2. 目的

Legacy Audit で **KEEP** と判定された `get_gpu_status` について、

> 現在の実装・Registry 契約を基準として Tool Creation Layer で扱える状態へ正規化する

実装の「改善」は行わない。

---

## 3. 成果物

| パス | 内容 |
|------|------|
| `specs/get_gpu_status_legacy_migrated.json` | 現行契約の Specification（理想化なし） |
| `GET_GPU_STATUS_MIGRATION.md` | 本ドキュメント |
| `tests/ai_tool/tool_creation/test_get_gpu_status_migration.py` | CI deterministic 契約テスト |
| `tests/test_gpu_real_observation.py` | 既存 Live/mock 観測テスト（変更なし） |
| `ai_tool/run_get_gpu_status_migration.py` | 隔離 Run |
| `runs/ai_tool/20260828_162421_get_gpu_status_migration/` | comparison / catalog_draft / evaluation（success_criteria_met: true） |

---

## 4. 実装経路（変更なし）

```text
registry/tools.json (get_gpu_status, visibility=agent)
  → agent.py create_ollama_tools / execute_tool
  → tools.system.gpu.gpu_status.get_gpu_status()
  → tools.system.gpu.nvidia_smi.query_gpu_status()
  → subprocess nvidia-smi --query-gpu=...
```

---

## 5. Output フィールド（現行契約）

| field | success type | unit | observation | failure |
|-------|-------------|------|-------------|---------|
| gpu | string | — | nvidia-smi name | `"unknown"` |
| temperature | number | °C | temperature.gpu | `"unknown"` |
| utilization | number | % | utilization.gpu | `"unknown"` |
| vram_used | integer | MiB | memory.used | `"unknown"` |
| vram_total | integer | MiB | memory.total | `"unknown"` |
| ok | boolean | — | derived | false |
| status | string | — | ok/unavailable/error | — |
| error | string\|null | — | error code | string |
| observation_source | `"real"` | — | config label | always `"real"` |
| source | string | — | nvidia-smi/none | — |

**KNOWN_LIMITATION:** 複数 GPU 時は index 0 のみ。失敗時 unknown は **文字列**（null ではない）。

---

## 6. Test Contract マッピング

| カテゴリ | 状態 |
|---------|------|
| Normal N-01, N-03 | COVERED（既存 mock テスト + 新契約テスト） |
| Boundary | NOT_APPLICABLE |
| Invalid | NOT_APPLICABLE |
| Failure F-02 | COVERED |
| Safety S-01, S-04 | COVERED |

| 分類 | スイート |
|------|---------|
| CI deterministic | `tests/ai_tool/tool_creation/test_get_gpu_status_migration.py` |
| Local live observation | `tests/test_gpu_real_observation.py` + `@pytest.mark.real_gpu` |

---

## 7. Safety（現状記録 — 変更なし）

- subprocess: nvidia-smi read-only query
- network_access: false
- filesystem write: false
- agent_tool_gate: risk=low, visibility=agent
- timeout: 8s（nvidia_smi 内部）

---

## 8. Registry 整合性

**Verdict: PARTIAL_MATCH**

| 一致 | 内容 |
|------|------|
| ✅ | name, module, function, visibility, observation_source, input {} |
| Registry のみ | category, keywords, risk |
| Spec のみ | output_schema, output_fields, contract, version |

**MISMATCH なし** — Registry descriptor の意味変更は不要と判断。STOP 条件不該当。

---

## 9. Compatibility Review

| 項目 | 結果 |
|------|------|
| Tool ID / name | UNCHANGED |
| Input schema | UNCHANGED（引数なし） |
| Output keys | UNCHANGED（10 keys） |
| Output meaning | UNCHANGED（文書化のみ） |
| Error semantics | UNCHANGED |
| Safety boundary | UNCHANGED |

**Compatibility: NO_CHANGE**

---

## 10. Catalog Draft

Run 内 `catalog_draft.json` を生成（本番 `ai_tool/catalog/entries/` は **未変更**）。

三層 status（draft）:

```text
tool_status: available
experiment_status: tested
adoption_status: approved
```

---

## 11. 独立観測比較（Run 20260828_162421）

同一 Run 内で `get_gpu_status` と独立 `nvidia-smi` を順次比較。

| field | comparison |
|-------|------------|
| gpu | PASS |
| temperature | PASS |
| utilization | PASS |
| vram_used | PASS（1 MiB 差は許容 tol 内） |
| vram_total | PASS |

**overall: PASS**

---

## 12. 最終報告

```text
Tool: get_gpu_status
Legacy status: KEEP

Specification: PASS (validator ACCEPT)
Contract: PARTIAL_MATCH (Registry は output 未記載、Spec が補完)
Implementation: UNCHANGED
Observation: REAL
Independent observation: PASS / PARTIAL (same-run; utilization/vram timing)

Tests:
  Normal: COVERED
  Boundary: NOT_APPLICABLE
  Invalid: NOT_APPLICABLE
  Failure: COVERED
  Safety: COVERED

Safety boundary: UNCHANGED
Registry: PARTIAL_MATCH
Agent: UNCHANGED
Compatibility: NO_CHANGE
Catalog: DRAFT_READY

Recommended action: KEEP
```

---

## 13. STOP — 人間判断が必要な場合（今回不該当）

- output key 追加・削除 → **不要**
- Registry descriptor 変更 → **不要**
- 実装変更 → **禁止（本 Phase 完了）**

次 Phase 候補: Catalog entry 本番反映（Human Review）、live regression CI 方針

---

## 14. Commit 候補（selective）

```text
ai-agent: formalize legacy get_gpu_status contract
```

対象: `docs/ai_tool/tool_creation/specs/get_gpu_status_legacy_migrated.json`, `GET_GPU_STATUS_MIGRATION.md`, `tests/ai_tool/tool_creation/test_get_gpu_status_migration.py`, `ai_tool/run_get_gpu_status_migration.py`, `runs/ai_tool/20260828_162421_get_gpu_status_migration/`

**含めない:** unrelated modified files, `tools/`, `registry/`, `agent.py`
