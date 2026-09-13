# cpu_status — Legacy → Current Tool Migration Phase 2

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
| `cpu_status.py` diff | なし |
| `agent.py` diff | なし |
| `registry/tools.json` | 未コミット diff あり（本 Phase では変更なし） |

---

## 2. 最重要判断

**「不足している情報」と「現行仕様違反」は分離する。**

| 区分 | 内容 |
|------|------|
| **現行仕様** | Windows CIM `Win32_Processor.LoadPercentage` を `status` 文字列で返す |
| **NOT PROVIDED** | model, cores, threads, temperature, observation_source, ok, error |
| **仕様違反か？** | model/cores 未返却 → **違反ではない**（現行スコープ外） |
| **OBSERVED GAP** | Registry `observation_source=real` だが output に含めない → metadata/output 乖離（output 追加は Human Review） |

Registry description「CPUの基本状態を取得する。**個別メトリクスの取得可否は未確認。**」は、LoadPercentage のみの実装と **hedge 付きで整合**。

---

## 3. 成果物

| パス | 内容 |
|------|------|
| `specs/cpu_status_legacy_migrated.json` | 現行契約 Specification（validator **ACCEPT**） |
| `CPU_STATUS_MIGRATION.md` | 本ドキュメント |
| `tests/ai_tool/tool_creation/test_cpu_status_migration.py` | CI deterministic 契約テスト（10 tests） |
| `ai_tool/run_cpu_status_migration.py` | 隔離 Run |
| `runs/ai_tool/20260828_162825_cpu_status_migration/` | comparison / catalog_draft / evaluation |

---

## 4. 現行目的（調査結果）

```text
registry/tools.json
  name=cpu_status, visibility=agent, observation_source=real, output=[status]
        ↓
agent.py: create_ollama_tools / execute_tool → find_tool("cpu_status")
        ↓
tools.system.cpu.cpu_status.cpu_status()
        ↓
powershell Get-CimInstance Win32_Processor | Select LoadPercentage
        ↓
{'status': '<LoadPercentage>'}  or  {'status': 'error'}
```

**Current purpose:** CPU LoadPercentage（使用率 %）の実測取得のみ。

---

## 5. 観測経路（コード確認済み）

| 使用 | 未使用 |
|------|--------|
| PowerShell subprocess | psutil |
| CIM `Win32_Processor` | WMI COM 直接 |
| `Select LoadPercentage` | network, NVML |

---

## 6. Output（現行固定）

| field | provided | type | unit | meaning |
|-------|----------|------|------|---------|
| status | ✅ | string | percent | LoadPercentage または `"error"` |
| model | ❌ NOT_PROVIDED | — | — | — |
| cores | ❌ NOT_PROVIDED | — | — | — |
| threads | ❌ NOT_PROVIDED | — | — | — |
| temperature | ❌ NOT_PROVIDED | — | — | — |
| observation_source | ❌ NOT_PROVIDED | — | — | Registry metadata のみ |

**KNOWN_LIMITATION:** `status` キー名は load と general status の両方に解釈可能。

---

## 7. 独立観測（Run 20260828_162825）

同一 Run 内で `cpu_status()` と独立 PowerShell CIM を順次比較。

| field | tool | independent | comparison |
|-------|------|-------------|------------|
| LoadPercentage | 64 | 63 | **PASS**（許容差 15pt 内） |
| model | NOT_RETURNED | 12th Gen Intel i5-12400 | OBSERVED GAP（仕様外） |
| cores | NOT_RETURNED | 6 | OBSERVED GAP（仕様外） |
| threads | NOT_RETURNED | 12 | OBSERVED GAP（仕様外） |

**overall: PASS**（LoadPercentage のみ現行契約の比較対象）

---

## 8. GPU Tool との比較（参考のみ）

| 項目 | get_gpu_status | cpu_status |
|------|----------------|------------|
| model | 提供 (gpu) | NOT_PROVIDED |
| cores | N/A | NOT_PROVIDED |
| threads | N/A | NOT_PROVIDED |
| temperature | 提供 | NOT_PROVIDED |
| utilization | 提供 | 提供 (status 文字列) |
| VRAM | 提供 | N/A |
| observation_source | 提供 | NOT_PROVIDED |
| ok/error | 提供 | NOT_PROVIDED |

