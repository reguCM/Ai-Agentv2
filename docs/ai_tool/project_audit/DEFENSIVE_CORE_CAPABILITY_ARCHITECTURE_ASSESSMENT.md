# Defensive Core Capability Architecture — Independent Assessment

**Date:** 2026-08-29  
**HEAD (investigation):** `f881ae8`  
**Scope:** Architecture / Risk / Benefit / Policy evaluation only  
**Production changes:** None  
**Git commit:** None (per phase instruction)

---

## Independent Architecture Assessment

### Verdict: **条件付き賛成**

Core Capability の一定範囲を先行構築する方針は、**AI Agent 一般論としては合理性がある**が、**このプロジェクトの現状・過去 Phase の観測結果を踏まえると、無条件採用は不適切**である。

採用すべきなのは **Model B（Production は必要性・実測 Failure 重視 ＋ Core Capability は低コスト・観測専用なら先行可）** であり、Model C（将来便利そうなものを積極先行）は **反対** である。

---

## Q1 — 先行 Core Capability に通常以上の合理性はあるか

**結論: 部分的に Yes。ただし「AI Agent だから全部先に作る」ではない。**

AI Agent 固有要因:

| 要因 | 先行構築を支持する | 支持しない |
|------|-------------------|-----------|
| LLM 非決定性 | 観測・検証層の eval-only 先行 | 主経路への未検証防御 |
| モデル/Prompt 変更 | web_status / boundary / diagnosis の再利用 | モデル固有 hardcode |
| Tool 追加 | production_mirror + injectable fixtures | 全 Tool 共通 RTT |
| 自律修正 | Failure taxonomy + regression | 「予防」名目の量産 |

**本プロジェクトの実績:** Web Tool 系 Core Capability（web_status, boundary, evidence, extraction normalization, failure diagnosis, evaluation harness）は、**ほぼすべて「障害・ギャップが観測された後」に最小変更で導入**され、Golden 6/6・Osaka E2E PASS に到達している。Reactive 方針は **機能している**。

一方、**後から追加するとコストが高い層**も確認済み:

- eval 経路と Production 経路の乖離（`execute_registry_tool` mock default、boundary 未適用）
- SUCCESS-class LLM failure の計測（Web vs LLM 分離がなければ Architecture 判断不能）
- Claim-level verification の eval 基盤（存在すれば Production 接続判断が可能）

→ **「観測・計測・診断」系 Core Capability だけは、Production 接続前の先行に合理性がある。**

---

## Q2 — 先行 Core Capability の将来価値

| 利用可能性 | 評価 |
|-----------|------|
| 複数用途に利用 | web_status, boundary, diagnosis, eval harness — **高** |
| 将来問題への転用 | claim verification (eval), layer separation — **中〜高** |
| 評価基盤 | production_mirror, golden, success_class — **既に高** |
| Agent 自律改善 | autonomous improvement loop — **中（eval gap 残存）** |
| LLM 変更時 | web_status/boundary — **高**; mechanical answer — **低（現時点）** |
| Failure 被害抑制 | boundary (numeric suppression) — **実証済み** |

**「念のため」だけでは不十分。** 先行価値があるのは、**計測可能・複数 Phase で再利用・Production 主経路と分離可能**な Capability に限られる。

---

## Q3 — 先行 Core Capability のリスク

| リスク | 本プロジェクトでの顕在度 |
|--------|------------------------|
| YAGNI / 過剰設計 | 中 — RTT, structured claim, mechanical answer は複数 Phase で Deferred 済み |
| Architecture bloat | 中 — `ai_tool/web_tool_*` harness が多数存在 |
| 抽象化の早期固定 | 中 — Research Transaction は defer 判断が妥当だった |
| 防御機構自体の Failure | 低〜中 — boundary false positive は live E2E で確認 |
| LLM 責務境界の複雑化 | 中 — mechanical answer 主経路化はリスク大 |
| Cursor 暴走（予防名目の実装増） | **高** — 自律改善ループ + 「Core 先行可」ルールの組合せ |
| Legacy 化 | 中 — 未使用 harness / deferred 案の蓄積 |
| テスト・保守コスト | 中 — broader eval で 32 pytest、runner 実行 ~2–8 分 |
| 開発速度低下 | 低〜中 — eval-only なら許容、Production 接続は別判断 |

