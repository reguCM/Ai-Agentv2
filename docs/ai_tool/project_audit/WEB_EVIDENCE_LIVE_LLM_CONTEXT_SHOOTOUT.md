# Web Evidence → Live LLM Context Format Shootout

**Date:** 2026-08-29  
**Git HEAD (start/end):** `f881ae87a60809c33ac4cc1b16c914155bbeaf08`  
**Run:** `runs/ai_tool/20260829_152927_web_evidence_live_llm_context_shootout/`  
**Model:** `qwen3:8b` (ollama live)  
**Production changes:** NONE  
**Git commit:** NOT EXECUTED

## 目的

前 Phase（proxy evaluation）では RAW / PASSAGE / GROUPED / HYBRID が概ね同等（54.5%）だった。**同一 Evidence を qwen3:8b に渡したとき、包装形式が回答品質に再現性のある差を生むか**を live LLM で検証する。

---

## Phase 開始 baseline

| 項目 | 値 |
|------|-----|
| HEAD | `f881ae8` |
| Golden GT1–GT6 | offline runner: GT3/GT6 PASS；pytest regression **PASS** |
| 前 Phase | proxy — A1/A2/A3/A6 同率 54.5%；A4/A5 悪化 |
| Production | 変更なし |

---

## 1. 各 Format の総合結果

11 cases × 4 formats = 44 arms（同一 Evidence、包装のみ変更）

| Format | Accuracy | Context (avg chars) | Latency (avg ms) | Refusal rate | Contradiction | Numeric error |
|--------|----------|---------------------|------------------|--------------|---------------|---------------|
| **A_RAW** | **81.8%** (9/11) | 1494 | 7299 | 45.5% | 9.1% | 0% |
| **B_PASSAGE** | **81.8%** (9/11) | 127 | 5786 | 18.2% | 0% | 9.1% |
| **C_GROUPED** | **72.7%** (8/11) | 341 | 6334 | 27.3% | 9.1% | 9.1% |
| **D_HYBRID** | **90.9%** (10/11) | 294 | 6754 | 18.2% | 0% | 0% |

**Accuracy spread:** 18.2pp（72.7%–90.9%）  
**Context format effect:** CONFIRMED（spread ≥ 5pp）

ただし **全体 accuracy 差は 1 case（10/11 vs 9/11）** に相当。カテゴリ別では temporal / numeric / scope で D_HYBRID が優位。

---

## 2. Category 別結果

| Category | A_RAW | B_PASSAGE | C_GROUPED | D_HYBRID | 所見 |
|----------|-------|-----------|-----------|----------|------|
| basic | 1.0 | 1.0 | 1.0 | 1.0 | 全形式 OK |
| entity | 1.0 | 1.0 | 1.0 | 1.0 | 全形式 OK |
| numeric (IC-B03) | **0.0** | 1.0 | 1.0 | 1.0 | RAW のみ `fact_ready`/JSON 過多で「未確認」 |
| temporal (IC-B04) | 1.0 | **0.0** | **0.0** | 1.0 | PASSAGE/GROUPED が excerpt 不足 |
| comparison | 1.0 | 1.0 | 1.0 | 1.0 | OK |
| scope (IC-B06) | 1.0 | 1.0 | **0.0** | 1.0 | GROUPED が fact coverage 0/1 |
| english (IC-B07) | 0.0 | 0.0 | 0.0 | 0.0 | **全形式 fail** — evaluator が million↔万 不一致 |
| non_wiki | 1.0 | 1.0 | 1.0 | 1.0 | OK |
| multi_source | 1.0 | 1.0 | 1.0 | 1.0 | OK |
| noise | 1.0 | 1.0 | 1.0 | 1.0 | OK |
| conflict (IC-F01) | 1.0 | 1.0 | 1.0 | 1.0 | **全形式で年度・定義を区別** |

---

## 3. Failure taxonomy

