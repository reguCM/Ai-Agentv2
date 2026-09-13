# 条件付き Facet Discovery の Workflow 接続（Phase O）

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_183121_conditional_discovery_integration`  
**Production 変更:** 0  
**新規 C3:** 0  
**`standard_workflow` 既定値:** `facet_discovery="off"`（未変更）  
**判定:** `ADOPT_CONDITIONAL`

## 目的

これまでの実測（Policy D と Coverage Overlay）を、Experimental な Standard Workflow 経路としてつなぐ。既定動作と Production は変えない。

- **条件付き Facet Discovery**（必要なときだけ必要情報を探す処理）
- **Coverage Overlay**（Cue 表だけでなく、目的・条件・既存 Research から Facet を列挙する層）
- **関連 Facet の取り出し**（Relevant Facet Routing）

## 実施内容

`run_standard_workflow` に実験用引数を追加した。既定は off。

```text
facet_discovery = "off" | "conditional"   # 既定 off
coverage_overlay = True                    # conditional のときだけ効く
facet_routing = "off" | "relevant"         # 既定 off
```

処理順（conditional 時）:

```text
Gate → Goal Abstraction → Capability Discovery
  → 条件付き Discovery（Policy D）
  → Research Reuse
  → 関連 Facet の取り出し
  → 不足分だけ Web Research
  → Decision Support → Tool Spec / Feasibility
```

JSON 等の単純要求は従来どおり Gate で早期終了。Discovery は Skip。Routing もしない。

「人間が途中で操作できる？」は起動するが **Required にしない**。UR の既存 Research があれば Candidate。

## 比較方法

| 方式 | 設定 |
|------|------|
| A 既存 Workflow | discovery off, routing off |
| B Conditional のみ | discovery conditional, coverage なし |
| C + Coverage | coverage overlay あり, routing off |
| D 全部 | coverage + relevant routing |

## 実測結果

| 指標 | A | B | C | D |
|------|---|---|---|---|
| Required Recall | 0.00 | 0.50 | **1.00** | **1.00** |
| False Discovery / 不要流入 | 0 | 0 | 0 | **0** |
| JSON 早期終了 | 維持 | 維持 | 維持 | **維持** |
| 平均 Web Search | 0 | — | — | 0.11（クエリ実体は follow-up 合計 0） |

Follow-up 6 手番: Python 3.12 を保持、CUDA / Windows / RTX を追加、毎回 Full Research しない。検索合計 **0**。

Phase F は **ADOPT のまま**（c3=0）。G / K / N / M / UR H・I（offline）も通過。

## データの流れ（具体例）

要求: 「前に調べたAをPython 3.12で使えるか調べて」

```text
Requirement
  → Gate: RESEARCH_REQUIRED
  → Discovery Policy D: REQUIRED（起動）
  → Coverage Overlay
        Required: python_version, environment, external_evidence
        Candidate: cuda, license（既存から保持。必須と断定しない）
        Unknown: docker（要求していないので発明しない）
  → Research Reuse: assess は no_reuse だが、
        follow-up の missing=0 のため Web Search = 0
  → 関連 Facet の取り出し: python_version, cuda, license
        Conflict「3.12 vs 3.13」を保持
  → Decision Support: coverage を渡す。feasible キーなし
```

以前の既定経路では、この要求でも Discovery 段が無く、判断材料の Facet 一覧が Decision Support に届かなかった。

## 分かったこと

1. **既定 off のまま接続できる。** Phase F の JSON 早期終了は壊れない。
2. Conditional だけでは足りない（B=0.50）。Coverage Overlay で API 言い換え・比較軸が復元される（C/D=1.00）。
3. Gate が RESEARCH_NOT_REQUIRED でも、Policy D が起動する要求（比較の「どちら」、人間操作）は Experimental 経路では Discovery に進む。既定経路は従来どおり Gate で抜ける。
4. 見つけた Facet を全部 Required にしない運用が、Workflow 上でも成立する。

## 分からなかったこと / 取りこぼし

- Cue / 信号表に無い言い換えは、また Skip か空の Coverage になる（表はドメイン知識のまま）。
- `assess_reuse` が `no_reuse` でも follow-up の missing=0 で検索を止めるため、Reuse 段のラベルと実検索がずれることがある。
- 平均 Search が A よりわずかに見えるのは、曖昧要求が Gate を越えるため。Follow-up の実クエリは 0。

## 過剰検出

JSON / 単純コード生成では Discovery を起動しない。License / CUDA / Docker を Decision Support に流さない。

人間操作は Candidate。safe / 操作できる という結論は出さない。

## 再利用状況

既存の Gate / Goal Abstraction / Capability Discovery / ResearchStore / `plan_follow_up` / 関連 Facet の取り出し / Decision Support を再利用。新規 Core なし。

## 今後の判断

**ADOPT_CONDITIONAL。** Experimental フラグとして完成。デフォルトを on にする ADOPT はしない。ライブ利用のあとで再判定する。

## 作らなかったもの

```text
Reasoning Core
Graph Core
RAG / Vector DB
Knowledge Base
Version Matrix Core
```

Discovery に feasible / safe / build / correct をやらせていない。

## Production変更数 / 新規C3数

```text
Production changes = 0
New C3 = 0
facet_discovery 既定 = off
```
