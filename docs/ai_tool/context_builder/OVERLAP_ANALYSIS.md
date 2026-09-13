# Tool Development Context Builder — Overlap Analysis (Phase 1)

**日付:** 2026-08-28  
**結論:** **新規**（診断 FW のパターン再利用、ドメインは Tool Creation 専用）

## 既存機能との関係

| 既存 | 関係 | 今回の扱い |
|------|------|------------|
| NH9 Fixed Slot (`fixed_slots.py`) | **重複しない** | slot 名・語彙は Tool 用に別定義 |
| NH10 Mechanical Prefill | **重複しない** | 診断 materials 専用 |
| NH12-2 Compression | **パターン再利用** | 全文 / メタデータのみ（LLM 要約なし） |
| NH13 `build_context()` | **パターン再利用** | `(manifest, content)` 分離 API |
| NH13-7 Glossary Selector | **重複しない** | 診断用語選択。Tool 版 rules は新規 |
| NH14 External Help Package | **参考のみ** | ファイルレイアウト思想を run 成果物に転用 |
| `workspace_read_text_scoped` | **利用** | Context 本文取得（allowlist 厳守） |
| `TOOL_CONTRACT.md` L83 | **ギャップ** | 「LLM Context 生成 = UNKNOWN」→ 本 Phase で最小実装 |

## 新規 vs 再利用 vs 重複

```text
新規:           Tool Development Context Builder 本体
既存機能の再利用: scoped_read, NH13 manifest 分離, UNKNOWN 方針
既存機能の拡張:   なし（diagnostic_framework / agent 未変更）
既存機能との重複: なし（NH9–NH14 パイプラインは呼ばない）
```

## 意図的に作らないもの

- LLM によるファイル選択 / 要約
- allowlist 外読取（`tools/` 実装本文などは参照のみ）
- Registry / Catalog 自動更新
- Agent / Ollama / Cursor API 接続

## 参照

- [CONTEXT_BUILDER_SPEC.md](./CONTEXT_BUILDER_SPEC.md)
- [../tool_creation/TOOL_CONTRACT.md](../tool_creation/TOOL_CONTRACT.md)
