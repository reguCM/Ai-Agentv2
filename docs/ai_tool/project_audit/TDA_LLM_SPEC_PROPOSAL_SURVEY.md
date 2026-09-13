# LLM 仕様候補提案 — Phase 1 調査

**日付:** 2026-08-31  
**範囲:** 調査のみ。コード変更なし。Phase 2 以降未着手。  
**Run:** `runs/ai_tool/20260831_121500_llm_spec_proposal_survey`  
**判定:** 調査 PASS。機能の仕様充足は **未着手（NOT_IMPLEMENTED として実装していない）**

---

## 起動経路（ユーザー要求 → LLM → Tool → 再判断）

| 経路 | 入口 | 接続状態 | 仕様候補との関係 |
|------|------|----------|------------------|
| PROJECT_AGENT | `agent.py` | LLM Tool ループ CONNECTED。Clarity Gate あり | `create_tool_proposal` は関数・Registry あり。**visibility 未指定のため Ollama 公開集合に入らない**（既存監査どおり）。呼ばれた場合のみ材料まとめ → 別 LLM に JSON 仕様を書かせ `validate_tool_spec` |
| Chat 通常 | `run_chat_turn` → `_chat_turn` | Tool ループ CONNECTED（`AGENT_VISIBLE_DEFAULT`） | 仕様候補生成 **NOT_CONNECTED** |
| Chat Tool作成 | `classify_request` → `_tool_creation_turn` | キーワード一致時のみ | `create_tool_proposal`（材料）+ LLM に**自由文**仕様。JSON 契約なし。`validate_tool_spec` **未接続** |
| Chat development / research 分類 | `classify.py` に Route あり | `run_chat_turn` は `tool_creation` 以外すべて `_chat_turn` | **NOT_CONNECTED**（分類しても別経路に入らない） |
| Research / TDA | `standard_workflow` / `build_spec_draft` | Chat/agent.py から **NOT_CONNECTED** | 機械 draft（候補ページから）。LLM 仕様提案ではない |
| Matrix ask | `/api/matrix/ask` | Chat 通常 **NOT_CONNECTED** | 知識十分性。仕様提案ではない |
| Policy | `evaluate_development_work` / `apply_final_answer_policy` | 完成申告の注記と `/api/policy/evaluate` | 仕様**候補生成には未接続**。完成判定用 |

---

## 既存の「仕様提案」部品

| 部品 | 実体 | LLM が仕様を書くか | 再利用可否 |
|------|------|-------------------|------------|
| `create_tool_proposal` | `tools/ai/tool_builder/proposal.py` | **否**。検証済み入力と rules をまとめるだけ | **材料レイヤとして再利用すべき** |
| `PROPOSAL_INSTRUCTIONS` + `validate_proposals` | `agent.py` | はい（Tool spec JSON）。Tool が呼ばれた後 | Tool 専用スキーマ。一般要求には過大 |
| `validate_tool_spec` | `tools/system/tool_builder/validate/spec.py` | 検証のみ | Tool 名/category/module 必須。汎用仕様候補には不適合 |
| Chat `_tool_creation_turn` | `agent_turn.py` | はいが **非構造化日本語** | 経路はある。記録・不明点スキーマ・Policy 未接続 |
| `build_spec_draft` | TDA `spec_draft.py` | **否**（候補 dict から機械生成） | Web Research 用。今回の「要求→LLM仕様」とは別 |
| `development_spec_from_materials` | TDA | **否**（「LLM スタンドイン」と注記） | Facet 材料用 |
| Clarity | `run_clarity_gate` | 要求の clear / 質問。仕様書ではない | 曖昧さの人間確認として部分再利用可 |
| PROJECT_SPEC.md | 文書 | Agent は読まない | 実行時 **NOT_CONNECTED** |

`create_tool_proposal` を「LLM 仕様生成」として再実装してはいけない。既存は **材料梱包** である。

---

## Policy との接続

| Policy 機能 | 仕様候補への利用 |
|-------------|------------------|
| `development_policy.json` / Loader | 状態語（CONNECTED, NEED_HUMAN_DECISION 等）は揃っている。提案スキーマには未使用 |
| `evaluate_development_work` | 項目リスト前提。提案 JSON を items に変換する接続は **無い** |
| Completion | 「提案が出た」を COMPLETE にしない設計は既にある。提案経路からは未呼び出し |
| Human Decision | 状態と `may_proceed_implementation` のみ。確認 UI/再開は無い |
| 「仕様候補を必ず提示」の機械確認 | **NOT_IMPLEMENTED**。Chat 通常は提案を要求しない。agent.py は Tool 非公開のため提案 LLM が走らないことが多い |

---

## 核心の未確定（実装に進まない理由）

1. **対象範囲:** 任意のユーザー要求か、Tool 作成要求だけか。既存実装はほぼ後者。  
2. **入口:** Chat 全ターン強制 / Tool作成キーワードのみ / 新 API / agent.py 公開 Tool。  
3. **スキーマ:** `validate_tool_spec` の Tool JSON か、より小さい汎用候補か。

これを推測で固定しない。Phase 2 は人間確認後。
