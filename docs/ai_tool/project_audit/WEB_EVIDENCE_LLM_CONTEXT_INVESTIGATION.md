# Web Evidence → LLM Context Architecture Investigation

**Date:** 2026-08-29  
**Git HEAD (start/end):** `f881ae87a60809c33ac4cc1b16c914155bbeaf08`  
**Run:** `runs/ai_tool/20260829_152131_web_evidence_llm_context_investigation/`  
**Production changes:** NONE  
**Git commit:** NOT EXECUTED

## 目的

Production Web Tool chain（Search → Fetch → Extraction → Evidence → web_status → Boundary → LLM）は安定している一方、**Evidence をどの形で LLM に渡すべきか**という Context Architecture は未評価だった。本 Phase ではこの領域を experimental harness のみで独立調査する。

**最重要方針:** 「LLM にもっと情報を渡す」Phase ではない。形式・量・メタデータ・衝突の扱いを **deterministic proxy + ExpectedFact** で比較し、Core Capability の要否を分類する。

---

## Phase 開始 baseline

| 項目 | 値 |
|------|-----|
| initial HEAD | `f881ae8` |
| Production baseline | Search → Fetch → Extraction(S4) → Evidence → web_status → Boundary → LLM |
| Golden GT1–GT6 | offline runner: GT3/GT6 PASS（live fetch skip）；pytest suite で 6/6 維持 |
| pytest | **PASS**（runner 同梱: web_status, web_evidence_pipeline, 本 Phase tests, success_class） |
| success-class accuracy | 既存 Phase 記録参照（mock + live subset） |
| broader accuracy | 84.6%（broader eval Phase 記録） |
| 既存 Core | CC-01 Eval Parity Bridge, CC-02 Mechanical Verification, production_mirror, web_status, web_answer_boundary |

---

## 1. 現在の Evidence → LLM 経路の評価

| 経路 | 内容 | 評価 |
|------|------|------|
| **Production** | `enrich_web_tool_result` → tool JSON（main_text + grounding hints）を LLM messages に注入 | 安定。専用 Packager なし |
| **Evaluation** | `run_canonical_web_eval` → boundary → final_answer | CC-01 経由で再現性あり |
| **Gap** | Context 形式の体系的比較なし；claim / verification / conflict の envelope 未設計 | **本 Phase で experimental 比較を実施** |

Evidence 層自体は Benchmark Phase で強みが確認済み。ボトルネックは Search 側が多いが、**Context 変換が LLM 消費を改善するか**は別問題として切り出した。

---

## 2. Context 形式ごとの比較（Investigation A）

同一 Evidence（11 cases × 6 formats = 66 arms）を deterministic proxy LLM + `classify_answer` で評価。

| Format | 説明 | accuracy | avg context (chars) | avg fact coverage |
|--------|------|----------|---------------------|-------------------|
| **A1_RAW** | Evidence ほぼそのまま | **54.5%** (6/11) | 161 | 100% |
| **A2_PASSAGE** | 関連 paragraph のみ | **54.5%** | 127 | 90.9% |
| **A3_SOURCE_GROUPED** | source / title / URL / excerpt | **54.5%** | 341 | 90.9% |
| **A4_CLAIM** | claim-oriented JSON | **18.2%** (2/11) | 251 | 95.5% |
| **A5_VERIFY** | claim + verification metadata | **27.3%** (3/11) | 989 | 100% |
| **A6_HYBRID** | passage + source + claim + verify | **54.5%** | 1105 | 100% |

### 所見

- **A1 / A2 / A3 / A6 は proxy accuracy で同等。** passage 選択（A2）や source grouping（A3）単独では改善なし。
- **A4 / A5 は悪化。** claim candidate が pattern match の部分文字列（例: `2,750`）のみを抽出し、proxy が不完全数値を生成 → Numeric Error。
- **A6 は A1 と同率だが context 7倍。** hybrid の追加コストに見合う proxy 改善なし。
- **fact coverage in context ≠ 正答。** A4 でも coverage 95%+ だが accuracy 18% — 「情報はあるが消費されない / 歪む」ケースを確認。

---

## 3. Query complexity 別結果（Investigation B）

