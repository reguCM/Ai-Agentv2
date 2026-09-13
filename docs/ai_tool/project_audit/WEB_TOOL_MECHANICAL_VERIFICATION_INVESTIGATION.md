# Web Tool — Mechanical Verification Investigation

**Date:** 2026-08-29  
**HEAD:** `f881ae8`  
**Run:** `runs/ai_tool/20260829_144008_web_tool_mechanical_verification/`  
**Human Intervention:** 0

---

## Overall: **PASS**

Golden 6/6 intact. Experimental Mechanical Verification capability built and evaluated. **Production changes: NONE.**

---

## Independent Conclusion

### **C — Experimental Capability として先行構築**

| 段階 | 判断 |
|------|------|
| 作らない | ❌ |
| 設計のみ | ❌（低コストで実装可能と確認） |
| **Experimental 構築** | **✅ 推奨（完了）** |
| Production Warning | ❌（実測 FP/FN + HR 不足） |
| Retry / Mechanical Fallback | ❌ |

**Mechanical Answer（回答置換）と Mechanical Verification（Claim検証）は別判断:**

- Mechanical Answer Production: **NOT RECOMMENDED**
- Mechanical Verification Experimental: **RECOMMENDED**（observation-only 維持）

---

## Cost / Risk / Value

| 次元 | 評価 |
|------|------|
| Cost | **LOW** (~200 LOC experimental + harness reuse) |
| Risk | **LOW** (Production 非接続) |
| Reuse Value | **HIGH** (success_class, broader eval, future OPT7) |
| Defensive Value | **MEDIUM** (verify-only; taxonomy 50% on replay edge cases) |

---

## Phase 1 — Existing Architecture（重複回避）

### 既存の「機械的検証に近い処理」

| 既存 | 役割 | 本 Phase との関係 |
|------|------|------------------|
| `web_answer_boundary` | Failure 時 numeric 抑制 | **別責務** — Web 失敗時のみ |
| `detect_unsupported_web_claims` | numeric パターン検出 | boundary 用、Evidence 照合なし |
| `web_evidence.enrich` | grounding hints | LLM 入力用、検証なし |
| `web_status` / WebSessionTracker | 層状態 | SUCCESS 判定、Claim 検証なし |
| `success_class classify_answer` | ExpectedFact + claim-level | **再利用** — 本 Capability の core |
| `_detect_unsupported_additions` | numeric_not_in_evidence | **再利用** |
| `numeric_range_match`, `regex_entity`, `year_match` | deterministic methods | **再利用** |

**重複実装を避け、`ai_tool/experimental/mechanical_verification/verifier.py` は既存 logic をラップし MATCH/MISMATCH/UNSUPPORTED/UNKNOWN 語彙を追加。**

---

## Phase 2 — Capability Boundary

### A. Evidence Fact Extraction

| Fact 種別 | 機械抽出 | 条件 |
|-----------|---------|------|
| 人口（数値） | ✅ | `extract_population_numeric_values`（万、million） |
| 面積 | ✅ | `extract_numeric_values` + range |
| 年 | ✅ | `YEAR_PATTERN` |
| Entity（首都等） | △ | **ExpectedFact パターン必要** |
| 比較関係 | △ | regex パターン必要 |
| 開放域 | ❌ | ExpectedFact なしでは限界 |

### B. Claim Extraction

| Claim 種別 | 抽出 | 備考 |
|-----------|------|------|
| 数値 Claim | ✅ | answer から numeric 抽出 |
| Entity Claim | △ | ExpectedFact.answer_patterns 経由 |
| Temporal Claim | ✅ | year 抽出 |
| 比較 Claim | △ | regex |
| 長文からの複数 Claim | △ | ExpectedFact 単位；heuristic 分割なし |

### C. Claim ↔ Evidence Verification

```text
MATCH       ← supported (evidence と整合)
MISMATCH    ← contradicted (数値/entity/year 不一致)
UNSUPPORTED ← unsupported (evidence に根拠なし)
UNKNOWN     ← ambiguous (判定不能)
```

**数値許容:** 相対誤差 **5%**（`DEFAULT_NUMERIC_RELATIVE_TOLERANCE`）。「約282万人」↔ 2,817,627 → MATCH。

**重要:** 「機械的に検証できる」≠「機械的に正解判定できる」。ExpectedFact / 質問コンテキストが必要。

---

## Phase 3 — Cost / Risk Assessment

