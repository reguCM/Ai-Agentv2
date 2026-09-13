# TDA Generalized Facet Discovery Evaluation (Phase N+1)

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_175138_generalized_facet_discovery`  
**Production 変更:** 0  
**新規 C3:** 0  
**判定:** `GENERALIZED_PASS`（構造。Cue 表そのものはまだドメイン拡張が必要）

仮説 H-N1:

> 要求から判断・調査に必要な情報の種類（Facet）を抽出し、対応する既存 Research を選択再利用する処理は、UR 固有ではなく TDA 上位概念として成立する。

```bash
python ai_tool/run_tda_generalized_facet_discovery.py
pytest tests/ai_tool/project_audit/test_generalized_facet_discovery.py -q
```

---

## 1. Generalization 結果

**成立するのは「形」であり、自動で任意ドメインを理解するエンジンではない。**

同じ Experimental adapter（`discover_facets` → `route_relevant_facets(needed_facet_ids)` → `plan_follow_up`）が、Python / Docker / API / License / Hardware / 比較で UR Facet を漏らさず動いた。

Generic Docker 要求は `ursim` / `control_authority` を引かない。URSim+Docker のときは従来どおり UR 環境 companion を付ける。無理な同一 Facet 押し込み（Control Authority = License）はしていない。

Cue を足さないドメインは依然として落ちる。これは Reasoning Core が要る証拠ではなく、**cue 表がドメイン知識である**ことの証拠。

---

## 2–4. ドメイン別 Recall / Suppression / Search

| Domain | Mode C Recall | 備考 |
|--------|---------------|------|
| python_version | 1.00 | 3.12 は version_facts 再利用、検索 0 |
| docker_environment | 1.00 | Docker/Storage。Python/CUDA/License 非選択 |
| api_capability | 1.00 | 存在確認 Facet。使うべきかの判定は出さない |
| license | 1.00 | License。Python/CUDA 非選択 |
| hardware_environment | 1.00 | Hardware/VRAM/OS。「動く」判定なし |
| comparison | 1.00 | 概念セット。Mode B は概念を出さない |
| multi_facet | 1.00 | 既存 3.12/CUDA/Windows/RTX は再検索しない |
| version_isolation | 1.00 | Python だけ missing。5.17→5.15 暗黙適用なし |
| llm_only JSON | n/a | Discovery **起動しない** |

Mode 比較（JSON 以外）:

| | Recall | Suppression | 平均検索 C |
|--|--------|-------------|------------|
| **A** Goal + RequirementFacets | **0.28** | 1.00（出さない） | — |
| **B** Record 全件 | **0.89** | **0.32** | — |
| **C** Discovery → Routing → Reuse | **1.00** | **1.00** | **0.4** |

Mode B の Recall 0.89 は比較ケースが「概念」であり全件 dump では埋まらないため。Noise は高い。

C の reused mean 2.5 / new 0.3。不足 Facet だけが検索対象。

---

## 5. Follow-up 連続性

```text
① Aについて調べて
② Python 3.12 だけ
③ その場合 CUDA 12.3 では？
④ Windows なら？
⑤ RTX 3060 12GB なら？
⑥ 前の結果と B を比較して
```

実測: 毎回 `full_reresearch=False`。②のあと ③で **Python 3.12 セッションを保持**したまま CUDA を追加。前回 Facet を消さない。

---

## 6–7. Version Isolation / Unknown·Conflict

- A が Python 3.12 + CUDA 12.3 のとき、新要求 3.13 + 12.3 → **Python だけ missing**。CUDA は再利用。
- A 5.15 vs 5.17 メモ → `conflict` 保持。5.17 を 5.15 へ適用する判定は出さない。
- API ケースは availability / currentness を Unknown 側の概念として保持（「今使える＝Yes」とは書かない）。

---

## 8. LLM-only Early Exit

「JSONをPythonで読み込む方法を教えて」→ Gate `RESEARCH_NOT_REQUIRED` かつ Discovery `research_needed=False` → **Discovery を起動しない**。検索 0。

失敗して直した点: 当初 Mode C は Gate 終了なら常に Discovery を飛ばし、**API 確認・比較要求まで JSON と同じ扱いで落ちた**。Cycle（Phase N-12）と同型。  
修正後: Gate 終了かつ Discovery が need を出さないときだけ skip。

---

## 9. Mode A / B / C

期待どおり **A 低 Recall、B 高 Recall+高 Noise、C 高 Recall+低 Noise**。数値は成功扱いの前提ではなく実測。

Facet Discovery は safe / feasible / build / correct を出さない（テスト保証）。

---

## 10. Workflow 挿入地点

Goal Abstraction の L0–L3 は Facet スロットを持たない。Capability Discovery の名前は TDA モジュール名であり Research Facet ではない。

**推奨 C（C3 化しない）:**

```text
Requirement
→ Gate
→ L0–L2 Goal Abstraction
→ Capability Discovery
→ Facet Discovery     ← 追加（default off のままが安全）
→ Research Reuse / Relevant Routing
→ Web（不足のみ）
→ Decision Support
→ Tool Spec
```

Discovery の出力は Routing / Reuse の検索キー。Goal の前に置いても Goal はそれを読まない。

---

## 11. 上位概念への引き上げ

| ドメイン固有 | 共通 Facet | 押し込まないもの |
|--------------|------------|------------------|
| UR Control Authority | ownership / state | License |
| Python Tool | environment / version / dependency | — |
| Docker Tool | container / runtime / storage | URSim（generic A では付けない） |
| API Tool | api / version / availability | 「使うべき」 |
| License Tool | license / distribution / dependency | CUDA/Python |

階層は **nested dict**（Graph Core ではない）。

---

## 12. Idea Preservation

RECORD:

- GPU passthrough Facet（Docker+GPU。今回 Unknown）
- License の distribution / modification サブ Facet

REASONING / Graph / RAG / Vector DB: **REJECT** のまま。Core は作っていない。

---

## 13–14. C3 / Production

新規 C3: **0**  
Production 変更: **0**

---

## 失敗した条件（成功話で終わらない）

1. **Gate 一括 skip** は JSON 以外（API 確認、比較、Cycle）を落とす。Discovery `research_needed` と AND しないと一般化に失敗する。
2. **Cue 未登録のドメイン**は Mode A と同じく Recall 0。汎用推論ではない。
3. **曖昧 Follow-up**（そのPython版 / その環境 / 前のやつ / さっきの条件 / 別の方法）は推測せず `UNRESOLVED` / `CLARIFICATION_REQUIRED`。解けない。
4. Mode B は比較に必要な **概念** を出さない（全件 Facet ID だけ）。
5. 「上手く動いた」は **fixture 上の cue 表の範囲**。オープンワールドの Requirement では未証明。

---

## 15. 次 Phase 候補

- Standard Workflow へ `facet_discovery` を **default off の optional** として挿すか（C 地点）。今回はまだ挿していない。
- Gate と Discovery の skip 条件を Workflow 側で文書化。
- 新規 Cue は IdeaCatalog RECORD 経由。Core 化しない。
- Cross-Facet Reasoning / Graph / RAG は今回も **REJECT**。

---

## 判定の読み方

`GENERALIZED_PASS` = **同じ処理形が UR 以外でも成立し、UR 漏れと JSON 肥大化が起きない。**  
= Facet Discovery を今すぐ Production 既定にする、ではない。Adapter は EXPERIMENTAL。Cue 拡張はドメイン作業であり Reasoning Core ではない。
