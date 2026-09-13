# Tool Creation Layer — Phase 2 Plan

**目的:** Phase 1 の文書化された Workflow を、本番統合なしで機械化する。

## スコープ

| Phase | 内容 | 状態 |
|-------|------|------|
| 2-A | Specification Validator | 実装済 |
| 2-B | Catalog Entry Draft Generator | 実装済 |
| 2-C | Test Contract Skeleton Generator | 実装済 |
| 2-D | 既存 Tool Mapping 再現 | 実装済 |
| 2-E | 意図的 Failure ケース 8 件 | 実装済 |
| 2-F | 評価・レポート | 実装済 |

## 隔離方針

| 領域 | パス |
|------|------|
| 実装 | `docs/ai_tool/tool_creation/validator/` |
| 有効 Spec | `docs/ai_tool/tool_creation/specs/` |
| Failure ケース | `docs/ai_tool/tool_creation/failure_cases/` |
| 実験出力 | `runs/ai_tool/<timestamp>_tool_creation_phase2/` |

## 変更禁止（遵守）

- `agent.py`, `tools/`, `registry/tools.json`
- Diagnostic Framework, Selector 本番

## 実行

```powershell
cd D:\AI-Agent
.\.venv\Scripts\python.exe docs\ai_tool\tool_creation\validator\run_phase2.py
```

依存: `jsonschema`（`.venv` 済み）

## 成功条件

```text
Idea → Tool Specification → Mechanical Validation → Implementation
  → Test Contract → Safety Check → Catalog Draft → Human Approval → Registry
```

「Tool 自動生成」ではなく、**作成途中の不備を機械的に発見**できること。

## 関連ドキュメント

- [VALIDATOR.md](./VALIDATOR.md)
- [CATALOG_DRAFT.md](./CATALOG_DRAFT.md)
- [TEST_GENERATION.md](./TEST_GENERATION.md)
- [PHASE2_REPORT.md](./PHASE2_REPORT.md)
- [FAILURE_ANALYSIS.md](./FAILURE_ANALYSIS.md)
- [NEXT_STEPS.md](./NEXT_STEPS.md)