| Failure | 主な発生 | 原因分類 |
|---------|----------|----------|
| Contradiction | A_RAW (IC-B03), C_GROUPED (IC-B06) | LLM が Evidence 内数値を見落とし「未確認」 |
| Numeric Error | B/C (IC-B04) | passage/grouped excerpt に 2020 人口が含まれない |
| Unsupported Addition | 全形式 (IC-B07) | 英語 Evidence「2.75 million」→ 回答「275万人」；ExpectedFact 範囲外 |
| Refusal / 未確認 | A_RAW 高率 (45.5%) | production-shaped JSON + grounding instruction が過剰保守的 |

**Context 形式に依存しない失敗:** IC-B07（english）— 形式変更では解決せず。

---

## 4. Conflict 結果（IC-F01）

2024推計 2,750,000 vs 2020国勢調査 2,752,412 — **4形式すべて Correct**

| 観点 | 結果 |
|------|------|
| 年度区別 | ✅ 2024 / 2020 を明示 |
| 定義区別 | ✅ 推計 vs 国勢調査 |
| 数値混同 | ✅ 両方保持、混同なし |
| unsupported 数字 | ✅ なし |

**Conflict は source メタデータ付き packaging で LLM が適切に処理。** CTX-CONFLICT の Production 実装 urgency は低い（C1 Record）。

---

## 5. Context size / Latency

| Format | Size vs RAW | Latency vs RAW | 評価 |
|--------|-------------|----------------|------|
| A_RAW | 1.0× (baseline) | 1.0× | 最大 context、最高 refusal |
| B_PASSAGE | **0.09×** | 0.79× | RAW 同等 accuracy、大幅縮小 |
| C_GROUPED | 0.23× | 0.87× | accuracy **低下** — JSON grouping のコスト > benefit |
| D_HYBRID | 0.20× | 0.93× | 最高 accuracy、context 适中 |

**PASSAGE** は token/latency 面で最良の圧縮効率。**GROUPED は live LLM で劣化**（proxy では RAW 同等だった点と差異あり）。

---

## 6. Deterministic evaluation 結果

- **LLM Judge 不使用**
- `classify_answer` + `ExpectedFact` で全 arms 判定
- IC-B07 は Evidence に `2.75 million` があるが回答が `275万人` → Unsupported Addition（evaluator 限界；要 human review または million 正規化拡張）
- 判定不能ケース: 0（全 arms に answer_class 付与）

---

## 7. C0–C4 判定

| Format | 分類 | 理由 |
|--------|------|------|
| A_RAW | **C0** | Production 現状維持；81.8% で best tier |
| B_PASSAGE | **C0** | RAW 同率；context 91% 削減 — future token budget 向け Record |
| C_GROUPED | **C0** | accuracy 72.7% — **劣化**、採用却下 |
| D_HYBRID | **C1** | +9.1pp だが 1 case 差；カテゴリ横断一貫性不足 |

**C3 / C4:** なし。Production 接続候補なし。

---

## 8. Core 候補

| ID | 分類 | 判断 |
|----|------|------|
| CTX-PASSAGE | C0 | Live でも RAW 同率；latency/size benefit のみ |
| CTX-CONFLICT | C1 | Conflict case 全形式成功 — 専用 builder 不要 |
| CTX-BUILDER | C1 | D_HYBRID 微優位 — standalone builder 未正当化 |
| SHOOTOUT-VERDICT | C2 | Format effect confirmed；再現性検証（dataset 拡大）推奨 |

**C3 新規 Experimental Capability:** 本 Phase では **作成なし**。

---

## 9. Production 変更

**なし。** 最良 Format（D_HYBRID）を Production に採用しない。

理由:

1. 全体差は **1 case**（11中）— 少数差のみで Production 変更禁止ルールに該当
2. English case は **全形式 fail** — Context 変更では解決不可
3. A_RAW の高 refusal は production-shaped JSON の副作用 — Production path 自体の問題ではない
4. GROUPED は live で劣化 — 「外部 Tool 模倣」の根拠にならない

