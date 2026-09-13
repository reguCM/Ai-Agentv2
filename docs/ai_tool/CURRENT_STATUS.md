# AI-TOOL Layer — Current Status (Phase 1)

最終更新: 2026-08-28

## 完了条件チェック（10 項目）

| # | 条件 | 状態 | 根拠 |
|---|------|------|------|
| 1 | 既存 Local Tool を共通 Tool Model で表現 | **ADOPT CANDIDATE** | `LocalToolProvider` が `registry/tools.json` を `ToolDescriptor` に変換 |
| 2 | MCP Tool を同じ Model で表現 | **EXPERIMENTAL** | `MCPToolProvider.list_descriptors()` + 手動カタログ |
| 3 | MCP read-only Tool を 1 つ呼び出し | **EXPERIMENTAL** | `get_current_time`（EXP-001 成功） |
| 4 | Local/MCP を同じ Agent から認識 | **NOT READY** | `ToolCatalog.summarize_for_agent_view()` のみ。`agent.py` 未統合 |
| 5 | 既存 Registry を破壊していない | **ADOPT CANDIDATE** | `tools.json` 未変更。別ファイル `ai_tool_catalog.json` |
| 6 | metadata と実行の分離 | **ADOPT CANDIDATE** | Descriptor / Provider / Safety / Audit を分離 |
| 7 | read/write/modify を区別 | **ADOPT CANDIDATE** | `evaluate_tool_safety()` + `execution_mode` |
| 8 | 監査ログ | **EXPERIMENTAL** | `runs/ai_tool/audit.jsonl`（discovery / experiment） |
| 9 | Diagnostic Framework 未変更 | **ADOPT CANDIDATE** | 本番 DF コード・NH run 未着手 |
| 10 | 有料 API 不要 | **ADOPT CANDIDATE** | ローカル MCP stdio のみ |

## コンポーネント別ステータス

| コンポーネント | ラベル | 備考 |
|----------------|--------|------|
| `ToolDescriptor` / `ToolExecutionResult` | EXPERIMENTAL | Phase 1 ドラフト。output_schema 等は未整備 |
| `LocalToolProvider` | ADOPT CANDIDATE | registry 読み取り・実行は動作確認済 |
| `MCPToolProvider` | EXPERIMENTAL | MCP 2.x snake_case 対応済。stdio のみ |
| `ToolCatalog` | EXPERIMENTAL | 統合ビュー。live MCP discovery は例外握りつぶし |
| `evaluate_tool_safety` | ADOPT CANDIDATE | 外部 Tool はデフォルト `human_required` |
| `append_audit` | EXPERIMENTAL | JSONL。ローテーション・検索なし |
| Agent 統合 | NOT READY | `execute_tool` / `create_ollama_tools` 未接続 |
| Registry 自動登録 | NOT READY | 手動カタログのみ |
| APIToolProvider | UNKNOWN | 未設計・未実装 |
| Tool Builder 連携 | UNKNOWN | 将来フックのみ想定 |

## 最終報告

### 既存 Tool 構造

- **Registry:** `registry/tools.json`（21 Tool）。`name`, `module`, `function`, `input`, `risk`, `visibility` 等
- **Agent:** `load_registry()` → `create_ollama_tools()`（`visibility=="agent"` のみ）→ `execute_tool()`（`importlib` + `agent_tool_gate`）
- **実行形式:** 関数呼び出し。戻り値は Python dict / list 等（Tool ごとに非統一）
- **安全:** `tools/system/agent_tool_gate.py`（PROJECT_AGENT 専用。Research Pipeline とは非統合）

### MCP との対応関係

| 既存概念 | MCP 概念 |
|----------|----------|
| `registry/tools.json` エントリ | `tools/list` の Tool 定義 |
| `name` | `name` |
| `description` | `description` |
| `input`（registry 形式） | `inputSchema`（JSON Schema） |
| `module` + `function` | MCP Server 内実装 |
| `execute_tool()` | `tools/call` |
| `visibility` | MCP には直接相当なし（クライアント側ポリシー） |
| `risk` | MCP annotations（**信頼できない扱い**） |

### 共通 Tool Model

`ai_tool/core/models.py` の `ToolDescriptor`。Local は registry から機械変換、MCP は `tools/list` + 手動カタログで補完。

### Local Provider

- **状態:** ADOPT CANDIDATE
- registry を読み取り専用でラップ。実行は既存 `importlib` パスと同等

### MCP Provider

- **状態:** EXPERIMENTAL
- stdio サブプロセスで `ai_tool.providers.mcp.time_server` に接続
- 呼び出し成功 Tool: `get_current_time`（read-only）

### 実験 EXP-001（Local vs MCP）

- **記録:** `runs/ai_tool/20260828_140000_local_vs_mcp_time/`
- **結果:** MCP 呼び出し成功（`mcp_ok: true`）
- **比較要点:**
  - 入力: 両方とも空 object
  - 出力: Local は構造化 dict、MCP は text + structured_content
  - 実行時間: Local ~0.02ms、MCP ~1058ms（プロセス起動オーバーヘッド）
  - 安全: Local `allow`、MCP `human_required`（外部 Tool デフォルト）
  - LLM 説明量: MCP は content 配列が増える
  - 監査: discovery / experiment イベントを JSONL に記録

### 未解決問題

1. MCP 呼び出しごとに stdio プロセス起動 → レイテンシ大
2. `agent.py` 未統合のため、本番 Agent は MCP を認識しない
3. MCP SDK 2.x の camelCase / snake_case 混在（クライアント側で吸収が必要）
4. 外部 Server の信頼モデル（署名・allowlist）未実装
5. write/modify の人間承認フローと `agent_tool_gate` の統合方針未決

### 本番統合可能か

**NOT READY（全体）**。Local Provider の registry 読み取りは統合候補。MCP は実験段階のまま維持すべき。

### experimental にすべき部分

- すべての MCP 経路
- `registry/ai_tool_catalog.json`
- `ToolCatalog` の live MCP discovery
- 監査ログフォーマット

### 次に実装すべきもの（最大 3 件）

1. **Agent 非破壊アダプタ** — `execute_tool` を変更せず、オプションで `ToolCatalog` を参照する薄いフック
2. **MCP 接続プール / 永続 stdio** — 実験で確認した起動コストの低減
3. **外部 Tool 信頼ポリシー** — allowlist + `trust_external` の設定ファイル化

## 変更していないもの（確認済）

- `agent.py`
- `registry/tools.json`（既存エントリ）
- `tools/` 本番モジュール
- `diagnostic_framework/` 本番コード・NH1–NH14 run
- `selector.py`, `rules.json`, `auto_fix`
