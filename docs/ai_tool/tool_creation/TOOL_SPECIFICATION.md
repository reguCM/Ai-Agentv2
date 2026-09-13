# Tool Specification

新規 Tool を実装する前に記述する機械的仕様書。LLM 推測の代替ではなく、**人間・Validator・Catalog が参照する一次情報**。

**状態:** ADOPT CANDIDATE（ドラフト。既存 Tool Mapping で表現可能性を確認済み）

## 1. Identity

| フィールド | 必須 | 説明 |
|------------|------|------|
| `tool_id` | yes | グローバル一意 ID。例: `local:get_gpu_status`, `mcp:get_current_time` |
| `name` | yes | 実行名（Registry / MCP `name` と一致させる） |
| `version` | yes | 仕様バージョン。例: `1.0.0` |
| `description` | yes | 人間可読説明（Agent LLM にも渡しうる） |
| `provider` | yes | `local` \| `mcp` \| `api` \| `external` \| `unknown` |
| `source` | yes | 由来。例: `registry/tools.json`, MCP server ラベル, API base URL |

### provider 値

| 値 | 意味 |
|----|------|
| `local` | `tools/` 配下の Python 実装 + Registry |
| `mcp` | MCP Server 経由 |
| `api` | HTTP 等の API 呼び出し |
| `external` | 上記以外の外部実行体 |
| `unknown` | 未分類・調査中 |

## 2. Capability

| フィールド | 必須 | 説明 |
|------------|------|------|
| `capability` | yes | 能力タグの配列。例: `["gpu", "observation"]` |
| `purpose` | yes | 1 文の目的 |
| `allowed_operations` | yes | 許可操作。例: `["read"]` |
| `prohibited_operations` | yes | 禁止操作。例: `["write", "modify", "network"]` |

### 操作タグ（推奨語彙）

`read`, `write`, `modify`, `execute`, `network`, `filesystem`, `subprocess`

Diagnostic Framework Glossary の「観測」「実行」概念と矛盾しないよう、`read` は観測取得、`execute` は副作用のある外部プロセス起動を指す。

## 3. Input

| フィールド | 必須 | 説明 |
|------------|------|------|
| `input_schema` | yes | JSON Schema（`registry/tools.json` の `input` はここへ正規化） |
| `required` | no | 必須パラメータ名（`input_schema.required` と重複可） |
| `optional` | no | 任意パラメータ名 |
| `constraints` | no | 追加制約の自然言語または機械ルール |
| `examples` | no | 入力例の配列 |

既存 Registry 形式:

```json
"query": {
  "type": "string",
  "description": "検索クエリ（必須）",
  "required": true
}
```

→ `input_schema.properties` + `required: ["query"]` に変換。

## 4. Output

| フィールド | 必須 | 説明 |
|------------|------|------|
| `output_schema` | yes | 成功時の JSON Schema（理想）またはフィールド名リスト |
| `success_format` | no | 成功時の説明・例 |
| `error_format` | yes | 失敗時の dict 形状。例: `{"error": string}` または `{"status": "error"}` |

既存 Tool は戻り値が非統一。新 Specification では **error を dict 内に含めるパターン**を推奨（`get_gpu_status` 型）し、`cpu_status` 型（`status: error` のみ）は legacy として Mapping で記録。

## 5. Side Effect

| フィールド | 必須 | 説明 |
|------------|------|------|
| `side_effect` | yes | 副作用クラス（下表） |

| 値 | 意味 |
|----|------|
| `none` | 純粋計算・定数返却 |
| `read_only` | 観測のみ（システム状態読み取り、検索取得） |
| `write` | 新規作成・追記 |
| `modify` | 既存データの変更・削除 |
| `execute` | 外部プロセス・コマンド実行 |
| `unknown` | 未確認 |

`ai_tool` の `execution_mode`（read/write/modify）と対応させる。`execute` は subprocess 起動など read 以外の機械的操作を明示するため追加。

## 6. Security / Permission

| フィールド | 必須 | 説明 |
|------------|------|------|
| `required_permission` | no | 例: `visibility:agent` |
| `authentication` | yes | `none` \| `user` \| `token` \| `oauth` \| `unknown` |
| `network_access` | yes | boolean |
| `filesystem_access` | yes | `none` \| `read` \| `write` \| `read_write` |
| `external_service_access` | no | 依存サービス名の配列 |
| `risk_level` | yes | `low` \| `medium` \| `high` |

既存 Registry の `risk` と `visibility` をここへマッピング。

## 7. Reliability

| フィールド | 必須 | 説明 |
|------------|------|------|
| `expected_failure` | no | 想定失敗モードの配列 |
| `timeout_seconds` | no | 推奨タイムアウト |
| `retry_policy` | no | `none` \| `idempotent_retry` \| `unknown` |
| `deterministic` | no | boolean |
| `known_limitations` | no | プラットフォーム制約等 |

## 8. Cost

| フィールド | 必須 | 説明 |
|------------|------|------|
| `cost` | yes | `free` \| `local_cost` \| `paid` \| `unknown` |

Phase 1 では有料 API 接続不要。

## 9. Catalog / Lifecycle（Specification 内）

Specification には **Tool 稼働状態**のみ。実験・採用は Catalog 側（[CATALOG.md](./CATALOG.md)）。

| フィールド | 説明 |
|------------|------|
| `tool_status` | `available` \| `disabled` \| `unavailable` \| `deprecated` |

## 10. Tool Contract 参照

CAN/CANNOT/MUST/MUST_NOT は [TOOL_CONTRACT.md](./TOOL_CONTRACT.md) の `contract` ブロックに分離可能。

## 11. Provider 拡張（provider_specific）

共通化できない情報は `provider_specific` に格納:

```json
"provider_specific": {
  "local": {
    "module": "tools.system.gpu.gpu_status",
    "function": "get_gpu_status",
    "registry_visibility": "agent"
  }
}
```

## JSON Schema

機械検証用ドラフト: [tool_spec.schema.json](./tool_spec.schema.json)（EXPERIMENTAL）

## 既存 Tool Builder 提案仕様との差

| 項目 | `validate_tool_spec`（既存） | Tool Specification（新） |
|------|------------------------------|--------------------------|
| 必須数 | 15 フィールド | Identity + I/O + Side Effect + Security 中心 |
| `runtime` / `dependencies` | 必須 | `provider_specific` または Reliability へ |
| `output` | フィールド名リスト | `output_schema` + `error_format` |
| Provider | local のみ暗黙 | 明示的 `provider` |

既存 Builder は**変更しない**。新 Specification は将来の統合候補として並立。