---

## 10. Golden regression

| Check | Result |
|-------|--------|
| Golden GT (offline) | PARTIAL (GT3/GT6 PASS, live fetch skip) |
| pytest (web_status, web_evidence_pipeline, shootout, prior investigation) | **PASS** (exit 0) |
| Production file changes | **0** |

---

## 11. Git 変更

実験コードのみ（未 commit）:

- `ai_tool/web_evidence_live_llm_context_shootout.py`
- `ai_tool/run_web_evidence_live_llm_context_shootout.py`
- `ai_tool/experimental/evidence_context/packager.py`（`build_production_raw_context`, `build_hybrid_context` 追加）
- `tests/ai_tool/project_audit/test_web_evidence_live_llm_context_shootout.py`

---

## 12. Human Review 要否

**不要。** Production 接続候補なし。IC-B07 evaluator 拡張（million 正規化）は optional follow-up。

---

## 13. 次 Phase 候補

1. **Dataset 拡大 + D_HYBRID 再検証** — 1 case 差が再現するか（C2）
2. **English / million 正規化** — ExpectedFact 側拡張（Context ではない）
3. **Search 改善** — E2E ボトルネックは引き続き Search 側（Benchmark 前提）

---

## 14. STOP / CONTINUE 理由

| 判断 | **RECORD**（実質 STOP_NO_CHANGE に近い） |
|------|------------------------------------------|
| STOP 要素 | RAW/PASSAGE 同率；Production 変更根拠なし；Conflict は packaging で解決済 |
| CONTINUE 要素 | D_HYBRID +9.1pp、format effect 18.2pp spread — **再現性検証** worth C2 |
| 却下 | C_GROUPED（劣化）、CLAIM-only（前 Phase）、Production 直結 |

**正式結論:**

> Context 形式は live LLM で **差が存在する**（effect CONFIRMED）が、**Production Context 変更は不要**。D_HYBRID は C1 として記録し、dataset 拡大で再検証するまで Experimental 保有にとどめる。

**Architecture Spec (SCR-02):** Context packaging は LLM 拡張候補であり、Mechanical Answer や Production 回答置換の根拠にはならない。→ [WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md](./WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md)

---

## Decision Log

| 項目 | 内容 |
|------|------|
| **Question** | Context format による実 LLM 品質差はあるか |
| **Evidence** | 44 arms, qwen3:8b live；aggregate 上記 |
| **Decision** | **RECORD** |
| **Production** | 変更なし |
| **Rejected** | C_GROUPED（accuracy 低下）；B_PASSAGE（accuracy 同等のみ） |
| **Core** | SHOOTOUT-VERDICT C2；他 C0/C1 |

---

## 再実行

```bash
python ai_tool/run_web_evidence_live_llm_context_shootout.py
```

Mock-only（CI）:

```python
from ai_tool.web_evidence_live_llm_context_shootout import (
    make_mock_shootout_chat_fn,
    run_web_evidence_live_llm_context_shootout,
)
run_web_evidence_live_llm_context_shootout(
    chat_fn=make_mock_shootout_chat_fn(),
    model="mock",
    llm_enabled=True,
)
```

---

## Cost / Benefit サマリ

| Format | Accuracy benefit | Grounding | Context size | Implementation | Production risk |
|--------|------------------|-----------|--------------|----------------|-----------------|
| A_RAW | baseline | baseline | 大 | NONE | NONE |
| B_PASSAGE | 0 | 同等 | **最小** | LOW | LOW |
| C_GROUPED | **-9.1pp** | 劣化 | 中 | LOW | MEDIUM |
| D_HYBRID | +9.1pp (1 case) | 改善 | 小 | MEDIUM | MEDIUM |

---

## 最重要ルール遵守

> 「一番良かった Context 形式を Production に採用する」— **実施せず**

D_HYBRID 90.9% でも **RECORD / 現状維持**。Human Review Required なし。
