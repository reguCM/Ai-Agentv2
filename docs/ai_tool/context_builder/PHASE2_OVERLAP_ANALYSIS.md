# Phase 2 Overlap Analysis — External Help Package

**結論:** **新規**（NH14 パターン再利用、診断 FW コードは呼ばない）

| 既存 | 関係 |
|------|------|
| NH14 `build_external_help_package()` | **パターン再利用** — request.json, SUMMARY.md, 制約文言 |
| Phase 1 Context Builder | **拡張** — 入力として利用 |
| Phase 1 `selected_context/` | **重複しない** — EHP は slot 別 Markdown レイアウト |
| NH13 Glossary Full | **投入しない** — NH13 知見に従い Tool 固有情報中心 |
| Diagnostic Framework | **変更なし** |

## 新規実装

- `ai_tool/context_builder/package_generator.py`
- `EXTERNAL_HELP_PACKAGE_SPEC.md`

## 意図的に作らないもの

- LLM 要約 / 自動投入
- 実装方法の断定
- Registry / Agent 統合
