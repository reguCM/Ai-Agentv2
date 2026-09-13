# 実Researchでも bind / diff / select は成立する。既存 Workflow への接続はまだ Adapter が要る

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_193559_r2_research_selection`  
**Production 変更:** 0  
**新規 C3:** 0  
**既定 Workflow 変更:** なし（`facet_discovery="off"`）  
**総合判定:** `PARTIAL_PASS`  
**機械的経路（Experimental）:** `PASS`

## 何を測ったか

R1 は手組み fixture の ResearchRecord だった。R2 は既存 TDA パイプライン

`run_tda_case`（search + read_url）→ `add_from_run` → ResearchRecord

で保存した記憶に対して、同じ機械的経路が成立するかを測った。live インターネットは使っていない。取得経路そのものは本番相当の TDA 抽出である。

```text
ユーザー要求
  → Goal / Requirement
  → Facet Discovery
  → ResearchRecord / Session
  → mechanical bind
  → mechanical diff
  → mechanical select
  → 必要な Evidence / Unknown / Conflict だけ
  → LLM
  → Spec / Code / Test
```

LLM に全記憶を渡して選ばせる方式は使っていない。新しい Core は作っていない。

## 修正前に当たった壁

1. **`add_from_run` 直後の `facet_records` は空**（5 Record すべて 0）。既存 `build_research_record` は run に Facet が無いと切らない。このままだと全記憶 Facet 数も slice も測れない。  
   → Experimental Adapter `derive_facet_records` / `enrich_environment_from_candidates` を足して再実行した。ResearchRecord のスキーマは変更していない。

2. **TDA の Python 抽出が `Python library` を先に取り、Version が落ちて `python="Python "` になった。** 否定文の `No CUDA` / `No URSim` も誤検出した。  
   → HTML の語順を直し、Version 無しのときだけ candidate の `all_versions` から補う Adapter を足した。`technology_candidate.py` は触っていない。

## 実測（R2-5）

| Record 数 | 全記憶 Facet | LLM へ渡した Facet | 混入 |
|-----------|--------------|--------------------|------|
| 5 | 15 | **4** | 0 |
| 20 | 90 | **4** | 0 |
| 50 | 240 | **4** | 0 |
| 100 | **490** | **4** | 0 |

100 Record 時の削減率 **0.9918**。R1（304 → 4、削減率 0.9868）と同程度の選択性を維持した。

中心要求「前に調べた技術AをPython 3.13で使えるか調べて」:

- bind: RR-A
- 再調査: **1**（python_version:3.13）
- 再利用: Windows / CUDA 12.3 / License
- Python 3.12: historical
- 3.12 Evidence のコピー: なし
- 技術A固有 Facet `product_api`: Record 上に残る

## 項目結果

| 項目 | 判定 | 要点 |
|------|------|------|
| R2-1 実Research | PASS | パイプライン保存後も bind/diff/select が成立 |
| R2-2 混入 | PASS | B/C/D の Python / CUDA / URSim / Node.js は使わない。E も不要なら不使用 |
| R2-3 機械的 diff | PASS | Py / CUDA / OS / Docker / 同時変更。変わった Facet だけ。既存は消さない |
| R2-4 Unknown / Conflict | PASS | 3.13 は UNKNOWN。Conflict の winner なし。「確実に動く」は出さない |
| R2-5 LLM 入力削減 | PASS | 490 → 4。LLM に整理させていない |
| R2-6 保存形式 | PASS | 既存フィールドで足りる。スキーマ変更なし |
| R2-7 Session 継続 | PASS | 7 手番。戻した 3.12 は historical を再利用。全件 Research しない |
| R2-8 曖昧要求 | PASS | 一意だけ BOUND。複数は UNRESOLVED + clarification_required |
| R2-9 既存 Workflow 接続 | PARTIAL_PASS | 既定 off は維持。Reuse は `no_reuse`。session bind は未接続 |
| R2-10 Cursor 境界 | PASS | Spec の受け渡し項目は確認。接続は実装していない |

## R2-6：既存構造で足りるか

| 欲しいもの | 既存 | 判定 |
|------------|------|------|
| record_id | `research_id` | 足りる |
| session_id | Session 側 | Record に足さない |
| subject / target | `topic` + `environment_facts.label` | 足りる |
| facet | `facet_records`（ingest 後は導出） | スキーマ変更なし |
| version / environment | `version_facts` / `environment_facts` | 足りる |
| evidence / source / timestamp | Facet evidence / `sources` / `checked_at` | 足りる |
| unknown / conflict | `unknowns` / `conflicts` | 足りる |
| historical / current | Session の history / FacetSlot | Record に混ぜない |
| status | Session の evidence | Record トップには無い |

**記憶**（ResearchRecord）と **検索結果**（TDA run）と **現在の要求**（Session）は分けたままにする。

## R2-9 / R2-10

R2-1〜R2-8 が成立したので調査した。

既存 Workflow へ載せる候補:

```text
Goal → Gate → Conditional Discovery → Coverage
  → Experimental bind/diff/select
  → Reuse / Routing → Decision Support
```

実測では experimental で Discovery / Coverage / Routing / Decision Support は通る。ただし **Reuse は session bind を使わず `no_reuse`**。接続には Experimental Adapter が要る。既定 `facet_discovery=off` は壊していない。Production 接続はしない。

Cursor へ渡してよいもの: `tool_name` / `purpose` / `runtime` / `dependencies` / `api_notes` / `unknowns` / `constraints` / `license`  
Local Agent に残すもの: Session / Facet / bind / conflicts / history  

Cursor 本番接続は実装していない。

## 作るもの / 作らないもの

**維持:** Experimental の bind / diff / select。`derive_facet_records`（スキーマを増やさない導出）。

**今は作らない:** Reasoning / Graph / RAG / Vector DB / Knowledge Base、全記憶を LLM に渡す層、Evidence の Version 間コピー、Discovery の feasible / safe / correct、Production 接続、Cursor 本番接続、巨大 Memory Manager。

**Production へ進める条件（未達）:** session bind が Reuse と矛盾しないこと。live インターネットでも混入 0 を再測すること。既定 off を維持したまま experimental フラグだけで再現できること。

## ラベル

```text
RECORD       : TDA パイプラインから保存した ResearchRecord
EXPERIMENTAL : derive_facet_records / enrich / R2 harness
PARTIAL_PASS : 総合（機械的経路は成立、Reuse 未接続）
REJECT_NOW   : Production 接続、Cursor 本番接続、新 Core
```
