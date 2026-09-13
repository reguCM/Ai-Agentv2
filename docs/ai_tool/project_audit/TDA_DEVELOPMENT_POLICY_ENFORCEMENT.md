# 開発 Policy 実効機構（最小接続）

**日付:** 2026-08-31  
**依頼:** 開発思想を Agent の実行時判断を拘束する契約にする。大規模再実装はしない。  
**実行主体:** Cursor  
**Run:** `runs/ai_tool/20260831_114500_development_policy_enforcement`  
**Server:** `LocalAgentChat/0.17`  
**機械契約:** `ai_tool/policy/development_policy.json`  
**Cursor 文章:** `.cursor/rules/agent-development-policy.mdc`（v1.2 で JSON を機械正本として指す）

Cursor live: **NOT OBSERVED**  
Chat 通常ターン → Policy evaluate: **NOT_CONNECTED**  
Machine Test: **NOT AVAILABLE**  
Git commit: **していない**

---

## 判定の分離（この案件自体）

| 層 | 判定 |
|----|------|
| Policy定義 | **CONNECTED**（JSON 契約 + Cursor 文章参照） |
| Policy読込 | **CONNECTED**（`load_development_policy`。失敗時は完成禁止） |
| Policy判断 | **CONNECTED**（`evaluate_development_work`。LLM なし） |
| Policy強制 | **PARTIAL**（評価 API / 完成申告テキストは機械上書き。Chat ターンは未接続。Agent の Tool ループ自体は止めない） |
| Completion判定 | **CONNECTED**（項目リストを渡したとき。空リストでは COMPLETE にしない） |
| Human相談 | **PARTIAL**（`NEED_HUMAN_DECISION` で実装進行を false。Question/Pending/再開ループは **NOT_IMPLEMENTED**） |
| テスト | Cursor 実行: `tests/ai_tool/policy` + `test_policy_api` **PASS**（17 件中、当該ファイル） |
| 仕様充足 | **PARTIAL**（実効の核はできた。開発オーケストレータ全体ではない） |
| 未観測 | Cursor 製品が mdc を注入する内部 |
| 未確定 | 正本を「文章のみ一本化」するかは運用。機械正本は JSON と明示した |
| 未接続 | `run_chat_turn`、Research Pipeline、`execution_gate`、Matrix |

**仕様 COMPLETE とは言わない。** pytest が通ったことと混同しない。

---

## 正本（今回決めたこと）

二重管理を避けるため役割を分けた。勝手な一本化ではなく、調査で POLICY_SOURCE_UNCLEAR だったものへの **仮でない接続方針**:

| 役割 | ファイル |
|------|----------|
| Cursor が読む説明 | `.cursor/rules/agent-development-policy.mdc` |
| AI-Agent が読む機械契約 | `ai_tool/policy/development_policy.json` |

JSON が読めない → `specification_status=NOT_OBSERVED`、完成申告不可。

---

## 何が実際に変わったか（実測）

1. `evaluate_development_work(items=[{PARTIAL}], tests_passed=True, claim_specification_complete=True)`  
   → `test_status=PASS` かつ `specification_status=PARTIAL` かつ `may_claim_specification_complete=false` かつ `blocked_complete_claim=true`  
   **テスト成功だけでは完成にならない。**

2. 空チェックリスト + 完成申告  
   → COMPLETE にならない。

3. 全項目 CONNECTED、tests_passed=None  
   → 仕様は COMPLETE、test_status は NOT_OBSERVED（テスト未実施でも仕様 COMPLETE は項目状態だけ。報告では両方出す）。

4. `NEED_HUMAN_DECISION`  
   → `may_proceed_implementation=false`。

5. `apply_final_answer_policy("GPUは62度です。")`  
   → **applied=false**（通常回答は書き換えない）。

6. `apply_final_answer_policy("実装完了しました。仕様完成です。")`  
   → 末尾に `[DEVELOPMENT_POLICY] ... may_claim_specification_complete=false` を機械付与。  
   **agent.py の最終回答経路でこの関数を呼ぶ。**

7. HTTP `POST /api/policy/evaluate` で NOT_CONNECTED 項目 + tests_passed true + 完成申告 → INCOMPLETE。LLM なし。

Chat の `/api/chat` は **呼ばない**。会話 Agent の日常回答を Policy で止めない。

---

## 接続図（実装した範囲）

```text
development_policy.json
        ↓ load_development_policy
evaluate_development_work  ← POST /api/policy/evaluate
        ↓
  specification_status / test_status を分離
        ↓
apply_final_answer_policy  ← agent.py 最終回答（完成申告があるときだけ）
```

`agent.py` SYSTEM_PROMPT に `policy_prompt_block()` を入れる = **INPUT_CONNECTED**。強制そのものではない。強制は evaluate / apply_final_answer_policy。

---

## 作らなかったもの

- 新しい Agent Framework
- Chat SYSTEM_PROMPT への Policy 全文
- Tool Gate と仕様相談の統合
- Human の Question → Pending → 再開
- Research / Matrix の改修
- pipeline.yaml
- `AGENT_VISIBLE_DEFAULT` への Policy Tool
- UI に Policy を出しただけの完成扱い

---

## 未完成（明示）

- Chat ターンからの自動 evaluate: **NOT_CONNECTED**
- 仕様不足の対話再開: **NOT_IMPLEMENTED**
- 要求項目の自動抽出: **NOT_IMPLEMENTED**（呼び出し側が items を渡す）
- Policy 違反での Tool 実行 abort: **NOT_IMPLEMENTED**（完成申告の注記と評価 API まで）
- Cursor 出力の機械 reject: **NOT_IMPLEMENTED**
