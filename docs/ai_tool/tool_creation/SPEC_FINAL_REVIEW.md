# Specification Final Review — `local:workspace_read_text_scoped`

**日付:** 2026-08-28  
**状態:** 実Tool完成 Phase 1（文書レビュー。Registry 変更なし）

## フィールド確認

| フィールド | 状態 | 備考 |
|------------|------|------|
| tool_id | PASS | `local:workspace_read_text_scoped` |
| purpose | PASS | allowlist 内 read-only。実験→実Tool候補として十分 |
| input | PASS | path 必須、offset/limit 任意 |
| output | PASS | ok/path/content/metadata。read_file と意図的差別化 |
| errors | PASS | expected_failure 一覧と実装一致（encoding は下記 UNKNOWN） |
| side_effect | PASS | read_only |
| permissions | PASS | visibility:experimental |
| risk | PASS | low |
| contract | PASS | can/cannot/must/must_not 定義済 |
| provider_specific | PASS | module/function/allowlist_config 記載済 |
| status | ISSUE | `tool_status: unavailable` — Registry 未登録として正しいが「実装完成」とは別軸 |

## 実Toolとして必要十分か

**判定: PASS（experimental スコープ内）**

allowlist 限定 read-only Tool として Specification は実装・テストを支える十分な契約。  
本番 Agent 公開には `tool_status` / Registry / visibility 更新が別 Phase。

## 文書修正案（実装変更なし）

| # | 提案 | 分類 | 今回適用 |
|---|------|------|----------|
| 1 | `known_limitations` に `max_lines_default=500` を明記 | Specification | **適用**（最小追記） |
| 2 | `expected_failure` に `encoding error` 追加 | Specification | **適用**（実装に存在） |
| 3 | `version` を `0.1.0` へ（draft 解除） | Specification | 保留（人間承認後） |
| 4 | `purpose` を「実験用のみ」から「安全 scoped read 基盤」へ拡張 | Specification | 保留 |
| 5 | 成功時 `path` は resolved 相対、失敗時は requested 混在 | Implementation | IMPLEMENTATION_REVIEW 参照 |

## 再利用（再実装不要）

| 成果物 | 利用 |
|--------|------|
| specs/local_workspace_read_text_scoped.json | 一次基準 |
| allowed_roots.experimental.json | allowlist |
| validator/ | Mechanical ACCEPT |
| tests/ai_tool/experimental/ | Tool Contract 実証 |
| Context Builder / EHP | 開発支援（本 Phase スコープ外） |
| runs/ai_tool/20260828_055850_scoped_filesystem_read/ | 参照 run（変更しない） |

## 参照

- [TOOL_COMPLETION_REPORT.md](./TOOL_COMPLETION_REPORT.md)
- [IMPLEMENTATION_REVIEW.md](./IMPLEMENTATION_REVIEW.md)
