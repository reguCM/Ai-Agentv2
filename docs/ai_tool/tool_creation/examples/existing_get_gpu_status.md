# Mapping: existing `get_gpu_status` → Tool Specification

**移行なし。** 表現可能性の確認のみ。実装・Registry・動作は変更しない。

**状態:** ADOPT CANDIDATE（Mapping 検証済み）

## 既存ソース

| 種別 | パス |
|------|------|
| Registry | `registry/tools.json` L3-21 |
| 実装 | `tools/system/gpu/gpu_status.py` |
| テスト | `tests/test_gpu_real_observation.py` |

## Tool Specification（Mapping 結果）

```json
{
  "tool_id": "local:get_gpu_status",
  "name": "get_gpu_status",
  "version": "1.0.0",
  "description": "GPUの基本状態を取得する。GPUモデル、温度、使用率、VRAM使用量を nvidia-smi から実測する。取得不能時は unknown/unavailable を返し固定値へフォールバックしない。",
  "provider": "local",
  "source": "registry/tools.json",
  "capability": ["GPU", "VRAM", "温度", "使用率", "observation"],
  "purpose": "nvidia-smi から GPU 基本メトリクスを実測して返す",
  "allowed_operations": ["read"],
  "prohibited_operations": ["write", "modify", "network"],
  "input_schema": {
    "type": "object",
    "additionalProperties": false
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "gpu": {},
      "temperature": {},
      "utilization": {},
      "vram_used": {},
      "vram_total": {},
      "ok": { "type": "boolean" },
      "status": {},
      "error": {},
      "observation_source": { "const": "real" },
      "source": {}
    }
  },
  "success_format": "ok=true かつ nvidia-smi 由来のフィールドが埋まる",
  "error_format": {
    "ok": false,
    "status": "error|unavailable",
    "error": "string|null",
    "observation_source": "real"
  },
  "side_effect": "read_only",
  "required_permission": ["visibility:agent"],
  "authentication": "none",
  "network_access": false,
  "filesystem_access": "none",
  "external_service_access": ["nvidia-smi"],
  "risk_level": "low",
  "expected_failure": ["nvidia-smi not found", "no GPU", "parse error"],
  "retry_policy": "none",
  "deterministic": false,
  "known_limitations": ["NVIDIA GPU + nvidia-smi 必須"],
  "cost": "free",
  "tool_status": "available",
  "contract": {
    "can": [
      "read_gpu_metrics_via_nvidia_smi",
      "return_unknown_on_observation_failure"
    ],
    "cannot": [
      "fabricate_gpu_values",
      "write_to_filesystem",
      "call_network_apis"
    ],
    "must": [
      "set_observation_source_real",
      "include_ok_status_error_fields"
    ],
    "must_not": [
      "fallback_to_hardcoded_temperature_or_utilization"
    ]
  },
  "provider_specific": {
    "module": "tools.system.gpu.gpu_status",
    "function": "get_gpu_status",
    "registry_visibility": "agent",
    "registry_observation_source": "real"
  }
}
```

## Catalog Entry（対応）

| フィールド | 値 |
|------------|-----|
| tool_status | available |
| experiment_status | tested |
| adoption_status | approved |

## Test Contract 適用

| カテゴリ | 適用 |
|----------|------|
| Normal | N-01, N-03（mock 実測テストあり） |
| Boundary | NOT_APPLICABLE（引数なし） |
| Invalid | NOT_APPLICABLE |
| Failure | F-02（nvidia-smi 失敗ケースをテストで検証） |
| Safety | S-01〜S-04（フォールバック禁止テスト） |

## 表現できない / ギャップ

| 項目 | 扱い |
|------|------|
| Registry に `output` 未記載 | Specification の `output_schema` で補完 |
| `validate_tool_spec` の `runtime` 等 | `provider_specific` または Reliability へ移せる |
| subprocess（nvidia-smi） | `side_effect: read_only` + `external_service_access` で表現。`execute` タグは不要と判断 |

## 結論

**新 Specification で十分に表現可能。** 既存の最もリッチな観測 Tool の参照モデルとして ADOPT CANDIDATE。