| 項目 | 評価 |
|------|------|
| 実装規模 | LOW |
| 既存 Production 影響 | **なし** |
| テスト量 | 11 unit + 27 scenario replay |
| 保守コスト | LOW（success_class と共有 logic） |
| False Positive | 0（今回 run） |
| False Negative | 0（今回 run；taxonomy replay 50%） |
| 言語依存 | 中（ja 万、en million；fact_id 命名に依存） |
| 表記揺れ | 中（regex ベース） |
| 単位変換 | 万・million のみ |
| 曖昧表現「約」 | 許容範囲内で MATCH |
| 複数 Claim | ExpectedFact 複数で対応 |
| 長文回答 | V10 PASS |
| 推論結果 | **検証不可** → UNKNOWN |
| 一般知識（evidence 外で正しい） | **MISMATCH/UNSUPPORTED リスク** — Production 接続時問題 |
| Evidence 不完全 | boundary が先に担当；verify は SUCCESS-class 想定 |

---

## Phase 4 — Evaluation Results

**Run:** 27 scenarios（builtin 10 + success_class/broader replay 17）

| Metric | Value |
|--------|-------|
| scenario_pass_rate | **92.6%** |
| builtin_pass_rate | 90.0% |
| replay_pass_rate | 94.1% |
| false_positive_count | **0** |
| false_negative_count | **0** |
| taxonomy_detection_rate | 50% |

### 失敗ケース（2件）

| ID | Expected | Observed | 注記 |
|----|----------|----------|------|
| V03 | MISMATCH | UNSUPPORTED | 問題検出は成功、verdict 分類差 |
| BC-EN01 | MATCH | UNKNOWN | replay fact_id `osaka_pop_en` — population extract 未適用 |

---

## Phase 5 — Architecture Comparison

| OPT | 段階 | 判断 |
|-----|------|------|
| OPT0 現状維持 | — | Rejected（Experimental 価値確認済） |
| **OPT1 Experimental** | observation-only | **Selected** |
| OPT2 Production Warning | warning | Deferred（HR、FP 監視必要） |
| OPT3 Retry | retry | Rejected |
| OPT4 Mechanical Fallback | fallback | Rejected |
| OPT5 Structured Claim | structured | Deferred（コスト高） |
| OPT6 Hybrid | hybrid | Deferred |
| **OPT7 Post-LLM verify metadata** | observation→warning | Future candidate |

**段階的導入:** Observation-only（現在地）→ Warning metadata → Retry → Fallback（非推奨）

---

## Phase 6 — 開発思想（Model B）の妥当性

**条件付き妥当。** 今回の Mechanical Verification は Model B の好例:

- Production 実測 Failure なしでも eval-only 先行 **正当**
- Production 接続は **別判断**（今回は不採用）
- 既存 success_class logic 再利用で **低コスト**
- Sunset 可能（experimental モジュール削除容易）

---

## Production Changes

**NONE**

## Experimental Changes

- `ai_tool/experimental/mechanical_verification/verifier.py`
- `ai_tool/experimental/mechanical_verification/__init__.py`
- `ai_tool/web_tool_mechanical_verification_investigation.py`
- `ai_tool/run_web_tool_mechanical_verification_investigation.py`
- `tests/ai_tool/project_audit/test_web_tool_mechanical_verification_investigation.py`

---

## Regression

pytest: **32 passed** (web_status, web_evidence, mechanical verification, success_class)

Golden: **6/6 PASS**

---

## Human Review

**不要**（Experimental-only）

**必要になる条件:** OPT2 Warning 接続、OPT3 Retry、boundary 拡張

---

## Recommended Next Iteration

1. Experimental module 維持；broader dataset 定期 replay
2. BC-EN01 型: fact_id 命名規約 or million 一般化
3. taxonomy detection 改善（V03: MISMATCH vs UNSUPPORTED 統一）
4. live numeric_error > 15%  sustained → OPT7 再評価
5. **Production Warning 接続はしない**（現時点）

---

## STOP

**YES** — Experimental Capability 構築・評価完了。Production 実装へ進まない。

---

## Decision Log Summary

```json
{
  "initial_head": "f881ae8",
  "conclusion": "C_EXPERIMENTAL",
  "production_changes": [],
  "experimental_changes": ["mechanical_verification/verifier.py", "investigation harness"],
  "scenario_pass_rate": 0.9259,
  "false_positive": 0,
  "false_negative": 0,
  "mechanical_answer_production": "NOT_RECOMMENDED",
  "mechanical_verification": "EXPERIMENTAL_BUILT"
}
```