---

## 「便利な予防線」の評価（Capability 作成 vs Production 接続）

**A（Capability を作る）と B（Production 主経路へ接続）は別問題** — 本プロジェクトはこの分離を **既に実践している**。

```text
既存パターン:
  web_status + boundary     → Production 接続済み（実測 Failure 後）
  failure_diagnosis         → eval-only（ObservationBundle → diagnose）
  success_class evaluation  → eval-only（ExpectedFact → classify）
  mechanical verification   → eval-only prototype（Production NOT recommended）
```

段階的導入:

```text
Phase 1: Observation-only  （eval harness, no Production gate）
Phase 2: Warning / metadata （system_notice, grounding hints）
Phase 3: Fallback / block   （boundary 相当 — 実測後のみ）
```

**メリット:** Regression リスク低、ROI 測定可能、削除容易  
**デメリット:** 二重経路（eval vs Production）の維持コスト、接続判断の先延ばし

→ **メリットが上回る。ただし Phase 1 で止まり続ける Capability は Legacy 化リスクあり — 削除基準が必要。**

---

## 先行実装条件（§6）の評価

提示された 12 条件は **妥当。不足は 2 点**:

| # | 条件 | 評価 |
|---|------|------|
| 1–12 | 提示条件 | **妥当** — 特に observation-only, 独立 module, 削除可能 |
| +13 | **Sunset 条件**（N Phase 未使用なら削除候補） | **追加推奨** |
| +14 | **接続ゲート**（Production 接続は measured failure + HR 行列） | **追加推奨** |

過剰な条件: なし（12 条件は「何でも先に作る」を防ぐのに十分）。

---

## Capability 評価表（§7）

| Capability | 状態 | 先行価値 | 実装リスク | 後付けコスト | 再利用性 | 判断 |
|------------|------|---------|-----------|------------|---------|------|
| **Mechanical Verification** | eval prototype あり | 中 | 中 | 中 | 高 | **Deferred（eval 拡張可、Production 不可）** |
| **Claim Verification** | success_class harness 内 | 中〜高 | 低〜中 | 中 | 高 | **条件付き先行（eval module 分離）** |
| **Evidence provenance** | `enrich_web_tool_result` 部分 | 中 | 低 | 中 |  high | **維持・拡張は observation-only** |
| **Failure Boundary** | Production 統合済 | — | — | 高（無いと危険） | 高 | **既存維持（変更 HR）** |
| **Fallback framework** | なし | 低 | 高 | 高 | 中 | **Deferred** |
| **Retry / Recovery** | search backend 最小 | 低〜中 | 中 | 中 | 中 | **必要時のみ（Web layer）** |
| **Confidence / uncertainty** | diagnosis + capability_route 部分 | 低〜中 |  mid | 中 | 高 | **eval 拡張可、Production defer** |
| **Research Transaction** | 複数 Phase defer | 低 | 高 | 非常に高 | 中 | **Deferred** |
| **Capability registry** | registry 存在、eval gap | 中 | 中 | 中 | 高 | **OPT7 eval bridge のみ先行可** |
| **web_status** | Production | — | — | — | 高 | **既存** |
| **WebSessionTracker** | Production | — | — | — | 高 | **既存** |
| **Failure Diagnosis** | eval engine | 高 | 低 | 高 | 高 | **既存・拡張可** |
| **production_mirror** | eval canonical | 高 | 低 | 高 | 高 | **既存・必須** |
| **Success-class eval** | eval | 高 | 低 | 高 | 高 | **既存・定期再実行** |

---

