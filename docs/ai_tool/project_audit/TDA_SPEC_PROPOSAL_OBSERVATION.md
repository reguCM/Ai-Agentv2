# 仕様提案の観測・修正追記（学習は未確立）

**日付:** 2026-08-31  
**実行主体:** Cursor  
**方針:** 仮仕様の観測・追記蓄積。自動学習・自動改善はしない。  
**Run:** `runs/ai_tool/20260831_151000_spec_proposal_observation`  
**Server:** `LocalAgentChat/0.19`  
**Policy:** `ai_tool/policy/development_policy.json` version **1.1**

Cursor live: **NOT OBSERVED**  
Machine Test: **NOT AVAILABLE**  
Git commit: **していない**

---

## 判定の分離

| 層 | 判定 |
|----|------|
| LLM 提案の JSONL 追記 | **CONNECTED**（既存。`origin=llm_proposal` を新規行に付与） |
| 原本非上書き | **CONNECTED**（人間修正・問題記録は別 `proposal_id`） |
| 人間修正追記 | **CONNECTED**（`append_human_revision` / `POST /api/spec/revise`。LLM なし） |
| 修正理由 | **CONNECTED**（空なら `revision_reason_status=UNKNOWN`。保存はする） |
| 問題記録 | **CONNECTED**（`append_problem_record`。原因欠落は `cause_status=NOT_DETERMINED`） |
| LLM 正誤の自動判定 | **NOT_IMPLEMENTED**（`llm_judgment=NOT_IMPLEMENTED`。正しい/間違いを付けない） |
| 意味的差分分類 | **NOT_IMPLEMENTED** |
| 学習方法 | **NOT_DETERMINED**（Policy と各レコードに明示） |
| 自動改善 | **NOT_IMPLEMENTED** |
| Chat Job / session への proposal_id | **CONNECTED** |
| 実装・テスト run の実書き込み | **NOT_CONNECTED**（ID 欄はある。writer は呼び出し側が渡したときだけ） |
| Cursor 内部ログ | **NOT_OBSERVED**（推測で埋めない） |
| 仕様完成 | **しない**。観測基盤としても **PARTIAL** |

pytest PASS ≠ 仕様正しい ≠ 人間と同等。

---

## 仮仕様（明示）

- 人間修正は親の `request_id` を継承する（要求文が変わっても系譜を切らない）。これは設計レビュー論点 B の仮採用。
- `version` は同一 `request_id` の通番のまま。`origin` で LLM / 人間 / 問題を区別する。
- 過去 JSONL（origin 無し）は書き換えない。無い origin は読取時に推測しない（今回の新規行だけ `origin` がある）。

---

## 実装済み / 未接続

実装済み: 人間修正 API、問題記録 API、parent 一覧、Policy への学習未確立の明示、Chat の proposal_id 関連付け。

未接続: agent.py、通常 Chat、実装パイプライン、テスト run 自動紐付け、差分分類器。

未実装: 自動学習、Policy 自動変更、LLM 評価器、ファインチューニング。
