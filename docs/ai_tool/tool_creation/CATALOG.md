# Tool Catalog

Local / MCP / API / External を横断する **metadata カタログ**の設計。

**状態:** EXPERIMENTAL（スキーマドラフト。本番マージは NOT READY）

## 配置

| パス | 用途 |
|------|------|
| `registry/tools.json` | 本番 Local Tool（**変更しない**） |
| `registry/ai_tool_catalog.json` | AI-TOOL 実験用手動エントリ |
| `docs/ai_tool/catalog/` | Catalog スキーマ・方針（本ドキュメント） |
| 将来 `ai_tool/catalog/entries/` | 承認済み Catalog JSON（NOT READY） |

## 概念構造

```text
Tool Catalog
├── Local      ← registry/tools.json（読み取りビュー）
├── MCP        ← ai_tool_catalog.json + live discovery
├── API        ← 未実装
├── External   ← 未実装
└── Unknown
```

## Catalog Entry（ドラフト）

```json
{
  "tool_id": "local:get_gpu_status",
  "name": "get_gpu_status",
  "provider": "local",
  "version": "1.0.0",
  "description": "...",
  "capabilities": ["gpu", "observation"],
  "input_schema": { "type": "object", "additionalProperties": false },
  "output_schema": { "type": "object", "properties": { "gpu": {}, "ok": {} } },
  "side_effect": "read_only",
  "permissions": ["visibility:agent"],
  "network_access": false,
  "filesystem_access": "none",
  "risk_level": "low",
  "cost": "free",
  "tool_status": "available",
  "experiment_status": "tested",
  "adoption_status": "approved",
  "spec_ref": "docs/ai_tool/tool_creation/examples/existing_get_gpu_status.md",
  "provider_specific": {
    "module": "tools.system.gpu.gpu_status",
    "function": "get_gpu_status"
  }
}
```

JSON Schema: [catalog_entry.schema.json](../catalog/catalog_entry.schema.json)

## 状態の三層分離（Phase 7）

Diagnostic Framework の「SUPPORTED ≠ 本番採用」を反映。

### tool_status（Tool そのもの）

| 値 | 意味 |
|----|------|
| `available` | 実行可能・メンテ対象 |
| `disabled` | 意図的無効化 |
| `unavailable` | 環境不足で利用不可 |
| `deprecated` | 廃止予定 |

### experiment_status（実験）

| 値 | 意味 |
|----|------|
| `unknown` | 未実験 |
| `experimental` | 実験中 |
| `tested` | テスト完了（採用とは別） |
| `unsupported` | 実験失敗・非対応 |

### adoption_status（採用）

| 値 | 意味 |
|----|------|
| `not_reviewed` | 未レビュー |
| `candidate` | 採用候補 |
| `approved` | 本番採用承認 |
| `rejected` | 採用拒否 |

**ルール:** `adoption_status: approved` かつ `tool_status: available` でなければ、Agent 本番公開にしない（将来運用）。

## 既存レジストリとの関係

| ソース | Catalog への取り込み |
|--------|----------------------|
| `tools.json` | `LocalToolProvider.list_descriptors()` で読み取りビュー（実装済） |
| `ai_tool_catalog.json` | 手動エントリ（実験） |
| 自動マージ | **禁止**（Phase 1） |

## ai_tool.ToolDescriptor との差

| Catalog | ToolDescriptor（ai_tool） |
|---------|---------------------------|
| experiment_status | なし（追加予定） |
| adoption_status | なし（`status` が混在） |
| spec_ref | なし |
| side_effect | `execution_mode`（read/write/modify） |

将来統合は EXPERIMENTAL。今回は文書上で役割分担。

## 状態

| 項目 | ラベル |
|------|--------|
| 三層状態モデル | ADOPT CANDIDATE |
| catalog_entry.schema.json | EXPERIMENTAL |
| 自動生成・マージ | NOT READY |
| API/External エントリ | UNKNOWN |