## Cursor 自律開発への影響（§8）

### 良い可能性

- Failure 発生前の **計測基盤**（success_class, layer separation）
- 修正判断の **観測データ**（diagnosis, run artifacts）
- Regression 検出（golden, pytest, production_mirror）
- 「直したつもり」の **検証**（before/after, STOP 条件）

### 悪い可能性

- **「Core Capability 先行可」が Cursor 暴走の正当化材料**になる
- harness / doc / deferred 案の **蓄積**
- Architecture 複雑化で **自律ループの判断コスト増**

### 暴走抑制（必須）

1. Production 接続は **STOP_NO_CHANGE / measured failure** まで禁止
2. eval-only Capability は **1 モジュール・1 責務・削除可能**
3. Phase あたり **新規 Core Capability 先行は最大 1 件**
4. Deferred 連続 2 Phase → **削除または接続判断を強制**

---

## Model A / B / C 比較（§9）

| 次元 | Model A 必要時のみ | Model B Production必要 + Core低コスト先行 | Model C 積極先行 |
|------|-------------------|------------------------------------------|-----------------|
| 開発速度 | 高 | 中〜高 | 低 |
| 保守性 | 高（短期）/ 後付けで低下 | **中〜高** | 低 |
| 安全性 | 低（障害後対応） | **中〜高** | 中（未検証防御） |
| 拡張性 | 低〜中 | **高** | 高（bloat リスク） |
| 自律開発適性 | 低（観測不足） | **高** | 低（暴走） |
| 過剰設計リスク | 低 | **低〜中** | 高 |
| 将来変更コスト | 高 | **中** | 低（早期）/ 高（legacy） |

**推奨: Model B**

---

## Mechanical Verification の再評価（§10）

| 観点 | 判断 |
|------|------|
| Production 主経路への Answer replacement | **NOT RECOMMENDED**（numeric_error 7.7%, broader eval STOP_NO_CHANGE） |
| eval-only Verification Engine | **価値あり** — claim-level, deterministic, 既に harness 内に prototype |
| 先行 Capability としての Module 分離 | **条件付き可** — observation-only, Production 非接続 |
| Verify-only（LLM 回答を置換しない） | **将来最有力候補** — numeric_error 上昇時に HR 付き接続 |

**Answer replacement と Verification は明確に分離する。**

---

## Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------:|-------:|------------|
| 過剰設計 | Medium | High | Model B + 12条件 + Phase 1件上限 |
| Complexity | Medium | Medium | 独立 module、Production 分離 |
| Maintenance | Medium | Medium | Sunset 条件、Legacy 削除 |
| False positive | Low–Medium | Medium | observation-only 先行、boundary 実績参照 |
| Legacy 化 | Medium | Medium | 2 Phase defer → 削除/接続強制 |
| Cursor 暴走 | **High** | High | Production 接続ゲート、STOP 必須、commit 最小 |
| Architecture lock-in | Low–Medium | High | RTT/mechanical defer 継続、削除可能設計 |
| Development slowdown | Low–Medium | Medium | eval-only 限定、End Tool は YAGNI 維持 |

---

## Benefit Matrix

| Capability | Current Value | Future Value | Reusability | Defensive Value |
|------------|-------------:|-------------:|------------:|----------------:|
| web_status / WebSessionTracker | **High** | High | High | **High** |
| Failure Boundary | **High** | High | High | **High** |
| web_evidence enrich | Medium | High | High | Medium |
| Failure Diagnosis | **High** (eval) | High | High | Medium |
| production_mirror | **High** (eval) | High | High | Medium |
| Success-class eval | **High** (eval) | High | High | Medium |
| Claim Verification (module) | Low–Medium | **High** | High | Medium–High |
| Mechanical Verification | Low (Production) | Medium | High | Medium (if verify-only) |
| Fallback / RTT | None | Low–Medium | Medium | Low (now) |
| Eval canonical bridge (OPT7) | Medium | High | High | Low (observability) |