**結論を出さない:** CPU に model 等を追加すべき、とは本 Phase では判断しない。

---

## 9. REPAIR の分解

| 分類 | 必要 | 本 Phase |
|------|------|---------|
| A. Documentation | ✅ | ✅ 本ドキュメント |
| B. Specification | ✅ | ✅ `cpu_status_legacy_migrated.json` |
| C. Test | ✅ | ✅ 契約テスト追加 |
| D. Implementation | ❌ | 変更なし — LoadPercentage 実測は VALID |
| E. Safety | ❌ | 境界 UNCHANGED、記録のみ |
| F. Interface | ❌ | output 追加は Human Review 要 |

**Implementation Repair ではない。** 現行実装は最小契約として **VALID**。

---

## 10. PROPOSED_SPEC_CHANGE（適用外）

Human Review 待ちの改善候補（`specs/cpu_status_legacy_migrated.json` 内 `proposed_spec_change` 参照）:

- observation_source / ok / error 出力（get_gpu_status 型統一）
- load 専用キー名（status 曖昧さ解消）
- model, cores, threads（CIM で取得可能）
- temperature（取得経路 UNKNOWN）

---

## 11. Test Contract

| カテゴリ | 状態 |
|---------|------|
| Normal | COVERED |
| Boundary | NOT_APPLICABLE |
| Invalid | NOT_APPLICABLE |
| Failure | COVERED |
| Safety | COVERED |

| 分類 | スイート |
|------|---------|
| CI deterministic | `tests/ai_tool/tool_creation/test_cpu_status_migration.py` |
| Local live | `@pytest.mark.real_cpu` |

---

## 12. Registry 整合性

**Verdict: PARTIAL_MATCH**

- ✅ name, module, function, visibility, input, output=[status]
- ⚠️ observation_source は Registry metadata のみ（output なし）
- ⚠️ description  breadth vs LoadPercentage-only — hedge あり

**MISMATCH なし** — STOP 不要。

---

## 13. Compatibility

| 項目 | 結果 |
|------|------|
| Tool ID / Input | UNCHANGED |
| Output keys | UNCHANGED（status のみ） |
| Output meaning | UNCHANGED |
| Error semantics | UNCHANGED（status=error） |
| Safety boundary | UNCHANGED |

**Compatibility: NO_CHANGE**

---

## 14. 最終報告

```text
Tool: cpu_status
Legacy status: REPAIR

Current purpose:
Windows CIM LoadPercentage を status 文字列で返す最小 Legacy CPU 観測 Tool

Observation validity: PARTIAL
Current implementation: VALID
Specification: PASS
Contract: PARTIAL_MATCH

Tests:
  Normal: COVERED
  Boundary: NOT_APPLICABLE
  Invalid: NOT_APPLICABLE
  Failure: COVERED
  Safety: COVERED

Independent observation: PASS (LoadPercentage; same-run)

Safety boundary: UNCHANGED
Registry: PARTIAL_MATCH
Agent: UNCHANGED
Compatibility: NO_CHANGE

Repair classification:
  Documentation: YES
  Specification: YES
  Test: YES
  Implementation: NO
  Safety: NO
  Interface: NO

Proposed specification changes: DEFERRED (see proposed_spec_change)
Human Review: NOT_REQUIRED (this phase)

Recommended action: REPAIR
```

---

## 15. Commit 候補（selective、未実行）

```text
ai-agent: formalize legacy cpu_status contract
```

対象: `docs/ai_tool/tool_creation/specs/cpu_status_legacy_migrated.json`, `CPU_STATUS_MIGRATION.md`, `tests/ai_tool/tool_creation/test_cpu_status_migration.py`, `ai_tool/run_cpu_status_migration.py`, `runs/ai_tool/20260828_162825_cpu_status_migration/`

**含めない:** unrelated changes, `tools/`, `registry/`, `agent.py`
