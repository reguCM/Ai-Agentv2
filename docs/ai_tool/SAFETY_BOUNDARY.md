# Safety Boundary (Phase 1)

Diagnostic Framework の Gate / Validator 思想を AI-TOOL に適用した機械的安全層。

## パイプライン

```text
Tool discovery
    ↓
Tool metadata (ToolDescriptor)
    ↓
permission check (descriptor.permissions, status)
    ↓
risk check (risk_level)
    ↓
execution_mode check (read / write / modify)
    ↓
external trust check (provider != local)
    ↓
execution (Provider)
    ↓
result (ToolExecutionResult)
    ↓
audit log (append_audit)
```

実装: `ai_tool/core/safety.py`, `ai_tool/core/audit.py`

## evaluate_tool_safety()

機械判定のみ。LLM は呼ばない。

| 条件 | 判定 |
|------|------|
| `status == disabled` | `deny` |
| `execution_mode == write` かつ `allow_write=False` | `human_required` |
| `execution_mode == modify` かつ `allow_modify=False` | `human_required` |
| `provider != local` かつ `trust_external=False` | `human_required` |
| `risk_level == high` | `human_required` |
| Local + low risk + read | `allow` |

### Phase 1 デフォルト

- **write / modify:** 自動実行しない（`human_required`）
- **外部 Tool:** `trust_external=False` のため常に `human_required`
- **MCP は安全ではない:** プロトコル経由でも信頼は別途付与が必要

## execution_mode

| モード | 意味 | Phase 1 |
|--------|------|---------|
| `read` | 観測・取得のみ | Local low risk は `allow`、外部は `human_required` |
| `write` | 新規作成・追記 | 自動実行禁止 |
| `modify` | 変更・削除・修復 | 自動実行禁止 |

Local の `execution_mode` は registry 名から機械推論（暫定）。誤分類リスクあり → **ADOPT CANDIDATE だが registry 明示化は将来課題**。

## 監査ログ

- **パス:** `runs/ai_tool/audit.jsonl`
- **形式:** JSONL（1 行 1 イベント）
- **イベント例:** `tool_discovery`, `experiment_complete`
- **フィールド:** `audit_id`, `timestamp`, `event`, ...

実行結果そのものの全文保存は Phase 1 では最小限。将来は tool_id, verdict, duration, error の標準化を検討。

## 既存 agent_tool_gate との関係

| | agent_tool_gate | AI-TOOL safety |
|--|-----------------|----------------|
| 対象 | PROJECT_AGENT 公開 Tool | Local + 外部（実験） |
| 統合 | なし（Phase 1） | 将来アダプタで連携検討 |
| 思想 | 人間確認デフォルト | 外部は常に明示的信頼要求 |

Research Pipeline の `execution_gate` とも非統合（既存設計を維持）。

## 禁止事項（ユーザー指示の反映）

- 外部 write Tool の自動実行
- MCP だから安全と判断
- 外部 metadata の無条件信頼
- API キーのコード保存
