# テスト改善ループ v0 凍結

**人間向け表示名:** テスト改善ループ  
**内部ID:** `test_improvement_loop`  
**正本:** `research/test_improvement_loop/`  
**状態:** v0 凍結 / Experimental / 名称変更後 Regression 確認済み / Production 未統合  
**記録日:** 2026-09-09

旧名称: Auto Upgrade System v0  
旧 path: `research/auto_upgrade_system/`（互換 alias。`runs/` は正本への junction）

---

## 何のために作ったか

テストで発見した System 上の問題を、個別パッチではなく **一般化した改善候補** として、段階を飛ばさずに試験するため。

Orchestrator が stage / n 上限 / confirm / 停止を所有する。LLM の提案で stage を飛ばさない。

## 標準テストとの違い

| | 役割 |
|---|---|
| 標準テスト | 問題を見つける |
| テスト改善ループ | 見つかった問題を System 改善候補へ変え、安全に試験する |

pytest PASS は、そのテスト範囲の成功だけを意味する。仕様完成や Production 採用ではない。

---

## 現在できること

- Case 取込
- target layer 分類
- 一般則としての改善（Q番号 allowlist にしない）
- 1 → 確認 → 5 → 確認 → Target → Holdout 制御（stage skip 禁止）
- Before / After
- Regression（true AUTO 脱落検知を含む）
- Validation Gate（hidden_eval を evaluator として stage confirm に接続。adopted 本文は Local に送らない）
- Human Review Packet

名称変更後の基本動作と関連 Regression は確認済み（2026-09-09）。旧 import は正本と同一クラス。過去 Run と HUMAN_REVIEW / Before / After は保持。

## 現在保持している Experimental 一般則

Adoption Gate 側に保持。本ループが Production へ入れたわけではない。

1. `cardinality_index_or_head_select`（Gate 1、証拠 Q31）
2. `polarity_fork_unclosed`（Gate 2、証拠 Q2）
3. `shared_keyword_family_prefer`（Gate 1、証拠 Q36）

参照 run（本文は書き換えない。Git 保全は次の2 Run）:

- Q2 / Q31: `research/test_improvement_loop/runs/20260908T223431Z/`
- Q36: `research/test_improvement_loop/runs/20260908T224940Z/`

## 現在できないこと

- 上位 LLM による Failure分析 → 一般化 → Candidate生成 の完全自動 Loop
- Production Runtime 統合
- 自動 Promote
- 全 Upgrade 種別への汎用対応（v0 は H4 Adoption Gate を主対象にした薄い層）
- Human Approval 省略
- 本ループ自身による自動修復（名称整理も通常の Cursor 作業として実施した）

---

## 凍結の意味

今後しばらくは、人間が実験を見ながら進める。v0 資産として凍結する。

凍結は廃棄ではない。再開トリガーが来るまで、新しい自動 Loop や Production 統合に着手しない。

コード入口:

- `research/test_improvement_loop/orchestrator.py`
- `research/test_improvement_loop/schema.py`
- `research/test_improvement_loop/validation_gate.py`
- `research/test_improvement_loop/adapters/h4_gate.py`
- `research/test_improvement_loop/run_v0.py`
- `research/test_improvement_loop/run_q36_case.py`

---

## 再開トリガー

次のいずれかが観測されたとき、この凍結を開いてよいか人間が判断する。

- テストケースが増えて人間が追えなくなった
- 同種 Failure が繰り返される
- Cursor / grokkun / Codex / Local LLM の並行開発で改善案件が増えた
- Failure分析の自動化が必要になった
- Production 統合を検討する段階になった
- 上位 LLM による Failure分析 → 一般化 → Candidate生成 を独立 Phase として始める指示が出た
