# Next Steps (Phase 2 候補)

優先度順。最大 3 件を Phase 1 完了時点の推奨とする。

## 1. Agent 非破壊アダプタ（NOT READY → 着手候補）

**目標:** `agent.py` の `execute_tool` / `create_ollama_tools` を変更せず、オプションで `ToolCatalog` を参照。

- 環境変数または設定ファイルで AI-TOOL 有効化
- MCP Tool はデフォルトで LLM に公開しない（metadata ビューのみ）
- 既存 registry パスをフォールバック

**状態:** NOT READY

## 2. MCP 接続の永続化（EXPERIMENTAL → 性能改善）

**目標:** 呼び出しごとの subprocess 起動（~1s）を削減。

- stdio セッションのプールまたは長寿命ワーカー
- Server クラッシュ時の再接続

**状態:** EXPERIMENTAL

## 3. 外部 Tool 信頼ポリシー（UNKNOWN → 安全強化）

**目標:** `trust_external` を設定ファイルで管理。

```text
trust_policy.json
  allow_servers: [ai-tool-time-server]
  allow_tools: [mcp:get_current_time]
  default: deny
```

- Server フィンガープリント（コマンドハッシュ）
- write/modify の人間承認と `agent_tool_gate` の連携設計

**状態:** UNKNOWN

---

## その他（優先度低）

| 項目 | 状態 |
|------|------|
| `registry/tools.json` への自動マージ | NOT READY（意図的に延期） |
| APIToolProvider | UNKNOWN |
| HTTP MCP トランスポート | UNKNOWN |
| Tool Builder → AI-TOOL 自動登録 | UNKNOWN |
| 監査ログの検索 UI | UNKNOWN |
| output_schema の registry 統一 | EXPERIMENTAL |

## Phase 1 でやらないこと（再確認）

- diagnostic_framework 改修
- NH15 以降の実験
- 外部 write Tool 自動実行
- 有料 API
- 既存 Tool の MCP 置換
