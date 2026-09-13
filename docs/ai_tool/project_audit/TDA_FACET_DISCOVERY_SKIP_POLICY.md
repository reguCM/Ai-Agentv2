# TDA Facet Discovery Skip Policy Evaluation (Phase N+1b)

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_180342_discovery_skip_policy`  
**Production 変更:** 0  
**新規 C3:** 0  
**Standard Workflow 変更:** なし（挿入案のみ）  
**判定:** `ADOPT_CONDITIONAL`（Policy D。Production / default workflow には未配線）

目的は Facet Discovery の増強ではない。

> TDA において、いつ Discovery を起動すべきか

を既存 adapter だけで確定する。

```bash
python ai_tool/run_tda_discovery_skip_policy_evaluation.py
pytest tests/ai_tool/project_audit/test_discovery_skip_policy.py -q
```

---

## 判定（先に結論）

**Conditional automatic Discovery は成立する。** 常時起動も、常時スキップも採用しない。

- **起動:** 調査・Version・環境・API・License・比較・実行可能性・Tool化・条件変更・既存 Research への follow-up、および不明ドメインの確認。
- **Skip:** LLM-only 知識質問、単純コード生成。Gate が `RESEARCH_NOT_REQUIRED` でも、比較 / 作れそう / 曖昧 follow-up は Skip しない。
- **挿入位置:** Capability Discovery の後、Research Reuse / Relevant Routing の前（Phase N+1 案 C）。
- **いまやること:** Experimental のまま。`facet_routing` デフォルト `"off"` は維持。`standard_workflow.py` は未変更。

成功は起動回数ではない。Policy D は 18 件中 **12 回だけ**起動し、False Discovery 0 / Missed Discovery（REQUIRED）0。

---

## 1. Discovery 自動起動条件

Policy D（採用候補）は `discover_facets` を判定に使わない（循環を避ける）。

`DISCOVERY_REQUIRED`（起動する）:

* 要求に調査信号がある（調べ / 最新 / Version / 環境 / API / License / 比較 / 動かせ / 作れそう / Tool化 / 前回調査 / 条件変更）
* または Requirement Gate が `RESEARCH_REQUIRED`
* または follow-up かつ ResearchStore に既存レコードがある
* または Goal Abstraction が research 側（skip パターン以外）

`DISCOVERY_OPTIONAL`（起動するが Facet を確定しない）:

* 曖昧 follow-up（その環境なら / さっきの方法を別の環境 / これToolにできる？）
* 未知ドメイン（FooBar 等）→ `UNKNOWN_DOMAIN` + `CLARIFICATION_REQUIRED`

実装: `ai_tool/experimental/development_assistance/discovery_skip_policy.py`

---

## 2. Skip 条件

`DISCOVERY_SKIP`（起動しない）:

* `とは何ですか` / `for文を教えて` などの単純知識（S1）
* `コードを書いて` / `関数を作って` / CSV・JSON 読み込みコード（S2）
* 調査語が無いこと。`調べて` がある要求は Skip パターンより優先しない

Gate の LLM-only と Skip は一致しない。Gate だけに頼ると比較・曖昧・未知ドメインを落とす。

---

## 3. False Discovery

定義: Skip すべき要求で Discovery を起動し、研究用 Facet（Version / Environment / License 等）を出したこと。

| Policy | 不要起動 | False Discovery（Facet 生成） |
|--------|----------|-------------------------------|
| A Always | 6（S1+S2） | 0（empty `needed` では Routing dump しない） |
| B Gate | 0 | 0 |
| C Signal | 0 | 0 |
| D Goal+Gate+Store | 0 | 0 |

Policy A は Facet 洪水にはならなかったが、**起動そのものが悪化**（後述コスト）。  
以前の失敗モード: empty `needed_facet_ids` を keyword Routing に渡すと、`Pythonのfor文` でも `python_version` が付く。Workflow 挿入時は **needed が空なら Routing しない**。

S2c「PythonでJSONを読むコードを書いて」: Policy D は Skip。License / CUDA / Docker は出さない。

---

## 4. Missed Discovery

定義: `DISCOVERY_REQUIRED` なのに起動しない。最重要指標の一つ。

| Policy | Missed REQUIRED | Missed OPTIONAL（確認漏れ） |
|--------|-----------------|------------------------------|
| A | 0 | 0 |
| B | **2（S5 比較, Q5 作れそう）** | **4（U1, Q3, Q4, Q6）** |
| C | 0 | 0 |
| D | 0 | 0 |

M1「AをPython 3.12で動かせるか調べて」は C/D で起動。`python_version` 取得。Gate-only でもここは起動する（Version + 調べ）。

Gate-only が見落とすのは **調べてが無い比較** と **作れそうか見て**。Phase N の Cycle/API と同型。

---

## 5. Relevant Recall

Discovery 起動後、期待 Facet / 概念を取れたか（起動判定とは別）。

Policy C/D: **0.80**

内訳:

* S4 環境 / S6 License / M1 Python / S5 比較概念: 1.00
* **S3 API 調査: 0.00（catalog id）** — 起動は正しい。既存 cue は `このAPI` / `apiを使える` が狭く、「使えるAPIを調べて」では `version` / `api_availability` が空。Keyword dump で埋めない（意図的）。RECORD: API cue 拡張。これは Skip 失敗ではなく **cue 表の穴**。

---

## 6. Irrelevant Suppression

Skip 対象でノイズ Facet を出さない率。

Policy C/D: **1.00**（起動しない）  
Policy A: **1.00**（起動するが empty needed → Routing off）

---

## 7. Web Search 削減

本 fixture は既存 Research があるため、全 Policy で `searches_estimate = 0`。検索回数の差は測れない。

削減として測れたのは **Discovery 起動 18→12**（S1/S2 の 6 件を止める）。不足分 Web Research は Reuse 後に回す前提のまま。

---

## 8. Research Reuse

Policy D: `research_reuse_count = 12`（follow-up が `plan_follow_up` に乗った件数の reusable 合計）。  
Q1「もう少し調べて」は全件再調査にしない。Python 3.12→3.13 は Python だけ missing、CUDA / License は保持。

---

## 9. Follow-up continuity

```text
① Aについて調べて     REQUIRED  起動。この時点では cue なし → catalog 空
② Python 3.12の場合だけ  python_version 追加
③ CUDA 12.3では？        cuda 追加。Python を失わない
④ Windowsなら？          os 追加
⑤ RTX 3060 12GBなら？    hardware / vram 追加
⑥ Bと比較して            比較概念。acc を捨てない。full_reresearch=False
```

`continuity = true` / `all_invoked = true`。毎回全 Research を再構築しない。

---

## 10. Version Isolation

A 5.15 vs 5.17 メモに対し「A 5.15で使いたい」:

**PASS。** 5.17 を 5.15 へ適用する判定は出さない。conflict envelope 保持。

---

## 11. Unknown Preservation

Research: CUDA 12.3 対応、Python 3.13 は公式情報なし。  
要求: 「Python 3.13で使える？」

**Python 3.13 = missing / UNKNOWN。** CUDA 対応から Python 対応を推論しない。

---

## 12. Conflict Preservation

Official: Python 3.12 supported / Third-party: Python 3.13 supported を **両方保持**。Discovery は片方を消さない。Decision Support へ渡す材料。

---

## 13. Ambiguous request handling

| 要求 | 判定 | 推測して Facet 確定したか |
|------|------|---------------------------|
| Aについてもう少し調べて | REQUIRED（調べ） | しない。Store の `Aについて`→RR-A は既存参照 |
| 前に調べたAを使いたい | REQUIRED | RR-A に bind |
| その環境ならどう？ | OPTIONAL | `その環境` UNRESOLVED。推測しない |
| さっきの方法を別の環境でも使える？ | OPTIONAL | 方法を推測しない |
| Aを実際に作れそうか見て | REQUIRED | 起動のみ。feasible 判定は出さない |
| これToolにできる？ | OPTIONAL | 確認要求。OSS Facet を発明しない |

---

## 14. Unknown domain handling

「FooBarという特殊な装置をTool化したい」

* Policy D: `DISCOVERY_OPTIONAL` + `unknown_domain`
* Python / CUDA / Docker / License を **作らない**
* Gate-only は Skip → 確認機会を逃す（Missed OPTIONAL）

---

## 15. Policy A/B/C/D 比較

| | A Always | B Gate | C Signal | D Goal+Gate+Store |
|--|----------|--------|----------|-------------------|
| 起動回数 | 18 | 6 | 12 | **12** |
| 不要起動 | 6 | 0 | 0 | **0** |
| False Discovery | 0* | 0 | 0 | **0** |
| Missed REQUIRED | 0 | **2** | 0 | **0** |
| Missed OPTIONAL | 0 | **4** | 0 | **0** |
| Recall | 0.80 | 0.60 | 0.80 | **0.80** |
| Suppression | 1.00 | 1.00 | 1.00 | **1.00** |
| 採用 | REJECT | REJECT | ほぼ同等 | **採用候補** |

\*A の False Facet は、empty needed を Routing に流さない限り 0。流すと S1b/S2 で `python_version` が付く。

C と D はこのセットでは起動集合が同じ。D を選ぶ理由は Standard Workflow 上の材料（Gate + Goal + Store）を **Discovery 本体の前に** 使えること。C の信号表だけだと Gate 拡張と二重管理になる。

起動回数の多さは成功ではない。A は最多で最悪（不要 6）。B は最少だが Miss が許容できない。

---

## 16. 最適な Workflow 挿入位置

案 C を維持。**実装はまだしない。**

```text
Requirement
 → Gate（LLM-only かつ skip パターンなら Early Exit）
 → Goal Abstraction
 → Capability Discovery
 → classify_discovery(policy=D)
      SKIP     → Discovery / Routing しない
      REQUIRED → discover_facets → needed があれば Relevant Routing → Reuse
      OPTIONAL → discover_facets（確定禁止）→ UNRESOLVED / CLARIFICATION
 → 不足分のみ Web Research
 → Decision Support
 → Tool Spec / Feasibility