---

## Recommended Policy

```text
End Tool:
  必要になってから実装（原則 A 維持）

Production Core:
  実測 Failure + 最小変更 + Regression + Decision Log
  接続前に measured ROI 必須
  Agent / Prompt / Registry 変更は Human Review

Core Capability (eval / observation):
  以下を ALL 満たす場合のみ先行可:
    1. Core system capability（末端 Tool ではない）
    2. 複数将来用途が具体例付きで説明できる
    3. 独立 module + observation-only 導入可能
    4. 自動テスト可能
    5. Production 主経路を壊さない
    6. Sunset / 削除可能
  Phase あたり新規先行は最大 1 件

Production 接続ゲート:
  measured failure rate OR confirmed defect
  + existing tests protect baseline
  + Human Review（policy/registry/boundary 変更時）

Cursor 自律改善:
  STOP 条件必須
  「Core 先行」を Production 変更の理由にしない
  eval harness 増殖は Sunset で抑制
```

**Model B を正式方針とする。Model C は採用しない。Model A のみでは eval–Production 乖離と Architecture 判断遅延が残る。**

---

## 現在存在する Core Capability（HEAD `f881ae8`）

### Production 統合済

- `search_web` + search hardening
- `read_url_text` + extraction normalization (S4)
- `web_evidence.enrich_web_tool_result`
- `web_status` / `WebSessionTracker`
- `web_answer_boundary`
- `agent_tool_gate`
- Agent tool loop（gate → enrich → session → boundary）

### eval / observation 統合済

- `production_agent_web_loop` (production_mirror)
- `web_tool_failure_diagnosis_phase4`
- `web_tool_*` evaluation harness 群
- success_class / broader success_class accuracy evaluation
- autonomous improvement / post-baseline exploration

### Deferred / 未 Production

- Mechanical Answer (Production)
- Research Transaction
- Structured Claim (Production)
- Fallback framework
- Post-LLM verify-only (Production 接続)
- Eval canonical bridge (OPT7)

---

## 今後の実装候補（評価のみ — 今回実装しない）

| 優先 | 候補 | 種別 | 条件 |
|------|------|------|------|
| 1 | Eval canonical bridge (OPT7) | eval-only | 自律 metrics 乖離が問題化した時 |
| 2 | Claim Verification module 分離 | eval-only | success_class harness から抽出 |
| 3 | Post-LLM verify-only prototype | eval-only | live numeric_error > 15%  sustained |
| — | Mechanical Answer Production | **不要（現時点）** | numeric_error < 25% |
| — | RTT / Fallback | **Deferred** | 新 confirmed Production symptom なし |

---

## 今回実装しなかった理由

- Phase 指示: **評価のみ、実装禁止**
- 観測: Production baseline 安定、SUCCESS-class accuracy 85%、STOP_NO_CHANGE
- Policy 判断: Model B 採用で **追加 Core 先行の緊急性は低い**
- 既存 eval 基盤で Architecture 判断は **可能**
- Cursor 暴走リスクを増やす無差別先行は **反対**

---

## STOP

| # | 条件 | 状態 |
|---|------|------|
| 1 | Core 先行開発の是非評価 | ✅ 条件付き賛成 |
| 2 | 最小開発との比較 | ✅ Model B 推奨 |
| 3 | リスク列挙・評価 | ✅ Risk Matrix |
| 4 | 利点列挙・評価 | ✅ Benefit Matrix |
| 5 | Mechanical 分離評価 | ✅ verify-only defer |
| 6 | Cursor 自律開発影響 | ✅ 評価済 |
| 7 | Recommended Policy | ✅ 提示 |
| 8 | Production 変更なし | ✅ |
| 9 | Decision Log | ✅ `runs/ai_tool/20260829_defensive_core_capability_assessment/` |
| 10 | Git / unrelated 非破壊 | ✅ commit なし |

**次 Implementation Phase へ自動進行しない。**
