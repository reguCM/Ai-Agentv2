# Phase P-7〜P-12：記憶増量と機械的な再配分

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_190654_phase_p7_memory_redistribution`  
**Production 変更:** 0  
**新規 C3:** 0  
**`standard_workflow` 既定値:** `facet_discovery="off"`（未変更）  
**判定:** `PASS`

## 目的

記憶量が増えたとき、LLM に全件を読ませて整理させるのではなく、

```text
記憶全体
  → 機械的 bind
  → 機械的 Facet diff
  → 機械的 selection
  → 必要部分だけ LLM
  → Decision / Spec / Code / Test
```

が成立するかを実測する。この構造は **設計候補として記録するだけ**。今は Core にしない。

## 実測結果（結論）

マトリクスを大きくすると LLM の負荷が増える、というより、**機械的な bind / diff / select で LLM に渡す Facet を小さくできた**。

| 比較 | 数 |
|------|----|
| 全記憶 Facet（5 Record に分散） | **19** |
| LLM へ全件渡す場合 | **19** |
| 機械的選択後に LLM へ渡す | **4** |
| 削減率 | **0.79** |
| 再調査対象（P-9） | **1**（Python 3.13） |
| 再利用（P-9） | **3**（Windows / CUDA 12.3 / License Y） |
| 別 Record の混入 | **0** |
| live Web Search | **0** |

URSim / ROS / Node.js / Docker は、技術 A の手番に勝手に入っていない。

---

## 各項目

| 項目 | 判定 | 内容 |
|------|------|------|
| P-7 記憶量を増やす | PASS | RR-A〜E の 5 件。1 件の巨大 Record ではない |
| P-8 その技術A | PASS | session id があれば RR-A。無ければ UNRESOLVED。session が B のときは A を当てない |
| P-9 1 Facet 変更 | PASS | Python 3.12→3.13 は UNKNOWN。Windows / CUDA 12.3 / License Y は保持。3.12 はコピーしない |
| P-10 別 Facet 変更 | PASS | CUDA 12.3→12.4 だけ不足。Python 3.13 の UNKNOWN を消さない。全件再検索しない |
| P-11 過去へ戻す | PASS | Python 3.12 を historical から confirmed に戻す。3.13 は 3.12 の Evidence にしない。CUDA 12.4 は残る |
| P-12 LLM へ渡す量 | PASS | 全件 19 vs 選択 4。混入 0 |
| 重複 Facet（一意） | PASS | 「WindowsでPython 3.12の方」→ RR-WA のみ |
| 重複 Facet（曖昧） | PASS | 「Windowsの方」→ UNRESOLVED（推測しない） |

## 記憶 / 選択 / LLM / 再調査

P-9「Python 3.13で使えるか調べて」:

- 全記憶 Facet 数: 19
- 選択 Facet 数: 4（python_version, os, cuda, license）
- LLM へ渡した Facet 数: 4
- 再調査 Facet 数: 1
- 混入した不要 Facet: なし

P-10「CUDAは12.4の環境で」:

- 再調査: `cuda:12.4` のみ
- Python 3.13 は UNKNOWN のまま保持（再 UNKNOWN 化も全件再検索もしない）

## Version / Conflict / Unknown

- Python 3.13: UNKNOWN。3.12 Evidence は historical。コピーなし
- CUDA 12.4: UNKNOWN。12.3 は historical。コピーなし
- 戻した Python 3.12: confirmed（historical_restore）
- Record A の Conflict「3.12 vs 3.13」は残している
- Docker / URSim は A の session に足していない

最終 session Facet:

- python_version = 3.12 confirmed
- os = windows confirmed
- cuda = 12.4 UNKNOWN
- license = Y confirmed

## 既定 Workflow との差

既定は `facet_discovery="off"` のまま。JSON 等の単純要求は従来どおり Gate で終わる。

複数 Record が入った store で「Python 3.13で使えるか」を conditional + relevant で流すと、Routing は `python_version` を返す。今回の Adapter はそれに加え、**どの Record の python_version か**を session id で固定する。文字列「python」だけで B の 3.13 を混ぜない。

既定経路にこの bind / slice は接続していない。

## 今後 Core 化すべきか

**今はしない（REJECT_NOW）。**

成立したのは「小さく切ってから LLM に渡す」という候補である。Reasoning Core / Graph / RAG / Knowledge Base にはしない。LLM に 19 件を渡して整理させる方向にも進まない。

次に試してよいのは、experimental 経路だけへの接続（既定は off）に留める。

## ラベル

```text
RECORD       : 5 件の fixture、Version 履歴
EXPERIMENTAL : pointer / session / memory_slice
REJECT       : 新 Core、全記憶を LLM に渡す整理層
REJECT_NOW   : memory_slice の Core 化
```

Phase F ADOPT、Phase O / P の既存テストは維持。
