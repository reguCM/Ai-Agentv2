# Safety Boundary — Tool Creation Layer

Tool 実行パイプラインの分離定義。Diagnostic Framework の Gate/Validator 思想を継承。

**状態:** ADOPT CANDIDATE

## パイプライン

```text
DISCOVER    — Registry / Catalog / MCP tools/list
    ↓
DESCRIBE    — Tool Specification / ToolDescriptor
    ↓
SELECT      — LLM またはルールベース Selector（本番は LLM）
    ↓
VALIDATE    — Safety + Contract + Gate（機械的）
    ↓
EXECUTE     — Provider / execute_tool
    ↓
RESULT      — ToolExecutionResult / raw dict
    ↓
AUDIT       — execution_identity.jsonl / runs/ai_tool/audit.jsonl
```

## SELECT ≠ VALIDATE

| 層 | 主体 | 入力 | 出力 |
|----|------|------|------|
| SELECT | LLM（または将来の Selector） | ユーザー意図 + Tool metadata subset | 候補 Tool 名 |
| VALIDATE | 機械（Gate, Safety, Contract） | ToolDescriptor + 引数 + ポリシー | allow / deny / human_required |

LLM が「この Tool を使いたい」と判断しても、Validator が許可するとは限らない。

### 既存実装との対応

| ステップ | 既存 | Tool Creation / AI-TOOL |
|----------|------|-------------------------|
| DISCOVER | `load_registry`, `create_ollama_tools` | `ToolCatalog.list_all_descriptors` |
| DESCRIBE | Registry description + input | Tool Specification |
| SELECT | Ollama tool_call | 変更なし（本 Phase） |
| VALIDATE | `agent_tool_gate` | `evaluate_tool_safety` + Contract（将来） |
| EXECUTE | `execute_tool` | Provider（実験） |
| AUDIT | `log_tool_call/result` | `append_audit` |

**二重ゲート:** `agent_tool_gate`（人間確認）と Builder AST Safety は**非統合**のまま維持。

## execution_mode / side_effect

| side_effect | 自動実行（Phase 1 方針） |
|-------------|--------------------------|
| `none`, `read_only` | Local low risk のみ検討可 |
| `write`, `modify` | **禁止**（human_required） |
| `execute` | **禁止**（subprocess 等） |
| `unknown` | human_required |

外部 Provider（mcp/api/external）は `trust_external` なしでは常に human_required（AI-TOOL `safety.py` 準拠）。

## write Tool 禁止（ユーザー指示）

Phase 1 / Tool Creation Layer では:

- 外部 write Tool の自動実行禁止
- Specification 段階で `side_effect: write|modify` はレビュー必須
- Test Contract Safety カテゴリ必須

## 監査

| ログ | 用途 |
|------|------|
| `logs/execution_identity.jsonl` | 本番 Agent tool_call/result ダイジェスト |
| `runs/ai_tool/audit.jsonl` | AI-TOOL discovery / 実験 |

Tool Creation Layer 専用ログは**未作成**（将来 `runs/tool_creation/` を検討 — UNKNOWN）。

## 状態

| 項目 | ラベル |
|------|--------|
| パイプライン定義 | ADOPT CANDIDATE |
| Contract Validator 連携 | NOT READY |
| 統一 Audit フォーマット | EXPERIMENTAL |
