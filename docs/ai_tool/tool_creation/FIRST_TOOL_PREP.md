# First Tool — Pre-Implementation Package

**Tool:** `local:workspace_read_text_scoped`（Scoped Filesystem Read）  
**状態:** Local 実装完了（2026-08-28）。Registry / Agent 統合は未着手。

| ファイル | 内容 |
|----------|------|
| [LOCAL_IMPLEMENTATION_REPORT.md](./LOCAL_IMPLEMENTATION_REPORT.md) | Local Phase 完了報告 |
| [ALLOWLIST_POLICY.md](./ALLOWLIST_POLICY.md) | experimental allowlist |
| [allowed_roots.experimental.json](./allowed_roots.experimental.json) | 許可ルート設定 |
| [specs/local_workspace_read_text_scoped.json](./specs/local_workspace_read_text_scoped.json) | Tool Specification ドラフト |
| [EXISTING_READ_FILE_RELATION.md](./EXISTING_READ_FILE_RELATION.md) | 本番 `read_file` との非置換関係 |
| [MCP_SDK_COMPATIBILITY.md](./MCP_SDK_COMPATIBILITY.md) | MCP 1.x / 2.x と公式 Server 接続方針 |

## Mechanical Validation

```powershell
cd D:\AI-Agent\docs\ai_tool\tool_creation
..\..\..\.venv\Scripts\python.exe -c "
from pathlib import Path
from validator.validate import validate_tool_spec_file
r = validate_tool_spec_file(Path('specs/local_workspace_read_text_scoped.json'))
print(r.verdict, r.schema_errors, [i for i in r.safety_issues if i.get('severity')=='error'])
"
```

期待: `ACCEPT`

## 実装 Phase で行うこと（未着手）

1. `ai_tool/experimental/` または隔離モジュールに Local 実装
2. allowlist JSON 読み込み + path 検証
3. [TEST_CONTRACT.md](./TEST_CONTRACT.md) に沿った pytest（temp dir + allowlist 違反）
4. Catalog draft 生成（`validator/catalog_draft.py`）
5. MCP: npx filesystem + 3 allowed dirs（[MCP_SDK_COMPATIBILITY.md](./MCP_SDK_COMPATIBILITY.md)）
6. 人間承認後のみ Registry 検討

## 実装 Phase で行わないこと

- `tools/file/workspace/read_file.py` 変更
- `registry/tools.json` 自動追記
- `agent.py` 統合
- write Tool

## Workflow 適合（再掲）

| ステップ | 本パッケージ |
|----------|--------------|
| Idea | PUBLIC_TOOL_COMPARISON で選定済み |
| Specification | `specs/local_workspace_read_text_scoped.json` |
| Mechanical Validation | Validator ACCEPT（下記実行で確認） |
| Implementation | NOT READY |
| Test Contract | 設計のみ（contract / expected_failure 記載済み） |
| Safety | allowlist ポリシー文書化済み |
| Catalog | draft 生成は実装 Phase |
| Human Approval | 必須（Registry 前） |

## 変更なし確認

- 本番 `tools/`、`agent.py`、`registry/tools.json` — **未変更**