```

`run_standard_workflow(..., facet_routing=)` のデフォルト `"off"` は維持。採用するなら別フラグ（例: `facet_discovery="conditional"`）を Experimental に足す案を、実装前にもう一度判定する。

責務は混ぜない。Discovery は「何を知る必要があるか」まで。safe / feasible / どちらを使うかは Decision Support / Feasibility。

---

## 17. REUSE / RECORD / DEFER / EXPERIMENTAL / REJECT

| 概念 | 判定 |
|------|------|
| Conditional skip policy adapter | **EXPERIMENTAL** |
| Always-on Discovery | **REJECT** |
| Gate-only 起動 | **REJECT** |
| Discovery が判定まで行う | **REJECT** |
| Cross-Facet Reasoning / Graph / Matrix / KB / RAG / Vector DB / General Reasoning | **REJECT** |
| 「Aについて」の named bind / API cue 拡張 | **RECORD** |
| Docker→VirtualBox envelope drop | **EXPERIMENTAL**（helper。Graph Core ではない） |
| Goal Abstraction / Capability Discovery / Facet Discovery / Routing / Reuse / Decision Support | **REUSE** |

---

## 18–19. Production / C3

```text
Production changes = 0
New C3 Core = 0
```

変更は experimental adapter + harness + テスト + 本ドキュメントのみ。

---

## 20. 次 Phase 候補

1. Experimental `standard_workflow` に `facet_discovery="off"|"conditional"` を **提案どおり実装**（デフォルト off）。Phase F ADOPT を壊さないこと。
2. S3 API cue を RECORD どおり最小拡張（Discovery 増強が目的なら別 Phase）。
3. 実 Web Search 件数差（fixture ではなく live / stub 検索）で費用を再測。

---

## Discovery を起動して悪化したケース

1. **Policy A × S1/S2:** 知識質問・コード生成で 6 回不要起動。Gate 比で Discovery は約 **9×** の相対時間。Facet 洪水は empty-needed 抑制後は起きないが、起動コストは無駄。
2. **empty needed → keyword Routing:** 抑制しないと `Pythonのfor文` / JSON コードに `python_version` が付く。Workflow に入れるなら禁止。
3. **S3:** 起動は正しいが既存 cue が API を拾わず catalog 空。起動したのに Routing 材料が増えない（cue 穴。Skip 失敗ではない）。

## Discovery を Skip して見落としたケース

1. **Policy B × S5:** 「AとBを今の環境で比較して」— Gate は `調べ` も Version 数字も無く `RESEARCH_NOT_REQUIRED`。比較 Facet が走らない。
2. **Policy B × Q5:** 「作れそうか見て」— 実行可能性の確認が要るのに Skip。
3. **Policy B × U1/Q3/Q4/Q6:** 未知ドメインと曖昧 follow-up で確認を出さない。

Policy D では上記 Miss は 0。

---

## 費用（relative overhead）

同一要求「Aを Windows + RTX 3060 + Python 3.12 で動かせるか調べて」、40 回平均:

| 段 | ms | Gate 比 |
|----|-----|---------|
| Gate only | 0.008 | 1.0 |
| Gate + skip policy | 0.033 | ~4 |
| Gate + Discovery | 0.072 | **~9** |
| Gate + Discovery + Routing | 0.078 | ~10 |
| Gate + Reuse plan | 0.009 | ~1 |

LLM token は本評価では 0（決定的 cue）。Discovery は安いがゼロではない。だから LLM-only で回すな、が定量的にも言える。

---

## Core Gate

```text
Cross-Facet Reasoning Core  REJECT
Facet Graph Core            REJECT
Facet Matrix Core           REJECT
Knowledge Base              REJECT
RAG / Vector DB             REJECT
General Reasoning Engine    REJECT
```

既存構造で不足が実証されたのは「いつ起動するか」の **薄い分類器** であり、推論エンジンではない。
