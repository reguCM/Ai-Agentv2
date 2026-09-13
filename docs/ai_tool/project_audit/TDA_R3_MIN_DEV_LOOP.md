# 最小開発ループは fixture で一本通る。Production と Cursor API にはまだ繋がない

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_194658_r3_min_dev_loop`  
**Production 変更:** 0  
**新規 C3:** 0  
**既定 Workflow 変更:** なし（`facet_discovery="off"`）  
**総合判定:** `PARTIAL_PASS`  
**機械的経路（Experimental）:** `PASS`  
**Production 接続:** `REJECT_NOW`

## 通したループ

```text
Requirement
  → Memory / bind / diff / select
  → 必要 Facet だけ LLM 材料へ
  → Development Spec
  → Cursor 相当（runtime.py / test_runtime.py）
  → Test
  → Session.last_test_result
```

実 Cursor API は使っていない。独立 fixture のみ。`liba_demo_tool` は上書きしていない。

## 修正前の失敗

同じ `runtime.py` を直したあと、古い Version のまま Test が FAIL のまま残った（モジュール再読込）。  
内容ハッシュでモジュール名を分け、`__pycache__` を消して再実行した。**新 Core は不要。**

## 実測

| 項目 | 値 |
|------|-----|
| 全 Facet（100 Record） | **490** |
| LLM へ渡した Facet | **4** |
| 不要 Facet / Record 混入 | **0** |
| Research 回数（3.13 変更） | **1** |
| 成功 Test | **PASS** |
| FAIL→再評価後 Test | **PASS** |

20 Record: 全 90 / LLM 4 / 混入 0 / Test PASS  
100 Record: 全 490 / LLM 4 / 混入 0 / Test PASS

LLM への指示は「この材料から Development Spec を作成せよ」。記憶から探せ、とは書いていない。実 LLM は呼んでいない（材料境界のスタンドイン）。

## 項目

| 項目 | 判定 | 要点 |
|------|------|------|
| R3-1 LLM 入力境界 | PASS | dump_all なし。必要 Facet のみ |
| R3-2 Development Spec | PASS | 安全 / 確実 / 実行可能 を含めない |
| R3-3 Cursor 相当 | PASS | runtime.py 変更 → Test。API 未使用 |
| R3-4 Test 帰還 | PASS | Session.last_test_result に構造化 |
| R3-5 FAIL→再評価 | PASS | 不足は python_version:3.13 のみ。全件 Research しない |
| R3-6 Version | PASS | 3.13 は UNKNOWN。戻した 3.12 は historical 再利用。Test は 3.12 |
| R3-7 混入 | PASS | B/C/D を LLM に渡さない |
| R3-8 LLM 役割 | PASS | 禁止行為（全記憶検索、Version コピー、Conflict 統合）なし |
| R3-9 責務 | PASS | 境界は成立。Cursor API は未実装 |
| R3-10 人間確認 | PASS | `awaiting_human_review` を Session に持てる。UI なし |
| R3-11 成功一本 | PASS | 3.13 / Windows / CUDA 12.3 → Test PASS → Session |
| R3-12 失敗一本 | PASS | わざと 3.12 コード → FAIL → 修正 → PASS |
| R3-13 肥大化 | PASS | 20 / 100 でも LLM は 4 Facet |
| R3-14 Production | REJECT_NOW | 実験条件は満たし得るが未配線・API 未接続 |

## Production 10 条件（実験経路）

1〜9 は実験上 PASS。10 は既定 `facet_discovery=off` を確認。  
満たしても **接続しない**。既定 Workflow に bind/select を載せておらず、Cursor API もない。

## 作らないもの（守った）

Reasoning Core / Graph / RAG / Vector DB / Knowledge Base / 全記憶 LLM / Safety Core / Cursor 本番 API / UI / Avatar / Mobile App
