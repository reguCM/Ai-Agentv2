# LLM 仕様候補提案 Phase 1

**日付:** 2026-08-31  
**依頼:** 仕様候補の生成・構造化・仮定/不明点/人間確認の分離・追記保存。自動改善は対象外。  
**実行主体:** Cursor  
**Run:** `runs/ai_tool/20260831_123000_llm_spec_proposal_phase1`  
**Server 確認:** `LocalAgentChat/0.18`（`http://127.0.0.1:8766/`）  
**既存 8765:** ヘッダは `LocalAgentChat/0.16`。今回の API 確認には使っていない。

Cursor live: **NOT OBSERVED**  
Machine Test: **NOT AVAILABLE**  
Git commit: **していない**  
pytest 件数 ≠ 仕様完成。

---

## 判定の分離

| 層 | 判定 |
|----|------|
| 汎用 SpecificationProposal 生成 | **CONNECTED**（`propose_specification`。JSON 必須。自由文は PARSE_FAILED） |
| 追記保存（上書きしない） | **CONNECTED**（`runs/spec_proposals/proposals.jsonl` + `last_proposal.json`。同一要求は version 加算） |
| CONFIRMED / PROPOSED / ASSUMED / UNKNOWN / HUMAN_CONFIRMATION_REQUIRED 分離 | **CONNECTED**（別リスト。混在入力は status で再配置） |
| Policy 評価 | **CONNECTED**（`evaluate_development_work(save=False)`。提案が出ても COMPLETE にしない） |
| Chat `tool_creation` | **CONNECTED**（自由文仕様を構造化保存に置換。Registry 書き込みなし） |
| Chat `development` | **CONNECTED**（仮仕様。従来の `_chat_turn` Tool ループは通らない） |
| Chat 通常（GPU 等） | **NOT_CONNECTED**（意図的。観測 Q&A を仕様ループに混ぜない） |
| Chat `research` | **NOT_CONNECTED** |
| `agent.py` | **NOT_CONNECTED** |
| `create_tool_proposal` | **再利用**（Tool作成時の材料のみ。LLM 仕様生成としては再実装していない） |
| `validate_tool_spec` | **NOT_CONNECTED**（Tool JSON と汎用仕様を同一視しない） |
| 人間修正差分 | **NOT_IMPLEMENTED**（Phase 2。`human_revision` は null） |
| 実装・テスト紐付け | **NOT_CONNECTED**（Phase 3） |
| 傾向分析・自動改善 | **NOT_IMPLEMENTED**（Phase 4–6） |
| UI 処理タブ | **CONNECTED**（最後の提案表示）。ボタンからの live POST クリックは **NOT_OBSERVED** |
| 仕様充足（Phase 1 指示） | **PARTIAL** |

**仕様 COMPLETE とは言わない。**

---

## SPECIFICATION_GAP（入口。仮仕様で進めた）

問題:
全 Chat ターンに仕様候補を強制するか、分類済み開発要求と専用 API にするかが指示書だけでは機械確定しない。

現在確定していること:
- Phase 1 は Request → LLM 提案 → 構造化 → 仮定/不明/人間確認 → 保存
- Tool 仕様と一般仕様は同一視しない
- 自由文だけで保存しない
- 上書きしない

不足していること:
- 「要求を受けた場合」が Chat の全発話を含むか

妥当な候補:
- A: Chat 全ターン強制
- B: `tool_creation` + `development` + `POST /api/spec/propose`（採用）
- C: API のみ

推奨: B

理由:
A は GPU 観測などの実行時 Q&A を仕様設計ループに混ぜ、既存 Chat 経路を大きく変える。修正コストは HIGH。

A で仮実装しても問題が小さいか: **NO**  
間違った場合の修正コスト: **HIGH**（A）/ B は **MEDIUM**（キーワード漏れ）  
人間確認: **OPTIONAL**（仮仕様として記録済み。`entrypoint_assumption` フィールド）

---

## 再利用した既存部品

| 部品 | 使い方 |
|------|--------|
| `create_tool_proposal` | Tool作成要求の材料梱包。Registry 全文は保存しない |
| `evaluate_development_work` | 提案を COMPLETE にしない。`last_policy_eval.json` は上書きしない（save=False） |
| `classify_request` | Chat 分岐。分類器の再実装なし |
| Event / correlation | 既存 `event()`。存在しない Event は作っていない |

`build_spec_draft` / `development_spec_from_materials` / Clarity Gate は **未接続**（TDA 機械 draft / 要求明確化であり、今回の LLM 仕様候補ではない）。

---

## 実測

### pytest（Cursor 実行。Machine Test ではない）

- `tests/ai_tool/spec_proposal` + `test_spec_proposal_api` + 既存 Chat/Matrix ask 回帰: **73 passed**（chat_interface + matrix ask）および当該 kernel は別途 **34 passed** の部分集合で確認
- 自由文 → PARSE_FAILED、COMPLETE にならない
- 同一要求 → version 2、proposal_id 別
- Chat「GPUの状態を教えて」→ jsonl 増えない
- HUMAN_CONFIRMATION_REQUIRED あり → `may_proceed_implementation=false`

### ライブ LLM

- モデル: `qwen3:8b`（configured の 16b ではない。所要時間の都合）
- `proposal_id`: `sp-20260831_032953-d68e7d66`
- `parse_status`: **ok**
- `confidence`: **UNCONFIRMED**（LLM 自己評価 0.85 は `llm_reported_confidence` 側。機械信頼度にしない）
- Policy: `specification_status=NEED_HUMAN_DECISION`（LLM が「データベーススキーマ設計」を人間確認にしたため）。`may_claim_specification_complete=false`
- 実装は JSONL なのに LLM が DB スキーマを人間確認にした。これは **LLM の提案内容**であり、コード欠陥とは判定しない。Phase 4 の差分分析対象になりうる。

### UI

- `GET /api/spec/last` を処理タブで表示。CONFIRMED / PROPOSED / ASSUMED / UNKNOWN / HUMAN_CONFIRMATION_REQUIRED が別表示
- 「仕様候補を提案」ボタンの live クリック: **NOT_OBSERVED**（同じ保存結果の読込は観測済み。kernel live と HTTP テストで POST は確認）

---

## 接続図（Phase 1）

```
Request
  ├─ POST /api/spec/propose          CONNECTED
  ├─ Chat tool_creation              CONNECTED → create_tool_proposal 材料 → LLM JSON → 保存
  ├─ Chat development                CONNECTED（仮）
  ├─ Chat chat / research            NOT_CONNECTED
  └─ agent.py                        NOT_CONNECTED
        ↓
LLM SpecificationProposal JSON
        ↓
parse ok | PARSE_FAILED | LLM_ERROR
        ↓
Policy evaluate（COMPLETE にしない）
        ↓
proposals.jsonl 追記（上書きしない）
```

---

## Phase 2 以降（今回やらない）

未実装: 人間修正差分、実装/テスト紐付け、傾向分析、Improvement Proposal、Policy による自動適用。

人間仕様との差分を「LLM の失敗」と自動判定する経路は **作っていない**。