| Case | Category | A1_RAW 結果 | 主な failure 分類 |
|------|----------|-------------|-------------------|
| IC-B01 | basic（人口） | Correct | — |
| IC-B02 | entity（首都） | Correct | — |
| IC-B03 | numeric（面積） | Correct | — |
| IC-B04 | temporal（2020人口） | **Contradiction** | proxy が汎用文；temporal 特化不足 |
| IC-B05 | comparison（最多都市） | Correct | — |
| IC-B06 | scope（横浜人口） | **Contradiction** | 数値 regex 未ヒット |
| IC-B07 | english | **Contradiction** | million 表記 vs numeric range |
| IC-B08 | non_wiki | **Contradiction** | 汎用 fallback |
| IC-B09 | multi_source | **Numeric Error** | 人口 OK / 面積 fact 未反映 |
| IC-B10 | noise | Correct | passage 選択で nav 除去効果 |
| IC-F01 | conflict | Correct（proxy optimistic） | pessimistic では unsupported numeric |

**パターン:** 単純 fact / entity / comparison は raw で十分。temporal / english / multi-fact / conflict は **packaging 以前に proxy（≒ LLM 消費）の弱点**が顕在化。

---

## 4. Evidence 量による差（Investigation C / D）

compression ladder（IC-B01〜B05）:

| Level | 典型 size | vs full accuracy |
|-------|-----------|------------------|
| full (A1) | 91–252 | baseline |
| passage (A2) | 100–178 | **同等**（full と同じ Correct/Incorrect） |
| source_summary (A3) | 280–359 | **同等** |
| claim (A4) | 237–243 | **劣化**（IC-B01, B03 で Numeric Error / Contradiction） |

**結論:** 「情報を増やせば必ず良くなる」は **否定**。claim 形式は情報量増にもかかわらず proxy 正答率低下。passage / source summary は **サイズ削減しつつ full と同等** — token 節約の副次効果はあるが、accuracy 改善は確認されず。

---

## 5. Verification metadata の効果（Investigation E）

A4_CLAIM 上で E1–E4 を比較（IC-B01〜B03）:

| Mode | 内容 | IC-B01 結果 |
|------|------|-------------|
| E1_NONE | metadata なし | Numeric Error |
| E2_FULL | 全 verification 結果 | Numeric Error |
| E3_MATCH_ONLY | MATCH のみ | Numeric Error |
| E4_ALL_VERDICTS | MATCH/MISMATCH/UNSUPPORTED/UNKNOWN | Numeric Error |

**proxy LLM は verification metadata を消費しない**（設計通り）。CC-02 の envelope を context に載せても、**回答生成 proxy には効果なし**。

→ live LLM 評価は remaining unknown。Production 接続判断材料としては **INVESTIGATE 継続（C2）**。

---

## 6. Conflict case の結果（Investigation F）

**IC-F01:** 2024推計 275万人 vs 2020国勢調査 2,752,412人

| 条件 | proxy answer | 分類 |
|------|--------------|------|
| A1_RAW, optimistic | 両 fact を個別に反映 | Correct |
| A1_RAW / A3, pessimistic | 「人口は999万人」 | unsupported numeric |
| dual fact in evidence | passes | Evidence 自体は両方保持 |

**Evidence を LLM に渡すだけでは解決できない問題がある:**

- 年度・定義の違いを **明示的に区別して回答**するには、conflict annotation または multi-claim envelope が必要
- 現状 Production path に conflict-aware packaging なし
- packaging だけでは pessimistic proxy は誤統合

---

## 7. Deterministic に検証できる範囲

| 可能 | 不可（本 Phase では LLM Judge 禁止） |
|------|--------------------------------------|
| ExpectedFact / answer_patterns | 自然言語の「良い要約」品質 |
| numeric / entity / temporal matching | live LLM が metadata を読むか |
| evidence presence / fact_coverage_in_context | 回答冗長性の人間評価 |
| unsupported addition（claim-level） | 外部 Tool との orchestration 比較 |
| source attribution（pattern） | |
| failure classification（Correct / Numeric Error / Contradiction 等） | |

Harness: `ai_tool/web_evidence_llm_context_investigation.py`  
Experimental packager: `ai_tool/experimental/evidence_context/packager.py`

---

## 8. 新規 Core 候補

| ID | 名称 | 分類 | 根拠 |
|----|------|------|------|
| CTX-PASSAGE | Relevant Passage Selector | **C0** | A2 ≈ A1；accuracy 改善なし |
| CTX-VERIFY-ENV | Verification Metadata Envelope | **C2** | CC-02 拡張；live LLM 効果未検証 |
| CTX-BUILDER | Standalone Context Builder | **C0** | packager 関数で十分 |
| CTX-CONFLICT | Conflict-aware Context Builder | **C2** | IC-F01；packaging のみでは不十分 |

