# Mapping: existing `cpu_status` → Tool Specification

**移行なし。** 表現可能性の確認のみ。

**状態:** ADOPT CANDIDATE（Mapping 検証済み。legacy パターンの記録あり）

## 既存ソース

| 種別 | パス |
|------|------|
| Registry | `registry/tools.json` L41-58 |
| 実装 | `tools/system/cpu/cpu_status.py` |
| テスト | 専用ユニットテストなし（`test_f001_summarize_separation.py` で要約のみ） |

## 実装事実（コードより）

```python
def cpu_status():
    # powershell Get-CimInstance Win32_Processor
    # 成功: {'status': '<LoadPercentage>'}
    # 失敗: {'status': 'error'}
```

- 引数なし
- Windows + PowerShell 依存
- `observation_source` フィールドなし（Registry には `observation_source: real` があるが実装は未設定）

## Tool Specification（Mapping 結果）

```json
{
  "tool_id": "local:cpu_status",
  "name": "cpu_status",
  "version": "1.0.0",
  "description": "CPUの基本状態を取得する。個別メトリクスの取得可否は未確認。",
  "provider": "local",
  "source": "registry/tools.json",
  "capability": ["CPU", "状態"],
  "purpose": "Windows CIM から CPU LoadPercentage を取得する",
  "allowed_operations": ["read", "execute"],
  "prohibited_operations": ["write", "modify", "network"],
  "input_schema": {
    "type": "object",
    "additionalProperties": false
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "status": { "type": "string" }
    },
    "required": ["status"]
  },
  "success_format": "{\"status\": \"<LoadPercentage>\"}",
  "error_format": {
    "status": "error"
  },
  "side_effect": "execute",
  "required_permission": ["visibility:agent"],
  "authentication": "none",
  "network_access": false,
  "filesystem_access": "none",
  "external_service_access": ["powershell", "Win32_Processor"],
  "risk_level": "low",
  "expected_failure": ["powershell non-zero exit", "non-Windows"],
  "retry_policy": "none",
  "deterministic": false,
  "known_limitations": [
    "Windows only",
    "LoadPercentage のみ（Registry description の「個別メトリクス未確認」と一致）",
    "observation_source フィールドを実装が返さない（Registry と実装の乖離）"
  ],
  "cost": "free",
  "tool_status": "available",
  "contract": {
    "can": ["invoke_powershell_cim_query", "return_load_percentage_string"],
    "cannot": ["write_files", "network_access"],
    "must": ["return_dict_with_status_key"],
    "must_not": ["raise_on_powershell_failure"]
  },
  "provider_specific": {
    "module": "tools.system.cpu.cpu_status",
    "function": "cpu_status",
    "registry_visibility": "agent",
    "registry_output": ["status"]
  }
}
```

## Catalog Entry（対応）

| フィールド | 値 |
|------------|-----|
| tool_status | available |
| experiment_status | unknown（専用テスト不足） |
| adoption_status | approved（本番稼働中だが契約は薄い） |

## Test Contract 適用

| カテゴリ | 適用 |
|----------|------|
| Normal | N-01（手動/環境依存） |
| Boundary | NOT_APPLICABLE |
| Invalid | NOT_APPLICABLE |
| Failure | F-02（`status: error`）— 自動テストなし |
| Safety | S-04 要検討（subprocess は `execute`） |

## 表現上の注意（legacy）

| ギャップ | 新 Specification での扱い |
|----------|---------------------------|
| 最小戻り値（`status` のみ） | 表現可能だが情報量少ない |
| エラー詳細なし | `error_format` が貧弱 — 新 Tool では改善推奨 |
| Registry `output: ["status"]` のみ | `output_schema` にマッピング可能 |
| subprocess | `side_effect: execute`（read_only より正確） |

## 結論

**新 Specification で表現可能。** ただし既存実装は「最小契約」の legacy 例。新 Tool は `get_gpu_status` 型の error/observation 契約を推奨。
