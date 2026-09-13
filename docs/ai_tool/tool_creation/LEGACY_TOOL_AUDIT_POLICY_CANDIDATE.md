# LEGACY_TOOL_AUDIT_POLICY — Candidate

**状態:** Phase 1 監査により必要性を確認 — **未採用・未実装**  
**目的:** Legacy Registered Tool に Tool Creation Layer を「適用する」のではなく「照合監査する」正式工程の候補定義

---

## 1. 背景

Tool Creation Layer 確立以前から Registry / Agent に存在する Tool（GPU/CPU 等）について:

- 動作している ≠ 契約が正しい
- Registry にある ≠ Specification がある
- Specification 不足 ≠ 実装が間違い

**Legacy Tool Audit** はこの中間層を公式化する。

---

## 2. 提案フロー

```text
Legacy Registered Tool
        ↓
Legacy Audit (read-only)
  ├─ Trace: Registry → Agent → Implementation → OS source
  ├─ Classify: REAL / HARDCODED / MOCK / UNKNOWN
  ├─ Independent observation compare
  ├─ Coverage: Spec / Contract / Test / Safety / Catalog
  └─ Gap: Documentation vs Implementation vs Safety
        ↓
Human decision (NOT automated)
  KEEP | REPAIR | REBUILD | RETIRE
        ↓
(Optional future) Migration / Repair / Rebuild under Tool Creation Layer
```

---

## 3. 監査出力（必須フィールド）

| フィールド | 説明 |
|-----------|------|
| `observation_validity` | REAL / PARTIAL / MOCK / UNKNOWN |
| `field_classification` | REAL_OBSERVATION, DERIVED_VALUE, HARDCODED, etc. |
| `independent_comparison` | PASS / MISMATCH / UNKNOWN per field |
| `creation_layer_coverage` | 各工程 FOUND / PARTIAL / MISSING |
| `gap_class` | A: Documentation / B: Implementation / C: Safety |
| `recommended_action` | KEEP / REPAIR / REBUILD / RETIRE（候補のみ） |

---

## 4. STOP 条件（監査 Phase）

監査 Phase では以下禁止:

- `tools/` 実装変更
- `registry/tools.json` 変更
- `agent.py` 変更
- 自動 REPAIR / REBUILD
- 「問題発見 → その場修正」

---

## 5. 新規 Tool 作成との関係

Legacy Audit **≠** 新規 Tool 作成。

| | 新規 Tool Creation | Legacy Audit |
|---|-------------------|--------------|
| 入口 | Idea / Spec 新規 | 既存 Registry Tool |
| 成果 | 実装 + Catalog + Registry 判断 | 監査レポート + 人間判断材料 |
| Registry | 登録は別 Phase | **変更しない** |

---

## 6. Phase 1 で検証したこと

| 検証項目 | 結果 |
|---------|------|
| Legacy Audit フロー成立 | ✅ |
| GPU Tool 実測確認 | ✅ REAL |
| CPU Tool 部分実測 | ✅ PARTIAL |
| KEEP/REPAIR 分岐可能 | ✅ |
| Tool Creation Layer 全工程への無理な載せ替え不要 | ✅ |

---

## 7. 未解決 UNKNOWN

| 項目 | 状態 |
|------|------|
| Legacy Tool の formal version 規則 | UNKNOWN |
| working tree 未コミット実装を監査正本とするか | 人間判断 |
| live 回帰テストの CI 組込み | 未設計 |
| Human Review 記録の Legacy 適用 | 未設計 |

---

## 8. 次 Phase 候補（人間判断後）

1. `LEGACY_TOOL_AUDIT_POLICY.md` 正式採用
2. get_gpu_status — Catalog entry + live regression
3. cpu_status / get_gpu_processes — REPAIR 仕様ドラフト
4. Validator に Legacy Audit checklist テンプレ追加（read-only）

---

## 9. 参照

- [LEGACY_TOOL_AUDIT.md](../project_audit/LEGACY_TOOL_AUDIT.md)
- [CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md)
- [TOOL_CONTRACT.md](./TOOL_CONTRACT.md)