**C3 新規 Experimental Capability:** 本 Phase では **作成なし**（packager module で調査完結）。

---

## 9. 既存 Core で代替可能なもの

| 候補 | 代替 / 拡張先 |
|------|---------------|
| Verification Metadata Envelope | **CC-02 Mechanical Verification** を拡張（重複新規 Core 禁止） |
| Eval parity | **CC-01** — live format shootout 時に reuse |
| Evidence 正規化 | Extraction / Evidence contract（Production 変更禁止のため触らず） |
| Boundary / web_status | 回答制約・layer 観測は既存 Production path |

---

## 10. C0–C4 分類サマリ

| Class | 項目 |
|-------|------|
| **C0**（既存で十分） | CTX-PASSAGE, CTX-BUILDER, A4-only claim packaging |
| **C1**（Record） | — |
| **C2**（Investigate） | CTX-VERIFY-ENV, CTX-CONFLICT |
| **C3**（Experimental 先行） | なし（本 Phase） |
| **C4**（Production 必要） | なし — raw/enrich path 維持 |

---

## 11. Production 変更の必要性

**不要（本 Phase 結論）**

- Raw / enrich 経路で proxy eval 上は最良 tier
- Context 変換による再現可能な改善なし
- claim-oriented 単独導入は **リスク > benefit**

---

## 12. Production 接続候補

| 候補 | 状態 |
|------|------|
| Evidence Packager を enrich に接続 | **却下** — benefit 未実証 |
| Passage selector を Production LLM context に | **保留** — C0 |
| Verification envelope を LLM prompt に | **保留** — C2 + live eval |
| Conflict-aware builder | **保留** — C2 |

**自動 Production 接続なし。**

---

## 13. Human Review Required

**現時点: 不要**

Production failure を Context Architecture で解決すべき状況は確認されなかった。次 Phase（live LLM format shootout）実施時は **HR optional**。

---

## 14. 次 Phase 候補

1. **Live LLM same-evidence format shootout** — qwen3:8b 等で A1 vs A2 vs A3 を同一 evidence で比較（verification metadata 消費の検証）
2. **C2: Conflict-aware context prototype** — IC-F01 拡張；年度/定義ラベル付き envelope
3. **Search 改善優先の再確認** — Context より Search weakness が E2E を支配するケースが多い（Benchmark 前提の再確認）

---

## 15. STOP / CONTINUE 判断

| 判断 | **INVESTIGATE**（部分 STOP 要素あり） |
|------|----------------------------------------|
| Raw sufficient? | **proxy 上は A1 が best tier（他と同率）** — format 変更の urgency は低い |
| Context 改善の再現 | **A4/A5 改善なし（悪化）** — claim-only 導入 STOP |
| 新規 Core 重複 | CC-02 拡張で verification envelope は吸収可能 |
| C3 低価値 | packager で experimental 保有；standalone C3 不要 |
| Production failure なし | Production 接続 STOP |

**正式結論:**

- **Context Architecture 専用 Production Capability は今不要（C0/C2 Record）**
- **Experimental packager は保有価値あり**（`ai_tool/experimental/evidence_context/`）
- **Live LLM 評価まで CONTINUE（INVESTIGATE）** — ただし Search 改善が E2E 優先である点は変わらず

---

## 成果物

| 種別 | パス |
|------|------|
| Investigation harness | `ai_tool/web_evidence_llm_context_investigation.py` |
| Runner | `ai_tool/run_web_evidence_llm_context_investigation.py` |
| Experimental packager | `ai_tool/experimental/evidence_context/packager.py` |
| Tests | `tests/ai_tool/project_audit/test_web_evidence_llm_context_investigation.py` |
| Run artifacts | `runs/ai_tool/20260829_152131_web_evidence_llm_context_investigation/` |

### Architecture options（記録）

| ID | Status | Rationale |
|----|--------|-----------|
| OPT_KEEP_ENRICH | PROPOSE | Production enrich path 安定 |
| OPT_PACKAGER_EXPERIMENTAL | INVESTIGATE | Best proxy: A1_RAW；Production 非接続 |

---

## 再実行

```bash
python ai_tool/run_web_evidence_llm_context_investigation.py
```

Live Golden 含む baseline 記録:

```python
from ai_tool.web_evidence_llm_context_investigation import run_web_evidence_llm_context_investigation
run_web_evidence_llm_context_investigation(fetch_live_baseline=True)
```
