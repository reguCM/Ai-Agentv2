# Tool Development Context Builder — Phase 2 Report

**Run:** `runs/ai_tool/20260828_061436_tool_development_context_phase2/tool_development_context/`

## 完了条件

| # | 条件 | 結果 |
|---|------|------|
| 1 | EHP 仕様 | [EXTERNAL_HELP_PACKAGE_SPEC.md](./EXTERNAL_HELP_PACKAGE_SPEC.md) |
| 2 | Package Generator | `package_generator.py` |
| 3 | 代表 Tool 3 件 | READY × 3 |
| 4 | P0 不足検出 | NOT_READY（unknown tool_id）テスト済 |
| 5 | UNKNOWN 捏造なし | UNKNOWN_AND_MISSING.md + pytest |
| 6 | sensitive 混入なし | pytest |
| 7 | allowlist violation | wrong_inclusion=0 |
| 8 | deterministic | pytest |
| 9 | pytest | 27 passed |
| 10 | レポート | 本書 + run REPORT.md |

## 生成 Package 例

```text
runs/ai_tool/.../packages/local_get_gpu_status/external_help_package/
├── request.json
├── SUMMARY.md
├── CONTEXT_MANIFEST.json
├── SPECIFICATION.md
├── CONTRACT.md
├── IMPLEMENTATION_CONTEXT.md  (REFERENCE_ONLY)
├── TEST_CONTEXT.md
├── SAFETY_CONTEXT.md
├── CHANGE_POLICY.md
├── CATALOG_CONTEXT.md
├── KNOWN_LIMITATIONS.md
├── RELATED_CONTEXT.md
└── UNKNOWN_AND_MISSING.md
```

## 評価

```text
wrong_file_inclusion: 0
unsafe_accept:        0
all_ready:            true
pytest:               27 passed
```

## 既存機能との関係

- **新規:** EHP Generator
- **再利用:** Phase 1 Context Builder, NH14 request/SUMMARY 思想
- **拡張:** Phase 1 の出力形式
- **重複なし:** NH14 診断パイプライン、Phase 1 selected_context レイアウト

## STOP

Agent / LLM 自動投入 / Registry — 未着手

## 本番化に必要な条件（UNKNOWN）

- Cursor IDE 連携 API
- 人間承認フロー
- allowlist 拡張ポリシー（実装本文を含めるか）

## 次の候補（最大3）

1. PARTIAL 時の人間向けチェックリスト強化
2. Tool 版 Mechanical Selection（NH13-7 型 hint rules）
3. Package 差分（Tool 変更前後の Context diff）
