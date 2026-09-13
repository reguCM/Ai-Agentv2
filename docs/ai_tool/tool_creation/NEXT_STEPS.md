# Tool Creation Layer — Phase 3 候補

Phase 2 完了後の次ステップ（最大 3 件）。

## 1. Validator の CI 接続（NOT READY → 着手候補）

- `docs/ai_tool/tool_creation/specs/` と `failure_cases/` を pytest で回す
- 新 Spec 追加時に ACCEPT/REJECT を PR チェック化
- **本番 tools/ や registry には触れない**

**ラベル:** ADOPT CANDIDATE

## 2. 実装結果と output_schema の実行時照合（EXPERIMENTAL）

- Phase 2 の fixture 照合を拡張
- **隔離環境**で Local Tool を import 実行し、戻り値 key を Spec と比較
- 本番 `test_tool()` とは別パス。人間承認後のみ有効化

**ラベル:** EXPERIMENTAL

## 3. Catalog draft レビュー UI / CLI（NOT READY）

- `drafts/*.json` の diff 表示
- `adoption_status` 手動更新ワークフロー
- Registry への export は**明示コマンド + 人間確認**のみ

**ラベル:** NOT READY

---

## Phase 3 でまだやらないこと

- Agent 本番統合
- Registry 自動登録
- Tool 自動生成
- MCP 大量導入
- auto_fix

## AI-TOOL Layer との関係

Phase 3 完了後に:

1. 簡単な Local Tool（Specification 経由で作成）
2. 同等 MCP Tool
3. 公開 MCP Tool

を比較し、AI-TOOL 実装範囲を決定（Phase 1 計画どおり）。
