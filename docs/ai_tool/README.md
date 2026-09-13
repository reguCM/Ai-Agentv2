# AI-TOOL Layer — Phase 1

AI-Agent に外部 Tool（MCP 等）と既存 Local Tool を共存させるための実験的基盤。

## 目的

- 外部 Tool の調査・仕様理解
- 自作 Tool と外部 Tool の共通 metadata モデル
- Provider 分離（Local / MCP）
- 安全境界（read / write / modify、外部 Tool の明示的信頼）
- 既存 Registry / Agent / Diagnostic Framework を**破壊しない**拡張

## スコープ外（Phase 1）

- `agent.py` への本番統合
- `registry/tools.json` への自動マージ
- 外部 write Tool の自動実行
- MCP Server の大量導入
- 有料 API 接続

## ドキュメント一覧

| ファイル | 内容 |
|----------|------|
| [CURRENT_STATUS.md](./CURRENT_STATUS.md) | 完了条件・状態ラベル・最終報告 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | レイヤ構成と既存システムとの境界 |
| [EXTERNAL_TOOL_RESEARCH.md](./EXTERNAL_TOOL_RESEARCH.md) | 外部 Tool 方式調査サマリ |
| [TOOL_MODEL.md](./TOOL_MODEL.md) | 共通 ToolDescriptor モデル |
| [PROVIDER_MODEL.md](./PROVIDER_MODEL.md) | Local / MCP Provider 設計 |
| [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) | 安全ゲートと監査ログ |
| [NEXT_STEPS.md](./NEXT_STEPS.md) | 次に実装すべき項目 |
| [external_tool_research/](./external_tool_research/) | MCP / Apps SDK 詳細調査 |
| [experiments/](./experiments/) | AI-TOOL 固有実験記録（NH 番号は使用しない） |
| [tool_creation/](./tool_creation/) | Tool Creation Layer（仕様・テスト契約・Catalog） |
| [context_builder/](./context_builder/) | Tool Development Context Builder（Phase 1 実験） |
| [mcp_comparison/](./mcp_comparison/) | MCP Fetch vs Local 比較 Phase 1（**FROZEN** — 14 cases） |
| [project_audit/](./project_audit/) | プロジェクト横断現在地監査 Phase 1（2026-08-28） |
| [agent_integration/](./agent_integration/) | Agent Tool Discovery Phase 1（read-only、実行・LLM 公開なし） |

## Tool Development Context Builder（Phase 1）

Tool 開発時に LLM / 人間へ渡す関連情報を機械的に収集。Agent 統合・LLM 自動投入は行わない。

- [context_builder/CONTEXT_BUILDER_SPEC.md](./context_builder/CONTEXT_BUILDER_SPEC.md)
- [context_builder/OVERLAP_ANALYSIS.md](./context_builder/OVERLAP_ANALYSIS.md)
- [context_builder/EXTERNAL_HELP_PACKAGE_SPEC.md](./context_builder/EXTERNAL_HELP_PACKAGE_SPEC.md)
- [context_builder/PHASE2_REPORT.md](./context_builder/PHASE2_REPORT.md)
- 実装: `ai_tool/context_builder/`（Phase 2: `package_generator.py`）

## Tool Creation Layer（別フェーズ）

新規 Tool を増やす**前**の標準化層。外部 Tool 実験（上記）とは分離。

- [tool_creation/README.md](./tool_creation/README.md)
- [tool_creation/PHASE1_REPORT.md](./tool_creation/PHASE1_REPORT.md)

## コード配置

```text
ai_tool/
├── core/           # models, safety, audit
├── providers/
│   ├── local/      # registry/tools.json ラッパ
│   └── mcp/        # stdio MCP クライアント + 参照サーバ
├── registry/       # ToolCatalog（統合ビュー）
└── run_compare_experiment.py

registry/ai_tool_catalog.json   # 手動カタログ（tools.json とは別）
runs/ai_tool/                 # 監査ログ・実験結果
```

## 実験の実行

```powershell
cd D:\AI-Agent
.\.venv\Scripts\python.exe ai_tool\run_compare_experiment.py
```

依存: `pip install -r ai_tool/requirements.txt`（`mcp>=2.1,<3`）

## 設計原則（Diagnostic Framework からの借用）

Tool そのものと選択・検証・実行・結果を分離する。metadata（capability, schema, risk, execution_mode 等）は LLM に推測させず、機械的フィールドとして扱う。
